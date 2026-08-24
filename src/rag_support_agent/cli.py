from __future__ import annotations

import sys
from pathlib import Path

from .llm import LLMConfig, OpenAIAnswerer
from .support_agent import SupportAgent, SupportResponse


def build_agent() -> SupportAgent:
    """Build the agent using the repository's supplied data folders."""
    project_root = Path(__file__).resolve().parents[2]
    config = LLMConfig.from_env()
    answerer = OpenAIAnswerer(config) if config.enabled else None
    return SupportAgent(
        project_root / "knowledge-base",
        project_root / "data" / "orders.json",
        llm_answerer=answerer,
    )


def format_response(response: SupportResponse) -> str:
    """Format one response for a person using the terminal."""
    lines = ["Agent:", response.answer]
    if response.sources and not any(
        source in response.answer for source in response.sources
    ):
        lines.append("Sources: " + "; ".join(response.sources))
    lines.append("Human help recommended: " + ("Yes" if response.handoff else "No"))
    return "\n".join(lines)


def main() -> None:
    agent = build_agent()
    session = agent.new_session()
    print("Aster & Row Support Agent")
    print("Type 'quit' to stop.")

    while True:
        try:
            message = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            return

        if message.lower() in {"quit", "exit"}:
            print("Goodbye.")
            return
        if not message:
            continue

        if "--debug" in sys.argv[1:]:
            response, trace = agent.answer_with_trace(message, session=session)
            print(format_response(response))
            print("\nDebug trace:")
            print(trace.to_json())
        else:
            print(format_response(session.answer(message)))


if __name__ == "__main__":
    main()
