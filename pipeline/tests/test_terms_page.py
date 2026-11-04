"""The static terms of use page published from docs/site/terms.html."""

from __future__ import annotations

import re
from pathlib import Path

DOCS_SITE = Path(__file__).resolve().parents[2] / "docs" / "site"
SNAPSHOT_WORKFLOW = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "snapshot.yml"


def _text(html: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", html).split())


def test_the_terms_page_names_the_operator_the_sources_and_the_law() -> None:
    html = (DOCS_SITE / "terms.html").read_text(encoding="utf-8")
    text = _text(html)
    for want in (
        "Chelsea Kelly-Reif",
        "chelsea@chelseakr.com",
        "not affiliated with or endorsed by LezWatch.TV, TVmaze",
        "can be wrong or late",
        "It does not mean a character lives.",
        "CC BY-SA 4.0",
        "laws of the State of California",
    ):
        assert want in text, want
    assert len(text.split()) < 700
    # Like privacy.html and support.html: no script, nothing from another site.
    assert "<script" not in html.lower()
    assert not re.search(r'(?:src|href)="//', html)
    assert not re.search(r'<link[^>]+href="https?://', html)


def test_the_publish_workflow_copies_the_terms_page() -> None:
    workflow = SNAPSHOT_WORKFLOW.read_text(encoding="utf-8")
    assert "cp ../docs/site/terms.html site/terms.html" in workflow
