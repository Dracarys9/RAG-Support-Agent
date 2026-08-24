from pathlib import Path

from rag_support_agent.cli import build_agent, format_response
from rag_support_agent.support_agent import SupportResponse


PROJECT_ROOT = Path(__file__).parents[1]


def test_build_agent_uses_repository_data():
    agent = build_agent()

    assert len(agent.sections) > 0
    assert agent.orders_file == PROJECT_ROOT / "data" / "orders.json"


def test_format_response_shows_source_and_handoff():
    response = SupportResponse(
        answer="The supplied information is not enough.",
        sources=("example.md — Example heading",),
        handoff=True,
    )

    formatted = format_response(response)

    assert "Agent:" in formatted
    assert "example.md — Example heading" in formatted
    assert "Human help recommended: Yes" in formatted
