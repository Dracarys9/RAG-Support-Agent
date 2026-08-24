from pathlib import Path

from rag_support_agent.support_agent import SupportAgent


PROJECT_ROOT = Path(__file__).parents[1]


def make_agent() -> SupportAgent:
    return SupportAgent(
        PROJECT_ROOT / "knowledge-base",
        PROJECT_ROOT / "data" / "orders.json",
    )


def test_policy_debug_trace_contains_source_and_answer():
    agent = make_agent()
    response, trace = agent.answer_with_trace(
        "How long does a regular customer have to return an unused backpack?"
    )

    trace_text = trace.to_json()
    assert response.answer == trace.final_answer
    assert "01-returns-policy-current.md" in trace_text
    assert "Standard return window" in trace_text
    assert trace.tool_used is None
    assert trace.handoff is False


def test_order_debug_trace_contains_safe_tool_details():
    agent = make_agent()
    response, trace = agent.answer_with_trace("Where is ORD-1007?")

    assert response.tool_used == "order_lookup"
    assert trace.tool_arguments == {"order_id": "ORD-1007"}
    trace_text = trace.to_json()
    assert "risk_score" not in trace_text
    assert "ava.morgan@example.test" not in trace_text


def test_debug_trace_contains_previous_messages_only():
    agent = make_agent()
    session = agent.new_session()
    session.answer("Do you ship internationally?")
    _, trace = agent.answer_with_trace("What about Canada?", session=session)

    assert trace.history == ("Do you ship internationally?",)
