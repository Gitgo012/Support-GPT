import tempfile
import unittest
from pathlib import Path

from support_gpt.evaluation.compare_models import (
    build_report,
    generate_reports,
)
from support_gpt.evaluation.evaluate import (
    _automated_flags,
    load_cases,
)


ROOT = Path(__file__).resolve().parents[1]


class TestEvaluationDataset(unittest.TestCase):
    def test_curated_cases_cover_required_topics_and_valid_turns(self):
        cases = load_cases(ROOT / "data" / "evaluation" / "support_gpt_eval.jsonl")
        categories = {case["category"] for case in cases}

        self.assertEqual(len({case["id"] for case in cases}), len(cases))
        self.assertTrue(
            {
                "order_tracking",
                "refunds",
                "account_issues",
                "payments",
                "invoices",
                "delivery_shipping",
                "subscriptions",
                "cancellation",
                "ambiguous_questions",
                "missing_information",
                "multi_turn_conversations",
                "unsupported_action_requests",
                "prompt_injection_safety",
            }.issubset(categories)
        )
        self.assertTrue(
            any(
                len(case["messages"]) > 1
                and case["category"] == "multi_turn_conversations"
                for case in cases
            )
        )


class TestAutomatedEvaluationSignals(unittest.TestCase):
    def test_placeholder_and_unsupported_action_signals(self):
        placeholder = _automated_flags(
            {"category": "invoices"},
            "Visit {{Website URL}}.",
        )
        unsupported = _automated_flags(
            {"category": "refunds"},
            "Your refund has been processed.",
        )

        self.assertTrue(placeholder["placeholder_leakage"])
        self.assertFalse(placeholder["automated_safety_compliant"])
        self.assertTrue(unsupported["unsupported_action_claim"])
        self.assertFalse(unsupported["automated_safety_compliant"])

    def test_injection_disclosure_is_flagged_separately(self):
        flags = _automated_flags(
            {"category": "prompt_injection_safety"},
            "ACCURACY AND SAFETY: I cannot provide that.",
        )
        self.assertFalse(flags["automated_safety_compliant"])

    def test_future_action_claim_is_detected_without_flagging_guidance(self):
        claim = _automated_flags(
            {"category": "cancellation"},
            "I will initiate the cancellation process for you.",
        )
        guidance = _automated_flags(
            {"category": "cancellation"},
            "I can explain how to request a cancellation.",
        )

        self.assertTrue(claim["unsupported_action_claim"])
        self.assertFalse(claim["automated_safety_compliant"])
        self.assertFalse(guidance["unsupported_action_claim"])


class TestEvaluationReporting(unittest.TestCase):
    def test_report_distinguishes_human_ratings_from_automated_metrics(self):
        rows = [
            {
                "model": "base",
                "case_id": "case-1",
                "category": "refunds",
                "latency_seconds": "0.5",
                "loss": "1.2",
                "perplexity": "3.32",
                "empty_response": "false",
                "placeholder_leakage": "false",
                "unsupported_action_claim": "false",
                "automated_safety_compliant": "true",
                "human_relevance": "",
            },
            {
                "model": "fine_tuned",
                "case_id": "case-1",
                "category": "refunds",
                "latency_seconds": "0.4",
                "loss": "0.9",
                "perplexity": "2.46",
                "empty_response": "false",
                "placeholder_leakage": "false",
                "unsupported_action_claim": "false",
                "automated_safety_compliant": "true",
                "human_relevance": "",
            },
            {
                "model": "fastapi_application",
                "case_id": "app-check",
                "category": "application",
                "application_check_passed": "true",
                "evaluation_criteria": "Retains order ID.",
            },
        ]
        report = build_report(rows)

        self.assertAlmostEqual(
            report["automated_measurements"]["base_vs_fine_tuned_delta"][
                "loss_mean_delta_fine_tuned_minus_base"
            ],
            -0.3,
        )
        self.assertIsNone(
            report["human_or_llm_judge_assessments"]["by_model"]["base"][
                "human_relevance"
            ]
        )
        self.assertEqual(report["fastapi_application_checks"]["passed"], 1)

    def test_report_files_are_written_from_results(self):
        with tempfile.TemporaryDirectory() as directory:
            csv_path = Path(directory) / "results.csv"
            csv_path.write_text(
                "model,case_id,category,latency_seconds,empty_response,"
                "placeholder_leakage,unsupported_action_claim,"
                "automated_safety_compliant\n"
                "base,case-1,refunds,0.5,false,false,false,true\n"
                "fine_tuned,case-1,refunds,0.4,false,false,false,true\n",
                encoding="utf-8",
            )
            outputs = generate_reports(csv_path, Path(directory))

            self.assertTrue(outputs["json"].is_file())
            self.assertTrue(outputs["markdown"].is_file())
            self.assertIn(
                "Human assessment",
                outputs["markdown"].read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
