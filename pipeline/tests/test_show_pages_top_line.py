"""The show page's top line (DECISIONS 0059): what the app does for this
visitor, above the "Does she die" paragraph, with a count the build computes.

A show with a dated next episode leads with that episode and the reminder;
every other show, ended or between seasons, leads with checking a show before
starting it. The count of shows is the snapshot's own, rounded down, never a
typed number. The line reads no death record and stays outside the sealed
answer. Every negative control asserts that its sabotage changed the input
before it asserts the outcome.
"""

from __future__ import annotations

import copy
import datetime as dt
import json
import re
from pathlib import Path

import pytest

from qtv_pipeline import app_store, show_pages
from tests import htmlprobe

REPO = Path(__file__).resolve().parents[2]
FIXTURE = REPO / "ios" / "GuideCore" / "Tests" / "Fixtures" / "snapshot.fixture.json"
TEMPLATE = REPO / "pipeline" / "src" / "qtv_pipeline" / "templates" / "show.html.j2"
BASE = "https://example.test/qf"
HARBOR = "shows/harbor-lights/index.html"  # running, next episode 2026-09-20
CARTOGRAPHERS = "shows/the-cartographers/index.html"  # ended
SALT = "shows/salt-and-ember/index.html"  # no TVmaze schedule
# The fixture's snapshot day.
TODAY = dt.date(2026, 9, 13)
DATED = ("Sunday, September 20, 2026", "2026-09-20")
PRICE_TAIL = "a one-time purchase ($4.99 in the US), no subscription."


@pytest.fixture
def doc() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _build(doc: dict, tmp_path: Path, **kw) -> dict[str, str]:
    show_pages.build_site(doc, tmp_path, base_url=BASE, **kw)
    return {
        str(p.relative_to(tmp_path)): p.read_text(encoding="utf-8")
        for p in sorted((tmp_path / "shows").rglob("index.html"))
        if p.parent.name != "shows"
    }


def _show(doc: dict, slug: str) -> dict:
    return next(s for s in doc["shows"] if s["slug"] == slug)


def _line(raw: str) -> str:
    """The top line's markup."""
    start = raw.index('<p class="app-line">')
    return raw[start : raw.index("</p>", start) + len("</p>")]


def _line_text(raw: str) -> str:
    """The line as a visitor reads it: its sentences, then the link text and
    the full stop after it."""
    sentences, link, stop = htmlprobe.parse(f"<body>{_line(raw)}</body>").outside
    assert (link, stop) == (app_store.APP_LINE_LINK_TEXT, ".")
    return f"{sentences} {link}{stop}"


def _with_shows(doc: dict, count: int) -> dict:
    """``doc`` with its show list padded to ``count`` shows: copies of the
    ended fixture show under their own ids and slugs, with no characters, so
    they add to the snapshot's count and build no page."""
    grown = copy.deepcopy(doc)
    template = _show(grown, "the-cartographers")
    for i in range(count - len(grown["shows"])):
        extra = copy.deepcopy(template)
        extra["id"] = f"lwtv:show:{900_000 + i}"
        extra["lwtv_id"] = 900_000 + i
        extra["slug"] = f"padding-{i}"
        extra["title"] = f"Padding {i}"
        grown["shows"].append(extra)
    assert len(grown["shows"]) == count
    return grown


# --- the count ------------------------------------------------------------


@pytest.mark.parametrize(
    ("count", "phrase"),
    [
        (2293, "2,200+"),
        (2200, "2,200+"),
        (2199, "2,100+"),
        (100, "100+"),
        (12345, "12,300+"),
        (99, None),
        (3, None),
        (0, None),
        (-5, None),
    ],
)
def test_the_count_is_rounded_down_and_never_above_the_snapshot(count, phrase):
    assert app_store.catalog_phrase(count) == phrase
    if phrase is not None:
        shown = int(phrase.rstrip("+").replace(",", ""))
        assert 0 < shown <= count and count - shown < app_store.CATALOG_STEP


@pytest.mark.parametrize("count", [None, True, "2293", 2293.0, [2293]])
def test_a_count_that_is_not_a_whole_number_is_left_out_not_guessed(count):
    assert app_store.catalog_phrase(count) is None
    text = app_store.app_line_text(None, count)
    assert "works offline" in text and "+" not in text and "shows" not in text


def test_no_count_is_typed_into_the_source_or_the_template():
    """The number on the page comes from ``len(doc["shows"])``. Neither the
    sentence's module nor the template holds a count of shows to go stale."""
    source = Path(app_store.__file__).read_text(encoding="utf-8")
    template = TEMPLATE.read_text(encoding="utf-8")
    for text in (source, template):
        assert re.search(r"\d,\d{3}", text) is None
        assert re.search(r"\d+\+ (?:TV )?shows", text) is None
    # The control: the pattern does match the sentence the build produces.
    assert re.search(r"\d,\d{3}", app_store.app_line_text(None, 2293))


# --- the two sentences ----------------------------------------------------


def test_a_dated_next_episode_leads_with_it_and_the_reminder():
    assert app_store.app_line_text(DATED, 2293) == (
        "Next episode: Sunday, September 20, 2026, per TVmaze. "
        "Queer Frame for iPhone can remind you when it airs, and it covers 2,200+ shows offline: "
        f"{PRICE_TAIL}"
    )


@pytest.mark.parametrize("next_episode", [None, (show_pages.TO_BE_ANNOUNCED, None)])
def test_any_other_show_leads_with_checking_before_you_start(next_episode):
    """An ended show, a show between seasons, and an episode TVmaze lists
    with no date: the app sets a reminder only for a dated episode, so none
    of these promises one."""
    text = app_store.app_line_text(next_episode, 2293)
    assert text == (
        "Checking a show before you start it? "
        f"Queer Frame for iPhone covers 2,200+ shows offline: {PRICE_TAIL}"
    )
    assert "remind" not in text and "Next episode" not in text


def test_the_line_is_escaped_and_links_once_with_the_show_top_campaign():
    line = app_store.get_app_line(next_episode=("<b>Monday</b>", "2026-09-21"), show_count=2293)
    assert "<b>" not in line and "&lt;b&gt;Monday&lt;/b&gt;" in line
    href = app_store.app_store_link("show-top").replace("&", "&amp;")
    assert line.endswith(f' <a href="{href}">See it on the App Store</a>.</p>')
    assert line.count("<a ") == 1


# --- the built pages ------------------------------------------------------


def test_running_and_ended_shows_get_their_own_sentence(doc, tmp_path):
    raws = _build(_with_shows(doc, 2293), tmp_path, app_store_live=True)
    assert _show(doc, "harbor-lights")["schedule"]["status"] == "Running"
    assert _show(doc, "the-cartographers")["schedule"]["status"] == "Ended"
    assert _line_text(raws[HARBOR]) == (
        f"{app_store.app_line_text(DATED, 2293)} See it on the App Store."
    )
    for rel in (CARTOGRAPHERS, SALT):
        assert _line_text(raws[rel]) == (
            f"{app_store.app_line_text(None, 2293)} See it on the App Store."
        ), rel
    # The date in the line is the one the page's own next-episode line gives.
    assert show_pages.next_episode_line(_show(doc, "harbor-lights"), TODAY) == DATED


def test_the_count_on_the_page_is_the_snapshots_number_of_shows(doc, tmp_path):
    small = _build(doc, tmp_path / "small", app_store_live=True)
    assert len(doc["shows"]) < app_store.CATALOG_STEP
    for raw in small.values():
        assert "works offline" in _line_text(raw) and "+" not in _line_text(raw)
    for count, phrase in ((150, "100+"), (2293, "2,200+"), (2300, "2,300+")):
        grown = _build(_with_shows(doc, count), tmp_path / str(count), app_store_live=True)
        assert set(grown) == set(small)  # the padding built no page
        for rel, raw in grown.items():
            assert f"covers {phrase} shows offline" in _line_text(raw), (count, rel)


def test_a_running_show_between_seasons_reads_like_an_ended_one(doc, tmp_path):
    show = _show(doc, "harbor-lights")
    before = _build(copy.deepcopy(doc), tmp_path / "before", app_store_live=True)
    assert _line_text(before[HARBOR]).startswith("Next episode: ")
    show["schedule"]["next_episode"] = None
    after = _build(doc, tmp_path / "after", app_store_live=True)
    assert _line_text(after[HARBOR]).startswith(app_store.APP_LINE_CHECKING)
    assert "remind" not in _line_text(after[HARBOR])


def test_the_line_sits_under_the_opening_and_above_the_question_paragraph(doc, tmp_path):
    for rel, raw in _build(doc, tmp_path, app_store_live=True).items():
        assert raw.count('<p class="app-line">') == 1, rel
        opening_end = raw.index("</p>", raw.index('<p class="opening">')) + len("</p>")
        # Nothing between the opening and the line: it is the second paragraph.
        assert raw[opening_end:].lstrip().startswith('<p class="app-line">'), rel
        assert (
            raw.index('<p class="app-line">')
            < raw.index("<p>Does she die in ")
            < raw.index('class="spoiler-warning"')
            < raw.index('<details class="answer"')
        ), rel


def test_with_the_switch_off_there_is_no_line(doc, tmp_path):
    for rel, raw in _build(doc, tmp_path).items():
        assert "app-line" not in raw and "apps.apple.com" not in raw, rel
        assert app_store.APP_LINE_CHECKING not in raw, rel


def test_the_lower_next_episode_line_and_the_badge_block_are_unchanged(doc, tmp_path):
    raw = _build(doc, tmp_path, app_store_live=True)[HARBOR]
    assert (
        '<p class="next-episode"><strong>Next episode:</strong> '
        '<time datetime="2026-09-20">Sunday, September 20, 2026</time>, per TVmaze. '
        "Get a reminder in the app.</p>" in raw
    )
    assert raw.count(app_store.get_app_block(f"{BASE}/app-store-badge.svg", "show")) == 1
    # Still two App Store links, the top line's and the badge's, in that order.
    links = [h for h in htmlprobe.parse(raw).hrefs() if "apps.apple.com" in h]
    assert links == [app_store.app_store_link("show-top"), app_store.app_store_link("show")]


# --- what the line never does ---------------------------------------------


def test_the_line_ignores_every_death_record_and_stays_outside_the_answer(doc, tmp_path):
    before = _build(copy.deepcopy(doc), tmp_path / "before", app_store_live=True)
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
    after = _build(swapped, tmp_path / "after", app_store_live=True)
    assert before[CARTOGRAPHERS] != after[CARTOGRAPHERS]  # the swap reached the page
    for rel in before:
        assert _line(before[rel]) == _line(after[rel]), rel
        page = htmlprobe.parse(after[rel])
        assert htmlprobe.details_problems(page) == [], rel
        assert not any(app_store.APP_LINE_CHECKING in t or "iPhone" in t for t in page.inside), rel


def test_the_line_never_prints_the_episode_name(doc, tmp_path):
    name = _show(doc, "harbor-lights")["schedule"]["next_episode"]["name"]
    assert name  # the fixture has a name to leak
    raw = _build(doc, tmp_path, app_store_live=True)[HARBOR]
    assert name not in raw


@pytest.mark.parametrize("next_episode", [None, DATED])
def test_the_line_makes_no_claim_the_site_has_not_approved(next_episode):
    """No label for a person (DECISIONS 0027), no tracking claim, no review,
    rating or sales claim, and nothing that says the app is sold everywhere
    (DECISIONS 0058)."""
    text = app_store.app_line_text(next_episode, 2293).lower()
    for word in (
        "gay",
        "tracking",
        "analytics",
        "review",
        "rated",
        "rating",
        "stars",
        "best",
        "bestsell",
        "downloads",
        "sold",
        "worldwide",
        "everywhere",
        "countries",
        "your local price",
    ):
        assert word not in text, word


def test_negative_control_a_line_inside_the_answer_is_caught(doc, tmp_path):
    raw = _build(doc, tmp_path, app_store_live=True)[CARTOGRAPHERS]
    line = _line(raw)
    moved = raw.replace(line, "", 1).replace(
        '<div class="answer-body" data-nosnippet>',
        f'<div class="answer-body" data-nosnippet>{line}',
    )
    assert moved != raw  # the sabotage landed
    inside = htmlprobe.parse(moved).inside
    assert any(app_store.APP_LINE_CHECKING in t for t in inside)
    assert not any(app_store.APP_LINE_CHECKING in t for t in htmlprobe.parse(raw).inside)
