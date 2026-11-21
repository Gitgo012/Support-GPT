
import json
from pathlib import Path

import numpy as np
from transformers import AutoTokenizer

MODEL_NAME = "Qwen/Qwen2.5-0.5B-Instruct"
DATA_DIR = Path("data/processed")


def main():
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

    lengths = []
    longest_examples = []

    for filename in ["train.jsonl", "validation.jsonl"]:
        path = DATA_DIR / filename
        print(f"\nInspecting {filename}...")

        with path.open("r", encoding="utf-8") as file:
            for line in file:
                record = json.loads(line)

                token_ids = tokenizer(
                    record["text"],
                    add_special_tokens=False,
                    truncation=False,
                )["input_ids"]

                length = len(token_ids)
                lengths.append(length)

                longest_examples.append({
                    "length": length,
                    "category": record["category"],
                    "intent": record["intent"],
                })

    values = np.array(lengths)

    print("\n" + "=" * 55)
    print("TOKEN LENGTH ANALYSIS")
    print("=" * 55)

    print(f"Total examples: {len(values):,}")
    print(f"Average: {values.mean():.1f} tokens")
    print(f"Median: {np.median(values):.1f} tokens")
    print(f"95th percentile: {np.percentile(values, 95):.1f} tokens")
    print(f"99th percentile: {np.percentile(values, 99):.1f} tokens")
    print(f"Maximum: {values.max():,} tokens")

    print("\nExamples exceeding common sequence lengths:")

    for limit in [512, 768, 1024, 1536, 2048]:
        count = int(np.sum(values > limit))
        percentage = count / len(values) * 100
        print(f">{limit:4} tokens: {count:5,} ({percentage:.2f}%)")

    print("\n10 longest examples:")

    longest_examples.sort(
        key=lambda item: item["length"],
        reverse=True,
    )

    for example in longest_examples[:10]:
        print(
            f"{example['length']:5} tokens | "
            f"{example['category']:12} | "
            f"{example['intent']}"
        )


if __name__ == "__main__":
    main()
