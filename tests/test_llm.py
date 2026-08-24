from __future__ import annotations

from pathlib import Path

from rag_support_agent.llm import LLMConfig, LLMUnavailable, OpenAIAnswerer
from rag_support_agent.support_agent import SupportAgent


ROOT = Path(__file__).parents[1]


class FakeMessage:
    content = "The return window is 30 calendar days from delivery."


class FakeChoice:
    message = FakeMessage()


class FakeResponse:
    choices = [FakeChoice()]


class FakeCompletions:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return FakeResponse()


class FakeChat:
    def __init__(self, completions: FakeCompletions) -> None:
        self.completions = completions


class FakeClient:
    def __init__(self) -> None:
        self.completions = FakeCompletions()
        self.chat = FakeChat(self.completions)


def make_agent(answerer=None) -> SupportAgent:
    return SupportAgent(
        ROOT / "knowledge-base",
        ROOT / "data" / "orders.json",
        llm_answerer=answerer,
    )


def test_llm_answerer_uses_selected_passages_only():
    client = FakeClient()
    answerer = OpenAIAnswerer(
        LLMConfig(provider="llm", model="test-model"), client=client
    )
    agent = make_agent(answerer)

    response = agent.answer("How long does a regular customer have to return an unused backpack?")

    assert response.generation_mode == "llm"
    assert "30 calendar days" in response.answer
    assert response.sources
    prompt = client.completions.calls[0]["messages"][1]["content"]
    assert "01-returns-policy-current.md" in prompt
    assert "14-internal-content-migration-notes.md" not in prompt
    assert "risk_score" not in prompt
    assert client.completions.calls[0]["model"] == "test-model"


def test_support_agent_uses_llm_with_sanitized_order_result():
    client = FakeClient()
    answerer = OpenAIAnswerer(
        LLMConfig(provider="llm", model="test-model"), client=client
    )
    agent = make_agent(answerer)

    response = agent.answer("Where is ORD-1007?")

    assert response.generation_mode == "llm"
    assert response.tool_used == "order_lookup"
    prompt = client.completions.calls[0]["messages"][1]["content"]
    assert "ORD-1007" in prompt
    assert "shipped" in prompt
    assert "risk_score" not in prompt
    assert "ava.morgan@example.test" not in prompt


def test_llm_prompt_contains_safe_order_result_not_private_order_fields():
    client = FakeClient()
    answerer = OpenAIAnswerer(
        LLMConfig(provider="llm", model="test-model"), client=client
    )
    safe_result = {
        "order_id": "ORD-1007",
        "status": "shipped",
        "carrier": "UPS",
        "estimated_delivery": "2026-08-22",
        "customer_safe_message": "In transit.",
    }

    answerer.answer(
        "Where is ORD-1007?",
        sanitized_tool_result=safe_result,
    )

    prompt = client.completions.calls[0]["messages"][1]["content"]
    assert "ORD-1007" in prompt
    assert "risk_score" not in prompt
    assert "email" not in prompt.lower()
    assert "shipping_address" not in prompt


def test_llm_mode_falls_back_to_deterministic_answer_when_key_is_missing():
    answerer = OpenAIAnswerer(LLMConfig(provider="llm", api_key=None))
    agent = make_agent(answerer)

    response = agent.answer("How long does a regular customer have to return an unused backpack?")

    assert response.generation_mode == "deterministic"
    assert response.fallback_reason == "llm_unavailable"
    assert "30 calendar days" in response.answer


def test_local_config_does_not_enable_llm():
    config = LLMConfig(provider="local")
    assert config.enabled is False
    try:
        OpenAIAnswerer(config).answer("hello")
    except LLMUnavailable as exc:
        assert "disabled" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("local mode should not call the model")
