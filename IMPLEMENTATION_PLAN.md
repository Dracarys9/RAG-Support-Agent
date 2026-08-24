# RAG Support Agent — Implementation Plan

## Objective

Build the smallest reliable AI support agent for Aster & Row that uses retrieval-augmented generation over the supplied knowledge base, performs safe order lookups, preserves relevant multi-turn context, resists instructions embedded in retrieved content, and demonstrates its behavior through deterministic evaluations and a short README-embedded demo.

The implementation will be performed incrementally. Before each milestone, I will explain the goal, files affected, design trade-offs, test strategy, and proposed commit message. No milestone will be started until it is approved.

## Requirements-to-task checklist

| ID | Requirement | Planned implementation | Acceptance evidence |
|---|---|---|---|
| R1 | RAG over `knowledge-base/` | Load Markdown files, parse front matter, split by headings into searchable chunks, and build a local derived index. | Retrieval tests return relevant chunks and retain filename, heading, and metadata. |
| R2 | Preserve useful metadata | Retain `document_id`, `title`, `status`, `effective_date`, `last_reviewed`, `audience`, `policy_authority`, `customer_answering`, and related fields when present. | Metadata appears in retrieval traces and source citations. |
| R3 | Relevant retrieval only | Send retrieved passages rather than the entire corpus to the answering layer. | Trace shows selected chunks; tests prevent full-corpus prompt inclusion. |
| R4 | Document precedence | Prefer active, official, customer-facing documents; exclude draft, non-authoritative, internal-only content from customer authority. | Standard return question selects current policy, not legacy or migration notes. |
| R5 | Source references | Include at least filename and relevant heading for each policy/product answer. | Deterministic source assertions cover visible cases. |
| R6 | Groundedness and abstention | Answer only from retrieved evidence, explicitly state insufficiency, and recommend human assistance when needed. | Vegan-material case abstains; unsupported country case does not guess. |
| R7 | Genuine conflict handling | Detect conflicting claims among active authoritative sources and surface both sources instead of silently selecting one. | Breeze Tumbler dishwasher case identifies the conflict and recommends safest interim guidance or human confirmation. |
| R8 | Order lookup tool/function | Implement a lookup over `data/orders.json` that returns only the minimum customer-safe fields needed for the question. | Tool-call tests verify lookup arguments and sanitized results. |
| R9 | Order ID handling | Ask for an ID when missing; safely reject malformed/unknown IDs; normalize case, whitespace, and ordinary punctuation without guessing a different ID. | Missing, malformed, normalized, and unknown-ID tests pass. |
| R10 | Order data precedence | Treat `status` as authoritative; suppress stale ETA/tracking claims for cancelled or returned orders; never invent ETA when absent. | Cancelled-order and shipped-without-ETA cases pass. |
| R11 | Privacy | Never place or expose customer email/address, internal notes, risk scores, support tags, or other internal-only fields. | Privacy tests scan tool output, prompt context, logs, and final responses. |
| R12 | Unsupported actions | Do not claim cancellation, refund, replacement, address change, price adjustment, or escalation completion because the dataset supports lookup only. | Action-request tests require a clear limitation and appropriate handoff. |
| R13 | Multi-turn context | Maintain relevant session context for follow-ups while preventing unrelated details from leaking across sessions. | Canada shipping, order follow-up, exception follow-up, and cross-session isolation tests pass. |
| R14 | Prompt and data safety | Treat user messages, retrieved passages, and tool results as untrusted data; application rules always take precedence. Refuse prompt, secret, and internal-data disclosure requests. | Migration-note prompt-injection and privacy cases pass without following embedded instructions. |
| R15 | Evaluation suite | Run every visible case plus at least five original cases; report individual results and separate categories. | One documented command prints per-case and category results. |
| R16 | Deterministic evaluation | Use assertions for source selection, tool calls/arguments, privacy, forbidden content, abstention, and handoff behavior wherever practical. | Evaluation output distinguishes deterministic pass/fail reasons. |
| R17 | Observability | Provide debug output for the current message, relevant history, retrieved chunks/metadata/scores, tool calls and sanitized results, final response, and fallbacks/errors. | Debug trace is inspectable and contains no secrets or forbidden order fields. |
| R18 | Minimal interface | Provide a simple CLI or basic API that visibly shows the answer, sources, and handoff recommendation. | Clean-clone run instructions demonstrate interactive use. |
| R19 | Repository documentation | Add setup, run, environment variables, `.env.example`, architecture, model/embedding/framework/storage choices, evaluation command, results, limitations, bug diary, and AI coding tool disclosure. | README checklist is reviewed line by line before final submission. |
| R20 | Demo artifact | Embed a 2–4 minute GIF or clickable video thumbnail/link showing citations, order lookup, multi-turn context, abstention/handoff, and evaluation execution. | README renders the demo link or GIF from the repository. |
| R21 | Submission hygiene | Do not commit API keys, credentials, customer data beyond the supplied mock assignment data, or unrelated documents/slides. | Secret scan and Git diff review pass before submission. |

## Execution milestones and proposed commits

| Milestone | Work | Planned commit |
|---|---|---|
| 0 | Clone/synchronize the public GitHub repository, preserve the supplied assignment content, establish a clean baseline, and record the initial test/run status. | `chore: bootstrap agent workspace and baseline checks` |
| 1 | Add the minimal project skeleton, dependency lock/setup files, `.env.example`, and a test runner without committing secrets. | `chore: add reproducible Python project setup` |
| 2 | Implement Markdown front-matter parsing, heading-aware chunking, and a local derived document index. | `feat: index knowledge base with source metadata` |
| 3 | Implement retrieval scoring, authority/status precedence, source citations, insufficiency handling, and active-source conflict detection. | `feat: add grounded precedence-aware retrieval` |
| 4 | Implement the sanitized order lookup function with normalization, safe field projection, status precedence, and deterministic time handling. | `feat: add privacy-safe order lookup tool` |
| 5 | Implement session state and the agent orchestration layer, including context resolution, tool-use decisions, safe instructions, refusal behavior, and handoff decisions. | `feat: orchestrate grounded multi-turn support agent` |
| 6 | Add a minimal CLI or basic API and structured debug traces with secret-safe logging. | `feat: add support CLI and structured observability` |
| 7 | Add visible-case coverage and at least five original cases, including regression tests for discovered failures. | `test: add behavior evaluation and regression suite` |
| 8 | Run an intentionally limited baseline, record failures, fix at least three bugs, and document reproduction, root cause, fix, and regression test in the README. | `docs: record baseline results and bug diary` |
| 9 | Add setup/run documentation, architecture and trade-offs, model/embedding/storage choices, evaluation results by category, limitations, AI coding tool disclosure, and demo instructions. | `docs: complete interview submission README` |
| 10 | Record the demo GIF/video, perform clean-clone validation, inspect Git history, scan for secrets, and verify every requirement. | `chore: finalize evaluation and submission artifacts` |

## Collaboration protocol

For every milestone, the explanation will include: what is being changed; why it satisfies specific README requirements; which files will change; what could go wrong; the exact command(s) used to verify it; and the proposed commit message. After the explanation, implementation will wait for explicit approval to proceed.

## Final acceptance checklist

Before considering the assignment complete, the following must all be true:

1. A clean clone can install dependencies and run the agent using documented commands.
2. All visible cases run in one command and report individual results plus category summaries.
3. At least five original cases are included and tested.
4. Retrieval traces show metadata, source headings, scores, and precedence decisions without sending the entire corpus to the model.
5. Order traces show only sanitized customer-safe fields and never expose internal data.
6. Multi-turn follow-ups resolve correctly, while separate sessions remain isolated.
7. Prompt-injection, unsupported-action, insufficiency, unknown-order, stale-ETA, and source-conflict behaviors are covered.
8. The README contains baseline/final results, three detailed bug-diary entries, limitations, AI-tool disclosure, and the required demo.
9. No credentials or unrelated sensitive files are committed.
10. Git history is organized into small, explainable commits suitable for interview review.
