"""The airing-now page, /airing/ (airing_page.py, DECISIONS 0033).

It lists the shows LezWatch.TV marks on air that TVmaze lists a new episode
for in the window, from the snapshot alone. It must never name an episode or
a character (so never a character's years), never change with a death
record, leave out a show LezWatch.TV has ended even when TVmaze lists a
revival, and never print an absent fact. Every negative control asserts that
its sabotage changed the page before it asserts that the check caught it.
"""

from __future__ import annotations

import copy
import datetime as dt
import json
from html.parser import HTMLParser
from pathlib import Path

import pytest

from qtv_pipeline import airing_page, show_pages, site_index
from qtv_pipeline.app_store import APP_STORE_URL
from tests import htmlprobe

REPO = Path(__file__).resolve().parents[2]
FIXTURE = REPO / "ios" / "GuideCore" / "Tests" / "Fixtures" / "snapshot.fixture.json"
BASE = "https://example.test"
AIRING = f"{BASE}/airing/"
EPISODE_NAME = "Dead Air"  # 0029's example of an episode name that is the answer


@pytest.fixture
def doc() -> dict:
    d = json.loads(FIXTURE.read_text(encoding="utf-8"))
    # Harbor Lights' next episode carries a name that would be a spoiler.
    _show(d, "harbor-lights")["schedule"]["next_episode"]["name"] = EPISODE_NAME
    return d


def _show(doc: dict, slug: str) -> dict:
    return next(s for s in doc["shows"] if s["slug"] == slug)


def _schedule(doc: dict, slug: str, airdate: str, season=2, number=3, **years) -> dict:
    """Give ``slug`` a TVmaze next episode (and, with ``years``, LezWatch years)."""
    show = _show(doc, slug)
    template = copy.deepcopy(_show(doc, "harbor-lights")["schedule"])
    template["next_episode"].update(
        {"airdate": airdate, "season": season, "number": number, "name": EPISODE_NAME}
    )
    show["schedule"] = template
    show["years"].update(years)
    return show


def _files(doc: dict, **kw) -> dict[str, str]:
    return show_pages.render_site(doc, base_url=BASE, **kw)


def _airing(doc: dict, **kw) -> str:
    return _files(doc, **kw)["airing/index.html"]


def _visible(text: str) -> str:
    """Everything a reader or a search engine reads: body text, title,
    description and the structured data."""
    page = htmlprobe.parse(text)
    return " ".join([*page.outside, *page.inside, page.title, page.description, *page.ld_json])


class _Lines(HTMLParser):
    """The text of each list item on the page, tags dropped, as one string."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.items: list[str] = []
        self.depth = 0

    def handle_starttag(self, tag, attrs):
        if tag == "li":
            self.items.append("")
            self.depth += 1

    def handle_endtag(self, tag):
        if tag == "li":
            self.depth -= 1

    def handle_data(self, data):
        if self.depth:
            self.items[-1] += data


def _lines(text: str) -> list[str]:
    probe = _Lines()
    probe.feed(text)
    return probe.items


# --- the spoiler checker the negative controls sabotage -----------------------


def spoiler_problems(text: str, doc: dict) -> list[str]:
    """Every episode name, character name, character's years and trope name
    of the snapshot that the page shows, and any answer element."""
    seen = _visible(text)
    found: list[str] = []
    for show in doc["shows"]:
        for key in ("next_episode", "previous_episode"):
            name = (show["schedule"][key] or {}).get("name")
            if name and name in seen:
                found.append(f"episode name {name!r}")
        found += [f"trope {t['name']!r}" for t in show["tropes"] if t["name"] in seen]
    for c in doc["characters"]:
        if c["name"] in seen:
            found.append(f"character {c['name']!r}")
        for link in c["shows"]:
            years = sorted(link["years"])
            if years and f"{years[0]} to {years[-1]}" in seen:
                found.append(f"years of {c['name']!r}")
    if htmlprobe.parse(text).named("details"):
        found.append("an answer element")
    return found


def test_the_page_shows_no_episode_name_character_years_or_trope(doc):
    text = _airing(doc)
    assert "Harbor Lights" in _visible(text)  # the show with the spoiler name is listed
    assert spoiler_problems(text, doc) == []


@pytest.mark.parametrize(
    "planted",
    [
        EPISODE_NAME,  # the episode name
        "Mara Quill",  # a character in the new season
        "2021 to 2026",  # her years, which say she is still there
        "Slow Burn",  # a trope
    ],
)
def test_negative_control_a_planted_spoiler_is_caught(doc, planted):
    text = _airing(doc)
    sabotaged = text.replace("<h2 id=", f"<p>{planted}</p><h2 id=", 1)
    assert sabotaged != text  # the sabotage landed
    assert spoiler_problems(sabotaged, doc)


def test_swapping_every_death_record_changes_no_byte(doc):
    swapped = copy.deepcopy(doc)
    for c in swapped["characters"]:
        dead = c["death"]["died"] is True
        c["death"] = (
            {"died": None, "death_known": False, "dates": [], "years": []}
            if dead
            else {
                "died": True,
                "death_known": True,
                "dates": [{"date": "2026-01-01", "year": 2026, "raw": "20260101"}],
                "years": [2026],
            }
        )
    for s in swapped["shows"]:
        s["counts"]["deaths"] = 9 - s["counts"]["deaths"]
        s["counts"]["deaths_source_reported"] = 7
    page = "shows/harbor-lights/index.html"
    # Control: the swap is real, the show page's answer changes.
    assert _files(swapped)[page] != _files(doc)[page]
    assert _airing(swapped) == _airing(doc)


# --- which shows ------------------------------------------------------------


def _plan(doc: dict) -> airing_page.Plan:
    built = {s["id"]: f"{BASE}/shows/{s['slug']}/" for s in show_pages.select_shows(doc)}
    return airing_page.plan_airing(doc, built)


def _titles(plan: airing_page.Plan) -> dict[str, list[str]]:
    return {
        "premiere": [a.title for a in plan.premieres],
        "episode": [a.title for a in plan.episodes],
        "soap": [a.title for a in plan.soaps],
    }


def _every(plan: airing_page.Plan) -> list[str]:
    return [a.title for a in (*plan.premieres, *plan.episodes, *plan.soaps)]


def test_a_running_show_with_a_next_episode_is_listed_with_its_page(doc):
    text = _airing(doc)
    page = htmlprobe.parse(text)
    assert f"{BASE}/shows/harbor-lights/" in page.hrefs()
    assert (
        "Harbor Lights, Example Network. Next episode Sunday, September 20, 2026 "
        "(season 3, episode 4). LezWatch.TV lists 2 queer characters."
    ) in _lines(text)
    assert '<time datetime="2026-09-20">' in text


def test_a_season_premiere_is_called_out(doc):
    _show(doc, "harbor-lights")["schedule"]["next_episode"].update({"season": 4, "number": 1})
    plan = _plan(doc)
    assert _titles(plan)["premiere"] == ["Harbor Lights"]
    text = _airing(doc)
    assert "Season premieres" in " ".join(htmlprobe.parse(text).outside)
    assert (
        "Harbor Lights, Example Network. Season 4 premieres Sunday, September 20, 2026. "
        "LezWatch.TV lists 2 queer characters." in _lines(text)
    )


def test_soaps_are_under_their_own_heading_with_only_a_date(doc):
    show = _show(doc, "harbor-lights")
    show["genres"] = [{"slug": "soap-opera", "name": "Soap Opera"}]
    plan = _plan(doc)
    assert _titles(plan) == {"premiere": [], "episode": [], "soap": ["Harbor Lights"]}
    text = _airing(doc)
    assert "Soaps and telenovelas" in " ".join(htmlprobe.parse(text).outside)
    assert (
        "Harbor Lights, Example Network. Next episode Sunday, September 20, 2026. "
        "LezWatch.TV lists 2 queer characters." in _lines(text)
    )
    assert "season 3" not in text


def test_a_show_lezwatch_marks_off_air_is_left_out_and_logged(doc):
    # The Law & Order case: LezWatch.TV ends it, TVmaze lists a revival.
    _schedule(doc, "the-cartographers", "2026-10-01")
    assert _show(doc, "the-cartographers")["years"]["on_air"] == "no"
    plan = _plan(doc)
    assert "The Cartographers" not in _every(plan)
    assert any("left out The Cartographers" in n and "on air" in n for n in plan.notes)
    assert "The Cartographers" not in _visible(_airing(doc)).split("Browse")[0]


def test_a_show_lezwatch_ended_before_the_episode_is_left_out(doc):
    _schedule(doc, "the-cartographers", "2026-10-01", on_air="yes", end=2018)
    plan = _plan(doc)
    assert "The Cartographers" not in _every(plan)
    assert any("ends the show in 2018" in n for n in plan.notes)
    # Control: the same show with no end year is listed.
    _show(doc, "the-cartographers")["years"]["end"] = None
    assert "The Cartographers" in _titles(_plan(doc))["episode"]


@pytest.mark.parametrize(
    ("airdate", "listed"),
    [("2026-09-12", False), ("2026-09-13", True), ("2027-01-31", True), ("2027-02-01", False)],
)
def test_the_window_runs_from_the_snapshot_date_to_the_end_of_the_fourth_month(
    doc, airdate, listed
):
    _show(doc, "harbor-lights")["schedule"]["next_episode"]["airdate"] = airdate
    assert ("Harbor Lights" in _titles(_plan(doc))["episode"]) is listed


def test_window_end_and_dates():
    assert airing_page.window_end(dt.date(2026, 11, 5)) == dt.date(2027, 3, 31)
    assert airing_page.window_end(dt.date(2026, 12, 31)) == dt.date(2027, 4, 30)
    assert airing_page.window_end(dt.date(2027, 10, 1)) == dt.date(2028, 2, 29)
    assert airing_page.us_date(dt.date(2026, 11, 20)) == "Friday, November 20, 2026"
    assert airing_page.airing_title(dt.date(2027, 3, 31)) == (
        "Queer TV airing now: new episodes through March 2027"
    )


def test_order_is_by_date_then_title(doc):
    _schedule(doc, "night-shift-radio", "2026-09-20", on_air="yes")
    _schedule(doc, "salt-and-ember", "2026-09-15", on_air="yes")
    assert _titles(_plan(doc))["episode"] == ["Salt & Ember", "Harbor Lights", "Night Shift Radio"]


# --- absence ----------------------------------------------------------------


def test_a_show_with_no_date_is_left_out_with_no_placeholder(doc):
    night = _show(doc, "night-shift-radio")
    assert night["years"]["on_air"] == "yes" and night["schedule"]["next_episode"] is None
    text = " ".join(htmlprobe.parse(_airing(doc)).outside)
    assert "Night Shift Radio" not in text
    assert "That does not mean they are not coming back." in text
    for word in ("Not returning", "Unknown", "Not recorded", "None", "TBA"):
        assert word not in text


def test_missing_facts_shorten_the_line(doc):
    # No network, no episode number, no listed character, no page built.
    show = _schedule(doc, "night-shift-radio", "2026-09-22", number=None)
    show["networks"] = []
    show["schedule"]["network"] = show["schedule"]["web_channel"] = None
    page = htmlprobe.parse(_airing(doc))
    assert "Night Shift Radio (on LezWatch.TV). Next episode Tuesday, September 22, 2026." in (
        _lines(_airing(doc))
    )
    assert show["source_url"] in page.hrefs()
    assert f"{BASE}/shows/night-shift-radio/" not in page.hrefs()


def test_no_schedules_at_all_says_so_instead_of_an_empty_list(doc):
    for s in doc["shows"]:
        s["schedule"]["schedule_known"] = False
    text = " ".join(htmlprobe.parse(_airing(doc)).outside)
    assert "has no TVmaze schedules" in text
    assert "That does not mean no show is coming back." in text
    assert "Harbor Lights" not in text.split("Browse")[0]


def test_an_empty_window_says_nothing_is_listed_yet(doc):
    _show(doc, "harbor-lights")["schedule"]["next_episode"]["airdate"] = "2030-01-01"
    text = " ".join(htmlprobe.parse(_airing(doc)).outside)
    assert "TVmaze lists no new episode before" in text


# --- links, indexing, the app ------------------------------------------------


def test_every_link_to_a_show_page_resolves(doc):
    _schedule(doc, "salt-and-ember", "2026-09-15", on_air="yes")
    _schedule(doc, "night-shift-radio", "2026-09-16", on_air="yes")
    files = _files(doc)
    hrefs = htmlprobe.parse(files["airing/index.html"]).hrefs()
    shows = [h for h in hrefs if h.startswith(f"{BASE}/shows/") and h != f"{BASE}/shows/"]
    assert len(shows) == 2  # Harbor Lights and Salt & Ember; Night Shift Radio has no page
    for h in shows:
        assert f"{h.removeprefix(BASE + '/')}index.html" in files, h


def test_the_page_is_in_the_sitemap_and_open_to_search(doc):
    files = _files(doc)
    assert AIRING in htmlprobe.sitemap(files["sitemap.xml"])["loc"]
    page = htmlprobe.parse(files["airing/index.html"])
    assert page.canonical == AIRING
    assert [a for a in page.named("meta") if a.get("name") == "robots"] == []
    assert show_pages.index_problems(files, base_url=BASE) == []


def test_negative_control_a_noindex_airing_page_is_refused(doc):
    files = _files(doc)
    tagged = files["airing/index.html"].replace(
        "<title>", '<meta name="robots" content="noindex,follow">\n<title>', 1
    )
    assert tagged != files["airing/index.html"]  # the sabotage landed
    assert show_pages.index_problems({**files, "airing/index.html": tagged}, base_url=BASE)


def test_negative_control_an_airing_page_missing_from_the_sitemap_is_refused(doc):
    files = _files(doc)
    sitemap = files["sitemap.xml"].replace(f"<loc>{AIRING}</loc>", f"<loc>{BASE}/</loc>")
    assert sitemap != files["sitemap.xml"]  # the sabotage landed
    problems = show_pages.index_problems({**files, "sitemap.xml": sitemap}, base_url=BASE)
    assert any("does not list" in p and "/airing/" in p for p in problems)


def test_without_the_page_nothing_links_to_it_or_lists_it(doc, tmp_path):
    files = _files(doc, airing=False)
    assert "airing/index.html" not in files
    assert "/airing/" not in files["sitemap.xml"]
    assert "/airing/" not in files["shows/index.html"]
    assert show_pages.index_problems(files, base_url=BASE) == []
    # And a sitemap that lists it anyway is refused.
    stale = files["sitemap.xml"].replace("</urlset>", f"<url><loc>{AIRING}</loc></url></urlset>")
    assert show_pages.index_problems({**files, "sitemap.xml": stale}, base_url=BASE)


def test_the_shows_index_and_home_page_link_to_it(doc, tmp_path):
    show_pages.build_site(doc, tmp_path, base_url=BASE)
    site_index.write_site(doc, tmp_path / "index.html", base_url=BASE)
    for rel in ("index.html", "shows/index.html"):
        assert AIRING in htmlprobe.parse((tmp_path / rel).read_text()).hrefs(), rel
    # Control: with no airing page beside it, the home page does not link to it.
    (tmp_path / "airing" / "index.html").unlink()
    site_index.write_site(doc, tmp_path / "index.html", base_url=BASE)
    assert AIRING not in htmlprobe.parse((tmp_path / "index.html").read_text()).hrefs()


def test_switch_off_no_app_store_link_and_the_app_is_described(doc):
    text = _airing(doc)
    assert "apps.apple.com" not in text and "apple-itunes-app" not in text
    assert "It is not on the App Store yet." in " ".join(htmlprobe.parse(text).outside)
    assert "new-episode" in text and "Up Next widget" in text


def test_switch_on_links_the_plain_app_store_url_with_no_tracking(doc):
    text = _airing(doc, app_store_live=True)
    links = [h for h in htmlprobe.parse(text).hrefs() if "apple.com" in h]
    assert links == [APP_STORE_URL]
    assert "?" not in APP_STORE_URL and "ct=" not in text and "pt=" not in text
    assert text.count("apple-itunes-app") == 1


def test_no_script_image_or_request_to_another_host(doc):
    page = htmlprobe.parse(_airing(doc))
    assert [a.get("type") for a in page.named("script")] == ["application/ld+json"]
    for tag in ("img", "iframe", "form", "link"):
        if tag == "link":
            assert [a.get("rel") for a in page.named("link")] == ["canonical"]
        else:
            assert page.named(tag) == [], tag
    assert "analytics" not in _airing(doc).replace("has no analytics", "")


def test_two_builds_are_byte_identical(doc):
    assert _airing(doc) == _airing(copy.deepcopy(doc))


def test_the_description_and_title_fit(doc):
    page = htmlprobe.parse(_airing(doc))
    assert len(page.title) <= show_pages.TITLE_MAX
    assert len(page.description) <= airing_page.DESCRIPTION_MAX
    assert "1 TV shows" not in page.description
