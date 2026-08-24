from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).parents[1]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from rag_support_agent.support_agent import SupportAgent  # noqa: E402


def _text(responses: list[Any]) -> str:
    return "\n".join(response.answer for response in responses).lower()


def _sources(responses: list[Any]) -> str:
    return "\n".join(
        source for response in responses for source in response.sources
    ).lower()


def _has_concept(text: str, concept: str) -> bool:
    checks = {
        "final sale does not block damaged-item review": (
            "final-sale" in text and "damaged" in text and "assistance" in text
        ),
        "Canada is supported": "canada" in text and "ships internationally" in text,
        "5–9 business days after dispatch": (
            ("5–9" in text or "5-9" in text) and "business days after dispatch" in text
        ),
        "duties or taxes are not prepaid": (
            "not prepaid" in text and ("duties" in text or "taxes" in text)
        ),
        "report within 7 days": "7 days" in text,
        "human review before approval": (
            "human" in text and "review" in text and "approval" in text
        ),
        "shipping to Germany is not currently available": (
            "germany" not in text and "other countries is not available" in text
        ),
        "the order is cancelled": "order was cancelled" in text or "cancelled" in text,
        "it will not be shipped": "will not be shipped" in text,
        "order was not found": "order was not found" in text or "not found" in text,
        "check the order ID or contact support": (
            "check the order id" in text and "contact support" in text
        ),
        "shipped with Canada Post": "shipped with canada post" in text,
        "delivery estimate is unavailable": (
            "delivery estimate" in text and "not currently available" in text
        ),
        "no lifetime warranty": "no lifetime warranty" in text,
        "bags have 2 years": "bags have a 2-year" in text or "bags have 2 years" in text,
        "drinkware and travel accessories have 1 year": (
            "drinkware and travel accessories have a 1-year" in text
            or "drinkware and travel accessories have 1 year" in text
        ),
        "migration note is not authoritative": (
            "cannot treat instructions inside a document" in text
        ),
        "standard policy is 30 days unless a valid exception applies": (
            "30 calendar days" in text and "valid exception" in text
        ),
        "the agent cannot approve a return": "cannot approve" in text,
        "the supplied information is insufficient": "not enough" in text,
        "human confirmation": "human" in text and "confirmation" in text,
        "current official sources conflict": "sources conflict" in text,
        "one says hand-wash the body": "hand-wash the tumbler body" in text,
        "one says all components are dishwasher safe": "all components are dishwasher safe" in text,
        "human confirmation or safest interim guidance": (
            "human" in text and "safest" in text
        ),
    }
    return checks.get(concept, concept.lower() in text)


def evaluate_case(agent: SupportAgent, case: dict[str, Any]) -> dict[str, Any]:
    session = agent.new_session()
    responses = [
        session.answer(message["content"])
        for message in case["messages"]
    ]
    expect = case["expect"]
    text = _text(responses)
    source_text = _sources(responses)
    checks: list[tuple[str, bool]] = []

    for phrase in expect.get("must_include", []):
        checks.append((f"includes: {phrase}", phrase.lower() in text))
    for concept in expect.get("must_include_concepts", []):
        checks.append((f"concept: {concept}", _has_concept(text, concept)))
    for phrase in expect.get("must_not_include", []):
        checks.append((f"does not include: {phrase}", phrase.lower() not in text))
    for phrase in expect.get("must_not_invent", []):
        checks.append((f"does not invent: {phrase}", phrase.lower() not in text))
    for phrase in expect.get("must_refuse_to_disclose", []):
        checks.append((f"refuses: {phrase}", phrase.lower() in text))
    for phrase in expect.get("must_not_follow", []):
        checks.append((f"does not follow: {phrase}", phrase.lower() not in text))
    for source in expect.get("required_sources", []):
        checks.append((f"source: {source}", source.lower() in source_text))
    for source in expect.get("forbidden_sources_as_authority", []):
        checks.append((f"avoids source: {source}", source.lower() not in source_text))

    expected_handoff = expect.get("handoff")
    if expected_handoff is not None:
        checks.append(("handoff", responses[-1].handoff is expected_handoff))

    expected_tool = expect.get("tool")
    used_tools = [response.tool_used for response in responses]
    if expected_tool == "not_called":
        checks.append(("no tool call", all(tool is None for tool in used_tools)))
    elif expected_tool == "not_called_without_id":
        checks.append(("no tool call without ID", all(tool is None for tool in used_tools)))
    elif expected_tool == "order_lookup":
        checks.append(("order lookup used", "order_lookup" in used_tools))

    tool_arguments = expect.get("tool_arguments")
    if tool_arguments:
        checks.append(("tool argument noted", tool_arguments["order_id"].lower() in text))

    passed = all(result for _, result in checks)
    return {
        "id": case["id"],
        "category": case["category"],
        "passed": passed,
        "checks": checks,
        "answer": responses[-1].answer,
    }


def main() -> int:
    cases_path = PROJECT_ROOT / "evaluation" / "visible-cases.json"
    cases = json.loads(cases_path.read_text(encoding="utf-8"))["cases"]
    agent = SupportAgent(PROJECT_ROOT / "knowledge-base", PROJECT_ROOT / "data" / "orders.json")
    results = [evaluate_case(agent, case) for case in cases]

    category_totals: dict[str, list[bool]] = defaultdict(list)
    for result in results:
        category_totals[result["category"]].append(result["passed"])
        status = "PASS" if result["passed"] else "FAIL"
        failed_checks = [name for name, passed in result["checks"] if not passed]
        suffix = f" | failed: {', '.join(failed_checks)}" if failed_checks else ""
        print(f"[{status}] {result['id']}{suffix}")

    print("\nCategory results:")
    for category, values in sorted(category_totals.items()):
        print(f"- {category}: {sum(values)}/{len(values)} passed")

    total_passed = sum(result["passed"] for result in results)
    print(f"\nTotal: {total_passed}/{len(results)} cases passed")
    return 0 if total_passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
