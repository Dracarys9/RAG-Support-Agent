from pathlib import Path

from rag_support_agent.support_agent import SupportAgent


PROJECT_ROOT = Path(__file__).parents[1]


def make_agent() -> SupportAgent:
    return SupportAgent(
        PROJECT_ROOT / "knowledge-base",
        PROJECT_ROOT / "data" / "orders.json",
    )


def test_canada_follow_up_uses_previous_shipping_topic():
    session = make_agent().new_session()

    first = session.answer("Do you ship internationally?")
    second = session.answer("What about Canada?")

    assert first.sources
    assert "Canada" in second.answer
    assert "06-international-shipping.md" in second.answer
    assert len(session.history) == 2


def test_order_follow_up_reuses_previous_order_id():
    session = make_agent().new_session()

    first = session.answer("Where is ORD-1007?")
    second = session.answer("When will it arrive?")

    assert first.tool_used == "order_lookup"
    assert second.tool_used == "order_lookup"
    assert "UPS" in second.answer
    assert "August 22, 2026" in second.answer


def test_separate_sessions_do_not_share_order_id():
    agent = make_agent()
    first_session = agent.new_session()
    second_session = agent.new_session()

    first_session.answer("Where is ORD-1007?")
    response = second_session.answer("When will it arrive?")

    assert "order ID" in response.answer
    assert response.tool_used is None
