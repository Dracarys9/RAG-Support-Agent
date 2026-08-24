from __future__ import annotations

from dataclasses import dataclass
import re
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class KnowledgeSection:
    """A searchable piece of a knowledge-base Markdown file."""

    file_name: str
    heading: str
    text: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class SearchResult:
    """A knowledge-base section and its simple matching score."""

    section: KnowledgeSection
    score: int


_QUERY_EXPANSIONS = {
    "long": {"window", "days", "delivery", "estimate"},
    "ship": {"shipping", "ships", "shipped", "destination"},
    "arrive": {"arrival", "delivery", "estimate"},
    "return": {"returns"},
}


_STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "can",
    "do",
    "does",
    "for",
    "how",
    "i",
    "is",
    "my",
    "of",
    "on",
    "the",
    "to",
    "what",
    "when",
    "where",
    "will",
    "with",
}



def _tokens(text: str) -> set[str]:
    """Return simple, case-insensitive search words."""
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {word for word in words if len(word) > 1 and word not in _STOP_WORDS}



def _parse_value(value: str) -> Any:
    """Convert the simple values used in the supplied front matter."""
    value = value.strip()

    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    if value.lower() in {"null", "none"}:
        return None
    return value.strip('"\'')



def parse_front_matter(lines: list[str]) -> tuple[dict[str, Any], int]:
    """Return front-matter values and the line where the document body starts."""
    if not lines or lines[0].strip() != "---":
        return {}, 0

    metadata: dict[str, Any] = {}
    for index in range(1, len(lines)):
        line = lines[index].strip()
        if line == "---":
            return metadata, index + 1
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = _parse_value(value)

    raise ValueError("Knowledge-base front matter was not closed with '---'.")



def parse_markdown_file(path: Path) -> list[KnowledgeSection]:
    """Parse one Markdown file into sections while preserving source metadata."""
    lines = path.read_text(encoding="utf-8").splitlines()
    metadata, body_start = parse_front_matter(lines)
    body = lines[body_start:]

    sections: list[KnowledgeSection] = []
    current_heading = str(metadata.get("title", path.stem))
    current_lines: list[str] = []

    def save_section() -> None:
        text = "\n".join(current_lines).strip()
        if text:
            sections.append(
                KnowledgeSection(
                    file_name=path.name,
                    heading=current_heading,
                    text=text,
                    metadata=dict(metadata),
                )
            )

    for line in body:
        if line.startswith("#"):
            save_section()
            current_heading = line.lstrip("#").strip() or current_heading
            current_lines = []
        else:
            current_lines.append(line)

    save_section()
    return sections



def search_knowledge_base(
    sections: list[KnowledgeSection], query: str, limit: int = 5
) -> list[SearchResult]:
    """Return the sections with the most words matching a customer question."""
    if limit < 1:
        raise ValueError("limit must be at least 1")

    query_tokens = _tokens(query)
    if not query_tokens:
        return []

    expanded_query_tokens = set(query_tokens)
    for token in query_tokens:
        expanded_query_tokens.update(_QUERY_EXPANSIONS.get(token, set()))

    results: list[SearchResult] = []
    for section in sections:
        heading_tokens = _tokens(section.heading)
        body_tokens = _tokens(section.text)
        matches = expanded_query_tokens & (heading_tokens | body_tokens)
        if not matches:
            continue

        exact_matches = query_tokens & (heading_tokens | body_tokens)
        expanded_matches = (expanded_query_tokens - query_tokens) & (
            heading_tokens | body_tokens
        )
        score = (
            (3 * len(exact_matches))
            + len(expanded_matches)
            + (2 * len(query_tokens & heading_tokens))
        )
        results.append(SearchResult(section=section, score=score))

    results.sort(
        key=lambda result: (
            -result.score,
            result.section.file_name,
            result.section.heading,
        )
    )
    return results[:limit]



def load_knowledge_base(directory: str | Path) -> list[KnowledgeSection]:
    """Load all Markdown files from a knowledge-base directory in filename order."""
    directory = Path(directory)
    if not directory.is_dir():
        raise FileNotFoundError(f"Knowledge-base directory not found: {directory}")

    sections: list[KnowledgeSection] = []
    for path in sorted(directory.glob("*.md")):
        sections.extend(parse_markdown_file(path))
    return sections
