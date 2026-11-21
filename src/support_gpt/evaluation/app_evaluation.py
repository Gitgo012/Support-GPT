"""Contract checks for the FastAPI route and stateful chat service."""

import asyncio
from typing import Any
from unittest.mock import patch

from fastapi import HTTPException

from app.api.routes import chat as chat_api
from app.services.chat_service import ChatService


class _RecordingAssistant:
    def __init__(self, responses: list[str] | None = None, error: Exception | None = None):
        self.responses = list(responses or [])
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def generate_response(
        self,
        message: str,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> str:
        self.calls.append(
            {
                "message": message,
                "conversation_history": conversation_history or [],
            }
        )
        if self.error is not None:
            raise self.error
        if not self.responses:
            return ""
        return self.responses.pop(0)


def _row(
    case_id: str,
    criterion: str,
    passed: bool,
    response: str = "",
    error: str = "",
) -> dict[str, Any]:
    return {
        "model": "fastapi_application",
        "case_id": case_id,
        "category": "application",
        "messages": "",
        "expected_behavior": criterion,
        "reference_answer": "",
        "evaluation_criteria": criterion,
        "expected_safety_behavior": criterion,
        "response": response,
        "latency_seconds": "",
        "loss": "",
        "perplexity": "",
        "error": error,
        "empty_response": "",
        "placeholder_leakage": "",
        "unsupported_action_claim": "",
        "automated_safety_compliant": "",
        "application_check_passed": passed,
        "human_relevance": "",
        "human_correctness": "",
        "human_helpfulness": "",
        "human_instruction_following": "",
    }


def _call_route(message: str, session_id: str | None = None):
    return asyncio.run(
        chat_api.chat(
            chat_api.ChatRequest(message=message, session_id=session_id)
        )
    )


def evaluate_application() -> list[dict[str, Any]]:
    """Run isolated application checks without loading the production model."""
    rows: list[dict[str, Any]] = []

    assistant = _RecordingAssistant(
        [
            "Thanks for sharing the order number. What do you need help with?",
            "You shared order number ORD-7821. I can't verify its status.",
        ]
    )
    service = ChatService()
    service.assistant = assistant
    with patch.object(chat_api, "chat_service", service):
        first = _call_route("My order number: ORD-7821", "eval-session")
        second = _call_route("Can you remind me which order it was?", "eval-session")

    retained = (
        len(assistant.calls) == 2
        and "ORD-7821" in assistant.calls[1]["message"]
        and any(
            entry["content"] == "My order number: ORD-7821"
            for entry in assistant.calls[1]["conversation_history"]
        )
        and first.session_id == second.session_id == "eval-session"
    )
    rows.append(
        _row(
            "app_session_order_id",
            "The API retains session history and customer-provided order IDs across turns.",
            retained,
            second.response,
            "" if retained else "Session history or order ID was not retained.",
        )
    )

    for case_id, generated, marker, criterion in (
        (
            "app_placeholder_validation",
            "Visit {{Website URL}}.",
            "official",
            "Unresolved placeholders are replaced with a safe fallback.",
        ),
        (
            "app_unsupported_action_validation",
            "Your refund has been processed.",
            "don't have access",
            "Unsupported claims of completed account actions are rejected.",
        ),
        (
            "app_empty_generation_validation",
            "",
            "couldn't generate",
            "An empty model response is converted to the configured failure response.",
        ),
    ):
        fake = _RecordingAssistant([generated])
        service = ChatService()
        service.assistant = fake
        with patch.object(chat_api, "chat_service", service):
            result = _call_route("Please help.", f"eval-{case_id}")
        passed = marker.lower() in result.response.lower()
        rows.append(
            _row(
                case_id,
                criterion,
                passed,
                result.response,
                "" if passed else f"Expected response to contain {marker!r}.",
            )
        )

    service = ChatService()
    service.assistant = _RecordingAssistant(["A response."])
    with patch.object(chat_api, "chat_service", service):
        try:
            _call_route("   ", "eval-whitespace")
        except HTTPException as exc:
            status_code = exc.status_code
        else:
            status_code = None
    passed = status_code == 422
    rows.append(
        _row(
            "app_blank_request_validation",
            "Whitespace-only customer messages are rejected with HTTP 422.",
            passed,
            error="" if passed else f"Observed status code: {status_code!r}.",
        )
    )

    service = ChatService()
    service.assistant = _RecordingAssistant(error=RuntimeError("test failure"))
    with patch.object(chat_api, "chat_service", service):
        try:
            _call_route("Please help.", "eval-error")
        except HTTPException as exc:
            status_code = exc.status_code
        else:
            status_code = None
    passed = status_code == 500
    rows.append(
        _row(
            "app_generation_error_mapping",
            "Model failures are surfaced as HTTP 500, not a success-shaped response.",
            passed,
            error="" if passed else f"Observed status code: {status_code!r}.",
        )
    )

    return rows
