from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .knowledge_base import KnowledgeSection, load_knowledge_base, search_knowledge_base
from .orders import lookup_order, normalize_order_id


@dataclass(frozen=True)
class SupportResponse:
    """The customer-facing answer and a few simple details for testing."""

    answer: str
    sources: tuple[str, ...] = ()
    handoff: bool = False
    tool_used: str | None = None


class SupportSession:
    """Conversation memory for one customer session only."""

    def __init__(self, agent: "SupportAgent"):
        self.agent = agent
        self.history: list[tuple[str, SupportResponse]] = []
        self.last_topic: str | None = None
        self.last_order_id: str | None = None

    def answer(self, message: str) -> SupportResponse:
        response = self.agent.answer(message, session=self)
        self.history.append((message, response))
        order_id = self.agent._find_order_id(message)
        if order_id:
            self.last_order_id = order_id
        if response.sources:
            self.last_topic = message
        return response


class SupportAgent:
    """A small, deterministic support program built on the safe data functions."""

    def __init__(self, knowledge_base_dir: str | Path, orders_file: str | Path):
        self.sections = load_knowledge_base(knowledge_base_dir)
        self.orders_file = Path(orders_file)

    def new_session(self) -> SupportSession:
        return SupportSession(self)

    def answer(
        self, message: str, session: SupportSession | None = None
    ) -> SupportResponse:
        """Answer one message using optional context from one session."""
        order_id = self._find_order_id(message)
        is_order_follow_up = bool(
            session
            and session.last_order_id
            and self._looks_like_order_follow_up(message)
        )
        if is_order_follow_up:
            order_id = session.last_order_id

        if self._asks_for_private_information(message):
            return SupportResponse(
                answer=(
                    "I can’t provide personal information or internal order data such "
                    "as an email address, shipping address, internal note, or risk score. "
                    "Please contact a human support specialist for help with that request."
                ),
                handoff=True,
            )

        if self._is_order_status_question(message) or is_order_follow_up:
            if not order_id:
                return SupportResponse(
                    answer="Please provide your order ID, such as ORD-1007, so I can check the order.",
                )
            return self._answer_order(order_id)

        search_message = message
        if session and session.last_topic and self._looks_like_follow_up(message):
            search_message = f"{session.last_topic} {message}"
        return self._answer_from_knowledge(search_message)

    def _answer_order(self, order_id: str) -> SupportResponse:
        result = lookup_order(
            self.orders_file,
            order_id,
            fields=[
                "order_id",
                "status",
                "carrier",
                "estimated_delivery",
                "customer_safe_message",
            ],
        )
        if not result["found"]:
            return SupportResponse(
                answer=result["message"],
                handoff=result.get("handoff_recommended", False),
                tool_used="order_lookup",
            )

        data: dict[str, Any] = result["data"]
        answer = data["customer_safe_message"]
        if data.get("carrier") and data["carrier"] not in answer:
            answer += f" Carrier: {data['carrier']}."
        if data.get("estimated_delivery") and data["estimated_delivery"] not in answer:
            answer += f" Estimated delivery: {data['estimated_delivery']}."

        return SupportResponse(
            answer=answer,
            handoff=result.get("handoff_recommended", False),
            tool_used="order_lookup",
        )

    def _answer_from_knowledge(self, message: str) -> SupportResponse:
        customer_sections = [
            section
            for section in self.sections
            if section.metadata.get("status") == "active"
            and section.metadata.get("policy_authority") == "official"
            and section.metadata.get("audience") == "customer"
        ]
        results = search_knowledge_base(customer_sections, message, limit=2)
        if not results:
            return SupportResponse(
                answer=(
                    "The supplied information is not enough for me to answer that reliably. "
                    "Please contact a human support specialist for confirmation."
                ),
                handoff=True,
            )

        best = results[0].section
        source = self._source_name(best)
        return SupportResponse(
            answer=f"{best.text}\n\nSource: {source}",
            sources=(source,),
        )

    @staticmethod
    def _source_name(section: KnowledgeSection) -> str:
        return f"{section.file_name} — {section.heading}"

    @staticmethod
    def _find_order_id(message: str) -> str | None:
        match = re.search(r"\bORD\s*-?\s*\d{4}\b", message, flags=re.IGNORECASE)
        return normalize_order_id(match.group(0)) if match else None

    @staticmethod
    def _looks_like_follow_up(message: str) -> bool:
        lowered = message.strip().lower()
        return lowered.startswith(("what about", "and ", "how long", "when ", "does it", "can it"))

    @staticmethod
    def _looks_like_order_follow_up(message: str) -> bool:
        lowered = message.lower()
        return any(
            word in lowered
            for word in ("when", "arrive", "delivery", "delivered", "shipped", "tracking")
        )

    @staticmethod
    def _is_order_status_question(message: str) -> bool:
        lowered = message.lower()
        if SupportAgent._find_order_id(message):
            return True

        order_words = ("order", "tracking", "track", "shipment")
        status_words = (
            "where",
            "status",
            "arrive",
            "delivery",
            "delivered",
            "shipped",
            "tracking",
            "when",
        )
        clear_delivery_follow_up = (
            ("when will" in lowered and "arrive" in lowered)
            or "where is" in lowered
            or "where's" in lowered
            or "has it shipped" in lowered
        )
        return clear_delivery_follow_up or (
            any(word in lowered for word in order_words)
            and any(word in lowered for word in status_words)
        )

    @staticmethod
    def _asks_for_private_information(message: str) -> bool:
        lowered = message.lower()
        private_terms = (
            "email",
            "e-mail",
            "address",
            "internal note",
            "risk score",
            "hidden prompt",
            "system prompt",
            "secret",
        )
        return any(term in lowered for term in private_terms)
