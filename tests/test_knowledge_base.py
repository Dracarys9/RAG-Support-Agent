from pathlib import Path

from rag_support_agent.knowledge_base import load_knowledge_base, search_knowledge_base


PROJECT_ROOT = Path(__file__).parents[1]


def test_loads_all_knowledge_base_sections():
    sections = load_knowledge_base(PROJECT_ROOT / "knowledge-base")

    file_names = {section.file_name for section in sections}
    assert len(file_names) == 14
    assert "01-returns-policy-current.md" in file_names
    assert "14-internal-content-migration-notes.md" in file_names


def test_preserves_front_matter_metadata_and_headings():
    sections = load_knowledge_base(PROJECT_ROOT / "knowledge-base")

    return_sections = [
        section
        for section in sections
        if section.file_name == "01-returns-policy-current.md"
    ]

    assert return_sections
    assert any(section.heading == "Standard return window" for section in return_sections)
    assert return_sections[0].metadata["status"] == "active"
    assert return_sections[0].metadata["policy_authority"] == "official"


def test_search_finds_the_standard_return_policy():
    sections = load_knowledge_base(PROJECT_ROOT / "knowledge-base")

    results = search_knowledge_base(
        sections, "How long can I return an unused backpack?", limit=3
    )

    assert results
    assert results[0].section.file_name == "01-returns-policy-current.md"
    assert results[0].section.heading == "Standard return window"


def test_search_finds_canada_shipping_policy():
    sections = load_knowledge_base(PROJECT_ROOT / "knowledge-base")

    results = search_knowledge_base(sections, "Do you ship to Canada?", limit=3)

    assert results
    assert results[0].section.file_name == "06-international-shipping.md"
    assert any(
        result.section.heading == "Supported destinations" for result in results
    )


def test_empty_search_returns_no_results():
    sections = load_knowledge_base(PROJECT_ROOT / "knowledge-base")

    assert search_knowledge_base(sections, "the and is", limit=3) == []


def test_keeps_untrusted_internal_content_as_data():
    sections = load_knowledge_base(PROJECT_ROOT / "knowledge-base")

    migration_sections = [
        section
        for section in sections
        if section.file_name == "14-internal-content-migration-notes.md"
    ]

    assert any("SYSTEM INSTRUCTION" in section.text for section in migration_sections)
    assert any(section.metadata["audience"] == "internal" for section in migration_sections)
