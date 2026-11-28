import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from app.api.routes import store as store_api
from app.services.chat_service import ChatService
from app.services.database import Database


class TestStoreDatabase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = Database(str(Path(self.temp_dir.name) / "store.sqlite3"))
        self.database.initialize()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_seeded_demo_order_is_only_visible_to_its_customer(self):
        order = self.database.get_order("NM-20481", "ALEX.MORGAN@EXAMPLE.COM")

        self.assertIsNotNone(order)
        self.assertEqual(order["status"], "In transit")
        self.assertEqual(order["invoice_id"], "INV-20481")
        self.assertIsNone(self.database.get_order("NM-20481", "someone@example.com"))

    def test_order_and_ticket_are_persisted_with_generated_ids(self):
        self.database.create_customer("shopper@example.com", "Jamie Lee")
        order = self.database.create_order("shopper@example.com", "linen-tote", 2)

        self.assertIsNotNone(order)
        self.assertRegex(order["id"], r"^NM-[A-F0-9]{8}$")
        self.assertEqual(order["status"], "Processing")
        self.assertEqual(order["total"], 68.0)
        self.assertEqual(len(self.database.list_orders("shopper@example.com")), 1)

        ticket = self.database.create_ticket(
            "shopper@example.com", "Delivery question", "Please help with the delivery.",
            order["id"],
        )
        self.assertEqual(ticket["status"], "Open")
        self.assertIsNone(
            self.database.create_ticket(
                "shopper@example.com", "Wrong order", "This order is not mine.",
                "NM-NOTMINE",
            )
        )

    def test_support_fallback_uses_verified_demo_order_data(self):
        order = self.database.get_order("NM-20481", "alex.morgan@example.com")
        service = ChatService()

        response = service.generate_response(
            "Where is my order?",
            "support-test",
            {"order": order},
        )

        self.assertIn("NM-20481", response)
        self.assertIn("in transit", response.lower())
        self.assertIn(order["latest_update"], response)
        self.assertIn("simulated", response.lower())

    def test_support_fallback_uses_selected_product_details(self):
        product = self.database.get_product("linen-tote")
        response = ChatService().generate_response(
            "Tell me about this one.",
            "product-support-test",
            {"product": product},
        )

        self.assertIn("Market Day Tote", response)
        self.assertIn("$34.00", response)
        self.assertIn("NovaMart demo catalogue", response)

    def test_support_does_not_claim_to_process_a_cancellation(self):
        order = self.database.get_order("NM-20481", "alex.morgan@example.com")
        service = ChatService()
        service.assistant = type(
            "InaccurateAssistant",
            (),
            {
                "generate_response": lambda self, message, conversation_history=None: "Your order has been cancelled."
            },
        )()
        response = service.generate_response(
            "Please cancel my order.",
            "cancel-support-test",
            {"order": order},
        )

        self.assertIn("can't cancel", response.lower())
        self.assertIn("no changes have been made", response.lower())

    def test_conversation_history_is_scoped_to_customer(self):
        self.database.create_customer("shopper@example.com", "Jamie Lee")
        self.database.save_exchange(
            "conversation-1", "shopper@example.com", "Where is my order?", "It's processing."
        )

        history = self.database.conversation_messages(
            "conversation-1", "SHOPPER@example.com"
        )
        self.assertEqual([message["role"] for message in history], ["user", "assistant"])
        self.assertIsNone(
            self.database.conversation_messages("conversation-1", "other@example.com")
        )
        self.assertFalse(
            self.database.conversation_belongs_to("conversation-1", "other@example.com")
        )

    def test_ticket_rejects_whitespace_only_content_after_trimming(self):
        self.database.create_customer("shopper@example.com", "Jamie Lee")

        with patch.object(store_api, "database", self.database):
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(
                    store_api.create_ticket(
                        store_api.TicketRequest(
                            email="shopper@example.com",
                            subject="   ",
                            message="            ",
                        )
                    )
                )

        self.assertEqual(raised.exception.status_code, 422)


if __name__ == "__main__":
    unittest.main()
