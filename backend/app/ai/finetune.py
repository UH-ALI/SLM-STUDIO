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
    "general":      "unsloth/Qwen3-1.7B-bnb-4bit",
   
    # Standard — balanced quality/speed  
    "education":    "unsloth/Qwen3-1.7B-bnb-4bit",
    "business":     "unsloth/Qwen3-4B-bnb-4bit",
   
    # Reasoning-heavy — need stronger logical capabilities
    "finance":      "unsloth/Qwen3-4B-bnb-4bit",
    "legal":        "unsloth/Qwen3-4B-bnb-4bit",
   
    # Precision-critical — medical needs highest accuracy
    "medical":      "unsloth/Phi-3.5-mini-instruct-bnb-4bit",
}

# ─── BASE MODEL ALIASES (frontend-facing names → real HF model IDs) ─────────
BASE_MODEL_ALIASES = {
    "qwen3-1.7b": "unsloth/Qwen3-1.7B-bnb-4bit",
    "qwen3-4b": "unsloth/Qwen3-4B-bnb-4bit",
    "phi-3.5-mini": "unsloth/Phi-3.5-mini-instruct-bnb-4bit",
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

    lora_r = 32 if use_case_lower in ("finance", "legal", "medical") else 16

    model = FastLanguageModel.get_peft_model(
        model,
        r=lora_r,
        target_modules=[
            "q_proj", "k_proj", "v_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj",
        ],
        lora_alpha=lora_r * 2,
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

    # 2.5 Split dataset into train (90%) and eval (10%) for validation loss
    split = dataset.train_test_split(test_size=0.1, seed=42)
    train_dataset = split["train"]
    eval_dataset = split["test"]
    print(f"📂 Split: {len(train_dataset)} train / {len(eval_dataset)} eval examples")

    # 3. Training Config
    print(f"\n🚀 Fine-tuning: {epochs} epochs | {len(train_dataset)} train examples | model={use_case_lower}")

    training_args = SFTConfig(
        output_dir=output_dir,
        dataset_text_field="text",
        max_length=max_seq_len,
        num_train_epochs=epochs,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size,
        gradient_accumulation_steps=grad_acc,
        eval_accumulation_steps=1,
        learning_rate=learning_rate,
        warmup_ratio=0.1,
        fp16=not torch.cuda.is_bf16_supported(),
        bf16=torch.cuda.is_bf16_supported(),
        logging_steps=5,
        save_strategy="epoch",
        eval_strategy="epoch",          # ← evaluate at each epoch
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        optim="adamw_8bit",
        weight_decay=0.01,
        lr_scheduler_type="cosine",
        seed=42,
        report_to="none",
        dataset_num_proc=2,
        packing=False,
    )

    # ─── GPU UTILIZATION HELPER ──────────────────────────────────────────────
    def get_gpu_utilization() -> float:
        """Return current GPU utilization % (0–100). Falls back to 0.0."""
        try:
            import subprocess
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5
            )
            return float(result.stdout.strip().split("\n")[0])
        except Exception:
            return 0.0

    # ─── EPOCH CALLBACK ──────────────────────────────────────────────────────
    from transformers import TrainerCallback
    epoch_history = []   # collects per-epoch snapshots

    class MemoryClearCallback(TrainerCallback):
        def on_evaluate(self, args, state, control, **kwargs):
            # Aggressively clear PyTorch allocator cache after validation
            # to prevent evaluation tensors from starving training memory
            import gc
            gc.collect()
            torch.cuda.empty_cache()

    class EpochUpdateCallback(TrainerCallback):
        def on_epoch_end(self, args, state, control, **kwargs):
            try:
                current_epoch = int(round(state.epoch))

                # Collect train loss: average of all log entries for this epoch
                log_history = state.log_history
                loss_entries = [e for e in log_history if "loss" in e]
                train_loss = round(loss_entries[-1]["loss"], 4) if loss_entries else None

                # Collect eval loss: the most recent eval_loss entry
                eval_entries = [e for e in log_history if "eval_loss" in e]
                val_loss = round(eval_entries[-1]["eval_loss"], 4) if eval_entries else None

                # Learning rate from the most recent logged step
                lr_entries = [e for e in log_history if "learning_rate" in e]
                lr = lr_entries[-1]["learning_rate"] if lr_entries else learning_rate

                gpu_util = get_gpu_utilization()

                epoch_snapshot = {
                    "epoch": current_epoch,
                    "trainLoss": train_loss,
                    "valLoss": val_loss,
                    "learningRate": lr,
                    "gpuUtil": gpu_util,
                }
                epoch_history.append(epoch_snapshot)

                # Persist epoch + progress + live metrics to DB
                db_session = SessionLocal()
                job = db_session.query(TrainingJob).filter(TrainingJob.id == job_id).first()
                if job and job.project:
                    job.project.epoch = current_epoch
                    progress_pct = 50 + int((current_epoch / epochs) * 40)
                    job.project.progress = min(progress_pct, 90)
                    # Store live metrics so the frontend can display them mid-training
                    job.project.metrics = {
                        "epoch": current_epoch,
                        "trainLoss": train_loss,
                        "valLoss": val_loss,
                        "learningRate": lr,
                        "gpuUtil": gpu_util,
                    }
                    db_session.commit()
                db_session.close()
            except Exception as e:
                print(f"Failed to update DB on epoch end: {e}")

    trainer = SFTTrainer(
        model=model,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,       # ← pass eval split
        processing_class=tokenizer,
        args=training_args,
        callbacks=[MemoryClearCallback(), EpochUpdateCallback()],
    )

    # 4. Execute Training
    trainer.train()
    # Use the last active recorded GPU util if available, rather than measuring it now (when it's idle)
    gpu_util_final = epoch_history[-1]["gpuUtil"] if epoch_history else get_gpu_utilization()
    print(f"\n✅ Training complete. Peak VRAM: {torch.cuda.max_memory_allocated()/1e9:.2f} GB")

    # 5. Post-training loss health check
    try:
        log_history  = trainer.state.log_history
        loss_entries = [e for e in log_history if "loss" in e]
        eval_entries = [e for e in log_history if "eval_loss" in e]
        if loss_entries:
            final_loss = loss_entries[-1]["loss"]
            print(f"\n📊 Final training loss: {final_loss:.4f}")
            if eval_entries:
                print(f"📊 Final validation loss: {eval_entries[-1]['eval_loss']:.4f}")
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

    # 6.5 Build metrics dict for caller
    log_history = trainer.state.log_history
    loss_entries = [e for e in log_history if "loss" in e]
    eval_entries = [e for e in log_history if "eval_loss" in e]

    final_train_loss = round(loss_entries[-1]["loss"], 4) if loss_entries else None
    final_val_loss = round(eval_entries[-1]["eval_loss"], 4) if eval_entries else None

    metrics = {
        "adapter_path": output_dir,
        "adapter_size_mb": round(total_size / 1e6, 2),
        "epochs_completed": epochs,
        "total_steps": trainer.state.global_step if hasattr(trainer.state, 'global_step') else 0,
        "learning_rate": learning_rate,
        "max_seq_len": max_seq_len,
        "batch_size": batch_size,
        "gradient_accumulation_steps": grad_acc,
        "train_loss": final_train_loss,
        "final_loss": final_train_loss,
        "val_loss": final_val_loss,
        "gpu_util": gpu_util_final,
        "training_history": epoch_history,
    }

    # 7. Aggressively clear memory to free VRAM for the Inference API
    import gc
    del model
    del tokenizer
    del trainer
    gc.collect()
    torch.cuda.empty_cache()
    print("🧹 Worker VRAM cleared successfully.")

    return metrics