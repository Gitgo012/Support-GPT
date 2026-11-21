
import re


PLACEHOLDER_PATTERN = re.compile(r"\{\{[^{}]+\}\}")

ORDER_PLACEHOLDER_PATTERN = re.compile(
    r"\{\{\s*(?:order\s*(?:number|id)|order_id)\s*\}\}",
    re.IGNORECASE,
)

# Claims that imply SupportGPT has accessed an external system
# or completed an operation on behalf of the customer.
UNSUPPORTED_ACTION_PATTERNS = [
    re.compile(
        r"\b(?:let me|i(?:'ll| will)|we(?:'ll| will))\s+"
        r"(?:check|look up|verify|retrieve|access)\s+"
        r"(?:the\s+)?(?:current\s+)?(?:status|details|records|account|order)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:i|we)\s+(?:have\s+)?"
        r"(?:checked|verified|retrieved|accessed|looked up)\s+"
        r"(?:your\s+)?(?:order|account|refund|payment|records)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:your\s+)?(?:refund|order|cancellation)\s+"
        r"(?:has been|is now)\s+(?:processed|completed|approved|cancelled)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:i|we)\s+(?:have\s+)?"
        r"(?:processed|issued|approved|cancelled|refunded)\s+"
        r"(?:your\s+)?(?:refund|order|cancellation|payment)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:i|we)\s+(?:am|are)\s+"
        r"(?:checking|verifying|retrieving|accessing)\s+"
        r"(?:your\s+)?(?:order|account|payment|refund)\b",
        re.IGNORECASE,
    ),
]


SAFE_FALLBACK = (
    "I can guide you through the process, but I don't have access to "
    "company order, account, or payment systems. You can check your order "
    "through the relevant company's official order history or contact "
    "its support team for verified information."
)


def validate_response(response: str, customer_details: dict) -> str:
    """Validate generated text before returning it to a customer."""

    if not isinstance(response, str) or not response.strip():
        return (
            "I'm sorry, but I couldn't generate a helpful response just now. "
            "Please try asking your question again."
        )

    response = response.strip()

    order_id = customer_details.get("order_id")

    if order_id:
        response = ORDER_PLACEHOLDER_PATTERN.sub(
            lambda match: str(order_id),
            response,
        )

    # Never expose unresolved training-data placeholders.
    if PLACEHOLDER_PATTERN.search(response):
        return SAFE_FALLBACK

    # Reject claims of external access or completed operations.
    for pattern in UNSUPPORTED_ACTION_PATTERNS:
        if pattern.search(response):
            return SAFE_FALLBACK

    return response
