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
