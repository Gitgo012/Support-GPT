import json
import math
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from support_gpt.data.training_data import (
    clean_example,
    normalize_user_prompt,
    oversample_training_categories,
    sanitize_completion,
    split_by_user_prompt,
    validate_training_jsonl,
)
from support_gpt.training.train import calculate_warmup_steps


ROOT = Path(__file__).resolve().parents[1]


class TestPolicyAwareCleaning(unittest.TestCase):
    def test_generic_resource_placeholder_is_rewritten_safely(self):
        response, reason, rewritten = sanitize_completion(
            "Visit {{Website URL}} to find the return information."
        )

        self.assertIsNone(reason)
        self.assertTrue(rewritten)
        self.assertNotIn("{{", response)
        self.assertIn("official website", response)

    def test_complex_placeholder_step_list_is_dropped(self):
        response, reason, rewritten = sanitize_completion(
            "1. Open {{Online Company Portal Info}}. "
            "2. Select the {{Online Order Interaction}} section."
        )

        self.assertIsNone(response)
        self.assertEqual(reason, "complex_resource_placeholder")
        self.assertFalse(rewritten)

    def test_one_resource_sentence_is_rewritten_without_losing_context(self):
        response, reason, rewritten = sanitize_completion(
            "Check your order details. Visit {{Website URL}} for current guidance. "
            "Policies can vary by seller."
        )

        self.assertIsNone(reason)
        self.assertTrue(rewritten)
        self.assertNotIn("{{", response)
        self.assertIn("Check your order details.", response)
        self.assertIn("Policies can vary by seller.", response)

    def test_customer_specific_placeholder_is_dropped(self):
        response, reason, rewritten = sanitize_completion(
            "Your order number is {{Order Number}}."
        )

        self.assertIsNone(response)
        self.assertEqual(reason, "non_resource_placeholder")
        self.assertFalse(rewritten)

    def test_unsupported_action_claim_is_dropped(self):
        for claim in (
            "I will initiate the cancellation process for you.",
            "We'll be able to update your order accordingly.",
            "We'll update it for you.",
            "We can definitely help you modify your address.",
            "We'll make the necessary changes for you.",
            "Please wait while I transfer you to a representative.",
            "I can look up the specific fee for you.",
            "Please allow me a moment to transfer you.",
            "I'll make sure it's updated in our system.",
            "I will check it for you.",
            (
                "Allow me a moment to assist you in locating and retrieving "
                "that invoice."
            ),
            "To quickly connect you with the right representative, share your details.",
            "We'll be happy to help you make the necessary updates.",
        ):
            with self.subTest(claim=claim):
                response, reason, _ = sanitize_completion(claim)
                self.assertIsNone(response)
                self.assertEqual(reason, "unsupported_action_claim")

    def test_company_specific_claims_are_dropped(self):
        examples = (
            (
                "Our customer support team is ready to help with the claim.",
                "unsupported_company_claim",
            ),
            ("Our business values your feedback.", "unsupported_company_claim"),
            ("Our goal is to provide excellent service.", "unsupported_company_claim"),
            ("Our platform includes useful tools.", "unsupported_company_claim"),
            (
                "We appreciate you reaching out to us.",
                "unsupported_company_claim",
            ),
            (
                "Our reimbursement policy is explained below.",
                "unsupported_company_claim",
            ),
            (
                "We offer a wide range of payment options.",
                "unsupported_company_claim",
            ),
            ("We have some exciting options for you.", "unsupported_company_claim"),
            (
                "Subscribe to our company newsletter.",
                "unsupported_company_claim",
            ),
            ("We accept Visa and Mastercard.", "unsupported_company_claim"),
            ("We have a 30-day refund policy.", "unsupported_policy_claim"),
            ("Call 1-800-555-1234 for a refund.", "unsupported_policy_claim"),
            (
                "Log in to your account to change the address.",
                "unsupported_feature_assumption",
            ),
            ("Check the order page for details.", "unsupported_feature_assumption"),
        )
        for answer, expected_reason in examples:
            with self.subTest(answer=answer):
                response, reason, rewritten = sanitize_completion(answer)
                self.assertIsNone(response)
                self.assertEqual(reason, expected_reason)
                self.assertFalse(rewritten)

    def test_conditional_feature_guidance_is_preserved(self):
        response, reason, rewritten = sanitize_completion(
            "If the seller offers it, check the seller's order history."
        )

        self.assertEqual(
            response,
            "If the seller offers it, check the seller's order history.",
        )
        self.assertIsNone(reason)
        self.assertFalse(rewritten)

    def test_prompt_placeholder_is_dropped(self):
        response, reason, rewritten = clean_example(
            "Can you find order {{Order Number}}?",
            "Check the seller's official order history.",
        )

        self.assertIsNone(response)
        self.assertEqual(reason, "prompt_placeholder")
        self.assertFalse(rewritten)


class TestGroupedTrainingSplit(unittest.TestCase):
    @staticmethod
    def _record(prompt: str, index: int) -> dict:
        return {
            "prompt": [
                {"role": "system", "content": "Policy"},
                {"role": "user", "content": prompt},
            ],
            "completion": [
                {"role": "assistant", "content": f"Answer {index}."}
            ],
        }

    def test_duplicate_normalized_prompts_stay_in_one_partition(self):
        records = [
            self._record("Where is my shipment?", 1),
            self._record("  WHERE is my shipment?  ", 2),
            self._record("How do invoices work?", 3),
            self._record("Can I change my account email?", 4),
            self._record("My payment did not go through.", 5),
        ]

        train, validation = split_by_user_prompt(records, 0.2, 42)
        train_prompts = {
            normalize_user_prompt(record["prompt"][-1]["content"])
            for record in train
        }
        validation_prompts = {
            normalize_user_prompt(record["prompt"][-1]["content"])
            for record in validation
        }

        self.assertTrue(train)
        self.assertTrue(validation)
        self.assertFalse(train_prompts & validation_prompts)
        self.assertEqual(len(train) + len(validation), len(records))

    def test_grouped_split_is_reproducible(self):
        records = [
            self._record(f"Question {index}", index)
            for index in range(10)
        ]

        first = split_by_user_prompt(records, 0.2, 42)
        second = split_by_user_prompt(records, 0.2, 42)
        self.assertEqual(first, second)

    def test_validation_split_is_stratified_by_category(self):
        records = []
        for category, count in (("DELIVERY", 20), ("INVOICE", 10), ("ORDER", 40)):
            records.extend(
                {
                    **self._record(f"{category} question {index}", index),
                    "category": category,
                }
                for index in range(count)
            )

        _, validation = split_by_user_prompt(records, 0.1, 42)
        validation_counts = Counter(record["category"] for record in validation)

        self.assertGreaterEqual(validation_counts["DELIVERY"], 2)
        self.assertGreaterEqual(validation_counts["INVOICE"], 1)
        self.assertGreaterEqual(validation_counts["ORDER"], 4)

    def test_category_oversampling_is_moderate_and_reproducible(self):
        records = [
            {"category": category, "index": index}
            for category, count in (("COMMON", 100), ("RARE", 25), ("RAREST", 4))
            for index in range(count)
        ]

        first, added = oversample_training_categories(records, seed=42)
        second, _ = oversample_training_categories(records, seed=42)
        final_counts = Counter(record["category"] for record in first)

        self.assertEqual(first, second)
        self.assertEqual(final_counts["COMMON"], 100)
        self.assertEqual(
            final_counts["RARE"],
            math.ceil(math.sqrt(25 * 100)),
        )
        self.assertEqual(
            final_counts["RAREST"],
            math.ceil(math.sqrt(4 * 100)),
        )
        self.assertEqual(len(first), len(records) + sum(added.values()))

    def test_supplemental_prompts_are_reserved_for_training(self):
        records = [
            self._record("Supplemental prompt", 1),
            self._record("Validation candidate one", 2),
            self._record("Validation candidate two", 3),
            self._record("Training candidate", 4),
        ]

        train, validation = split_by_user_prompt(
            records,
            validation_fraction=0.25,
            seed=42,
            train_only_prompts={"  supplemental   prompt "},
        )
        validation_prompts = {
            normalize_user_prompt(record["prompt"][-1]["content"])
            for record in validation
        }

        self.assertNotIn("supplemental prompt", validation_prompts)
        self.assertEqual(len(train) + len(validation), len(records))


class TestTrainingDataValidation(unittest.TestCase):
    def test_validator_rejects_placeholder_targets(self):
        record = {
            "prompt": [
                {"role": "system", "content": "Policy"},
                {"role": "user", "content": "Where can I get help?"},
            ],
            "completion": [
                {"role": "assistant", "content": "Visit {{Website URL}}."}
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "train.jsonl"
            path.write_text(json.dumps(record) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "target contains a placeholder"):
                validate_training_jsonl(path)

    def test_validator_rejects_unsupported_company_and_feature_claims(self):
        examples = (
            ("Visit our website to change your order.", "unsupported_company_claim"),
            (
                "Log in to your account to change your address.",
                "unsupported_feature_assumption",
            ),
        )
        for target, reason in examples:
            record = {
                "prompt": [
                    {"role": "system", "content": "Policy"},
                    {"role": "user", "content": "How can I change my address?"},
                ],
                "completion": [
                    {"role": "assistant", "content": target}
                ],
            }
            with self.subTest(target=target), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "train.jsonl"
                path.write_text(json.dumps(record) + "\n", encoding="utf-8")
                with self.assertRaisesRegex(ValueError, reason):
                    validate_training_jsonl(path)

    def test_supplemental_examples_are_separate_from_evaluation_cases(self):
        training_path = ROOT / "data" / "curated" / "support_supplemental.jsonl"
        evaluation_path = ROOT / "data" / "evaluation" / "support_gpt_eval.jsonl"
        training = [
            json.loads(line)
            for line in training_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        evaluation = [
            json.loads(line)
            for line in evaluation_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        evaluation_prompts = {
            normalize_user_prompt(case["messages"][-1]["content"])
            for case in evaluation
        }

        self.assertFalse(
            any(
                normalize_user_prompt(example["instruction"])
                in evaluation_prompts
                for example in training
            )
        )


class TestWarmupConfiguration(unittest.TestCase):
    def test_ratio_is_converted_to_supported_integer_warmup_steps(self):
        steps = calculate_warmup_steps(
            train_examples=14617,
            per_device_batch_size=4,
            gradient_accumulation_steps=2,
            num_train_epochs=2,
            warmup_ratio=0.03,
        )

        self.assertEqual(steps, 110)

    def test_invalid_warmup_ratio_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "warmup_ratio"):
            calculate_warmup_steps(
                train_examples=10,
                per_device_batch_size=1,
                gradient_accumulation_steps=1,
                num_train_epochs=1,
                warmup_ratio=1.1,
            )


if __name__ == "__main__":
    unittest.main()
