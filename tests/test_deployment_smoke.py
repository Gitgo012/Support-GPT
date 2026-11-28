import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.database import database
from app.services.rate_limiter import ChatRateLimiter


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPPORTGPT_LOAD_MODEL", "0")
    monkeypatch.setattr(database, "path", tmp_path / "smoke.sqlite3")
    with TestClient(app) as test_client:
        yield test_client


def test_root_health_and_demo_order_chat(client):
    home = client.get("/")
    health = client.get("/api/health")
    chat = client.post(
        "/api/chat",
        json={
            "message": "Where is my order?",
            "session_id": "deployment-smoke",
            "customer_email": "alex.morgan@example.com",
            "order_id": "NM-20481",
        },
    )

    assert home.status_code == 200
    assert "NovaMart" in home.text
    assert health.status_code == 200
    assert health.json()["model_loaded"] is False
    assert health.json()["device"] == "cpu"
    assert health.json()["adapter_source"] == "demo"
    assert chat.status_code == 200
    assert "in transit" in chat.json()["response"].lower()
    assert "simulated" in chat.json()["response"].lower()


def test_chat_rate_limit_is_per_ip(client, monkeypatch):
    import app.main as main_module

    monkeypatch.setattr(
        main_module,
        "chat_rate_limiter",
        ChatRateLimiter(max_requests=1, window_seconds=60),
    )
    payload = {"message": "I need delivery guidance."}

    first = client.post("/api/chat", json=payload)
    second = client.post("/api/chat", json=payload)

    assert first.status_code == 200
    assert second.status_code == 429
    assert int(second.headers["Retry-After"]) > 0


def test_chat_remembers_selected_order_across_turns(client):
    first = client.post(
        "/api/chat",
        json={
            "message": "Where is my order?",
            "session_id": "multi-turn-order",
            "customer_email": "alex.morgan@example.com",
            "order_id": "NM-20481",
        },
    )
    second = client.post(
        "/api/chat",
        json={
            "message": "And when will it arrive?",
            "session_id": "multi-turn-order",
            "customer_email": "alex.morgan@example.com",
        },
    )

    assert first.status_code == second.status_code == 200
    assert "NM-20481" in second.json()["response"]
    assert "estimated delivery" in second.json()["response"].lower()
    history = client.get(
        "/api/conversations/multi-turn-order?email=alex.morgan%40example.com"
    )
    assert [message["role"] for message in history.json()] == [
        "user", "assistant", "user", "assistant"
    ]

def test_chat_rehydrates_saved_history_after_service_restart(client, monkeypatch):
    from app.services.chat_service import chat_service

    captured_history = []

    class CapturingAssistant:
        def generate_response(self, message, conversation_history=None):
            captured_history.extend(conversation_history or [])
            return "Earlier, you asked where the order was."

    monkeypatch.setattr(chat_service, "assistant", CapturingAssistant())
    monkeypatch.setattr(chat_service, "sessions", {})
    first = client.post(
        "/api/chat",
        json={
            "message": "Where is my order?",
            "session_id": "restored-history",
            "customer_email": "alex.morgan@example.com",
            "order_id": "NM-20481",
        },
    )
    monkeypatch.setattr(chat_service, "sessions", {})
    second = client.post(
        "/api/chat",
        json={
            "message": "What did I ask earlier?",
            "session_id": "restored-history",
            "customer_email": "alex.morgan@example.com",
        },
    )

    assert first.status_code == second.status_code == 200
    assert any(
        item["role"] == "user" and item["content"] == "Where is my order?"
        for item in captured_history
    )
    assert "earlier" in second.json()["response"].lower()


def test_guest_product_context_does_not_require_customer_email(client):
    result = client.post(
        "/api/chat",
        json={
            "message": "Tell me about this one.",
            "session_id": "guest-product",
            "product_id": "linen-tote",
        },
    )

    assert result.status_code == 200
    assert "Market Day Tote" in result.json()["response"]
    assert "$34.00" in result.json()["response"]


def test_chat_resolves_typed_order_id_and_checks_customer_ownership(client):
    owned = client.post(
        "/api/chat",
        json={
            "message": "Where is order NM-20481?",
            "session_id": "typed-order-id",
            "customer_email": "alex.morgan@example.com",
        },
    )
    unknown = client.post(
        "/api/chat",
        json={
            "message": "Track order NM-99999",
            "session_id": "unknown-order-id",
            "customer_email": "alex.morgan@example.com",
        },
    )

    assert owned.status_code == 200
    assert "in transit" in owned.json()["response"].lower()
    assert unknown.status_code == 404


def test_explicit_human_escalation_creates_persisted_demo_ticket(client):
    result = client.post(
        "/api/chat",
        json={
            "message": "Please connect me with a human.",
            "session_id": "human-escalation",
            "customer_email": "alex.morgan@example.com",
            "order_id": "NM-20481",
        },
    )

    assert result.status_code == 200
    assert result.json()["ticket_id"].startswith("NM-")
    assert result.json()["escalation_available"] is False
    assert result.json()["ticket_id"] in result.json()["response"]
    assert "no live support agent" in result.json()["response"].lower()
    with database.connection() as connection:
        ticket = connection.execute(
            "SELECT order_id, status FROM tickets WHERE id = ?",
            (result.json()["ticket_id"],),
        ).fetchone()
    assert ticket["order_id"] == "NM-20481"
    assert ticket["status"] == "Open"
