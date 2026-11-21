
from pathlib import Path

BASE_MODEL = "Qwen/Qwen2.5-0.5B-Instruct"

TRAIN_FILE = Path("data/processed/support_gpt_safe/train.jsonl")
VALIDATION_FILE = Path("data/processed/support_gpt_safe/validation.jsonl")

OUTPUT_DIR = Path("models/adapters/support-gpt-lora-candidate")
LOG_DIR = Path("logs")

# LoRA
LORA_R = 16
LORA_ALPHA = 32
LORA_DROPOUT = 0.05

LORA_TARGET_MODULES = [
    "q_proj",
    "k_proj",
    "v_proj",
    "o_proj",
    "gate_proj",
    "up_proj",
    "down_proj",
]

# Training
MAX_SEQ_LENGTH = 768
PER_DEVICE_TRAIN_BATCH_SIZE = 4
PER_DEVICE_EVAL_BATCH_SIZE = 4
GRADIENT_ACCUMULATION_STEPS = 2

NUM_TRAIN_EPOCHS = 2
LEARNING_RATE = 2e-4
WARMUP_RATIO = 0.03
WEIGHT_DECAY = 0.01

GRADIENT_CHECKPOINTING = True
OPTIMIZER = "adamw_torch"

LOGGING_STEPS = 10
EVAL_STEPS = 500
SAVE_STEPS = 500
SAVE_TOTAL_LIMIT = 2

SEED = 42
