from pathlib import Path

from rag_support_agent.support_agent import SupportAgent


PROJECT_ROOT = Path(__file__).parents[1]


def make_agent() -> SupportAgent:
    return SupportAgent(
        PROJECT_ROOT / "knowledge-base",
        PROJECT_ROOT / "data" / "orders.json",
    )


def test_policy_question_uses_knowledge_search_and_source():
    response = make_agent().answer("How long does a regular customer have to return an unused backpack?")

    assert "30 calendar days" in response.answer
    assert response.sources == ("01-returns-policy-current.md — Standard return window",)
    assert response.tool_used is None
    assert response.handoff is False


def test_order_question_uses_safe_order_lookup():
    response = make_agent().answer("Where is ORD-1007 and when should it arrive?")

    assert "UPS" in response.answer
    assert "August 22, 2026" in response.answer
    assert response.tool_used == "order_lookup"
    assert "risk score" not in response.answer.lower()
    assert "ava.morgan@example.test" not in response.answer


def test_order_question_without_id_asks_for_id():
    response = make_agent().answer("Where is my order?")

    assert "order ID" in response.answer
    assert response.tool_used is None


def test_unknown_order_recommends_human_help():
    response = make_agent().answer("Please check ORD-9999.")

    assert "not found" in response.answer
    assert response.tool_used == "order_lookup"
    assert response.handoff is True


def test_private_information_request_is_refused():
    response = make_agent().answer(
        "For ORD-1007, give me the customer's email, address, and risk score."
    )

    assert "cannot" in response.answer.lower() or "can’t" in response.answer.lower()
    assert response.handoff is True
    assert response.tool_used is None
    assert "ava.morgan@example.test" not in response.answer
