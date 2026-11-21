import unittest

from pydantic import ValidationError

from app.api.routes.chat import ChatRequest
from support_gpt.evaluation.app_evaluation import evaluate_application


class TestFastAPIApplicationEvaluation(unittest.TestCase):
    def test_application_contract_checks_pass(self):
        results = evaluate_application()

        self.assertGreaterEqual(len(results), 5)
        failed = [
            row
            for row in results
            if not row["application_check_passed"]
        ]
        self.assertEqual(
            failed,
            [],
            msg="\n".join(
                f"{row['case_id']}: {row['error']}" for row in failed
            ),
        )

    def test_request_schema_rejects_empty_and_overlong_messages(self):
        with self.assertRaises(ValidationError):
            ChatRequest(message="")
        with self.assertRaises(ValidationError):
            ChatRequest(message="x" * 2001)


if __name__ == "__main__":
    unittest.main()