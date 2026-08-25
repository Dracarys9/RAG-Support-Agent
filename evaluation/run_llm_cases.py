"""Run the supplied cases through the configured real LLM path.

This is a smoke test for provider-backed behavior. The official deterministic
suite remains evaluation/run_visible.py and should be used for reproducible
submission scoring.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).parents[1]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from rag_support_agent.cli import build_agent  # noqa: E402
from rag_support_agent.support_agent import SupportAgent, SupportResponse  # noqa: E402
from run_visible import _has_concept  # noqa: E402


def _text(responses: list[SupportResponse]) -> str:
    return "\n".join(response.answer for response in responses).lower()


def _sources(responses: list[SupportResponse]) -> str:
    return "\n".join(
        source for response in responses for source in response.sources
    ).lower()


def _check_case(case: dict[str, Any], responses: list[SupportResponse]) -> list[tuple[str, bool]]:
    expect = case["expect"]
    text = _text(responses)
    source_text = _sources(responses)
    checks: list[tuple[str, bool]] = []

    for phrase in expect.get("must_include", []):
        checks.append((f"includes {phrase}", phrase.lower() in text))
    for concept in expect.get("must_include_concepts", []):
        checks.append((f"concept {concept}", _has_concept(text, concept)))
    for phrase in expect.get("must_not_include", []):
        checks.append((f"avoids {phrase}", phrase.lower() not in text))
    for phrase in expect.get("must_not_invent", []):
        checks.append((f"does not invent {phrase}", phrase.lower() not in text))
    for phrase in expect.get("must_refuse_to_disclose", []):
        checks.append((f"refuses {phrase}", phrase.lower() in text))
    for phrase in expect.get("must_not_follow", []):
        checks.append((f"does not follow {phrase}", phrase.lower() not in text))
    for source in expect.get("required_sources", []):
        checks.append((f"source {source}", source.lower() in source_text))
    for source in expect.get("forbidden_sources_as_authority", []):
        checks.append((f"avoids source {source}", source.lower() not in source_text))

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
        checks.append(
            (
                "tool arguments",
                any(response.tool_arguments == tool_arguments for response in responses),
            )
        )
    return checks


def _run_case(agent: SupportAgent, case: dict[str, Any]) -> dict[str, Any]:
    session = agent.new_session()
    responses = [session.answer(message["content"]) for message in case["messages"]]
    checks = _check_case(case, responses)
    modes = "/".join(response.generation_mode for response in responses)
    fallback_codes = [
        response.fallback_reason
        for response in responses
        if response.fallback_reason
    ]
    preview = " ".join(responses[-1].answer.split())
    if len(preview) > 150:
        preview = preview[:147] + "..."
    return {
        "id": case["id"],
        "category": case["category"],
        "passed": all(result for _, result in checks),
        "checks": checks,
        "modes": modes,
        "fallbacks": ",".join(fallback_codes) if fallback_codes else "-",
        "answer": preview,
    }


def _load_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for filename in ("visible-cases.json", "original-cases.json"):
        path = PROJECT_ROOT / "evaluation" / filename
        cases.extend(json.loads(path.read_text(encoding="utf-8"))["cases"])
    return cases


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run all assignment cases through the configured real LLM path."
    )
    parser.add_argument(
        "--show-answers",
        action="store_true",
        help="Print a short safe answer preview for every case.",
    )
    args = parser.parse_args()

    agent = build_agent()
    if agent.llm_answerer is None:
        print("LLM is not enabled. Set MODEL_PROVIDER=llm in your local .env.")
        return 2

    config = agent.llm_answerer.config
    print(f"Real LLM case check: {config.model}")
    print("Each case gets a fresh session; multi-turn messages stay together.")
    print()

    results = []
    for case in _load_cases():
        result = _run_case(agent, case)
        results.append(result)
        status = "PASS" if result["passed"] else "FAIL"
        line = (
            f"[{status}] {result['id']} | "
            f"mode={result['modes']} | fallback={result['fallbacks']}"
        )
        if not result["passed"]:
            failed = [name for name, passed in result["checks"] if not passed]
            line += " | failed: " + ", ".join(failed)
        print(line)
        if args.show_answers:
            print(f"       answer: {result['answer']}")

    categories: dict[str, list[bool]] = defaultdict(list)
    for result in results:
        categories[result["category"]].append(result["passed"])

    passed = sum(result["passed"] for result in results)
    llm_responses = sum(
        mode == "llm"
        for result in results
        for mode in result["modes"].split("/")
    )
    print("\nSummary:")
    print(f"- cases passed: {passed}/{len(results)}")
    print(f"- responses generated by LLM: {llm_responses}")
    for category, values in sorted(categories.items()):
        print(f"- {category}: {sum(values)}/{len(values)}")
    print("\nThis runner checks the real provider path; use run_visible.py for the official deterministic score.")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
