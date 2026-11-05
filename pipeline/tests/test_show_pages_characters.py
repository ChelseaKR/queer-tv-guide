"""The character list on a show page (DECISIONS 0035): a stable link anchor
per character and "played by <actor>" from LezWatch.TV, with no character
years, no death date and no cliche or trope outside the closed answer.

Every negative control asserts its sabotage changed the page before it
asserts that the checker caught it.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import pytest

from qtv_pipeline import show_pages
from tests import htmlprobe

REPO = Path(__file__).resolve().parents[2]
FIXTURE = REPO / "ios" / "GuideCore" / "Tests" / "Fixtures" / "snapshot.fixture.json"
BASE = "https://example.test/qf"
CARTOGRAPHERS = "shows/the-cartographers/index.html"


@pytest.fixture
def doc() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _character(doc: dict, slug: str) -> dict:
    return next(c for c in doc["characters"] if c["slug"] == slug)


def _build(doc: dict, tmp_path: Path) -> tuple[dict[str, htmlprobe.Page], dict[str, str]]:
    show_pages.build_site(doc, tmp_path, base_url=BASE)
    raws = {
        str(p.relative_to(tmp_path)): p.read_text(encoding="utf-8")
        for p in sorted(tmp_path.rglob("index.html"))
    }
    return {k: htmlprobe.parse(v) for k, v in raws.items()}, raws


def _cast_html(raw: str) -> str:
    start = raw.index('<ul class="cast">')
    return raw[start : raw.index("</ul>", start)]


# --- anchors and actors ----------------------------------------------------


def test_each_character_has_its_slug_as_an_anchor_regulars_first(doc, tmp_path):
    pages, _ = _build(doc, tmp_path)
    assert pages["shows/harbor-lights/index.html"].cast_ids == ["mara-quill", "ines-varga"]
    assert pages[CARTOGRAPHERS].cast_ids == ["odile-brandt", "thea-marsh"]
    _character(doc, "odile-brandt")["shows"][0]["role"] = "guest"
    pages, _ = _build(doc, tmp_path / "again")
    assert pages[CARTOGRAPHERS].cast_ids == ["thea-marsh", "odile-brandt"]


def test_played_by_uses_lezwatchs_actor_names(doc, tmp_path):
    _character(doc, "thea-marsh")["actors"].append(
        {"lwtv_id": 399, "slug": None, "name": "Example Actor Five"}
    )
    pages, _ = _build(doc, tmp_path)
    cast = " ".join(pages[CARTOGRAPHERS].cast)
    assert ", played by Example Actor Three. Role:" in cast
    assert ", played by Example Actor Four and Example Actor Five. Role:" in cast


def test_an_unresolved_actor_leaves_the_clause_out(doc, tmp_path):
    pages, _ = _build(doc, tmp_path)
    cast = " ".join(pages["shows/salt-and-ember/index.html"].cast)
    assert "Juno Adeyemi" in cast
    assert "played by" not in cast
    assert "None" not in cast and "Unknown" not in cast


def test_actors_are_never_links_and_there_are_no_actor_pages(doc, tmp_path):
    pages, raws = _build(doc, tmp_path)
    page_raw = _cast_html(raws[CARTOGRAPHERS])
    links = htmlprobe.parse(page_raw).hrefs()
    assert links == [c["source_url"] for c in doc["characters"] if c["slug"] in page_raw]
    assert not [p for p in pages if "actor" in p]


def test_anchors_are_stable_and_unique(doc, tmp_path):
    first, _ = _build(copy.deepcopy(doc), tmp_path / "a")
    second, _ = _build(copy.deepcopy(doc), tmp_path / "b")
    for name, page in first.items():
        assert htmlprobe.duplicate_ids(page) == [], name
        assert page.cast_ids == second[name].cast_ids
    for page in first.values():
        assert all(page.cast_ids), "every listed character has an anchor"


def test_a_repeated_or_reserved_slug_falls_back_to_the_lezwatch_id():
    chars = [
        {"slug": "sam", "lwtv_id": 1},
        {"slug": "sam", "lwtv_id": 2},
        {"slug": "main", "lwtv_id": 3},
        {"slug": "Not A Slug", "lwtv_id": 4},
        {"slug": "character-5", "lwtv_id": 6},
        {"slug": "x", "lwtv_id": 5},
        {"slug": "sam", "lwtv_id": 5},
    ]
    got = show_pages.anchors(chars)
    assert got == [
        "sam",
        "character-2",
        "character-3",
        "character-4",
        "character-5",
        "x",
        "character-5-2",
    ]
    assert len(set(got)) == len(got)


def test_a_planted_slug_clash_on_a_page_is_resolved(doc, tmp_path):
    _character(doc, "thea-marsh")["slug"] = "odile-brandt"
    pages, _ = _build(doc, tmp_path)
    page = pages[CARTOGRAPHERS]
    assert page.cast_ids == ["odile-brandt", "character-204"]
    assert htmlprobe.duplicate_ids(page) == []


def test_negative_control_a_repeated_anchor_is_caught(doc, tmp_path):
    pages, raws = _build(doc, tmp_path)
    bad = raws[CARTOGRAPHERS].replace('id="thea-marsh"', 'id="odile-brandt"')
    assert bad != raws[CARTOGRAPHERS]
    assert htmlprobe.duplicate_ids(pages[CARTOGRAPHERS]) == []
    assert htmlprobe.duplicate_ids(htmlprobe.parse(bad)) == ["odile-brandt"]


# --- spoilers: years, death dates, tropes ------------------------------------


def _plant(doc: dict) -> dict:
    """A character run that would give a death away, a dated death and
    death-revealing terms, all with values the page has no other reason to print."""
    _character(doc, "thea-marsh")["shows"][0]["years"] = ["1983", "1984"]
    odile = _character(doc, "odile-brandt")
    odile["death"]["dates"] = [{"date": "2017-04-09", "year": 2017, "raw": "20170409"}]
    odile["cliches"] = [
        {"slug": "dead", "name": "Dead Queers"},
        {"slug": "undead", "name": "Undead"},
    ]
    show = next(s for s in doc["shows"] if s["slug"] == "the-cartographers")
    show["tropes"] = [{"slug": "dead-queers", "name": "Bury Your Queers"}]
    return doc


SECRETS = ["1983", "1984", "2017-04-09", "April 9", "Dead Queers", "Undead", "Bury Your Queers"]


def test_no_character_year_death_date_or_death_term_is_visible(doc, tmp_path):
    pages, raws = _build(_plant(doc), tmp_path)
    page = pages[CARTOGRAPHERS]
    assert htmlprobe.answer_leaks(page, SECRETS) == []
    cast = " ".join(page.cast)
    assert not re.search(r"\b(19|20)\d\d\b", cast), cast
    assert not any(w in cast for w in ("Dies", "Dead", "dead", "Unknown", "died"))
    # The planted death is real: the answer inside the closed element has it.
    assert any("Dies (2017)" in t for t in page.inside)
    assert "1983" not in raws[CARTOGRAPHERS] and "1984" not in raws[CARTOGRAPHERS]


@pytest.mark.parametrize(
    ("needle", "where"),
    [
        ("1983 to 1984", "a character's years"),
        ("Died April 9, 2017", "a death date"),
        ("Undead", "a death-revealing cliche"),
    ],
)
def test_negative_control_a_planted_spoiler_in_the_list_is_caught(doc, tmp_path, needle, where):
    pages, raws = _build(_plant(doc), tmp_path)
    raw = raws[CARTOGRAPHERS]
    bad = raw.replace("Role: Regular. Gender:", f"{needle}. Role: Regular. Gender:", 1)
    assert bad != raw, where
    assert htmlprobe.answer_leaks(pages[CARTOGRAPHERS], [needle]) == []
    assert htmlprobe.answer_leaks(htmlprobe.parse(bad), [needle]) == [needle], where
    assert any(needle in t for t in htmlprobe.parse(bad).cast), where


def test_swapping_every_death_record_leaves_the_list_byte_for_byte(doc, tmp_path):
    _, before = _build(copy.deepcopy(doc), tmp_path / "before")
    swapped = copy.deepcopy(doc)
    for c in swapped["characters"]:
        dead = c["death"]["died"] is True
        c["death"] = (
            {"died": None, "death_known": False, "dates": [], "years": []}
            if dead
            else {
                "died": True,
                "death_known": True,
                "dates": [{"date": "2020-01-01", "year": 2020, "raw": "20200101"}],
                "years": [2020],
            }
        )
    _, after = _build(swapped, tmp_path / "after")
    assert before[CARTOGRAPHERS] != after[CARTOGRAPHERS]  # the swap reached the page
    for name in before:
        if '<ul class="cast">' in before[name]:
            assert _cast_html(before[name]) == _cast_html(after[name]), name
