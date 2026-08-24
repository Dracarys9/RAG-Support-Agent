from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class KnowledgeSection:
    """A searchable piece of a knowledge-base Markdown file."""

    file_name: str
    heading: str
    text: str
    metadata: dict[str, Any]



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



def load_knowledge_base(directory: str | Path) -> list[KnowledgeSection]:
    """Load all Markdown files from a knowledge-base directory in filename order."""
    directory = Path(directory)
    if not directory.is_dir():
        raise FileNotFoundError(f"Knowledge-base directory not found: {directory}")

    sections: list[KnowledgeSection] = []
    for path in sorted(directory.glob("*.md")):
        sections.extend(parse_markdown_file(path))
    return sections
