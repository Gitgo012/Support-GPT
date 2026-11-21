
import re
from pathlib import Path

import pandas as pd

DATASET_PATH = Path("data/raw/bitext.csv")


def main():
    df = pd.read_csv(DATASET_PATH)

    print("=" * 60)
    print("DATASET OVERVIEW")
    print("=" * 60)
    print(f"Rows: {len(df):,}")
    print(f"Columns: {list(df.columns)}")
    print(f"Missing values:\n{df.isnull().sum()}")

    print("\n" + "=" * 60)
    print("CATEGORY DISTRIBUTION")
    print("=" * 60)
    print(df["category"].value_counts().to_string())

    print("\n" + "=" * 60)
    print("TOP 20 INTENTS")
    print("=" * 60)
    print(df["intent"].value_counts().head(20).to_string())

    print("\n" + "=" * 60)
    print("SAMPLE EXAMPLES")
    print("=" * 60)

    for index, row in df.head(5).iterrows():
        print(f"\nExample {index + 1}")
        print(f"Category: {row['category']}")
        print(f"Intent: {row['intent']}")
        print(f"Instruction: {row['instruction']}")
        print(f"Response: {row['response']}")

    print("\n" + "=" * 60)
    print("PLACEHOLDER ANALYSIS")
    print("=" * 60)

    text = df["instruction"].fillna("") + " " + df["response"].fillna("")
    placeholders = text.str.findall(r"\{\{.*?\}\}")

    counts = {}
    for items in placeholders:
        for item in items:
            counts[item] = counts.get(item, 0) + 1

    for placeholder, count in sorted(
        counts.items(), key=lambda item: item[1], reverse=True
    ):
        print(f"{placeholder}: {count}")

    print(f"\nUnique placeholders: {len(counts)}")


if __name__ == "__main__":
    main()
