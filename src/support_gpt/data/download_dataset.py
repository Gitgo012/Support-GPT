
from pathlib import Path

from datasets import load_dataset

DATASET_NAME = "bitext/Bitext-customer-support-llm-chatbot-training-dataset"
OUTPUT_DIR = Path("data/raw")

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Downloading customer-support dataset...")
    dataset = load_dataset(DATASET_NAME, split="train")

    print(f"\nTotal examples: {len(dataset):,}")
    print(f"Columns: {dataset.column_names}")

    df = dataset.to_pandas()

    output_path = OUTPUT_DIR / "bitext.csv"
    df.to_csv(output_path, index=False, encoding="utf-8")

    print(f"\nSaved dataset to: {output_path}")

    print("\nExamples by category:")
    print(df["category"].value_counts())

    print("\nFirst example:")
    print("Instruction:", df.iloc[0]["instruction"])
    print("Response:", df.iloc[0]["response"])

if __name__ == "__main__":
    main()
