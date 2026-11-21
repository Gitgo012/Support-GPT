
import torch

from datasets import load_dataset
from peft import (
    LoraConfig,
    get_peft_model,
    prepare_model_for_kbit_training,
)
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
)
from trl import SFTConfig, SFTTrainer

MODEL_NAME = "Qwen/Qwen2.5-0.5B-Instruct"

TRAIN_FILE = "data/processed/train.jsonl"


def main():
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA GPU is not available.")

    print("GPU:", torch.cuda.get_device_name(0))

    # Load tokenizer
    print("\n1. Loading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # Load a quantized model
    print("\n2. Loading 4-bit model...")

    quantization_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )

    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        quantization_config=quantization_config,
        device_map={"": 0},
        dtype=torch.bfloat16,
        attn_implementation="sdpa",
    )

    model.config.use_cache = False

    model = prepare_model_for_kbit_training(
        model,
        use_gradient_checkpointing=False,
    )

    # Attach a small LoRA configuration
    print("\n3. Attaching LoRA...")

    lora_config = LoraConfig(
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        target_modules=[
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ],
        bias="none",
        task_type="CAUSAL_LM",
    )

    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # Load only four examples
    print("\n4. Loading four dataset examples...")

    dataset = load_dataset(
        "json",
        data_files=TRAIN_FILE,
        split="train",
    ).select(range(4))

    print("Test examples:", len(dataset))
    print("Dataset columns:", dataset.column_names)

    # Configure the trainer without starting training
    print("\n5. Initializing SFTTrainer...")

    args = SFTConfig(
        output_dir="models/compatibility_test",
        max_length=768,
        completion_only_loss=True,
        packing=False,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=1,
        bf16=True,
        fp16=False,
        gradient_checkpointing=False,
        report_to="none",
        save_strategy="no",
        eval_strategy="no",
        dataset_num_proc=None,
        remove_unused_columns=False,
    )

    trainer = SFTTrainer(
        model=model,
        args=args,
        train_dataset=dataset,
        processing_class=tokenizer,
    )

    # Inspect the processed example
    print("\n6. Inspecting processed training example...")

    example = trainer.train_dataset[0]

    print("Processed columns:", list(example.keys()))

    if "labels" not in example:
        raise RuntimeError("Trainer did not produce labels.")

    labels = example["labels"]

    supervised_tokens = [
        token for token in labels if token != -100
    ]

    masked_tokens = sum(
        token == -100 for token in labels
    )

    decoded_completion = tokenizer.decode(
        supervised_tokens,
        skip_special_tokens=False,
    )

    print("Total sequence tokens:", len(labels))
    print("Masked prompt tokens:", masked_tokens)
    print("Supervised completion tokens:", len(supervised_tokens))

    print("\nDecoded supervised portion:")
    print(decoded_completion)

    if not supervised_tokens:
        raise RuntimeError("No completion tokens are supervised.")

    if masked_tokens == 0:
        raise RuntimeError(
            "No prompt tokens were masked. "
            "Completion-only loss may not be working."
        )

    print("\nSUCCESS: TRL compatibility test passed.")
    print("No model training was performed.")


if __name__ == "__main__":
    main()
