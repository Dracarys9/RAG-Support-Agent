# Assignment Requirements Audit

This audit compares the original assignment brief preserved at `docs/assignment-brief.md` with the current application files, tests, evaluator, and README. It was prepared before creating the demo GIF/video.

## Status legend

| Status | Meaning |
| --- | --- |
| Complete | The requirement is implemented and has direct file or test evidence. |
| Partial | The main behavior exists, but one part of the requirement still needs improvement or is a deliberate limitation. |
| Missing | The requirement is not yet present and must be completed before final submission. |

## Customer problems and required capabilities

| Requirement | Status | Where it is filled | Evidence or remaining gap |
| --- | --- | --- | --- |
| Use RAG over `knowledge-base/` | Complete with offline fallback | `src/rag_support_agent/knowledge_base.py`, `src/rag_support_agent/llm.py`, `src/rag_support_agent/support_agent.py` | The project loads, filters, splits, and ranks passages, then optionally sends only selected passages to an OpenAI-compatible model. Local deterministic answers remain available when LLM mode is disabled or unavailable. |
| Split and index documents | Complete | `knowledge_base.py: parse_markdown_file`, `load_knowledge_base` | Heading-based sections are created for all 14 Markdown files. `tests/test_knowledge_base.py` checks file count and sections. |
| Preserve front-matter metadata | Complete | `knowledge_base.py: parse_front_matter`, `KnowledgeSection.metadata` | Metadata such as status, audience, and policy authority is kept. Tests check active and official metadata. |
| Retrieve relevant passages, not the whole corpus | Complete | `knowledge_base.py: search_knowledge_base`, `support_agent.py: _answer_from_knowledge`, `llm.py: OpenAIAnswerer` | Search returns a limited number of sections and LLM mode receives only those selected passage blocks. |
| Prefer active official policy documents | Complete | `support_agent.py: customer_sections` filter and `_choose_policy_section` | Only active, official, customer-facing sections are used for normal policy answers. The current returns policy is selected instead of legacy or migration content. |
| Cite filename and heading | Complete | `SupportResponse.sources`, `SupportAgent._source_name` | Answers show values such as `01-returns-policy-current.md — Standard return window`. Visible cases check required sources. |
| Avoid unsupported claims | Complete for supplied cases | `support_agent.py` special policy rules and abstention rule | The 15/15 visible evaluation result passes groundedness and abstention cases. Unusual paraphrases remain a known limitation because retrieval is word-based. |
| Say when information is insufficient | Complete | `SupportAgent._is_insufficient_question`, no-results branch | The vegan-materials case abstains and recommends human confirmation. `tests/test_safety_rules.py` covers it. |
| Surface genuine active-source conflicts | Complete for supplied conflict | `SupportAgent._is_source_conflict_question`, `_answer_source_conflict` | The Breeze Tumbler case shows both official sources, safest interim guidance, and handoff. The visible conflict case passes. |
| Do not rewrite supplied source files | Complete | `knowledge-base/` and `data/` remain supplied source files | The application creates behavior around the files; it does not replace the knowledge-base or order data. |

## Order lookup requirements

| Requirement | Status | Where it is filled | Evidence or remaining gap |
| --- | --- | --- | --- |
| Use `data/orders.json` | Complete | `src/rag_support_agent/orders.py: load_orders`, `lookup_order` | The lookup reads the supplied JSON snapshot. |
| Do not send the entire orders file to the answer layer | Complete | `orders.py: _safe_order`, `support_agent.py: _answer_order`, `llm.py: OpenAIAnswerer` | Only the sanitized lookup result is passed to the optional model. The full JSON file is never placed in the model prompt. |
| Ask for missing order ID | Complete | `SupportAgent._is_order_status_question`, `answer` | `missing-order-id` passes and `tests/test_support_agent.py` covers it. |
| Handle malformed and unknown IDs safely | Complete | `normalize_order_id`, `lookup_order` | Invalid and unknown IDs return safe messages without invented status data. |
| Normalize harmless input differences | Complete | `normalize_order_id` | Lowercase IDs, spaces, and ordinary punctuation are handled. Tests cover lowercase and spaces. |
| Treat current status as authoritative | Complete | `SupportAgent._answer_order`, `orders.py` | The response starts with the current status. Cancelled and returned statuses suppress stale delivery fields. |
| Do not invent delivery estimates | Complete | `orders.py` safe projection and `SupportAgent._answer_order` | Missing ETA stays unavailable. The shipped-without-ETA visible case passes. |
| Do not report stale cancelled/returned fields | Complete | `STALE_DELIVERY_FIELDS` and `_safe_order` | Cancelled and returned orders remove carrier, tracking, and ETA fields. Visible cancelled-order case passes. |
| Never expose private fields | Complete | `SAFE_FIELDS`, `_safe_items`, privacy refusal | Email, address, internal data, risk score, and notes are excluded. Privacy tests and visible case pass. |
| Never claim a lookup happened when it did not | Complete | Missing-ID path does not call lookup; unknown path reports not found | Visible missing-ID and unknown-order cases pass. |

## Conversation and behavior requirements

| Requirement | Status | Where it is filled | Evidence or remaining gap |
| --- | --- | --- | --- |
| Keep relevant context across turns | Complete | `SupportSession`, `last_topic`, `last_order_id` | Canada and order follow-up tests pass. |
| Handle Canada follow-up | Complete | `SupportSession` plus Canada special answer | Visible multi-turn case passes. |
| Handle order delivery follow-up | Complete | `SupportSession.last_order_id`, `_looks_like_order_follow_up` | Visible multi-turn order behavior and session tests pass. |
| Handle narrower exception follow-up | Partial | Session topic is retained and combined with follow-up text | Basic context exists, but more exception-specific paraphrase tests should be added to the original-case suite. |
| Isolate separate sessions | Complete | Each call to `new_session()` creates separate state | `tests/test_sessions.py` proves order IDs are not shared. |
| Treat retrieved text and tool results as untrusted | Complete for supplied injection case | Document filtering, explicit migration-note handling, safe order projection | Prompt-injection visible case passes. General arbitrary injection patterns remain a limitation. |
| Refuse system prompts, secrets, and internal data | Complete for supplied cases | `_asks_for_private_information` and safe refusal | Privacy and prompt-security visible cases pass. |
| Use company content over general knowledge | Complete for supported questions | Answers come from selected company sections, safe order data, or the grounded LLM prompt | The optional model receives only company passages/tool results; unsupported questions abstain. |
| Clarify missing required information | Complete | Missing order ID response | Visible case passes. |
| Recommend human help when needed | Complete for supplied cases | `SupportResponse.handoff`, conflict, insufficiency, unknown order, privacy, and unsupported action rules | Visible cases pass handoff checks. |
| Do not promise unsupported actions | Complete | `_requests_unsupported_action` and early action check | Cancellation test and visible behavior pass. |

## Evaluation-suite requirements

| Requirement | Status | Where it is filled | Evidence or remaining gap |
| --- | --- | --- | --- |
| Cover every supplied visible case | Complete | `evaluation/visible-cases.json`, `evaluation/run_visible.py` | The evaluator runs all 15 visible cases and reports each case. Current result: 15/15. |
| Add at least five original cases | Complete | `evaluation/original-cases.json`, `evaluation/run_visible.py` | Five original cases run with the visible cases. Current original result: 5/5. |
| One clearly documented evaluation command | Complete | `README.md`, `evaluation/run_visible.py` | Command is documented and works from PowerShell. |
| Report individual case results | Complete | `run_visible.py` | Each case prints `[PASS]` or `[FAIL]`. |
| Report useful categories separately | Complete | `run_visible.py` category totals | Categories include retrieval, groundedness, privacy, conversation, source conflict, tool use, and more. |
| Use deterministic assertions | Complete for visible cases | `run_visible.py` checks phrases, sources, tools, arguments, handoffs, and forbidden content | No LLM grader is required. |
| Do not rely exclusively on another LLM | Complete | Entire evaluator is deterministic | No model call is used. |
| Include baseline and final results | Complete in README | `README.md` current result and baseline sections | README records 8/15 baseline and 15/15 final. |
| Bug diary with at least three failures | Complete | `README.md: Bug diary` | Five failures include reproduction, cause, fix, and regression test. At least one, the `ordered` bug, was beyond an exact visible prompt. |

## Observability and interface

| Requirement | Status | Where it is filled | Evidence or remaining gap |
| --- | --- | --- | --- |
| Current user message in trace | Complete | `DebugTrace.message` | `--debug` prints JSON trace. |
| Relevant conversation history | Complete | `DebugTrace.history` | Debug regression test covers previous messages. |
| Retrieved passages, metadata, and scores | Complete | `SupportResponse.retrieved_passages`, `DebugTrace.retrieved_passages`, `llm.py` | Debug JSON includes passage text, filename, heading, metadata, and score; the same selected passage blocks are the only knowledge context sent to the model. |
| Tool calls and sanitized tool results | Complete | `SupportResponse.sanitized_tool_result`, `DebugTrace.sanitized_tool_result`, `llm.py` | Debug JSON includes safe tool output without private fields, and the optional model receives only that safe projection. |
| Final response | Complete | `DebugTrace.final_answer` | Included in JSON trace. |
| Errors, fallbacks, and handoffs | Complete | `SupportResponse.fallback_reason`, `DebugTrace.fallback_reason`, `handoff` | Missing IDs, privacy, insufficiency, unsupported actions, conflicts, and lookup errors have explicit reasons where applicable. |
| Simple interface | Complete | `src/rag_support_agent/cli.py` | Terminal chat displays answer, sources, and human-help status. |

## README requirements

| Requirement | Status | Where it is filled | Evidence or remaining gap |
| --- | --- | --- | --- |
| Clean-clone setup/run instructions | Complete | `README.md: Setup on Windows PowerShell` | Commands are documented and were tested locally. |
| Environment variables and `.env.example` | Complete | `.env.example`, `.gitignore`, `README.md` | No real credentials are included. |
| Model, embeddings, framework, storage choices | Complete | `README.md: Technology choices`, `src/rag_support_agent/llm.py` | States optional OpenAI-compatible `gpt-5-mini`, no embeddings, plain Python, file-based storage, and deterministic local fallback. |
| Architecture explanation | Complete | `README.md: How it works` | Three-layer explanation is present. |
| Evaluation command | Complete | `README.md` and `evaluation/run_visible.py` | Documented PowerShell command works. |
| Baseline/final results by category | Complete | `README.md: Current result` and `Evaluation` | Overall baseline/final plus category table are present. |
| Bug diary | Complete | `README.md: Bug diary` | Five entries are documented. |
| Limitations and production improvements | Complete | `README.md: Known limitations` | Limitations and production improvements are listed. |
| AI coding tools and wrong suggestion | Complete | `README.md: AI coding tools used` | Tool use and the `ordered` false-match example are documented. |
| 2–4 minute GIF/video embedded | **Missing** | `README.md` currently says the demo will be added | `docs/demo.gif` or a clickable video link does not exist yet. This is the main remaining submission artifact. |

## Final audit conclusion

The core support agent is working strongly against the supplied cases: **38 regular tests pass, 15/15 visible cases pass, and 5/5 original cases pass**. The project now has an optional real LLM-backed RAG path: retrieval selects a small set of safe passages, the model writes from that context, and the deterministic path remains available offline. The debug trace includes retrieved text, metadata, scores, sanitized tool results, generation mode, and fallback reasons.

The only remaining assignment item is the required **2–4 minute demo GIF/video** embedded or linked from the README. After the demo is added, run a final clean-clone check and a secret-file check before submission.