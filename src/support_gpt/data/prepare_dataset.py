import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from configs.support_policy import SUPPORT_SYSTEM_PROMPT
from support_gpt.data.training_data import (
    clean_example,
    normalize_user_prompt,
    oversample_training_categories,
    split_by_user_prompt,
    validate_training_jsonl,
)


INPUT_PATH = Path("data/raw/bitext.csv")
SUPPLEMENTAL_PATH = Path("data/curated/support_supplemental.jsonl")
EVALUATION_PATH = Path("data/evaluation/support_gpt_eval.jsonl")
OUTPUT_DIR = Path("data/processed/support_gpt_safe")
VALIDATION_FRACTION = 0.10
SEED = 42


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _record(
    instruction: str,
    response: str,
    category: str,
    intent: str,
) -> dict:
    return {
        "prompt": [
            {"role": "system", "content": SUPPORT_SYSTEM_PROMPT},
            {"role": "user", "content": instruction},
        ],
        "completion": [
            {"role": "assistant", "content": response},
        ],
        "category": category,
        "intent": intent,
    }


def _load_supplemental_examples() -> list[dict]:
    records = []
    with SUPPLEMENTAL_PATH.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            try:
                example = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"{SUPPLEMENTAL_PATH}:{line_number}: invalid JSON: {exc}"
                ) from exc

            required = {"instruction", "response", "category", "intent"}
            missing = required.difference(example)
            if missing:
                raise ValueError(
                    f"{SUPPLEMENTAL_PATH}:{line_number}: missing fields "
                    f"{sorted(missing)}"
                )
            response, reason, rewritten = clean_example(
                str(example["instruction"]),
                str(example["response"]),
            )
            if response is None or rewritten:
                raise ValueError(
                    f"{SUPPLEMENTAL_PATH}:{line_number}: curated example is "
                    f"not already policy-clean ({reason or 'requires rewrite'})"
                )
            records.append(
                _record(
                    str(example["instruction"]).strip(),
                    response,
                    str(example["category"]).strip(),
                    str(example["intent"]).strip(),
                )
            )
    return records


def _evaluation_prompts() -> set[str]:
    prompts = set()
    with EVALUATION_PATH.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            try:
                case = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"{EVALUATION_PATH}:{line_number}: invalid JSON: {exc}"
                ) from exc
            messages = case.get("messages")
            if not isinstance(messages, list) or not messages:
                raise ValueError(
                    f"{EVALUATION_PATH}:{line_number}: missing messages"
                )
            prompts.add(normalize_user_prompt(messages[-1]["content"]))
    return prompts


def _write_jsonl(path: Path, records: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")


def _category_counts(records: list[dict]) -> dict[str, int]:
    counts = Counter(record["category"] for record in records)
    return dict(sorted(counts.items()))


def main() -> None:
    if not INPUT_PATH.is_file():
        raise FileNotFoundError(INPUT_PATH)
    if not SUPPLEMENTAL_PATH.is_file():
        raise FileNotFoundError(SUPPLEMENTAL_PATH)
    if not EVALUATION_PATH.is_file():
        raise FileNotFoundError(EVALUATION_PATH)

    dataframe = pd.read_csv(INPUT_PATH).fillna("")
    required_columns = {"instruction", "response", "category", "intent"}
    missing_columns = required_columns.difference(dataframe.columns)
    if missing_columns:
        raise ValueError(
            f"{INPUT_PATH} is missing columns {sorted(missing_columns)}"
        )

    raw_records = []
    dropped_reasons: Counter[str] = Counter()
    rewritten_by_category: Counter[str] = Counter()
    original_by_category: Counter[str] = Counter()
    for row in dataframe.itertuples(index=False):
        instruction = str(getattr(row, "instruction")).strip()
        response = str(getattr(row, "response"))
        category = str(getattr(row, "category")).strip()
        intent = str(getattr(row, "intent")).strip()
        original_by_category[category] += 1

        cleaned_response, reason, rewritten = clean_example(instruction, response)
        if cleaned_response is None:
            dropped_reasons[reason or "unknown"] += 1
            continue
        if rewritten:
            rewritten_by_category[category] += 1
        raw_records.append(
            _record(instruction, cleaned_response, category, intent)
        )

    evaluation_prompts = _evaluation_prompts()
    supplemental_records = _load_supplemental_examples()
    supplemental_prompts = {
        normalize_user_prompt(record["prompt"][-1]["content"])
        for record in supplemental_records
    }
    for record in raw_records + supplemental_records:
        prompt = normalize_user_prompt(record["prompt"][-1]["content"])
        if prompt in evaluation_prompts:
            raise ValueError(
                "A training prompt duplicates a fixed evaluation case: "
                f"{record['prompt'][-1]['content']!r}"
            )

    train_records, validation_records = split_by_user_prompt(
        raw_records,
        validation_fraction=VALIDATION_FRACTION,
        seed=SEED,
        train_only_prompts=supplemental_prompts,
    )
    train_records.extend(supplemental_records)
    unbalanced_train_category_counts = _category_counts(train_records)
    train_records, oversampled_by_category = oversample_training_categories(
        train_records,
        seed=SEED,
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    train_path = OUTPUT_DIR / "train.jsonl"
    validation_path = OUTPUT_DIR / "validation.jsonl"
    report_path = OUTPUT_DIR / "data_quality_report.json"
    _write_jsonl(train_path, train_records)
    _write_jsonl(validation_path, validation_records)

    train_count = validate_training_jsonl(train_path)
    validation_count = validate_training_jsonl(validation_path)
    train_prompts = {
        normalize_user_prompt(record["prompt"][-1]["content"])
        for record in train_records
    }
    validation_prompts = {
        normalize_user_prompt(record["prompt"][-1]["content"])
        for record in validation_records
    }
    if train_prompts & validation_prompts:
        raise RuntimeError("Training and validation prompts overlap.")

    report = {
        "source_file": str(INPUT_PATH),
        "source_sha256": _sha256(INPUT_PATH),
        "supplemental_file": str(SUPPLEMENTAL_PATH),
        "supplemental_sha256": _sha256(SUPPLEMENTAL_PATH),
        "evaluation_file": str(EVALUATION_PATH),
        "validation_fraction": VALIDATION_FRACTION,
        "seed": SEED,
        "system_prompt_sha256": hashlib.sha256(
            SUPPORT_SYSTEM_PROMPT.encode("utf-8")
        ).hexdigest(),
        "source_rows": len(dataframe),
        "source_category_counts": dict(sorted(original_by_category.items())),
        "dropped_source_rows_by_reason": dict(sorted(dropped_reasons.items())),
        "rewritten_source_rows_by_category": dict(
            sorted(rewritten_by_category.items())
        ),
        "clean_source_rows": len(raw_records),
        "supplemental_training_rows": len(supplemental_records),
        "unbalanced_train_rows": sum(unbalanced_train_category_counts.values()),
        "oversampled_training_rows": sum(oversampled_by_category.values()),
        "oversampled_rows_by_category": dict(sorted(oversampled_by_category.items())),
        "train_rows": train_count,
        "validation_rows": validation_count,
        "unbalanced_train_category_counts": unbalanced_train_category_counts,
        "train_category_counts": _category_counts(train_records),
        "validation_category_counts": _category_counts(validation_records),
        "normalized_prompt_overlap": 0,
        "evaluation_prompt_overlap": 0,
        "output_files": {
            "train": str(train_path),
            "validation": str(validation_path),
        },
    }
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )

    print(f"Source examples: {len(dataframe):,}")
    print(f"Clean source examples: {len(raw_records):,}")
    print(f"Supplemental train-only examples: {len(supplemental_records):,}")
    print(f"Train examples: {train_count:,}")
    print(f"Validation examples: {validation_count:,}")
    print(f"Data quality report: {report_path}")


if __name__ == "__main__":
    main()
