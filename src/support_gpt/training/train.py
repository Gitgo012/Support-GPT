
import argparse
import json
import math
import os
import sys
from pathlib import Path
import torch
from datasets import load_dataset
from peft import (
    LoraConfig,
    get_peft_model,
)
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    set_seed,
)
from trl import SFTConfig, SFTTrainer


# Make project root importable.
PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

import configs.training_config as cfg


def check_environment():
    print("=" * 65)
    print("SUPPORTGPT - LoRA TRAINING")
    print("=" * 65)

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA GPU is not available.")

    if not torch.cuda.is_bf16_supported():
        raise RuntimeError("This training configuration requires BF16 support.")

    print("GPU:", torch.cuda.get_device_name(0))
    print("PyTorch:", torch.__version__)
    print("CUDA:", torch.version.cuda)
    print("BF16 supported:", torch.cuda.is_bf16_supported())

    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()


def load_tokenizer():
    print("\n[1/6] Loading tokenizer...")

    tokenizer = AutoTokenizer.from_pretrained(cfg.BASE_MODEL)

    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    tokenizer.padding_side = "right"

    return tokenizer


def load_model():
    print("\n[2/6] Loading base model (bf16, plain LoRA)...")

    model = AutoModelForCausalLM.from_pretrained(
        cfg.BASE_MODEL,
        dtype=torch.bfloat16,
        device_map={"": 0},
        attn_implementation="sdpa",
    )

    model.config.use_cache = False

    print("Quantized:", getattr(model, "is_quantized", False))
    print("Base parameter dtype:", next(model.parameters()).dtype)

    return model


def attach_lora(model):
    print("\n[3/6] Attaching LoRA adapters...")

    lora_config = LoraConfig(
        r=cfg.LORA_R,
        lora_alpha=cfg.LORA_ALPHA,
        lora_dropout=cfg.LORA_DROPOUT,
        target_modules=cfg.LORA_TARGET_MODULES,
        bias="none",
        task_type="CAUSAL_LM",
    )

    model = get_peft_model(model, lora_config)

    model.print_trainable_parameters()

    return model


def load_datasets():
    print("\n[4/6] Loading prepared datasets...")

    if not cfg.TRAIN_FILE.exists():
        raise FileNotFoundError(cfg.TRAIN_FILE)

    if not cfg.VALIDATION_FILE.exists():
        raise FileNotFoundError(cfg.VALIDATION_FILE)

    from support_gpt.data.training_data import validate_training_jsonl

    validate_training_jsonl(cfg.TRAIN_FILE)
    validate_training_jsonl(cfg.VALIDATION_FILE)

    dataset = load_dataset(
        "json",
        data_files={
            "train": str(cfg.TRAIN_FILE),
            "validation": str(cfg.VALIDATION_FILE),
        },
    )

    print("Training examples:", len(dataset["train"]))
    print("Validation examples:", len(dataset["validation"]))

    expected_columns = {"prompt", "completion"}

    if not expected_columns.issubset(dataset["train"].column_names):
        raise ValueError(
            "Dataset must contain prompt and completion columns."
        )

    return dataset


def calculate_warmup_steps(
    train_examples: int,
    per_device_batch_size: int,
    gradient_accumulation_steps: int,
    num_train_epochs: float,
    warmup_ratio: float,
    world_size: int = 1,
) -> int:
    if train_examples <= 0:
        raise ValueError("train_examples must be positive.")
    if min(
        per_device_batch_size,
        gradient_accumulation_steps,
        world_size,
    ) <= 0:
        raise ValueError(
            "Batch size, accumulation steps, and world size must be positive."
        )
    if num_train_epochs <= 0 or not 0 <= warmup_ratio <= 1:
        raise ValueError(
            "Epochs must be positive and warmup_ratio must be in [0, 1]."
        )

    batches_per_epoch = math.ceil(
        train_examples / (per_device_batch_size * world_size)
    )
    optimizer_steps_per_epoch = math.ceil(
        batches_per_epoch / gradient_accumulation_steps
    )
    total_optimizer_steps = math.ceil(
        optimizer_steps_per_epoch * num_train_epochs
    )
    return math.ceil(total_optimizer_steps * warmup_ratio)


def create_trainer(model, tokenizer, dataset):
    print("\n[5/6] Configuring SFTTrainer...")
    world_size = max(int(os.environ.get("WORLD_SIZE", "1")), 1)
    warmup_steps = calculate_warmup_steps(
        train_examples=len(dataset["train"]),
        per_device_batch_size=cfg.PER_DEVICE_TRAIN_BATCH_SIZE,
        gradient_accumulation_steps=cfg.GRADIENT_ACCUMULATION_STEPS,
        num_train_epochs=cfg.NUM_TRAIN_EPOCHS,
        warmup_ratio=cfg.WARMUP_RATIO,
        world_size=world_size,
    )
    print(f"Warmup steps: {warmup_steps} ({cfg.WARMUP_RATIO:.1%} of training)")

    training_args = SFTConfig(
        output_dir=str(cfg.OUTPUT_DIR),

        # Training
        num_train_epochs=cfg.NUM_TRAIN_EPOCHS,
        per_device_train_batch_size=cfg.PER_DEVICE_TRAIN_BATCH_SIZE,
        per_device_eval_batch_size=cfg.PER_DEVICE_EVAL_BATCH_SIZE,
        gradient_accumulation_steps=cfg.GRADIENT_ACCUMULATION_STEPS,

        # Optimization
        learning_rate=cfg.LEARNING_RATE,
        warmup_steps=warmup_steps,
        weight_decay=cfg.WEIGHT_DECAY,
        optim=cfg.OPTIMIZER,
        lr_scheduler_type="cosine",
        max_grad_norm=1.0,

        # Precision and memory
        bf16=True,
        fp16=False,
        gradient_checkpointing=cfg.GRADIENT_CHECKPOINTING,
        gradient_checkpointing_kwargs={"use_reentrant": False},

        # Dataset processing
        max_length=cfg.MAX_SEQ_LENGTH,
        packing=False,
        completion_only_loss=True,

        # Evaluation and checkpointing
        eval_strategy="epoch",
        save_strategy="epoch",
        save_total_limit=cfg.SAVE_TOTAL_LIMIT,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,

        # Logging
        logging_strategy="steps",
        logging_steps=cfg.LOGGING_STEPS,
        report_to="tensorboard",

        # Reproducibility
        seed=cfg.SEED,
        data_seed=cfg.SEED,

        # Windows-friendly data loading
        dataloader_num_workers=0,
        remove_unused_columns=False,
    )

    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=dataset["train"],
        eval_dataset=dataset["validation"],
        processing_class=tokenizer,
    )

    return trainer


def save_metrics(metrics, filename):
    output_path = cfg.OUTPUT_DIR / filename

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(metrics, file, indent=4, default=str)

    print("Metrics saved to:", output_path)


def print_gpu_memory():
    allocated = torch.cuda.max_memory_allocated() / (1024 ** 3)
    reserved = torch.cuda.max_memory_reserved() / (1024 ** 3)

    print("\nGPU MEMORY SUMMARY")
    print(f"Peak allocated: {allocated:.2f} GB")
    print(f"Peak reserved:  {reserved:.2f} GB")


def main():
    os.environ["TENSORBOARD_LOGGING_DIR"] = str(cfg.LOG_DIR)
    parser = argparse.ArgumentParser(
        description="Train SupportGPT using BF16 LoRA."
    )

    parser.add_argument(
        "--resume-from-checkpoint",
        type=str,
        default=None,
        help="Path to a Trainer checkpoint to resume from.",
    )

    args = parser.parse_args()

    set_seed(cfg.SEED)
    check_environment()

    cfg.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    cfg.LOG_DIR.mkdir(parents=True, exist_ok=True)

    tokenizer = load_tokenizer()
    model = load_model()
    model = attach_lora(model)

    dataset = load_datasets()

    trainer = create_trainer(
        model=model,
        tokenizer=tokenizer,
        dataset=dataset,
    )

    print("\n" + "=" * 65)
    print("STARTING SUPPORTGPT FINE-TUNING")
    print("=" * 65)

    train_result = trainer.train(
        resume_from_checkpoint=args.resume_from_checkpoint
    )

    print("\nTraining finished.")

    # Save the final adapter.
    final_adapter_path = cfg.OUTPUT_DIR / "final"
    trainer.save_model(str(final_adapter_path))
    tokenizer.save_pretrained(str(final_adapter_path))
    save_metrics(trainer.state.log_history, "log_history.json")

    # Save training metrics.
    save_metrics(
        train_result.metrics,
        "train_metrics.json",
    )

    print("\nRunning final validation...")

    evaluation_metrics = trainer.evaluate()

    save_metrics(
        evaluation_metrics,
        "evaluation_metrics.json",
    )

    print("\n" + "=" * 65)
    print("SUPPORTGPT TRAINING COMPLETED")
    print("=" * 65)

    print("Final adapter:", final_adapter_path)
    print("Training loss:", train_result.metrics.get("train_loss"))
    print("Evaluation loss:", evaluation_metrics.get("eval_loss"))

    print_gpu_memory()


if __name__ == "__main__":
    main()
