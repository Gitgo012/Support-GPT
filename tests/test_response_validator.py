
import unittest

from app.services.response_validator import validate_response


class TestResponseValidator(unittest.TestCase):

    def test_replaces_order_placeholder(self):
        response = "Your order number is {{Order Number}}."

        result = validate_response(
            response,
            {"order_id": "1234"},
        )

        self.assertEqual(result, "Your order number is 1234.")

    def test_rejects_website_placeholder(self):
        response = "Visit {{Website URL}}."

        result = validate_response(
            response,
            {"order_id": "1234"},
        )

        self.assertNotIn("{{Website URL}}", result)
        self.assertIn("official", result)

    def test_preserves_general_guidance(self):
        response = (
            "You can check your order status through "
            "the company's official website."
        )

        result = validate_response(response, {})

        self.assertEqual(result, response)

    def test_rejects_claim_of_checking_order(self):
        response = (
            "Let me check the current status of your order."
        )

        result = validate_response(response, {})

        self.assertEqual(
            result,
            "I can guide you through the process, but I don't have access to "
            "company order, account, or payment systems. You can check your order "
            "through the relevant company's official order history or contact "
            "its support team for verified information.",
        )

    def test_rejects_claim_of_completed_refund(self):
        response = "Your refund has been processed."

        result = validate_response(response, {})

        self.assertIn("don't have access", result)

    def test_rejects_empty_response(self):
        result = validate_response("", {})

        self.assertIn("couldn't generate", result)


if __name__ == "__main__":
    unittest.main()
