from __future__ import annotations

from pathlib import Path

from rag_support_agent.llm import LLMConfig, LLMUnavailable, OpenAIAnswerer
from rag_support_agent.support_agent import SupportAgent


ROOT = Path(__file__).parents[1]


class FakeMessage:
    content = (
        "A regular customer on the standard plan has 30 calendar days of delivery "
        "to request a return.\n\n**Source:** `01-returns-policy-current.md` — *Standard return window*"
    )


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


class FailingCompletions:
    def create(self, **kwargs):
        raise RuntimeError("provider failed with a private detail")


class FailingClient:
    def __init__(self) -> None:
        self.chat = FakeChat(FailingCompletions())


class ExtraMembershipAnswerer:
    def answer(self, message, *, history=(), passages=(), sanitized_tool_result=None):
        return (
            "Customers on the standard plan may request a return within 30 calendar days of delivery.\n\n"
            "TrailPlus members receive a different return window if membership was active when the order was placed."
        )


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
    assert "may request a return within 30 calendar days of delivery" in response.answer
    assert response.answer.count("Source:") == 1
    assert "**Source:**" not in response.answer
    assert response.sources
    prompt = client.completions.calls[0]["messages"][1]["content"]
    assert "01-returns-policy-current.md" in prompt
    assert "14-internal-content-migration-notes.md" not in prompt
    assert "risk_score" not in prompt
    assert client.completions.calls[0]["model"] == "test-model"


def test_llm_policy_cleanup_removes_repeated_within():
    cleaned = SupportAgent._clean_generated_policy_answer(
        "A customer may request a return within within 30 calendar days of delivery."
    )

    assert "within within" not in cleaned.lower()
    assert "within 30 calendar days of delivery" in cleaned


def test_standard_return_answer_removes_unrelated_membership_context():
    response = make_agent(ExtraMembershipAnswerer()).answer(
        "I am a regular customer. Can I return a backpack after 30 days?"
    )

    assert "standard plan" in response.answer.lower()
    assert "trailplus" not in response.answer.lower()
    assert response.sources == (
        "01-returns-policy-current.md — Standard return window",
    )


def test_llm_policy_cleanup_removes_markdown_repeated_within():
    cleaned = SupportAgent._clean_generated_policy_answer(
        "A customer may request a return within **within 30 calendar days of delivery**."
    )

    assert "within **within" not in cleaned.lower()
    assert "within **30 calendar days of delivery**" in cleaned


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


def test_provider_failure_has_secret_safe_debug_code():
    answerer = OpenAIAnswerer(
        LLMConfig(provider="llm", model="test-model", api_key="private-key"),
        client=FailingClient(),
    )
    agent = make_agent(answerer)

    response, trace = agent.answer_with_trace(
        "How long does a regular customer have to return an unused backpack?"
    )

    assert response.generation_mode == "deterministic"
    assert response.fallback_reason == "llm_unavailable"
    assert response.llm_error_code == "provider_request_failed"
    assert trace.llm_error_code == "provider_request_failed"
    assert "private detail" not in trace.to_json()
    assert "private-key" not in trace.to_json()


def test_local_config_does_not_enable_llm():
    config = LLMConfig(provider="local")
    assert config.enabled is False
    try:
        OpenAIAnswerer(config).answer("hello")
    except LLMUnavailable as exc:
        assert "disabled" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("local mode should not call the model")
