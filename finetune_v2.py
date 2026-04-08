"""
finetune_v2.py
No-Code SLM Studio — QLoRA Fine-Tuning Pipeline
Fixes: epoch-based training, model saving, inference test, VRAM monitoring
"""

import torch
import json
import os
from datasets import load_dataset
from trl import SFTTrainer
from transformers import TrainingArguments, TextStreamer

# ─── MODEL SELECTION ─────────────────────────────────────────────────────────
# Uncomment the model that matches your use case.
# All tested to fit on 8GB VRAM with QLoRA.

MODEL_CONFIGS = {
    "education":  "unsloth/TinyLlama-1.1B-Chat-v1.0-bnb-4bit",   # fastest, ~2GB VRAM
    "business":   "unsloth/Qwen2.5-1.5B-Instruct-bnb-4bit",      # instruction-following, ~3GB
    "medical":    "unsloth/Phi-2-bnb-4bit",                       # reasoning, ~4GB
    "general":    "unsloth/Qwen2.5-0.5B-Instruct-bnb-4bit",      # your current model (fine for testing)
}

# ── CHANGE THIS to select your model ──
USE_CASE      = "business"
MODEL_NAME    = MODEL_CONFIGS[USE_CASE]
DATA_FILE     = "train.jsonl"
OUTPUT_DIR    = f"./adapter_{USE_CASE}"   # where the LoRA adapter is saved
MAX_SEQ_LEN   = 1024   # lowered from 2048 — saves VRAM, 1024 is enough for Q&A pairs
EPOCHS        = 3      # 3 full passes over your dataset
BATCH_SIZE    = 1      # safe for 8GB GPU
GRAD_ACC      = 8      # effective batch = 1 * 8 = 8
LEARNING_RATE = 2e-4

# ─── VRAM CHECK ──────────────────────────────────────────────────────────────

def check_vram():
    if torch.cuda.is_available():
        total = torch.cuda.get_device_properties(0).total_memory / 1e9
        print(f"🖥️  GPU: {torch.cuda.get_device_name(0)}")
        print(f"💾 Total VRAM: {total:.1f} GB")
        if total < 7:
            print("⚠️  Warning: Less than 7GB VRAM. Switch to TinyLlama or Qwen2.5-0.5B.")
    else:
        print("❌ No GPU found. Training will be extremely slow on CPU.")

# ─── LOAD MODEL ──────────────────────────────────────────────────────────────

def load_model():
    # Unsloth must be imported after torch — it patches torch internals
    from unsloth import FastLanguageModel

    print(f"\n⏳ Loading {MODEL_NAME}...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=MODEL_NAME,
        max_seq_length=MAX_SEQ_LEN,
        dtype=None,           # auto-detect: bf16 on Ampere+, fp16 on older
        load_in_4bit=True,    # QLoRA: 4-bit base model weights
    )

    # Add LoRA adapters — only q_proj and v_proj to save VRAM
    # For 8GB GPU, don't target ALL projection layers like the original code did
    model = FastLanguageModel.get_peft_model(
        model,
        r=16,                              # LoRA rank
        target_modules=["q_proj", "v_proj"],  # minimal targets = less VRAM during training
        lora_alpha=32,                     # alpha = 2x rank is standard
        lora_dropout=0.05,
        bias="none",
        use_gradient_checkpointing="unsloth",  # saves ~30% VRAM
        random_state=42,
    )

    vram_used = torch.cuda.memory_allocated() / 1e9
    print(f"✅ Model loaded. VRAM used: {vram_used:.2f} GB")
    return model, tokenizer

# ─── FORMAT DATASET ──────────────────────────────────────────────────────────

def format_dataset(tokenizer):
    """Format JSONL into chat template that the model was trained on."""
    dataset = load_dataset("json", data_files=DATA_FILE, split="train")
    print(f"📂 Loaded {len(dataset)} training examples from '{DATA_FILE}'.")

    if len(dataset) < 20:
        print("⚠️  Warning: Less than 20 training examples. Run data_generator_v2.py first.")

    def format_prompts(examples):
        texts = []
        for instruction, output in zip(examples["instruction"], examples["output"]):
            # Use the model's native chat template
            messages = [
                {"role": "user",      "content": instruction},
                {"role": "assistant", "content": output}
            ]
            # apply_chat_template adds the correct special tokens for each model
            text = tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=False
            )
            texts.append(text)
        return {"text": texts}

    dataset = dataset.map(format_prompts, batched=True)
    return dataset

# ─── TRAINING ────────────────────────────────────────────────────────────────

def train(model, tokenizer, dataset):
    print(f"\n🚀 Starting fine-tuning: {EPOCHS} epochs, {len(dataset)} examples...")

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        dataset_text_field="text",
        max_seq_length=MAX_SEQ_LEN,
        dataset_num_proc=2,
        packing=False,
        args=TrainingArguments(
            num_train_epochs=EPOCHS,          # epoch-based, not step-based
            per_device_train_batch_size=BATCH_SIZE,
            gradient_accumulation_steps=GRAD_ACC,
            learning_rate=LEARNING_RATE,
            warmup_ratio=0.1,
            fp16=not torch.cuda.is_bf16_supported(),
            bf16=torch.cuda.is_bf16_supported(),
            logging_steps=5,
            save_strategy="epoch",            # save checkpoint after each epoch
            output_dir=OUTPUT_DIR,
            optim="adamw_8bit",
            weight_decay=0.01,
            lr_scheduler_type="cosine",       # cosine decay is smoother than linear
            seed=42,
            report_to="none",                 # disable wandb/tensorboard unless you want it
        ),
    )

    trainer.train()

    peak_vram = torch.cuda.max_memory_allocated() / 1e9
    print(f"\n✅ Fine-tuning complete! Peak VRAM used: {peak_vram:.2f} GB")
    return trainer

# ─── SAVE ADAPTER ────────────────────────────────────────────────────────────

def save_adapter(model, tokenizer):
    """
    Save ONLY the LoRA adapter (not the full model).
    The adapter is ~50-100MB. The full model is 1-4GB.
    At inference time, load base model + adapter together.
    """
    adapter_path = f"{OUTPUT_DIR}/lora_adapter"
    model.save_pretrained(adapter_path)
    tokenizer.save_pretrained(adapter_path)
    print(f"💾 Adapter saved to: {adapter_path}")
    print(f"   Size: {sum(os.path.getsize(os.path.join(adapter_path, f)) for f in os.listdir(adapter_path)) / 1e6:.1f} MB")

# ─── INFERENCE TEST ──────────────────────────────────────────────────────────

def test_inference(model, tokenizer):
    """Quick test to verify the model responds after fine-tuning."""
    from unsloth import FastLanguageModel
    FastLanguageModel.for_inference(model)  # switch to faster inference mode

    print("\n── Inference Test ────────────────────────────────────────")
    test_question = input("Enter a test question (or press Enter to skip): ").strip()

    if not test_question:
        print("Skipping inference test.")
        return

    messages = [{"role": "user", "content": test_question}]
    inputs = tokenizer.apply_chat_template(
        messages,
        tokenize=True,
        add_generation_prompt=True,
        return_tensors="pt"
    ).to("cuda")

    streamer = TextStreamer(tokenizer, skip_prompt=True)
    print("\n🤖 Model response:")
    _ = model.generate(
        input_ids=inputs,
        streamer=streamer,
        max_new_tokens=256,
        temperature=0.7,
        do_sample=True,
        pad_token_id=tokenizer.eos_token_id,
    )

# ─── MAIN ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    check_vram()
    model, tokenizer = load_model()
    dataset = format_dataset(tokenizer)
    trainer = train(model, tokenizer, dataset)
    save_adapter(model, tokenizer)
    test_inference(model, tokenizer)
