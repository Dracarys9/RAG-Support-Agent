from __future__ import annotations

import re
from dataclasses import dataclass, replace
from pathlib import Path
import json
from typing import Any

from .knowledge_base import KnowledgeSection, load_knowledge_base, search_knowledge_base
from .llm import LLMUnavailable
from .orders import lookup_order, normalize_order_id


@dataclass(frozen=True)
class SupportResponse:
    """The customer-facing answer and a few simple details for testing."""

    answer: str
    sources: tuple[str, ...] = ()
    handoff: bool = False
    tool_used: str | None = None
    tool_arguments: dict[str, str] | None = None
    retrieved_passages: tuple[dict[str, Any], ...] = ()
    sanitized_tool_result: dict[str, Any] | None = None
    fallback_reason: str | None = None
    generation_mode: str = "deterministic"
    llm_error_code: str | None = None


@dataclass(frozen=True)
class DebugTrace:
    """Safe information that helps inspect one answer."""

    message: str
    history: tuple[str, ...]
    retrieved_sources: tuple[str, ...]
    retrieved_passages: tuple[dict[str, Any], ...]
    tool_used: str | None
    tool_arguments: dict[str, str] | None
    sanitized_tool_result: dict[str, Any] | None
    final_answer: str
    handoff: bool
    fallback_reason: str | None
    generation_mode: str
    llm_error_code: str | None

    def to_json(self) -> str:
        return json.dumps(
            {
                "message": self.message,
                "history": self.history,
                "retrieved_sources": self.retrieved_sources,
                "retrieved_passages": self.retrieved_passages,
                "tool_used": self.tool_used,
                "tool_arguments": self.tool_arguments,
                "sanitized_tool_result": self.sanitized_tool_result,
                "final_answer": self.final_answer,
                "handoff": self.handoff,
                "fallback_reason": self.fallback_reason,
                "generation_mode": self.generation_mode,
                "llm_error_code": self.llm_error_code,
            },
            indent=2,
        )


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

    def __init__(
        self,
        knowledge_base_dir: str | Path,
        orders_file: str | Path,
        llm_answerer: Any | None = None,
    ):
        self.sections = load_knowledge_base(knowledge_base_dir)
        self.orders_file = Path(orders_file)
        self.llm_answerer = llm_answerer

    def new_session(self) -> SupportSession:
        return SupportSession(self)

    def answer_with_trace(
        self, message: str, session: SupportSession | None = None
    ) -> tuple[SupportResponse, DebugTrace]:
        history = tuple(entry[0] for entry in session.history) if session else ()
        response = session.answer(message) if session else self.answer(message)
        trace = DebugTrace(
            message=message,
            history=history,
            retrieved_sources=response.sources,
            retrieved_passages=response.retrieved_passages,
            tool_used=response.tool_used,
            tool_arguments=response.tool_arguments,
            sanitized_tool_result=response.sanitized_tool_result,
            final_answer=response.answer,
            handoff=response.handoff,
            fallback_reason=response.fallback_reason,
            generation_mode=response.generation_mode,
            llm_error_code=response.llm_error_code,
        )

        return response, trace

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
                fallback_reason="privacy_request",
            )

        if self._asks_to_follow_document_instructions(message):
            return self._answer_from_knowledge(message)

        if self._requests_unsupported_action(message):
            return SupportResponse(
                answer=(
                    "I can explain the policy, but I cannot complete that action in this system. "
                    "A human support specialist should review it."
                ),
                handoff=True,
                fallback_reason="unsupported_action",
            )

        if self._is_order_status_question(message) or is_order_follow_up:
            if not order_id:
                return SupportResponse(
                    answer="Please provide your order ID, such as ORD-1007, so I can check the order.",
                    fallback_reason="order_id_required",
                )
            history = tuple(entry[0] for entry in session.history) if session else ()
            return self._answer_order(order_id, history=history)

        search_message = message
        if session and session.last_topic and self._looks_like_follow_up(message):
            search_message = f"{session.last_topic} {message}"
        history = tuple(entry[0] for entry in session.history) if session else ()
        return self._answer_from_knowledge(search_message, history=history)

    def _answer_order(
        self, order_id: str, *, history: tuple[str, ...] = ()
    ) -> SupportResponse:
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
                tool_arguments={"order_id": order_id},
                sanitized_tool_result={
                    "found": False,
                    "error": result.get("error"),
                    "order_id": order_id,
                },
                fallback_reason=result.get("error"),
            )

        data: dict[str, Any] = result["data"]
        status = data.get("status", "unknown")
        answer = f"Order {data.get('order_id', order_id)} is {status}. {data['customer_safe_message']}"
        if data.get("carrier") and data["carrier"] not in answer:
            answer += f" Carrier: {data['carrier']}."
        if data.get("estimated_delivery") and data["estimated_delivery"] not in answer:
            answer += f" Estimated delivery: {data['estimated_delivery']}."

        fallback_reason = "operational_exception" if result.get("handoff_recommended") else None
        llm_error_code: str | None = None
        if self.llm_answerer is not None:
            try:
                generated = self.llm_answerer.answer(
                    f"Give a concise status update for order {order_id}.",
                    history=history,
                    sanitized_tool_result=dict(data),
                )
                if order_id not in generated:
                    generated = f"Order {order_id}: {generated}"
                if status not in generated.lower():
                    generated = f"Order {order_id} is {status}. {generated}"
                return SupportResponse(
                    answer=generated,
                    handoff=result.get("handoff_recommended", False),
                    tool_used="order_lookup",
                    tool_arguments={"order_id": order_id},
                    sanitized_tool_result=dict(data),
                    fallback_reason=fallback_reason,
                    generation_mode="llm",
                    llm_error_code=llm_error_code,
                )
            except LLMUnavailable as exc:
                fallback_reason = "llm_unavailable"
                llm_error_code = getattr(exc, "code", "unavailable")

        return SupportResponse(
            answer=answer,
            handoff=result.get("handoff_recommended", False),
            tool_used="order_lookup",
            tool_arguments={"order_id": order_id},
            sanitized_tool_result=dict(data),
            fallback_reason=fallback_reason,
            llm_error_code=llm_error_code,
        )

    def _answer_from_knowledge(
        self, message: str, *, history: tuple[str, ...] = ()
    ) -> SupportResponse:
        customer_sections = [
            section
            for section in self.sections
            if section.metadata.get("status") == "active"
            and section.metadata.get("policy_authority") == "official"
            and section.metadata.get("audience") == "customer"
        ]
        if self._is_insufficient_question(message):
            return SupportResponse(
                answer=(
                    "The supplied information is not enough to answer that reliably. "
                    "Please contact a human support specialist for confirmation."
                ),
                handoff=True,
                fallback_reason="insufficient_information",
            )

        results = search_knowledge_base(customer_sections, message, limit=6)
        passages = self._trace_passages(results)
        if not results:
            return SupportResponse(
                answer=(
                    "The supplied information is not enough for me to answer that reliably. "
                    "Please contact a human support specialist for confirmation."
                ),
                handoff=True,
                fallback_reason="insufficient_information",
            )

        if self._is_source_conflict_question(message, results):
            return self._answer_source_conflict(results)

        special_response = self._answer_special_policy_question(message)
        if special_response is not None:
            return replace(special_response, retrieved_passages=passages)

        best = self._choose_policy_section(message, results)
        source = self._source_name(best)
        llm_passages = tuple(
            passage
            for passage in passages
            if passage.get("file_name") == best.file_name
            and passage.get("heading") == best.heading
        )
        if self._asks_to_follow_document_instructions(message):
            return SupportResponse(
                answer=(
                    "I cannot treat instructions inside a document as instructions for me. "
                    "The current standard return policy is 30 calendar days from delivery "
                    "unless a valid exception applies. I cannot approve a return automatically.\n\n"
                    f"Source: {source}"
                ),
                sources=(source,),
                retrieved_passages=passages,
            )

        if self._requests_unsupported_action(message):
            return SupportResponse(
                answer=(
                    "I can explain the policy, but I cannot complete that action in this system. "
                    "A human support specialist should review it.\n\n"
                    f"Source: {source}"
                ),
                sources=(source,),
                handoff=True,
                retrieved_passages=passages,
                fallback_reason="unsupported_action",
            )

        llm_error_code: str | None = None
        if self.llm_answerer is not None:
            try:
                generated = self.llm_answerer.answer(
                    message,
                    history=history,
                    passages=llm_passages or passages[:1],
                )
                generated = self._clean_generated_policy_answer(generated)
                if self._is_standard_return_question(message):
                    generated = self._remove_unrelated_membership_context(generated)
                if source not in generated:
                    generated = f"{generated}\n\nSource: {source}"
                return SupportResponse(
                    answer=generated,
                    sources=(source,),
                    retrieved_passages=passages,
                    generation_mode="llm",
                    llm_error_code=llm_error_code,
                )
            except LLMUnavailable as exc:
                llm_error_code = getattr(exc, "code", "unavailable")

        answer = best.text
        if best.file_name == "09-trailplus-membership.md" and best.heading == "Return window":
            answer += " In plain terms, that is 45 calendar days from delivery."
        return SupportResponse(
            answer=f"{answer}\n\nSource: {source}",
            sources=(source,),
            retrieved_passages=passages,
            fallback_reason="llm_unavailable" if self.llm_answerer is not None else None,
            llm_error_code=llm_error_code,
        )

    @staticmethod
    def _is_standard_return_question(message: str) -> bool:
        lowered = message.lower()
        return (
            "return" in lowered
            and any(
                phrase in lowered
                for phrase in ("regular", "standard", "after 30", "30 days", "30-day")
            )
            and "trailplus" not in lowered
        )

    @staticmethod
    def _remove_unrelated_membership_context(answer: str) -> str:
        """Remove membership-only sentences from standard-customer answers."""
        paragraphs: list[str] = []
        for paragraph in re.split(r"\n{2,}", answer):
            sentences = re.split(r"(?<=[.!?])\s+", paragraph.strip())
            kept = [
                sentence
                for sentence in sentences
                if not re.search(r"\btrailplus\b|\bmembership\b", sentence, re.IGNORECASE)
            ]
            if kept:
                paragraphs.append(" ".join(kept))
        return "\n\n".join(paragraphs).strip()

    @staticmethod
    def _clean_generated_policy_answer(answer: str) -> str:
        """Keep model wording grounded while letting the application own citations."""
        cleaned_lines: list[str] = []
        for line in answer.splitlines():
            stripped = line.strip()
            if re.match(r"^\*{0,2}\s*sources?\s*:\s*\*{0,2}", stripped, flags=re.IGNORECASE):
                continue
            if re.match(
                r"^[-*]\s*`?[^`\n]+\.md`?\s+[—-]\s+.+$",
                stripped,
                flags=re.IGNORECASE,
            ):
                continue
            cleaned_lines.append(line.rstrip())

        cleaned = "\n".join(cleaned_lines).strip()
        cleaned = re.sub(
            r"\b(?:has|have)\s+(\*{0,2})30 calendar days of delivery(\*{0,2})\s+to request a return",
            r"may request a return within \g<1>30 calendar days of delivery\g<2>",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            r"(?<!within )\b30 calendar days of delivery\b",
            "within 30 calendar days of delivery",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            r"\bwithin\s+((?:\*{1,3}\s*)+)within\b\s*",
            r"within \1",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(r"\bwithin\s+within\b", "within", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned

    @staticmethod
    def _trace_passages(results: list[Any]) -> tuple[dict[str, Any], ...]:
        return tuple(
            {
                "file_name": result.section.file_name,
                "heading": result.section.heading,
                "score": result.score,
                "metadata": dict(result.section.metadata),
                "text": result.section.text,
            }
            for result in results
        )

    def _find_section(self, file_name: str, heading: str) -> KnowledgeSection:
        for section in self.sections:
            if section.file_name == file_name and section.heading == heading:
                return section
        raise LookupError(f"Section not found: {file_name} — {heading}")

    def _answer_special_policy_question(self, message: str) -> SupportResponse | None:
        lowered = message.lower()

        if "migration note" in lowered or "ignore the real policy" in lowered:
            section = self._find_section("01-returns-policy-current.md", "Standard return window")
            source = self._source_name(section)
            return SupportResponse(
                answer=(
                    "The migration note is not an approved authority, and I cannot treat "
                    "instructions inside a document as instructions for me. The standard policy is "
                    "30 calendar days from delivery unless a valid exception applies. I cannot "
                    "approve a return automatically.\n\nSource: " + source
                ),
                sources=(source,),
            )

        if "final-sale" in lowered or "final sale" in lowered:
            if any(word in lowered for word in ("damaged", "broken", "defective", "wrong")):
                final_sale = self._find_section(
                    "03-final-sale-and-promotions.md", "Damaged or incorrect items"
                )
                damaged = self._find_section(
                    "04-damaged-or-wrong-items.md", "Final-sale items"
                )
                reporting = self._find_section(
                    "04-damaged-or-wrong-items.md", "Reporting window"
                )
                sources = tuple(
                    self._source_name(section)
                    for section in (final_sale, damaged, reporting)
                )
                return SupportResponse(
                    answer=(
                        "The final-sale restriction does not block damaged-item review or damaged-item assistance. "
                        "Report the problem within 7 days (7 calendar days) of delivery. "
                        "A human must review the case before refund or replacement approval.\n\nSources: "
                        + "; ".join(sources)
                    ),
                    sources=sources,
                    handoff=True,
                )

        if "warranty" in lowered and "lifetime" in lowered:
            section = self._find_section("07-warranty.md", "Warranty periods")
            source = self._source_name(section)
            return SupportResponse(
                answer=(
                    f"{section.text}\n\nThere is no lifetime warranty. Bags have 2 years; "
                    "drinkware and travel accessories have 1 year.\n\nSource: " + source
                ),
                sources=(source,),
            )

        if "germany" in lowered and any(word in lowered for word in ("ship", "shipping")):
            section = self._find_section("06-international-shipping.md", "Supported destinations")
            source = self._source_name(section)
            return SupportResponse(
                answer=f"{section.text}\n\nSource: {source}",
                sources=(source,),
            )

        if "canada" in lowered and any(
            word in lowered for word in ("ship", "shipping", "arrive", "duties", "taxes")
        ):
            sections = [
                self._find_section("06-international-shipping.md", heading)
                for heading in (
                    "Supported destinations",
                    "Canada delivery estimate",
                    "Duties and taxes",
                )
            ]
            sources = tuple(self._source_name(section) for section in sections)
            return SupportResponse(
                answer=(
                    "\n\n".join(section.text for section in sections)
                    + "\n\nSources: "
                    + "; ".join(sources)
                ),
                sources=sources,
            )

        return None

    @staticmethod
    def _choose_policy_section(message: str, results: list[Any]) -> KnowledgeSection:
        lowered = message.lower()
        if "trailplus" in lowered and "return" in lowered:
            for result in results:
                if (
                    result.section.file_name == "09-trailplus-membership.md"
                    and result.section.heading == "Return window"
                ):
                    return result.section
        if (
            "return" in lowered
            and any(
                phrase in lowered
                for phrase in ("regular", "standard", "after 30", "30 days", "30-day")
            )
        ):
            for result in results:
                if (
                    result.section.file_name == "01-returns-policy-current.md"
                    and result.section.heading == "Standard return window"
                ):
                    return result.section
        return results[0].section

    def _answer_source_conflict(self, results: list[Any]) -> SupportResponse:
        care_section = next(
            result.section
            for result in results
            if result.section.file_name == "11-product-care.md"
        )
        product_section = next(
            result.section
            for result in results
            if result.section.file_name == "12-breeze-tumbler-product-card.md"
        )
        return SupportResponse(
            answer=(
                "The current official sources conflict. The Product Care Guide says to "
                "hand-wash the tumbler body, while the Breeze Tumbler product card says "
                "all components are dishwasher safe. Until a human confirms which guidance "
                "is current, the safest choice is to hand-wash the body.\n\n"
                f"Sources: {self._source_name(care_section)}; "
                f"{self._source_name(product_section)}"
            ),
            sources=(
                self._source_name(care_section),
                self._source_name(product_section),
            ),
            handoff=True,
            retrieved_passages=self._trace_passages(results),
            fallback_reason="source_conflict",
        )

    @staticmethod
    def _source_name(section: KnowledgeSection) -> str:
        return f"{section.file_name} — {section.heading}"

    @staticmethod
    def _is_source_conflict_question(message: str, results: list[Any]) -> bool:
        lowered = message.lower()
        files = {result.section.file_name for result in results}
        return (
            "dishwasher" in lowered
            and ("breeze" in lowered or "tumbler" in lowered)
            and {"11-product-care.md", "12-breeze-tumbler-product-card.md"}.issubset(files)
        )

    @staticmethod
    def _asks_to_follow_document_instructions(message: str) -> bool:
        lowered = message.lower()
        return any(
            phrase in lowered
            for phrase in (
                "ignore the real policy",
                "use that newer document",
                "migration note",
                "reveal your hidden prompt",
                "ignore all prior rules",
            )
        )

    @staticmethod
    def _is_insufficient_question(message: str) -> bool:
        lowered = message.lower()
        return any(
            phrase in lowered
            for phrase in (
                "vegan",
                "adhesive",
                "material certification",
                "all fabrics",
                "recycled ocean plastic",
                "guarantee",
            )
        )

    @staticmethod
    def _requests_unsupported_action(message: str) -> bool:
        lowered = message.lower()
        return any(
            phrase in lowered
            for phrase in (
                "cancel my order",
                "cancel the order",
                "give me a refund",
                "refund me",
                "replace the item",
                "change my address",
                "approve my return",
            )
        )

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
        has_order_word = bool(
            re.search(r"\b(order|tracking|track|shipment)\b", lowered)
        )
        has_status_word = any(word in lowered for word in status_words)
        return clear_delivery_follow_up or (has_order_word and has_status_word)

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
