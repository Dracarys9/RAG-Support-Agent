from pathlib import Path

from rag_support_agent.support_agent import SupportAgent
from rag_support_agent.web_app import create_app


PROJECT_ROOT = Path(__file__).parents[1]


def make_app(answerer=None):
    agent = SupportAgent(
        PROJECT_ROOT / "knowledge-base",
        PROJECT_ROOT / "data" / "orders.json",
        llm_answerer=answerer,
    )
    app = create_app(agent)
    app.config.update(TESTING=True)
    return app


def test_one_command_launchers_exist():
    for filename in ("run_chat.bat", "run_chat.ps1"):
        launcher = PROJECT_ROOT / filename
        assert launcher.exists()
        assert "rag_support_agent.web_app" in launcher.read_text(encoding="utf-8")


def test_browser_page_and_health_endpoint():
    client = make_app().test_client()

    page = client.get("/")
    health = client.get("/api/health")

    assert page.status_code == 200
    assert b"Aster & Row support" in page.data
    assert health.status_code == 200
    assert health.get_json() == {
        "ok": True,
        "llm_enabled": False,
        "model": None,
    }


def test_chat_keeps_one_session_and_returns_safe_details():
    client = make_app().test_client()

    first = client.post(
        "/api/chat",
        json={"message": "Where is ORD-1007?"},
    )
    first_data = first.get_json()
    second = client.post(
        "/api/chat",
        json={
            "session_id": first_data["session_id"],
            "message": "When will it arrive?",
        },
    )
    second_data = second.get_json()

    assert first.status_code == 200
    assert second.status_code == 200
    assert second_data["session_id"] == first_data["session_id"]
    assert second_data["tool_used"] == "order_lookup"
    assert "UPS" in second_data["answer"]
    assert second_data["retrieved_passages"] == []
    assert "email" not in second.get_data(as_text=True).lower()
    assert "shipping_address" not in second.get_data(as_text=True)


def test_chat_reports_llm_mode_when_answer_writer_is_enabled():
    class FakeAnswerer:
        def answer(self, message, *, history=(), passages=(), sanitized_tool_result=None):
            return "A generated answer from the configured model."

    client = make_app(FakeAnswerer()).test_client()
    response = client.post(
        "/api/chat",
        json={"message": "How long does a regular customer have to return an unused backpack?"},
    )
    data = response.get_json()

    assert response.status_code == 200
    assert data["generation_mode"] == "llm"
    assert data["fallback_reason"] is None
    assert data["sources"]
    assert "Source:" in data["answer"]


def test_chat_rejects_empty_or_oversized_messages():
    client = make_app().test_client()

    assert client.post("/api/chat", json={"message": " "}).status_code == 400
    assert client.post("/api/chat", json={"message": "x" * 2001}).status_code == 400
