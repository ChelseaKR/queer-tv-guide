"""DG-01: every source the snapshot credits has a committed data card.

The list of sources is the pipeline's own attribution list (`licence.py`),
the one the snapshot and the app display, so adding a source without a card
fails here.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from qtv_pipeline import licence

REPO = Path(__file__).resolve().parents[2]
CARDS = REPO / "docs" / "data"
REQUIRED_FIELDS = (
    "Source",
    "License",
    "Fetch/refresh cadence",
    "Staleness SLA",
    "Fetch timestamp",
    "Tier",
    "Known limitations",
    "Retention",
    "Dataset version",
)


def missing_fields(card_text: str) -> list[str]:
    """Required fields with no `| Field | value |` row, or an empty value."""
    missing = []
    for field in REQUIRED_FIELDS:
        rows = [
            line
            for line in card_text.splitlines()
            if line.startswith(f"| {field} |") and line.split("|")[2].strip()
        ]
        if not rows:
            missing.append(field)
    return missing


def test_the_attribution_list_names_sources() -> None:
    # Denominator: the check below must have something to check.
    assert [a["source"] for a in licence.ATTRIBUTION] == ["lezwatch", "tvmaze"]


@pytest.mark.parametrize("source", [a["source"] for a in licence.ATTRIBUTION])
def test_every_credited_source_has_a_complete_card(source: str) -> None:
    card = CARDS / f"{source}.md"
    assert card.is_file(), f"no data card for {source}: add docs/data/{source}.md"
    assert missing_fields(card.read_text()) == []


def test_an_incomplete_card_is_caught() -> None:
    card = (CARDS / "tvmaze.md").read_text()
    without_retention = "\n".join(
        line for line in card.splitlines() if not line.startswith("| Retention |")
    )
    assert without_retention != card, "sabotage did not land"
    assert missing_fields(without_retention) == ["Retention"]
    blank_tier = "\n".join(
        "| Tier | |" if line.startswith("| Tier |") else line for line in card.splitlines()
    )
    assert blank_tier != card, "sabotage did not land"
    assert missing_fields(blank_tier) == ["Tier"]
