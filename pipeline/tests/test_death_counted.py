"""The snapshot says whether a recorded death is counted (DECISIONS 0053).

LezWatch.TV keeps death dates and, separately, a status it shows as "Status:
Dead" or "Status: Alive" (the ``dead`` cliche). 0052 made the website follow
the status; 0053 puts the same decision into the snapshot as
``death.counted`` so the iOS and Android apps read it instead of deriving it.
The records are the real ones from the 2026-11-07 snapshot for the four shows
the 2026-11-08 cross-check found (Bernie Wolfe, Ava Silva, Sara Lance, Nora
West-Allen) and a marked-dead control (Rue Bennett).
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from qtv_pipeline import build as build_mod
from qtv_pipeline import findings, normalize, show_pages

FIXTURES = Path(__file__).parent / "fixtures"
REPO = Path(__file__).resolve().parents[2]
V1_FIXTURE = REPO / "ios" / "GuideCore" / "Tests" / "Fixtures" / "snapshot.fixture.json"

DEAD_ID, UNDEAD_ID, OTHER_ID = 134, 900, 901
CLICHES = {
    DEAD_ID: {"slug": "dead", "name": "Dead"},
    UNDEAD_ID: {"slug": "undead", "name": "Undead"},
    OTHER_ID: {"slug": "science", "name": "Science"},
}
TAX = {
    "cliches": CLICHES,
    "genders": {},
    "sexualities": {},
    "romantic": {},
}

# (name, lwtv id, death dates as LezWatch stores them, cliche ids, marked dead?)
FOUR = [
    ("Bernie Wolfe", 5417, ["2019-04-02"], [OTHER_ID], False),
    ("Ava Silva", 7001, ["2020-07-02"], [UNDEAD_ID], False),
    ("Sara Lance", 9003, ["2014-01-15", "2016-01-26", "2021-02-02"], [OTHER_ID], False),
    ("Nora West-Allen", 9004, ["2019-11-12"], [OTHER_ID], False),
]
CONTROL = ("Rue Bennett", 8001, ["2026-02-22"], [OTHER_ID, DEAD_ID], True)


def _raw(name: str, lwtv_id: int, dates: list[str] | None, cliche_ids: list[int]) -> dict:
    return {
        "id": lwtv_id,
        "slug": name.lower().replace(" ", "-"),
        "link": f"https://lezwatchtv.com/character/{lwtv_id}/",
        "modified_gmt": "2026-11-07T00:00:00",
        "title": {"rendered": name},
        "acf": {
            "lezchars_death_year": [{"date": d} for d in dates] if dates else None,
            "lezchars_show_group": [],
            "lezchars_actor": [],
        },
        "cliche": cliche_ids,
        "gender": [],
        "sexuality": [],
        "romantic": [],
    }


def _normalize(rec: tuple) -> dict:
    name, lwtv_id, dates, cliche_ids, _ = rec
    return normalize.normalize_character(_raw(name, lwtv_id, dates, cliche_ids), TAX, {})


@pytest.mark.parametrize("rec", FOUR, ids=[r[0] for r in FOUR])
def test_a_date_without_the_marker_is_recorded_but_not_counted(rec: tuple) -> None:
    death = _normalize(rec)["death"]
    assert death["died"] is True and death["death_known"] is True
    assert death["counted"] is False
    # The raw dates stay: episode placement (0041) and display need them.
    assert [d["raw"] for d in death["dates"]] == rec[2]
    assert death["years"] == sorted({int(d[:4]) for d in rec[2]})


def test_a_marked_dead_character_is_counted() -> None:
    death = _normalize(CONTROL)["death"]
    assert death["died"] is True and death["counted"] is True


def test_other_cliches_do_not_count_a_death() -> None:
    """ "Undead" alone (Ava Silva) is not "Dead"; with "Dead" it is (The Countess)."""
    assert _normalize(FOUR[1])["death"]["counted"] is False
    both = ("The Countess", 1, ["2016-01-06"], [UNDEAD_ID, DEAD_ID], True)
    assert _normalize(both)["death"]["counted"] is True


def test_no_recorded_death_carries_no_counted_field() -> None:
    """Absence stays absent: there is no death to count, and no false to read."""
    death = _normalize(("Serena Campbell", 5418, None, [], False))["death"]
    assert death == {"died": None, "death_known": False, "dates": [], "years": []}


def test_a_death_entry_with_no_usable_date_still_has_a_status() -> None:
    marked = normalize._normalize_death([{"date": None}], marked_dead=True)
    unmarked = normalize._normalize_death([{"date": None}], marked_dead=False)
    assert marked["counted"] is True
    assert unmarked["counted"] is False
    assert marked["dates"] == unmarked["dates"]


def test_the_field_validates_against_the_schema_and_is_never_null() -> None:
    schema = json.loads(build_mod._find_schema_path().read_text())
    death_schema = {"$defs": schema["$defs"], "$ref": "#/$defs/death"}
    validator = jsonschema.Draft202012Validator(death_schema)
    for rec in [*FOUR, CONTROL]:
        validator.validate(_normalize(rec)["death"])
    with pytest.raises(jsonschema.ValidationError):
        validator.validate({**_normalize(CONTROL)["death"], "counted": None})


def test_old_snapshots_without_the_field_still_validate() -> None:
    schema = json.loads(build_mod._find_schema_path().read_text())
    doc = json.loads(V1_FIXTURE.read_text())
    assert all("counted" not in c["death"] for c in doc["characters"])
    jsonschema.Draft202012Validator(schema).validate(doc)


def test_snapshot_and_website_agree_on_the_marker_rule() -> None:
    """One list, two readers: the site's ``marked_dead`` and the snapshot's
    ``counted`` give the same answer for every record above."""
    for rec in [*FOUR, CONTROL]:
        char = _normalize(rec)
        assert show_pages.marked_dead(char) is char["death"]["counted"] is rec[4]


def test_negative_control_without_the_rule_the_four_flip_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Switch the rule off (every date counts, as before 0052) and the four
    records read as counted again, while the control does not move. A rule that
    was never applied would fail here by leaving the four at False."""
    monkeypatch.setattr(normalize, "is_marked_dead", lambda _cliches: True)
    flipped = [_normalize(r)["death"]["counted"] for r in FOUR]
    assert flipped == [True] * 4
    assert _normalize(CONTROL)["death"]["counted"] is True


def test_findings_events_leave_out_uncounted_deaths() -> None:
    """The findings page measures deaths LezWatch.TV counts (0053)."""
    shows = [{"id": "lwtv:show:1"}]

    def doc(counted: bool | None) -> dict:
        death = {
            "died": True,
            "death_known": True,
            "dates": [{"date": "2019-04-02", "year": 2019, "raw": "2019-04-02"}],
            "years": [2019],
        }
        if counted is not None:
            death["counted"] = counted
        return {
            "shows": shows,
            "characters": [
                {
                    "death": death,
                    "shows": [{"show_id": "lwtv:show:1", "role": "main", "years": ["2019"]}],
                }
            ],
        }

    assert len(findings.death_events(doc(True))) == 1
    assert len(findings.death_events(doc(None))) == 1  # an older file: as before
    assert findings.death_events(doc(False)) == []
