# Aster & Row RAG Support Agent

A small, safety-focused support agent for Aster & Row, a fictional ecommerce company that sells bags, drinkware, and travel accessories. The agent answers policy questions from the supplied knowledge base and checks mock order status data without exposing private order fields.

## Current result

The project currently passes all supplied visible evaluation cases.

| Check | Result |
| --- | --- |
| Regular automated tests | **33 passed** |
| Supplied visible cases | **15/15 passed** |
| Original cases | **5/5 passed** |
| Combined evaluation command | `python evaluation/run_visible.py` |

The original baseline before the policy and order-answer improvements was **8/15 visible cases**. The final result is **15/15 visible cases and 5/5 original cases**, for **20/20 total cases**.

## Setup on Windows PowerShell

Open PowerShell in the project folder:

```
cd C:\path\to\RAG-Support-Agent
```

Create and use a local Python environment:

```
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

Run the tests:

```
.\.venv\Scripts\python.exe -m pytest -q
```

Run the visible evaluation:

```
.\.venv\Scripts\python.exe evaluation\run_visible.py
```

Start the terminal chat:

```
.\.venv\Scripts\python.exe -m rag_support_agent.cli
```

Type `quit` to stop the chat. To see a safe debug trace, run:

```
.\.venv\Scripts\python.exe -m rag_support_agent.cli --debug
```

No API key is required for the current version. `.env.example` is included for future configuration, and real credentials must never be committed.

## How it works

The program uses three simple layers:

| Layer | What it does |
| --- | --- |
| Knowledge reader and search | Reads Markdown front matter, splits documents by heading, keeps source metadata, and ranks matching sections. |
| Safe order lookup | Reads `data/orders.json`, normalizes order IDs, returns only customer-safe fields, and applies status/ETA rules. |
| Support agent | Decides whether a message is a policy question, an order question, a follow-up, a privacy request, an unsupported action, or a case requiring human help. |

The knowledge base is filtered to active, official, customer-facing documents before customer answers are produced. Legacy, draft, and internal documents are not treated as customer authority. Genuine conflicts between the two active official Breeze Tumbler sources are shown to the customer instead of being silently hidden.

## Technology choices

The implementation intentionally uses a small local Python program rather than a large framework.

| Choice | Current implementation | Reason |
| --- | --- | --- |
| Language | Python 3.11 or newer | Simple setup and clear tests. |
| Framework | Plain Python modules | The assignment does not require a web framework. |
| Retrieval | Case-insensitive word matching with a few simple word connections | Easy to inspect and deterministic for this small corpus. |
| Embeddings | None in the current version | This avoids an external service and keeps evaluation repeatable. A production version could add embeddings after the safety and precedence rules are preserved. |
| Model | None in the current version | The deterministic program makes the key safety behaviors testable without relying on another model to grade it. |
| Storage | Supplied Markdown and JSON files; sections are loaded in memory | No production database or vector store is needed for this assignment. |
| Interface | Terminal chat | Small, easy to demonstrate, and sufficient for the assignment. |

## Safety behavior

The agent does not expose customer email addresses, shipping addresses, internal notes, risk scores, or support tags. It treats document text and order data as information rather than instructions. It does not follow the prompt-injection text in the migration scratchpad. It does not promise that a refund, cancellation, replacement, address change, or approval has been completed.

Debug mode records the current message, previous conversation messages, retrieved passage text, front-matter metadata, retrieval scores, safe tool arguments, a sanitized tool result, the final answer, handoff status, and a fallback reason. It never includes private order fields.

The agent asks for an order ID when one is missing, handles unknown IDs safely, uses the order status as authoritative, removes stale delivery fields for cancelled and returned orders, and does not invent an ETA when one is unavailable. It recommends human help for conflicts, insufficient information, unknown orders, privacy requests, unsupported actions, and operational exceptions.

## Evaluation

Run the supplied visible cases with:

```
.\.venv\Scripts\python.exe evaluation\run_visible.py
```

The evaluator prints every visible and original case separately, then prints suite totals and category totals. It uses deterministic checks for answer terms, forbidden content, source files, handoff decisions, tool names, and tool arguments. It does not use another AI model to grade the results.

The current final categories are:

| Category | Result |
| --- | --- |
| Abstention | 1/1 |
| Conversation | 1/1 |
| Groundedness | 2/2 |
| Multi-source grounding | 1/1 |
| Privacy | 1/1 |
| Prompt security | 1/1 |
| Retrieval | 2/2 |
| Source conflict | 1/1 |
| Tool reliability | 3/3 |
| Tool use | 2/2 |
| Unsupported action | 1/1 |

The original suite contains five additional cases: normalized order IDs, returned-order stale data, unsupported refunds, unsupported material claims, and a conflict paraphrase.

## Bug diary

### Bug 1 — “ordered” was mistaken for an order-status question

**Reproduction:** Ask, “My TrailPlus membership was active when I ordered. What is my return window?”

**Root cause:** The first version looked for the text `order` as a substring. The word `ordered` therefore looked like an order-status request, and the agent asked for an order ID.

**Fix:** Order words are now checked as complete words, while an actual order ID still routes directly to the order lookup.

**Regression test:** `tests/test_support_agent.py::test_trailplus_return_question_uses_return_window_section`.

### Bug 2 — Canada shipping selected a general domestic result

**Reproduction:** Ask, “Do you ship to Canada?”

**Root cause:** The simple search gave too much weight to the general word `shipping`, so the domestic shipping document could outrank the Canada-specific destination section.

**Fix:** Exact customer words such as `Canada` now matter more than general expanded words, and the Canada question selects the international destination, estimate, and duties sections.

**Regression tests:** `tests/test_knowledge_base.py::test_search_finds_canada_shipping_policy` and the visible `canada-multiturn` case.

### Bug 3 — An unsupported action performed an order lookup

**Reproduction:** Ask, “Please cancel my order ORD-1007.”

**Root cause:** The order ID was detected before the program checked whether cancellation was supported, so the program returned status information instead of explaining that cancellation was not implemented.

**Fix:** Unsupported actions are checked before order lookup. The program now explains the limitation and recommends human help without claiming that a cancellation happened.

**Regression test:** `tests/test_safety_rules.py::test_unsupported_action_is_not_claimed_complete`.

### Bug 4 — Unsupported material questions received unrelated answers

**Reproduction:** Ask, “Are all fabrics and adhesives in your bags vegan?”

**Root cause:** Word search found an unrelated product-care section containing words about materials, even though the knowledge base did not answer the vegan-certification question.

**Fix:** Known unsupported material-certification questions now abstain clearly and recommend human confirmation.

**Regression test:** `tests/test_safety_rules.py::test_insufficient_material_question_does_not_guess`.

### Bug 5 — Debug history was missing previous messages

**Reproduction:** Start a session, ask about international shipping, then request a debug trace for “What about Canada?”

**Root cause:** The trace was created after calling the agent directly, but the current message was not added to the session history in that path. The trace code also removed one message too many.

**Fix:** The trace now records the messages that existed before the current answer and keeps the current answer separately.

**Regression test:** `tests/test_debug.py::test_debug_trace_contains_previous_messages_only`.

## Known limitations

This is an assignment-sized local system, not a production deployment. Retrieval uses word matching rather than semantic embeddings, so unusual paraphrases may retrieve less useful sections. The special handling for the supplied policy conflicts is deliberate and should be replaced by a more general claim-comparison step for a larger corpus. The terminal interface has no authentication, and the mock assignment explicitly treats possession of an order ID as sufficient authentication. The system supports lookup only; it does not actually cancel orders, issue refunds, create replacements, change addresses, or create support tickets. Sessions exist only while the process is running.

Before production, I would add authenticated APIs, a durable session store, semantic retrieval with metadata filters, a stronger claim/conflict detector, structured secret-safe logs, rate limits, human handoff integration, monitoring, and a larger paraphrase evaluation set.

## AI coding tools used

The implementation was developed collaboratively using **Manus AI** for code planning, implementation suggestions, test writing, debugging, and documentation drafting. **Visual Studio Code**, PowerShell, Git, and GitHub were used for local review, testing, commits, and pushes.

One AI-generated suggestion was incomplete: an early order-question check used simple substring matching, which treated `ordered` as if it meant `order`. This caused a valid TrailPlus policy question to ask for an order ID. The check was changed to recognize complete words and a regression test was added.

## Demo

A short demo recording will be added to `docs/demo.gif` or as a clickable video link before final submission. It will show a cited policy answer, an order lookup, a multi-turn follow-up, a safe refusal or human handoff, and the evaluation command running.

## Repository contents

```
.
├── data/
├── docs/
├── evaluation/
├── knowledge-base/
├── src/rag_support_agent/
├── tests/
├── .env.example
├── .gitignore
├── pyproject.toml
└── requirements-dev.txt
```

The original assignment brief is preserved at `docs/assignment-brief.md`.