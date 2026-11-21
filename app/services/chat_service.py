
import re
import threading

from app.services.response_validator import validate_response

class ChatService:
    def __init__(self):
        self.assistant = None
        self.generation_lock = threading.Lock()
        self.sessions = {}

        self.order_id_pattern = re.compile(
            r"\b(?:order\s+with\s+id|order\s*(?:id|number|#))"
            r"\s*[:#]?\s*([A-Z0-9-]{3,})\b",
            re.IGNORECASE,
        )



    def load_model(self):
        """Load SupportGPT once when the API starts."""
        if self.assistant is None:
            print("Initializing SupportGPT...")
            from src.support_gpt.inference.model import SupportGPT

            self.assistant = SupportGPT()
            print("SupportGPT initialization complete.")

    def generate_response(
        self,
        session_id: str,
        message: str,
        customer_context: dict | None = None,
    ) -> str:
        """Generate a response while retaining conversation context."""

        # Serialize access to the model and session state.
        with self.generation_lock:
            session = self.sessions.setdefault(
                session_id,
                {
                    "history": [],
                    "details": {},
                },
            )

            # Extract an order ID if the customer supplied one.
            match = self.order_id_pattern.search(message)

            if match:
                session["details"]["order_id"] = match.group(1)

            # Add known customer-provided details to the current prompt.
            model_message = message

            order_id = session["details"].get("order_id")

            if order_id:
                model_message += (
                    "\n\nCustomer-provided context: "
                    f"The customer's order ID is {order_id}. "
                    "This value has not been independently verified."
                )

            order = customer_context.get("order") if customer_context else None
            product = customer_context.get("product") if customer_context else None
            if order:
                context_note = (
                    "\n\nVerified demo order data from NovaMart's SQLite database "
                    "(use only these facts): "
                    f"order {order['id']}, status {order['status']}, "
                    f"estimated delivery {order['estimated_delivery']}, "
                    f"latest update: {order['latest_update']}. "
                    "The customer owns this order. State that this is simulated demo data."
                )
                model_message += context_note
            if product:
                model_message += (
                    "\n\nVerified NovaMart product data from the catalogue: "
                    f"{product['name']}, ${product['price']:.2f}. "
                    f"Description: {product['description']}"
                )

            if self.assistant is not None:
                response = self.assistant.generate_response(
                    message=model_message,
                    conversation_history=session["history"],
                )
            elif order:
                message_lower = message.lower()
                if "refund" in message_lower or "return" in message_lower:
                    response = (
                        f"Order {order['id']} is {order['status'].lower()}. "
                        "Refunds and returns aren't processed in this demo. For a real "
                        "purchase, check the seller's return policy and contact its official "
                        "support team with your order number. This demo status is simulated."
                    )
                elif "cancel" in message_lower:
                    response = (
                        f"Order {order['id']} is {order['status'].lower()}. "
                        f"Latest update: {order['latest_update']} "
                        "I can't cancel orders in this demo. For a real purchase, contact "
                        "the seller's official support team as soon as possible. No changes "
                        "have been made; this status is simulated."
                    )
                else:
                    response = (
                        f"Order {order['id']} is {order['status'].lower()}. "
                        f"The latest update is: {order['latest_update']} "
                        f"Estimated delivery: {order['estimated_delivery']}. "
                        "This status is simulated for the NovaMart demo."
                    )
            elif product:
                response = (
                    f"{product['name']} is ${product['price']:.2f}. "
                    f"{product['description']} This is NovaMart demo catalogue information."
                )
            elif customer_context:
                response = (
                    "I can help with your NovaMart account, delivery, or invoice. "
                    "Choose one of your orders above and I’ll use its current demo status. "
                    "Refunds and cancellations are guidance-only in this demo."
                )
            else:
                message_lower = message.lower()
                if "refund" in message_lower or "return" in message_lower:
                    response = (
                        "I can explain the next steps, but refunds aren't processed in this "
                        "demo. For a real purchase, check the seller's return policy and "
                        "contact its official support team with your order number. Select a "
                        "NovaMart order to see its simulated status."
                    )
                elif "cancel" in message_lower:
                    response = (
                        "Cancellations aren't enabled in this demo. For a real order, contact "
                        "the seller's official support team as soon as possible; eligibility "
                        "depends on its policy and order status. Select a NovaMart order to "
                        "see its simulated status."
                    )
                elif any(word in message_lower for word in ("delivery", "shipping", "track", "where is my order")):
                    response = (
                        "Choose one of your NovaMart orders above and I'll share its latest "
                        "simulated update and estimated delivery date. For a real shipment, "
                        "use the seller's official tracking details."
                    )
                else:
                    response = (
                        "I can help with delivery, refund, and cancellation guidance. "
                        "Choose an order for its simulated status, or pick a product for "
                        "catalogue details. No real payment or shipping actions are made."
                    )

            response = validate_response(response=response, customer_details=session["details"])

            # Store the actual conversation, not the internal context.
            session["history"].append({
                "role": "user",
                "content": message,
            })

            session["history"].append({
                "role": "assistant",
                "content": response,
            })

            # Retain the most recent 10 messages (5 exchanges).
            session["history"] = session["history"][-10:]

            return response


chat_service = ChatService()
