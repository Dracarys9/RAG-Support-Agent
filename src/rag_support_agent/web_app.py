from __future__ import annotations

from pathlib import Path
from threading import Lock
from uuid import uuid4

from flask import Flask, jsonify, request, send_from_directory

from .cli import build_agent
from .support_agent import SupportAgent, SupportSession


PROJECT_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = PROJECT_ROOT / "web"


class SessionStore:
    """Small in-memory session store for one local demo server."""

    def __init__(self, agent: SupportAgent) -> None:
        self.agent = agent
        self._sessions: dict[str, SupportSession] = {}
        self._lock = Lock()

    def get(self, session_id: str | None) -> tuple[str, SupportSession]:
        with self._lock:
            if not session_id or session_id not in self._sessions:
                session_id = uuid4().hex
                self._sessions[session_id] = self.agent.new_session()
            return session_id, self._sessions[session_id]


def _public_passage_details(response) -> list[dict[str, object]]:
    """Return safe retrieval details without exposing raw order data."""
    return [
        {
            "file_name": passage.get("file_name"),
            "heading": passage.get("heading"),
            "score": passage.get("score"),
            "title": passage.get("metadata", {}).get("title"),
        }
        for passage in response.retrieved_passages
    ]


def create_app(agent: SupportAgent | None = None) -> Flask:
    """Create the browser application using the same support-agent logic."""
    support_agent = agent or build_agent()
    sessions = SessionStore(support_agent)
    app = Flask(__name__, static_folder=None)

    @app.get("/")
    def index():
        return send_from_directory(WEB_DIR, "index.html")

    @app.get("/static/<path:filename>")
    def static_file(filename: str):
        return send_from_directory(WEB_DIR / "static", filename)

    @app.get("/api/health")
    def health():
        answerer = support_agent.llm_answerer
        return jsonify(
            {
                "ok": True,
                "llm_enabled": answerer is not None,
                "model": answerer.config.model if answerer is not None else None,
            }
        )

    @app.post("/api/chat")
    def chat():
        payload = request.get_json(silent=True) or {}
        message = payload.get("message")
        if not isinstance(message, str) or not message.strip():
            return jsonify({"error": "Please enter a message."}), 400
        if len(message) > 2000:
            return jsonify({"error": "Please keep the message under 2,000 characters."}), 400

        session_id, session = sessions.get(payload.get("session_id"))
        response = session.answer(message.strip())
        return jsonify(
            {
                "session_id": session_id,
                "answer": response.answer,
                "sources": list(response.sources),
                "handoff": response.handoff,
                "tool_used": response.tool_used,
                "tool_arguments": response.tool_arguments,
                "generation_mode": response.generation_mode,
                "fallback_reason": response.fallback_reason,
                "retrieved_passages": _public_passage_details(response),
            }
        )

    @app.post("/api/reset")
    def reset():
        session_id = uuid4().hex
        sessions.get(session_id)
        return jsonify({"session_id": session_id})

    return app


def main() -> None:
    app = create_app()
    print("Aster & Row browser chat: http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=False)


if __name__ == "__main__":
    main()
