"""Aggregate evaluation results and write machine-readable and Markdown reports."""

import argparse
import csv
import json
import math
import statistics
from pathlib import Path
from typing import Any


MODEL_NAMES = ("base", "fine_tuned")
AUTOMATED_RATE_FIELDS = (
    "empty_response",
    "placeholder_leakage",
    "unsupported_action_claim",
    "automated_safety_compliant",
)
LATENCY_FIELD = "latency_seconds"
LOSS_FIELDS = ("loss", "perplexity")
HUMAN_SCORE_FIELDS = (
    "human_relevance",
    "human_correctness",
    "human_helpfulness",
    "human_instruction_following",
)


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _mean(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


def _rate(rows: list[dict[str, Any]], field: str) -> float | None:
    values = [str(row.get(field, "")).lower() for row in rows]
    values = [value for value in values if value in ("true", "false")]
    if not values:
        return None
    return sum(value == "true" for value in values) / len(values)


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    latency = [
        number
        for row in rows
        if (number := _number(row.get(LATENCY_FIELD))) is not None
    ]
    error_count = sum(bool(row.get("error")) for row in rows)
    summary: dict[str, Any] = {
        "cases": len(rows),
        "errors": error_count,
        "error_rate": error_count / len(rows) if rows else None,
        "loss_errors": sum(bool(row.get("loss_error")) for row in rows),
        "latency_seconds_mean": _mean(latency),
        "latency_seconds_median": statistics.median(latency) if latency else None,
        "latency_seconds_p95": (
            sorted(latency)[max(0, int(0.95 * len(latency) + 0.999999) - 1)]
            if latency
            else None
        ),
    }

    for field in AUTOMATED_RATE_FIELDS:
        summary[field + "_rate"] = _rate(rows, field)

    for field in LOSS_FIELDS + HUMAN_SCORE_FIELDS:
        values = [
            number
            for row in rows
            if (number := _number(row.get(field))) is not None
        ]
        summary[field + "_mean"] = _mean(values)
        summary[field + "_rated_cases"] = len(values)

    return summary


def build_report(
    rows: list[dict[str, Any]],
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    raw_rows = [row for row in rows if row.get("model") in MODEL_NAMES]
    for row in raw_rows:
        for field in HUMAN_SCORE_FIELDS:
            raw_score = row.get(field)
            score = _number(raw_score)
            if raw_score not in (None, "") and score is None:
                raise ValueError(
                    f"{field} for {row.get('case_id', 'unknown case')} "
                    "must be a number from 1 to 5."
                )
            if score is not None and not 1 <= score <= 5:
                raise ValueError(
                    f"{field} for {row.get('case_id', 'unknown case')} "
                    "must be between 1 and 5."
                )
    by_model: dict[str, Any] = {
        model_name: _summarize(
            [row for row in raw_rows if row.get("model") == model_name]
        )
        for model_name in MODEL_NAMES
    }

    categories = sorted({str(row.get("category", "")) for row in raw_rows})
    by_category: dict[str, dict[str, Any]] = {}
    for category in categories:
        by_category[category] = {
            model_name: _summarize(
                [
                    row
                    for row in raw_rows
                    if row.get("model") == model_name
                    and row.get("category") == category
                ]
            )
            for model_name in MODEL_NAMES
        }

    comparison: dict[str, Any] = {}
    base = by_model["base"]
    fine_tuned = by_model["fine_tuned"]
    comparable_fields = (
        "latency_seconds_mean",
        "loss_mean",
        "perplexity_mean",
        "empty_response_rate",
        "placeholder_leakage_rate",
        "unsupported_action_claim_rate",
        "automated_safety_compliant_rate",
    )
    for field in comparable_fields:
        base_value = base[field]
        fine_tuned_value = fine_tuned[field]
        comparison[field + "_delta_fine_tuned_minus_base"] = (
            fine_tuned_value - base_value
            if base_value is not None and fine_tuned_value is not None
            else None
        )

    application_rows = [
        row for row in rows if row.get("model") == "fastapi_application"
    ]
    human_ratings_present = any(
        _number(row.get(field)) is not None
        for row in raw_rows
        for field in HUMAN_SCORE_FIELDS
    )

    return {
        "metadata": metadata or {},
        "evaluation_scope": {
            "raw_model_case_count_per_model": sum(
                row.get("model") == "base" for row in raw_rows
            ),
            "categories": categories,
            "subjective_assessments": (
                "Human rubric scores are blank until a reviewer enters ratings "
                "in the CSV and regenerates the reports."
            ),
        },
        "automated_measurements": {
            "by_model": by_model,
            "by_category": by_category,
            "base_vs_fine_tuned_delta": comparison,
        },
        "human_or_llm_judge_assessments": {
            "source": "Human CSV rubric ratings; no LLM judge is run.",
            "ratings_present": human_ratings_present,
            "metrics": list(HUMAN_SCORE_FIELDS),
            "by_model": {
                model_name: {
                    field: by_model[model_name][field + "_mean"]
                    for field in HUMAN_SCORE_FIELDS
                }
                for model_name in MODEL_NAMES
            },
        },
        "fastapi_application_checks": {
            "checks": len(application_rows),
            "passed": sum(
                str(row.get("application_check_passed", "")).lower() == "true"
                for row in application_rows
            ),
            "failed": sum(
                str(row.get("application_check_passed", "")).lower() == "false"
                for row in application_rows
            ),
            "results": [
                {
                    "case_id": row.get("case_id", ""),
                    "check": row.get("evaluation_criteria", ""),
                    "passed": str(
                        row.get("application_check_passed", "")
                    ).lower()
                    == "true",
                    "details": row.get("error", ""),
                }
                for row in application_rows
            ],
        },
        "limitations": [
            "Automated pattern checks are indicators, not a complete safety or quality judgment.",
            "Reference-conditioned loss/perplexity is reported only for cases with reference answers.",
            "Latency depends on hardware, software versions, and model-loading/device state.",
            "No ROUGE, BLEU, or exact-match score is treated as a standalone measure of support quality.",
        ],
    }


def _display(value: Any, digits: int = 3) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# SupportGPT Evaluation Report",
        "",
        "## Run information",
        "",
    ]
    metadata = report.get("metadata") or {}
    if metadata:
        lines.extend(
            f"- **{key.replace('_', ' ').title()}:** {value}"
            for key, value in metadata.items()
        )
    else:
        lines.append("- Run metadata was not supplied.")

    lines.extend(
        [
            "",
            "## Automated model measurements",
            "",
            "| Model | Cases | Error rate | Empty rate | Placeholder leakage | Unsupported-action claims | Safety checks passed | Mean latency (s) | Mean loss | Mean perplexity |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for model_name in MODEL_NAMES:
        summary = report["automated_measurements"]["by_model"][model_name]
        lines.append(
            "| {model} | {cases} | {errors} | {empty} | {placeholder} | "
            "{unsupported} | {safety} | {latency} | {loss} | {ppl} |".format(
                model=model_name,
                cases=summary["cases"],
                errors=_display(summary["error_rate"]),
                empty=_display(summary["empty_response_rate"]),
                placeholder=_display(summary["placeholder_leakage_rate"]),
                unsupported=_display(summary["unsupported_action_claim_rate"]),
                safety=_display(summary["automated_safety_compliant_rate"]),
                latency=_display(summary["latency_seconds_mean"]),
                loss=_display(summary["loss_mean"]),
                ppl=_display(summary["perplexity_mean"]),
            )
        )

    lines.extend(
        [
            "",
            "## Per-category comparison",
            "",
            "| Category | Model | Cases | Error rate | Empty rate | Unsupported-action claims | Safety checks passed | Mean latency (s) | Mean loss |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for category, model_summaries in report["automated_measurements"][
        "by_category"
    ].items():
        for model_name in MODEL_NAMES:
            summary = model_summaries[model_name]
            lines.append(
                "| {category} | {model} | {cases} | {errors} | {empty} | "
                "{unsupported} | {safety} | {latency} | {loss} |".format(
                    category=category,
                    model=model_name,
                    cases=summary["cases"],
                    errors=_display(summary["error_rate"]),
                    empty=_display(summary["empty_response_rate"]),
                    unsupported=_display(
                        summary["unsupported_action_claim_rate"]
                    ),
                    safety=_display(summary["automated_safety_compliant_rate"]),
                    latency=_display(summary["latency_seconds_mean"]),
                    loss=_display(summary["loss_mean"]),
                )
            )

    lines.extend(
        [
            "",
            "## Human assessment",
            "",
            "Relevance, correctness, helpfulness, and instruction-following scores "
            "are human rubric ratings, not automated model scores. "
            "Blank values mean they have not been assessed.",
            "",
            "| Model | Relevance | Correctness | Helpfulness | Instruction following |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for model_name in MODEL_NAMES:
        ratings = report["human_or_llm_judge_assessments"]["by_model"][
            model_name
        ]
        lines.append(
            "| {model} | {relevance} | {correctness} | {helpfulness} | "
            "{following} |".format(
                model=model_name,
                relevance=_display(ratings["human_relevance"]),
                correctness=_display(ratings["human_correctness"]),
                helpfulness=_display(ratings["human_helpfulness"]),
                following=_display(ratings["human_instruction_following"]),
            )
        )

    app_checks = report["fastapi_application_checks"]
    lines.extend(
        [
            "",
            "## FastAPI application checks",
            "",
            f"Application contract checks passed: {app_checks['passed']}/"
            f"{app_checks['checks']}. These use controlled test responses and "
            "are reported separately from raw model generations.",
            "",
        ]
    )
    if app_checks["results"]:
        lines.extend(
            [
                "| Check | Result | Details |",
                "|---|---|---|",
            ]
        )
        for result in app_checks["results"]:
            state = "PASS" if result["passed"] else "FAIL"
            detail = str(result["details"]).replace("|", "\\|").replace(
                "\n", " "
            )
            lines.append(f"| {result['check']} | {state} | {detail} |")

    lines.extend(["", "## Interpretation and limitations", ""])
    lines.extend(f"- {item}" for item in report["limitations"])
    lines.append("")
    return "\n".join(lines)


def generate_reports(
    input_csv: Path,
    output_dir: Path,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Path]:
    with input_csv.open("r", encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    if metadata is None:
        metadata_value = next(
            (
                row.get("run_metadata")
                for row in rows
                if row.get("run_metadata")
            ),
            None,
        )
        if metadata_value:
            try:
                metadata = json.loads(metadata_value)
            except json.JSONDecodeError as exc:
                raise ValueError("CSV run_metadata is not valid JSON.") from exc
    report = build_report(rows, metadata)

    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "evaluation_report.json"
    markdown_path = output_dir / "evaluation_report.md"
    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    return {"json": json_path, "markdown": markdown_path}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Regenerate SupportGPT evaluation summaries from a CSV."
    )
    parser.add_argument(
        "--input-csv",
        type=Path,
        default=Path("reports/evaluation_results.csv"),
    )
    parser.add_argument("--output-dir", type=Path, default=Path("reports"))
    args = parser.parse_args()
    paths = generate_reports(args.input_csv, args.output_dir)
    print(f"Wrote {paths['json']} and {paths['markdown']}")


if __name__ == "__main__":
    main()