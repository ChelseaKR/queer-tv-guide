"""The opening sentence of each show page (show_pages.opening, DECISIONS 0029).

It must be specific to the show, built only from snapshot facts, never say
anything a death record decides, and leave out a fact the snapshot lacks
instead of printing a placeholder. Every negative control asserts that its
sabotage changed the page before it asserts that the check caught it.
"""

from __future__ import annotations

import copy
import dataclasses
import json
import re
from pathlib import Path

import pytest

from qtv_pipeline import show_pages
from tests import htmlprobe

REPO = Path(__file__).resolve().parents[2]
FIXTURE = REPO / "ios" / "GuideCore" / "Tests" / "Fixtures" / "snapshot.fixture.json"
BASE = "https://example.test/qf"
# Words that mean "we do not know" (or a template with nothing in it). None
# of them may appear in an opening: an absent fact is left out instead.
PLACEHOLDERS = re.compile(
    r"Unknown|Not recorded|Not rated|None|null|\(\s*\)|\(\s*[,;]|[,;]\s*\)|  "
)


@pytest.fixture
def doc() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _show(doc: dict, slug: str) -> dict:
    return next(s for s in doc["shows"] if s["slug"] == slug)


def _opening(doc: dict, slug: str) -> str:
    show = _show(doc, slug)
    return show_pages.opening(show, show_pages._characters(doc, show))


def _page(doc: dict, tmp_path: Path, slug: str) -> htmlprobe.Page:
    show_pages.build_site(doc, tmp_path, base_url=BASE)
    path = tmp_path / "shows" / slug / "index.html"
    return htmlprobe.parse(path.read_text(encoding="utf-8"))


def placeholder_problems(text: str) -> list[str]:
    return PLACEHOLDERS.findall(text)


# --- what it says ----------------------------------------------------------


def test_an_ended_show_with_every_fact(doc):
    assert _opening(doc, "the-cartographers") == (
        "LezWatch.TV lists 2 queer characters in The Cartographers (Example Network, "
        "2016 to 2018): Odile Brandt and Thea Marsh. Its last "
        "episode on TVmaze aired on May 20, 2018 (season 2, episode 10)."
    )


def test_a_running_show_gives_the_most_recent_and_next_episode(doc):
    assert _opening(doc, "harbor-lights") == (
        "LezWatch.TV lists 2 queer characters in Harbor Lights (Example Network, "
        "2021 to present): Mara Quill and Inés Varga. Its most recent episode on "
        "TVmaze aired on September 13, 2026 (season 3, episode 3), and the next is "
        "listed for September 20, 2026."
    )


def test_more_characters_than_names_says_including(doc):
    show = _show(doc, "the-cartographers")
    cast = show_pages._characters(doc, show)
    guest = dataclasses.replace(cast[0], name="Ada Guest", role="Guest")
    extra = [guest, *cast]  # a third listed character, a guest listed first
    text = show_pages.opening(show, extra)
    assert text.startswith("LezWatch.TV lists 3 queer characters in The Cartographers")
    assert ", including Odile Brandt and Thea Marsh." in text


def test_a_list_of_networks_is_kept_apart_from_the_years(doc):
    show = _show(doc, "the-cartographers")
    show["networks"].append({"name": "Third Example", "slug": "third"})
    show["schedule"]["schedule_known"] = False  # LezWatch's stations only then
    text = show_pages.opening(show, show_pages._characters(doc, show))
    assert "(Example Network, Another Example, and Third Example; 2016 to 2018)" in text


def test_the_network_is_tvmazes_when_the_schedule_is_known(doc):
    """The same source as the Network row (DECISIONS 0031)."""
    show = _show(doc, "harbor-lights")
    show["networks"] = [{"name": "The CW", "slug": "the-cw"}]
    cast = show_pages._characters(doc, show)
    assert "(Example Network, 2021 to present)" in show_pages.opening(show, cast)
    show["schedule"]["network"] = None
    show["schedule"]["web_channel"] = {"name": "Example Streaming", "country_code": None}
    assert "(Example Streaming, 2021 to present)" in show_pages.opening(show, cast)
    assert "The CW" not in show_pages.opening(show, cast)
    show["schedule"]["schedule_known"] = False
    text = show_pages.opening(show, cast)
    assert "Example Streaming" not in text and "(The CW, 2021 to present)" in text


def test_it_is_the_first_paragraph_of_the_page(doc, tmp_path):
    page = _page(doc, tmp_path, "the-cartographers")
    text = _opening(doc, "the-cartographers")
    first = page.outside.index("Do any queer characters die in The Cartographers?")
    assert page.outside[first + 1] == text
    assert page.outside[first + 2].startswith("Does she die in The Cartographers?")


def test_every_built_page_has_a_different_opening(doc, tmp_path):
    show_pages.build_site(doc, tmp_path, base_url=BASE)
    openings = [
        show_pages.opening(s, show_pages._characters(doc, s)) for s in show_pages.select_shows(doc)
    ]
    assert len(openings) == len(set(openings)) == 3


# --- absence is left out, never rendered as a value -------------------------


def test_a_show_with_missing_facts_gets_a_shorter_sentence(doc):
    # Salt & Ember: no years, no network, no TVmaze match.
    text = _opening(doc, "salt-and-ember")
    assert text == "LezWatch.TV lists one queer character in Salt & Ember: Juno Adeyemi."
    assert placeholder_problems(text) == []


def test_each_fact_taken_away_shortens_the_sentence_and_leaves_no_trace(doc):
    show = _show(doc, "the-cartographers")
    cast = show_pages._characters(doc, show)
    lengths = [len(show_pages.opening(show, cast))]
    steps = [
        lambda s: s["schedule"].update(previous_episode=None),
        lambda s: s.update(networks=[]) or s["schedule"].update(network=None),
        lambda s: s["years"].update(start=None, end=None, on_air="unknown"),
    ]
    for step in steps:
        step(show)
        text = show_pages.opening(show, cast)
        assert placeholder_problems(text) == [], text
        lengths.append(len(text))
    assert lengths == sorted(lengths, reverse=True) and len(set(lengths)) == len(lengths)
    assert show_pages.opening(show, cast) == (
        "LezWatch.TV lists 2 queer characters in The Cartographers: Odile Brandt and Thea Marsh."
    )


def test_an_unreadable_date_or_episode_number_is_left_out(doc):
    show = _show(doc, "the-cartographers")
    cast = show_pages._characters(doc, show)
    show["schedule"]["previous_episode"]["season"] = None
    assert "(season" not in show_pages.opening(show, cast)
    assert "aired on May 20, 2018." in show_pages.opening(show, cast)
    show["schedule"]["previous_episode"]["airdate"] = "not a date"
    assert "TVmaze" not in show_pages.opening(show, cast)
    show["schedule"]["previous_episode"]["airdate"] = None
    assert "TVmaze" not in show_pages.opening(show, cast)


def test_a_start_year_without_an_end_says_from_not_present(doc):
    show = _show(doc, "harbor-lights")
    show["years"]["on_air"] = "unknown"
    text = show_pages.opening(show, show_pages._characters(doc, show))
    assert "(Example Network, from 2021)" in text
    assert "present" not in text


def test_negative_control_a_placeholder_is_caught(doc, tmp_path, monkeypatch):
    clean = _page(doc, tmp_path / "a", "salt-and-ember")
    assert all(placeholder_problems(t) == [] for t in clean.outside[:3])
    # Sabotage: the facts list's years wording, which says "Not recorded".
    monkeypatch.setattr(show_pages, "_opening_years", show_pages._years)
    text = _opening(doc, "salt-and-ember")
    assert "Not recorded" in text
    assert placeholder_problems(text) != []


# --- spoilers -------------------------------------------------------------


def test_the_opening_never_changes_with_the_deaths(doc):
    before = {s["slug"]: _opening(doc, s["slug"]) for s in show_pages.select_shows(doc)}
    swapped = copy.deepcopy(doc)
    for c in swapped["characters"]:
        died = c["death"]["died"] is not True
        c["death"] = {
            "death_known": died,
            "died": True if died else None,
            "years": [2017] if died else [],
        }
    for show in swapped["shows"]:
        show["counts"]["deaths"] = show["counts"]["deaths_source_reported"] = 9
        show["tropes"] = [{"slug": "dead-queers", "name": "Bury Your Queers"}]
    after = {s["slug"]: _opening(swapped, s["slug"]) for s in show_pages.select_shows(swapped)}
    assert after == before


def test_the_opening_holds_no_answer_and_no_episode_name(doc, tmp_path):
    show = _show(doc, "the-cartographers")
    show["schedule"]["previous_episode"]["name"] = "Dead Air"
    page = _page(doc, tmp_path, "the-cartographers")
    cast = show_pages._characters(doc, show)
    answers = [show_pages._answer(show, cast).headline, *[c.status for c in cast]]
    assert htmlprobe.answer_leaks(page, answers) == []
    text = show_pages.opening(show, cast)
    assert "Dead Air" not in text
    assert not re.search(r"\b(dies|died|dead|death|alive|lives|survives?)\b", text, re.I)


def test_negative_control_an_answer_in_the_opening_is_caught(doc, tmp_path, monkeypatch):
    show = _show(doc, "the-cartographers")
    cast = show_pages._characters(doc, show)
    headline = show_pages._answer(show, cast).headline
    real = show_pages.opening
    monkeypatch.setattr(show_pages, "opening", lambda s, c: f"{real(s, c)} {headline}")
    page = _page(doc, tmp_path, "the-cartographers")
    assert any(headline in t for t in page.outside)
    assert htmlprobe.answer_leaks(page, [headline]) == [headline]
