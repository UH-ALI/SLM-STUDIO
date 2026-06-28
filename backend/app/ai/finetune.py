import unsloth   # MUST be first
import torch
import os
import warnings
from datasets import load_dataset
from trl import SFTTrainer, SFTConfig
from huggingface_hub import snapshot_download
from app.core.config import settings
from app.database import SessionLocal
from app.models import TrainingJob
from app.ai.rag_inference import RAG_USER_TEMPLATE, DEFAULT_PERSONA, DEFAULT_STYLE, build_system_prompt


warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", message=".*warmup_ratio.*deprecated.*")
warnings.filterwarnings("ignore", message=".*max_new_tokens.*max_length.*")

# ─── MODEL SELECTION (FROM AI TEAM) ──────────────────────────────────────────

MODEL_CONFIGS = {
    # Lightweight — fastest inference, lowest VRAM
    "general":      "unsloth/Llama-3.2-1B-Instruct-bnb-4bit",      # ~2.5 GB
   
    # Standard — balanced quality/speed  
    "education":    "unsloth/Llama-3.2-1B-Instruct-bnb-4bit",      # ~2.5 GB
    "business":     "unsloth/Llama-3.2-1B-Instruct-bnb-4bit",      # ~2.5 GB
   
    # Reasoning-heavy — need stronger logical capabilities
    "finance":      "unsloth/gemma-2-2b-it-bnb-4bit",              # ~3.5 GB
    "legal":        "unsloth/gemma-2-2b-it-bnb-4bit",              # ~3.5 GB
   
    # Precision-critical — medical needs highest accuracy
    "medical":      "unsloth/Phi-3-mini-4k-instruct-bnb-4bit",     # ~3 GB
}

# ─── BASE MODEL ALIASES (frontend-facing names → real HF model IDs) ─────────
# Keep this in sync with the frontend's model selector component.
# Last updated: 2026-06-20
BASE_MODEL_ALIASES = {
    "slm-lite":    "unsloth/Qwen2.5-1.5B-Instruct-bnb-4bit",
    "slm-pro":     "unsloth/Qwen2.5-1.5B-Instruct-bnb-4bit",  # same for now, placeholder for future
}

MAX_SEQ_LEN   = 2048
EPOCHS        = 3
BATCH_SIZE    = 1
GRAD_ACC      = 8
LEARNING_RATE = 2e-4

# ─── HYBRID MODEL RESOLVER ───────────────────────────────────────────────────

def resolve_model_path(model_slug: str) -> str:
    """
    Hybrid resolver: prefers local cache, falls back to Hub slug.
    Cache hit  → returns local filesystem path (bypasses all API calls)
    Cache miss → returns original slug (allows download from Hub)
    """
    try:
        local_path = snapshot_download(repo_id=model_slug, local_files_only=True)
        print(f"✅ Cache hit: {model_slug} loaded from local disk")
        return local_path
    except Exception:
        print(f"⬇️ Cache miss: {model_slug} will download from HuggingFace Hub")
        return model_slug

# ─── RAG TRAINING TEMPLATE (FROM AI TEAM) ────────────────────────────────────

# ─── MAIN BACKEND ROUTER ─────────────────────────────────────────────────────

def run_finetuning_pipeline(job_id: str, use_case: str, hyperparameters: dict = None, base_model_name: str = None):
    # Fetch persona from DB
    db = SessionLocal()
    try:
        job = db.query(TrainingJob).filter(TrainingJob.id == job_id).first()
        active_persona = job.project.persona if job and job.project else DEFAULT_PERSONA
    finally:
        db.close()
    
    active_system = build_system_prompt(active_persona, DEFAULT_STYLE)

    """
    Backend Entry Point for Phase 3.
    Reads the synthetic train.jsonl data, fine-tunes the selected SLM using QLoRA,
    and saves the adapter to the job's directory.

    Model selection priority:
      1. base_model_name, resolved through BASE_MODEL_ALIASES (explicit override)
      2. MODEL_CONFIGS[use_case] (domain-tuned default)
      3. MODEL_CONFIGS["general"] (fallback)
    """
    use_case_lower = (use_case or "general").lower()
    default_model_name = MODEL_CONFIGS.get(use_case_lower, MODEL_CONFIGS["general"])

    requested_alias = (base_model_name or "").strip().lower()
    model_name = BASE_MODEL_ALIASES.get(requested_alias, default_model_name)

    if requested_alias and requested_alias not in BASE_MODEL_ALIASES:
        print(f"⚠️  base_model_name '{base_model_name}' not recognized — "
              f"falling back to use_case default for '{use_case_lower}': {model_name}")

    data_file = f"data/processed/job_{job_id}/train.jsonl"
    output_dir = f"data/adapters/job_{job_id}"

    if not os.path.exists(data_file):
        raise FileNotFoundError(f"Training data not found at {data_file}")

    print(f"\n⏳ Loading {model_name} for Job {job_id}…")

    # ─── HYPERPARAMETER OVERRIDES ─────────────────────────────────────────────
    hp = hyperparameters or {}
    epochs = hp.get("epochs", EPOCHS)
    max_seq_len = hp.get("max_seq_len", MAX_SEQ_LEN)
    learning_rate = hp.get("learning_rate", LEARNING_RATE)
    batch_size = hp.get("batch_size", BATCH_SIZE)
    grad_acc = hp.get("gradient_accumulation_steps", GRAD_ACC)

    print(f"⚙️  Hyperparameters: epochs={epochs}, lr={learning_rate}, seq_len={max_seq_len}")

    # 1. Load Model
    from unsloth import FastLanguageModel

    model_path = resolve_model_path(model_name)

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=model_path,
        max_seq_length=max_seq_len,
        dtype=None,
        load_in_4bit=True,
        token=settings.HF_TOKEN,
    )

    model = FastLanguageModel.get_peft_model(
        model,
        r=16,
        target_modules=["q_proj", "v_proj"],
        lora_alpha=32,
        lora_dropout=0.05,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=42,
    )
    print(f"✅ Model loaded. VRAM: {torch.cuda.memory_allocated()/1e9:.2f} GB")

    # 2. Format Dataset
    dataset = load_dataset("json", data_files=data_file, split="train")
    print(f"📂 Loaded {len(dataset)} training examples from '{data_file}'.")

    if "context" not in dataset.column_names:
        raise KeyError("'context' field missing from train.jsonl. Ensure data generation completed successfully.")

    def format_prompts(examples):
        texts = []
        for context, instruction, output in zip(
            examples["context"], examples["instruction"], examples["output"]
        ):
            user_content = RAG_USER_TEMPLATE.format(
                context=context,
                question=instruction,
            )
            messages = [
                {"role": "system",    "content": active_system},
                {"role": "user",      "content": user_content},
                {"role": "assistant", "content": output},
            ]
            texts.append(tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=False
            ))
        return {"text": texts}

    dataset = dataset.map(format_prompts, batched=True)

    # 3. Training Config
    print(f"\n🚀 Fine-tuning: {epochs} epochs | {len(dataset)} examples | model={use_case_lower}")

    training_args = SFTConfig(
        output_dir=output_dir,
        dataset_text_field="text",
        max_length=max_seq_len,
        num_train_epochs=epochs,
        per_device_train_batch_size=batch_size,
        gradient_accumulation_steps=grad_acc,
        learning_rate=learning_rate,
        warmup_ratio=0.1,
        fp16=not torch.cuda.is_bf16_supported(),
        bf16=torch.cuda.is_bf16_supported(),
        logging_steps=5,
        save_strategy="epoch",
        optim="adamw_8bit",
        weight_decay=0.01,
        lr_scheduler_type="cosine",
        seed=42,
        report_to="none",
        dataset_num_proc=2,
        packing=False,
    )

    trainer = SFTTrainer(
        model=model,
        train_dataset=dataset,
        processing_class=tokenizer,
        args=training_args,
    )

    # 4. Execute Training
    trainer.train()
    print(f"\n✅ Training complete. Peak VRAM: {torch.cuda.max_memory_allocated()/1e9:.2f} GB")

    # 5. Post-training loss health check
    try:
        log_history  = trainer.state.log_history
        loss_entries = [e for e in log_history if "loss" in e]
        if loss_entries:
            final_loss = loss_entries[-1]["loss"]
            print(f"\n📊 Final training loss: {final_loss:.4f}")
            if final_loss < 0.5:
                print("⚠️  Loss < 0.5 — possible overfitting. Consider reducing EPOCHS.")
            elif final_loss <= 1.3:
                print("✅ Loss in healthy range (0.5–1.3).")
            elif final_loss <= 1.8:
                print("⚠️  Loss 1.3–1.8 — borderline. Test inference quality.")
            else:
                print("❌ Loss > 1.8 — training failed. Check data quality.")
    except Exception as e:
        print(f"⚠️  Could not read loss history: {e}")

    # 6. Save Final Adapter
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)

    total_size = sum(
        os.path.getsize(os.path.join(r, f))
        for r, _, files in os.walk(output_dir) for f in files
    )
    print(f"💾 Adapter successfully saved to '{output_dir}'  ({total_size/1e6:.1f} MB)")

    # 6.5 Build metrics dict for caller (L3 fix)
    metrics = {
        "adapter_path": output_dir,
        "adapter_size_mb": round(total_size / 1e6, 2),
        "epochs_completed": epochs,
        "total_steps": trainer.state.global_step if hasattr(trainer.state, 'global_step') else 0,
        "learning_rate": learning_rate,
        "max_seq_len": max_seq_len,
        "batch_size": batch_size,
        "gradient_accumulation_steps": grad_acc,
    }

    # Add final loss if available
    try:
        log_history = trainer.state.log_history
        loss_entries = [e for e in log_history if "loss" in e]
        if loss_entries:
            metrics["final_loss"] = round(loss_entries[-1]["loss"], 4)
            metrics["train_loss"] = round(loss_entries[-1]["loss"], 4)
    except Exception:
        metrics["final_loss"] = None
        metrics["train_loss"] = None

    return metrics