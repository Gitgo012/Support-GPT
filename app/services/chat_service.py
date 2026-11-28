import re
import threading

from app.services.response_validator import validate_response


class ChatService:
    HUMAN_REQUEST = re.compile(
        r"\b(?:human|person|real person|live agent|representative|someone|support agent)\b"
        r"|\b(?:talk|speak|connect|escalate)\s+(?:to|with)\b"
        r"|\bcreate\s+(?:a\s+)?(?:support\s+)?ticket\b",
        re.IGNORECASE,
    )
    ORDER_ISSUE = re.compile(
        r"\b(?:damaged|broken|defective|wrong item|missing item|"
        r"never arrived|not received|didn't arrive|not delivered|late|delayed|"
        r"lost (?:package|parcel)|charged twice|duplicate charge|unauthorized charge)\b",
        re.IGNORECASE,
    )
    ORDER_ID = re.compile(r"\bNM-[A-Z0-9]{4,}\b", re.IGNORECASE)
    CUSTOMER_ORDER_ID = re.compile(
        r"\b(?:order\s+with\s+id|order\s*(?:id|number|#))"
        r"\s*[:#]?\s*([A-Z0-9-]{3,})\b",
        re.IGNORECASE,
    )

    def __init__(self):
        self.assistant = None
        self.generation_lock = threading.Lock()
        self.sessions = {}
        self.device = "cpu"
        self.adapter_source = "demo"

    @classmethod
    def classify_intent(cls, message: str) -> str:
        text = message.lower()
        if cls.HUMAN_REQUEST.search(message):
            return "human"
        if cls.ORDER_ISSUE.search(message):
            return "order_issue"
        if any(word in text for word in ("refund", "return", "money back")):
            return "refund"
        if any(word in text for word in ("cancel", "cancellation")):
            return "cancel"
        if any(
            word in text
            for word in (
                "track", "tracking", "delivery", "shipment", "arrive",
                "arriving", "parcel", "package", "where is my order",
                "where is order",
                "order status", "latest update",
            )
        ):
            return "tracking"
        if any(word in text for word in ("product", "item", "price", "catalogue", "catalog")):
            return "product"
        return "general"

    @classmethod
    def escalation_available(cls, message: str) -> bool:
        return (
            cls.ORDER_ISSUE.search(message) is not None
            or cls.classify_intent(message) in {"refund", "cancel", "human"}
        )

    def load_model(self):
        """Load SupportGPT once when the API starts."""
        if self.assistant is None:
            from src.support_gpt.inference.model import SupportGPT

            self.assistant = SupportGPT()
            self.device = str(self.assistant.device)
            self.adapter_source = self.assistant.adapter_source

    def generate_response(
        self,
        message: str,
        session_id: str,
        customer_context: dict | None = None,
        conversation_history: list[dict] | None = None,
    ) -> str:
        """Generate a response using verified context and recent conversation."""
        with self.generation_lock:
            session = self.sessions.setdefault(
                session_id,
                {"history": [], "details": {}},
            )
            if conversation_history is not None:
                session["history"] = [
                    {"role": item["role"], "content": item["content"]}
                    for item in conversation_history[-10:]
                    if item.get("role") in {"user", "assistant"}
                    and isinstance(item.get("content"), str)
                ]

            mentioned_id = self.CUSTOMER_ORDER_ID.search(message)
            order = customer_context.get("order") if customer_context else None
            if order:
                session["details"]["order_id"] = order["id"]
            elif mentioned_id:
                session["details"]["order_id"] = mentioned_id.group(1)

            product = customer_context.get("product") if customer_context else None
            intent = self.classify_intent(message)
            deterministic_response = None
            model_message = message

            if session["details"].get("order_id") and not order:
                model_message += (
                    "\n\nThe customer mentioned order ID "
                    f"{session['details']['order_id']}; this value is unverified. "
                    "Do not claim to have looked it up or know its status."
                )

            if order:
                model_message += (
                    "\n\nVerified demo order data from NovaMart's SQLite database "
                    "(use only these facts): "
                    f"order {order['id']}, status {order['status']}, "
                    f"estimated delivery {order['estimated_delivery']}, "
                    f"latest update: {order['latest_update']}. "
                    "The customer owns this order. State that this is simulated demo data."
                )
                if intent == "refund":
                    deterministic_response = (
                        f"Order {order['id']} is {order['status'].lower()}. Refunds and "
                        "returns aren't processed in this demo. For a real purchase, check "
                        "the seller's return policy and contact its official support team "
                        "with your order number. I can help you create a demo support ticket "
                        "if you'd like. This order status is simulated."
                    )
                elif intent == "cancel":
                    deterministic_response = (
                        f"Order {order['id']} is {order['status'].lower()}. "
                        f"Latest update: {order['latest_update']} I can't cancel orders "
                        "in this demo, and no changes have been made. For a real purchase, "
                        "contact the seller's official support team as soon as possible. "
                        "I can help you create a demo support ticket if you'd like."
                    )
                elif intent == "order_issue":
                    deterministic_response = (
                        f"I’m sorry you’re having trouble with order {order['id']}. "
                        f"The recorded status is {order['status'].lower()}; the latest "
                        f"simulated update is: {order['latest_update']} I can’t resolve "
                        "delivery or item problems in this demo, but you can create a "
                        "demo support ticket for the sample queue."
                    )
                elif intent in {"tracking", "order_issue", "human"}:
                    deterministic_response = (
                        f"Order {order['id']} is {order['status'].lower()}. "
                        f"The latest update is: {order['latest_update']} "
                        f"Estimated delivery: {order['estimated_delivery']}. "
                        "This status is simulated for the NovaMart demo."
                    )

            if product and intent in {"product", "general"} and deterministic_response is None:
                model_message += (
                    "\n\nVerified NovaMart product data from the catalogue: "
                    f"{product['name']}, ${product['price']:.2f}. "
                    f"Description: {product['description']}"
                )
                deterministic_response = (
                    f"{product['name']} is ${product['price']:.2f}. "
                    f"{product['description']} This is NovaMart demo catalogue information."
                )

            if deterministic_response is None and intent == "refund":
                deterministic_response = (
                    "Refunds and returns aren't processed in this demo. For a real "
                    "purchase, check the seller's return policy and contact its official "
                    "support team with your order number. If you share the order from your "
                    "NovaMart account, I can show its simulated status. I can also help "
                    "you create a demo support ticket."
                )
            elif deterministic_response is None and intent == "cancel":
                deterministic_response = (
                    "Cancellations aren't enabled in this demo, and I haven't changed "
                    "your order. For a real purchase, contact the seller's official support "
                    "team as soon as possible; eligibility depends on its policy and order "
                    "status. Select a NovaMart order to see its simulated status."
                )
            elif deterministic_response is None and intent == "order_issue":
                deterministic_response = (
                    "I'm sorry you're dealing with an order problem. I can't resolve "
                    "delivery or item issues in this demo, but you can select your order "
                    "and create a demo support ticket for the sample queue."
                )
            elif deterministic_response is None and intent in {"tracking", "human"}:
                deterministic_response = (
                    "I can only look up orders linked to your NovaMart demo account. "
                    "Choose an order above to see its simulated status. Refunds, delivery "
                    "changes, and other real-world actions aren't available here. Sign in "
                    "to the demo account if you'd like to create a support ticket."
                )
            elif deterministic_response is None and intent == "product" and product is None:
                deterministic_response = (
                    "Choose a product from the catalogue selector and I can share its "
                    "verified demo price and description."
                )
            elif (
                deterministic_response is None
                and not customer_context
                and self.assistant is None
            ):
                deterministic_response = (
                    "I can help with NovaMart order updates, product details, and refund or "
                    "cancellation guidance. Sign in with the demo account to see your "
                    "simulated orders. No real payment or shipping actions are made."
                )

            if deterministic_response is not None:
                response = deterministic_response
            elif self.assistant is not None:
                response = self.assistant.generate_response(
                    message=model_message,
                    conversation_history=session["history"],
                )
            else:
                response = (
                    "I can help with your NovaMart account, delivery, or invoice. "
                    "Refunds and cancellations are guidance-only in this demo."
                )

            response = validate_response(response=response, customer_details={})
            session["history"].extend(
                [
                    {"role": "user", "content": message},
                    {"role": "assistant", "content": response},
                ]
            )
            session["history"] = session["history"][-10:]
            return response


chat_service = ChatService()
