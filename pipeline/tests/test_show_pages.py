"""The per-show web pages (qtv_pipeline/show_pages.py, DECISIONS 0019).

Pages are read with html.parser (tests/htmlprobe.py), never with a regex over
HTML. Every negative control asserts that its sabotage changed the page
before it asserts that the checker caught it; a sabotage that silently no-ops
would otherwise read as a pass.
"""

from __future__ import annotations

import copy
import html
import json
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from qtv_pipeline import app_store, show_pages
from tests import htmlprobe

REPO = Path(__file__).resolve().parents[2]
FIXTURE = REPO / "ios" / "GuideCore" / "Tests" / "Fixtures" / "snapshot.fixture.json"
BUNDLED = REPO / "ios" / "QueerTVGuide" / "Resources" / "snapshot.v1.json"
BASE = "https://example.test/qf"
ALLOWED_HOSTS = {
    "example.test",
    "lezwatchtv.com",
    "www.tvmaze.com",
    "creativecommons.org",
}


@pytest.fixture
def doc() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _build(doc: dict, tmp_path: Path, **kw) -> dict[str, htmlprobe.Page]:
    show_pages.build_site(doc, tmp_path, base_url=BASE, **kw)
    return {
        str(p.relative_to(tmp_path)): htmlprobe.parse(p.read_text(encoding="utf-8"))
        for p in sorted(tmp_path.rglob("index.html"))
    }


def _raw(tmp_path: Path, relative: str) -> str:
    return (tmp_path / relative).read_text(encoding="utf-8")


def _show(doc: dict, slug: str) -> dict:
    return next(s for s in doc["shows"] if s["slug"] == slug)


def _answers(doc: dict, slug: str) -> list[str]:
    """Every sentence that answers the question for one show."""
    show = _show(doc, slug)
    cast = show_pages._characters(doc, show)
    return [show_pages._answer(show, cast).headline, *[c.status for c in cast]]


# --- which shows ---------------------------------------------------------


def test_the_rule_is_most_listed_characters_then_lower_id(doc):
    chosen = [s["slug"] for s in show_pages.select_shows(doc)]
    # 2, 2 (tie, id 101 first), 1; the show with no listed character is out.
    assert chosen == ["harbor-lights", "the-cartographers", "salt-and-ember"]
    assert "night-shift-radio" not in chosen


def test_the_rule_counts_listed_characters_not_lezwatchs_tally(doc):
    for show in doc["shows"]:
        show["counts"]["characters"] = 99 if show["slug"] == "salt-and-ember" else 0
    assert show_pages.select_shows(doc)[0]["slug"] == "harbor-lights"


def test_limit_and_the_rule_constants(doc):
    assert [s["slug"] for s in show_pages.select_shows(doc, 2)] == [
        "harbor-lights",
        "the-cartographers",
    ]
    # DECISIONS 0025: at least 5 listed characters and a TVmaze match, at
    # most 600 pages, never fewer than 50 while 50 shows list a character.
    assert show_pages.MIN_LISTED == 5
    assert show_pages.DEFAULT_LIMIT == 600
    assert show_pages.PAGE_FLOOR == 50
    assert show_pages.PINNED_MAX == 50
    assert show_pages.DEFAULT_LIMIT < show_pages.SITEMAP_MAX_URLS


def test_an_unsafe_or_repeated_slug_refuses_a_small_build(doc):
    # One bad show of three is far over the 5% a build may leave out
    # (test_show_pages_rule.py has the skip itself, on a larger snapshot).
    bad = copy.deepcopy(doc)
    _show(bad, "harbor-lights")["slug"] = "../escape"
    with pytest.raises(show_pages.ShowPagesError, match="unsafe slug for a path"):
        show_pages.select_shows(bad)
    same = copy.deepcopy(doc)
    _show(same, "harbor-lights")["slug"] = "the-cartographers"
    with pytest.raises(show_pages.ShowPagesError, match="has the same slug"):
        show_pages.select_shows(same)


def test_percent_encoded_slugs_are_allowed(doc):
    _show(doc, "harbor-lights")["slug"] = "girl-rules-%e0%b8%81"
    assert "girl-rules-%e0%b8%81" in [s["slug"] for s in show_pages.select_shows(doc)]


def test_nothing_to_build_is_an_error(doc, tmp_path):
    doc["characters"] = []
    with pytest.raises(show_pages.ShowPagesError, match="nothing to build"):
        show_pages.build_site(doc, tmp_path)
    assert list(tmp_path.iterdir()) == []


# --- files, sitemap, head ------------------------------------------------


def test_files_and_sitemap(doc, tmp_path):
    pages = _build(doc, tmp_path)
    assert sorted(pages) == [
        "shows/harbor-lights/index.html",
        "shows/index.html",
        "shows/salt-and-ember/index.html",
        "shows/the-cartographers/index.html",
    ]
    entries = htmlprobe.sitemap(_raw(tmp_path, "sitemap.xml"))
    # The home page (site_index.py) first, then every page built here.
    assert entries["loc"][0] == f"{BASE}/"
    assert sorted(entries["loc"][1:]) == sorted(p.canonical for p in pages.values())
    assert set(entries["lastmod"]) == {doc["generated_at"][:10]}
    assert _raw(tmp_path, "sitemap.xml").startswith('<?xml version="1.0" encoding="UTF-8"?>')


def test_head_is_unique_and_within_limits(doc, tmp_path):
    pages = _build(doc, tmp_path)
    titles = [p.title for p in pages.values()]
    descriptions = [p.description for p in pages.values()]
    assert len(set(titles)) == len(titles) and len(set(descriptions)) == len(descriptions)
    assert all(0 < len(t) <= 60 for t in titles), titles
    assert all(0 < len(d) <= 155 for d in descriptions), descriptions
    for rel, page in pages.items():
        assert page.canonical == f"{BASE}/{rel.removesuffix('index.html')}"
        assert page.lang == "en"


def test_long_titles_are_fitted_not_overrun():
    name = "A Very Long Show Title That Goes On And On Forever And Ever Amen"
    assert len(show_pages.show_title(name)) <= 60
    assert len(show_pages.show_description(name)) <= 155
    assert show_pages.show_title(name).endswith("…")
    assert show_pages.show_title("Short") == "Do any queer characters die in Short? Spoiler-free"
    assert show_pages.show_title("Twenty Character Name") == (
        "Does she die in Twenty Character Name? Spoiler-free"
    )


def test_breadcrumb_json_ld_matches_the_visible_trail(doc, tmp_path):
    pages = _build(doc, tmp_path)
    page = pages["shows/the-cartographers/index.html"]
    assert len(page.ld_json) == 1
    assert json.loads(page.ld_json[0])["@context"] == "https://schema.org"
    items = htmlprobe.ld_node(page, "BreadcrumbList")["itemListElement"]
    assert [i["position"] for i in items] == [1, 2, 3]
    assert [i["name"] for i in items] == ["Queer Frame", "Shows", "The Cartographers"]
    assert items[-1]["item"] == page.canonical
    shown = [t for t in page.outside if t in ("Queer Frame", "Shows", "The Cartographers")]
    assert shown[-3:] == ["Queer Frame", "Shows", "The Cartographers"]


def test_a_title_cannot_break_out_of_the_page_or_the_json_ld(doc, tmp_path):
    _show(doc, "harbor-lights")["title"] = 'Evil </script><script>alert(1)</script> & "q"'
    pages = _build(doc, tmp_path)
    page = pages["shows/harbor-lights/index.html"]
    assert [a.get("type") for a in page.named("script")] == ["application/ld+json"]
    crumbs = htmlprobe.ld_node(page, "BreadcrumbList")["itemListElement"]
    assert crumbs[-1]["name"] == _show(doc, "harbor-lights")["title"]
    assert htmlprobe.ld_node(page, "TVSeries")["name"] == _show(doc, "harbor-lights")["title"]


# --- the answer ----------------------------------------------------------


def test_the_answer_is_one_closed_details_with_a_summary(doc, tmp_path):
    for page in _build(doc, tmp_path).values():
        if page.canonical.endswith("/shows/"):
            assert page.named("details") == []
            continue
        assert htmlprobe.details_problems(page) == []
        assert len(page.named("summary")) == 1


def test_the_answer_appears_only_inside_details(doc, tmp_path):
    pages = _build(doc, tmp_path)
    for slug in ("harbor-lights", "the-cartographers", "salt-and-ember"):
        page = pages[f"shows/{slug}/index.html"]
        answers = _answers(doc, slug)
        assert answers and all(any(a in t for t in page.inside) for a in answers)
        assert htmlprobe.answer_leaks(page, answers) == []
    dead = pages["shows/the-cartographers/index.html"]
    assert any("Dies (2017)." in t for t in dead.inside)
    assert not any("Dies" in t for t in dead.outside)
    assert "2017" not in dead.title + dead.description + "".join(dead.ld_json)


def test_death_revealing_terms_stay_inside_the_answer(doc, tmp_path):
    show = _show(doc, "the-cartographers")
    show["tropes"] = [{"slug": "dead-queers", "name": "Bury Your Queers"}]
    show["triggers"] = [{"slug": "death", "name": "Death"}]
    page = _build(doc, tmp_path)["shows/the-cartographers/index.html"]
    note = "LezWatch.TV tags this show “Bury Your Queers”."
    assert any(note in t for t in page.inside)
    everywhere = " ".join(page.outside) + page.title + page.description
    assert "Bury Your Queers" not in everywhere
    assert "Death" not in everywhere and "Dead" not in everywhere


def test_a_disagreeing_tally_is_stated_inside_the_answer(doc, tmp_path):
    _show(doc, "the-cartographers")["counts"]["deaths_source_reported"] = 3
    page = _build(doc, tmp_path)["shows/the-cartographers/index.html"]
    assert any(
        "own tally for this show is 3 deaths; its character records list 1" in t
        for t in page.inside
    )
    assert not any("tally" in t for t in page.outside)


def test_a_multi_show_character_says_the_record_is_not_per_show(doc, tmp_path):
    odile = next(c for c in doc["characters"] if c["name"] == "Odile Brandt")
    odile["shows"].append({"show_id": "lwtv:show:101", "role": "guest", "years": ["2021"]})
    page = _build(doc, tmp_path)["shows/the-cartographers/index.html"]
    assert any("not to one show" in t for t in page.inside)


def test_two_deaths_and_a_missing_year(doc):
    two = {"died": True, "death_known": True, "dates": [], "years": [2019, 2015]}
    assert show_pages._death_status(two, 0) == (True, "Dies more than once (2015, 2019).")
    none = {"died": True, "death_known": True, "dates": [], "years": []}
    assert show_pages._death_status(none, 0) == (True, "Dies (year not recorded).")


def test_headline_wording(doc):
    harbor = _show(doc, "harbor-lights")
    cast = show_pages._characters(doc, harbor)
    head = show_pages._answer(harbor, cast).headline
    assert head.startswith("Unknown. LezWatch.TV has no death on record for any of the 2 listed")
    one = show_pages._answer(harbor, cast[:1]).headline
    assert "the one listed character" in one
    carto = _show(doc, "the-cartographers")
    cast = show_pages._characters(doc, carto)
    answer = show_pages._answer(carto, cast)
    assert answer.headline == "Yes. 1 of 2 listed characters dies: Odile Brandt."
    assert any("For the other 1, the answer is unknown" in n for n in answer.notes)


# --- unknown is never "no" ----------------------------------------------


def test_unknown_renders_as_unknown_never_no(doc, tmp_path):
    pages = _build(doc, tmp_path)
    harbor = pages["shows/harbor-lights/index.html"]
    assert [k for k, _ in harbor.statuses] == ["unknown", "unknown"]
    assert all(t.startswith("Unknown.") for _, t in harbor.statuses)
    for page in pages.values():
        assert htmlprobe.no_for_unknown(page) == []


@pytest.mark.parametrize(
    "death",
    [
        {"died": None, "death_known": False, "dates": [], "years": []},
        {"died": False, "death_known": False, "dates": [], "years": []},  # the schema forbids false
        {"died": False, "death_known": True, "dates": [], "years": []},
        {"died": True, "death_known": False, "dates": [], "years": []},
        {"died": None, "death_known": True, "dates": [], "years": []},
    ],
)
def test_anything_but_a_recorded_death_is_unknown(death):
    dies, text = show_pages._death_status(death, 0)
    assert dies is False
    assert text.startswith("Unknown.") and not text.startswith("No")


def test_negative_control_no_for_unknown_is_caught(doc, tmp_path):
    good = _build(doc, tmp_path)
    raw = _raw(tmp_path, "shows/harbor-lights/index.html")
    bad_raw = raw.replace(
        "Unknown. LezWatch.TV has not recorded", "No. LezWatch.TV has not recorded"
    )
    assert bad_raw != raw  # the sabotage applied
    assert htmlprobe.no_for_unknown(good["shows/harbor-lights/index.html"]) == []
    caught = htmlprobe.no_for_unknown(htmlprobe.parse(bad_raw))
    assert len(caught) == 2 and all(t.startswith("No.") for t in caught)


def test_negative_control_a_closed_answer_outside_details_is_caught(doc, tmp_path):
    pages = _build(doc, tmp_path)
    page = pages["shows/the-cartographers/index.html"]
    answers = _answers(doc, "the-cartographers")
    raw = _raw(tmp_path, "shows/the-cartographers/index.html")
    bad_raw = raw.replace("<details", "<div").replace("</details>", "</div>")
    assert bad_raw != raw  # the sabotage applied
    assert htmlprobe.answer_leaks(page, answers) == []
    assert htmlprobe.answer_leaks(htmlprobe.parse(bad_raw), answers) == answers
    # Two ways to leave it open, and both are seen.
    open_raw = raw.replace('<details class="answer">', '<details class="answer" open>')
    assert open_raw != raw
    assert htmlprobe.details_problems(page) == []
    assert htmlprobe.details_problems(htmlprobe.parse(open_raw)) == ["a <details> is open on load"]
    assert htmlprobe.details_problems(htmlprobe.parse(bad_raw)) != []


def test_negative_control_a_leaking_title_is_caught(doc, tmp_path):
    pages = _build(doc, tmp_path)
    page = pages["shows/the-cartographers/index.html"]
    answers = _answers(doc, "the-cartographers")
    raw = _raw(tmp_path, "shows/the-cartographers/index.html")
    bad_raw = raw.replace("<title>Do ", "<title>" + answers[0] + " Do ")
    assert bad_raw != raw
    assert htmlprobe.answer_leaks(page, answers) == []
    assert htmlprobe.answer_leaks(htmlprobe.parse(bad_raw), answers) == [answers[0]]


# --- facts: absence is stated, never a number ----------------------------


def _facts(page: htmlprobe.Page) -> dict[str, str]:
    assert len(page.facts) == 8  # the denominator: every fact row was read
    return page.facts


def test_facts_from_the_snapshot(doc, tmp_path):
    facts = _facts(_build(doc, tmp_path)["shows/the-cartographers/index.html"])
    assert facts["Years"] == "2016 to 2018"
    assert facts["Seasons"] == "2"
    assert facts["Network"] == "Example Network, Another Example"
    assert facts["Worth it, per LezWatch.TV"] == "Meh"


def test_missing_values_say_not_recorded_or_unknown(doc, tmp_path):
    facts = _facts(_build(doc, tmp_path)["shows/salt-and-ember/index.html"])
    assert facts["Years"] == "Not recorded"
    assert facts["Seasons"] == "Not recorded"
    assert facts["Network"] == "Not recorded"
    assert facts["Worth it, per LezWatch.TV"] == "Not rated"
    assert facts["Run status, per TVmaze"] == "Unknown"
    assert "0" not in facts["Seasons"]


def test_years_wording():
    y = show_pages._years
    assert y({"start": 2021, "end": None, "on_air": "yes"}) == "2021 to present"
    assert y({"start": 2021, "end": None, "on_air": "unknown"}) == "2021 (end year not recorded)"
    assert y({"start": 2021, "end": 2021, "on_air": "no"}) == "2021"


def test_network_falls_back_to_tvmaze(doc, tmp_path):
    show = _show(doc, "harbor-lights")
    show["networks"] = []
    show["schedule"]["network"] = None
    show["schedule"]["web_channel"] = {"name": "Streamer", "country_code": None}
    assert dict(show_pages._facts(show))["Network"] == "Streamer"


def test_characters_list_outside_the_answer_has_no_status(doc, tmp_path):
    page = _build(doc, tmp_path)["shows/the-cartographers/index.html"]
    assert "LGBTQ characters in The Cartographers" in page.outside
    assert any(t.startswith("Role: Regular. Gender:") or "Role: " in t for t in page.outside)
    assert not any("Unknown." in t or "Dies" in t for t in page.outside)


# --- credits and links ---------------------------------------------------


def test_every_page_credits_both_sources_with_their_licenses(doc, tmp_path):
    pages = _build(doc, tmp_path)
    for rel, page in pages.items():
        text = " ".join(page.outside)
        for a in doc["attribution"]:
            assert a["text"] in text, (rel, a["source"])
            assert a["licence_name"] in text
            assert a["licence_url"] in page.hrefs()
            assert a["terms_url"] in page.hrefs()
            assert a["url"] in page.hrefs()
        assert doc["licence"]["notice"] in text
        assert "LezWatch.TV and TVmaze do not endorse Queer Frame." in text
        assert doc["licence"]["snapshot"]["url"] in page.hrefs()


def test_each_show_links_back_to_its_lezwatch_and_tvmaze_pages(doc, tmp_path):
    page = _build(doc, tmp_path)["shows/the-cartographers/index.html"]
    show = _show(doc, "the-cartographers")
    assert show["source_url"] in page.hrefs()
    assert "View The Cartographers on LezWatch.TV" in page.outside
    assert show["schedule"]["tvmaze_url"] in page.hrefs()
    for c in doc["characters"]:
        if c["shows"][0]["show_id"] == show["id"]:
            assert c["source_url"] in page.hrefs()
    unknown = _build(doc, tmp_path / "x")["shows/salt-and-ember/index.html"]
    assert "https://www.tvmaze.com/" in unknown.hrefs()


# --- no analytics, no third-party requests, no cookies -------------------


def test_pages_load_nothing_and_set_nothing(doc, tmp_path):
    pages = _build(doc, tmp_path)
    for rel, page in pages.items():
        scripts = page.named("script")
        assert [s.get("type") for s in scripts] == ["application/ld+json"], rel
        assert all("src" not in s for s in scripts)
        for forbidden in ("img", "iframe", "form", "input", "video", "audio", "object", "embed"):
            assert page.named(forbidden) == [], (rel, forbidden)
        assert [a for a in page.named("link") if a.get("rel") != "canonical"] == []
        assert [a for t, a in page.tags if "src" in a or "srcset" in a] == []
        assert [a for t, a in page.tags if any(k.startswith("on") for k in a)] == []
        assert [a for a in page.named("meta") if a.get("http-equiv")] == []
        assert "url(" not in page.css and "@import" not in page.css
        hosts = {urlsplit(h).hostname for h in page.hrefs() if h.startswith("http")}
        assert hosts <= ALLOWED_HOSTS, (rel, hosts - ALLOWED_HOSTS)
        assert not any("analytics" in h or "google" in h for h in page.hrefs())


def test_colors_are_the_browsers_own_system_colors(doc, tmp_path):
    # The privacy and support pages use CanvasText and LinkText; reusing the
    # system colors keeps their contrast in light, dark and high-contrast.
    css = _build(doc, tmp_path)["shows/harbor-lights/index.html"].css
    assert "#" not in css and "rgb" not in css and "hsl" not in css
    for token in ("Canvas", "CanvasText", "LinkText", "VisitedText", "color-scheme: light dark"):
        assert token in css
    assert "opacity" not in css


# --- accessibility basics ------------------------------------------------


def test_landmarks_headings_and_skip_link(doc, tmp_path):
    for rel, page in _build(doc, tmp_path).items():
        names = [t for t, _ in page.tags]
        for landmark in ("header", "main", "footer"):
            assert names.count(landmark) == 1, (rel, landmark)
        # The breadcrumb everywhere; the shows index adds its letter list.
        labels = [n.get("aria-label") for n in page.named("nav")]
        want = ["Breadcrumb", "Jump to a letter"] if rel == "shows/index.html" else ["Breadcrumb"]
        assert labels == want, rel
        assert page.headings.count(1) == 1 and page.headings[0] == 1
        # No skipped level: each heading is at most one deeper than the last.
        assert all(b - a <= 1 for a, b in zip(page.headings, page.headings[1:], strict=False))
        nav = page.named("nav")[0]
        assert nav["aria-label"] == "Breadcrumb"
        skip = next(a for a in page.named("a") if a.get("class") == "skip")
        assert skip["href"] == "#main" and "main" in page.ids
        assert [a for a in page.named("span") if a.get("aria-current") == "page"]
        assert any(a.get("name") == "viewport" for a in page.named("meta"))


# --- the App Store link --------------------------------------------------


def _banners(page: htmlprobe.Page) -> list[dict]:
    return [a for a in page.named("meta") if a.get("name") == "apple-itunes-app"]


def test_no_app_link_while_the_switch_is_off(doc, tmp_path):
    for rel, page in _build(doc, tmp_path).items():
        assert not any("Get the app" in t for t in page.outside), rel
        assert not any("apple.com" in h for h in page.hrefs())
        assert _banners(page) == [], rel
        assert "apple-itunes-app" not in _raw(tmp_path, rel)


def test_app_link_uses_the_existing_constant_when_on(doc, tmp_path):
    pages = _build(doc, tmp_path, app_store_live=True)
    for rel, page in pages.items():
        assert page.hrefs().count(app_store.APP_STORE_URL) == 1, rel
        assert sum("Get the app" in t for t in page.outside) == 1, rel
        # The link says where it goes and what it costs, from app_store.py.
        assert app_store.PRICE_COPY in page.outside, rel
    # Not inside the spoiler: opening the answer is not a sales pitch.
    inside = pages["shows/the-cartographers/index.html"].inside
    assert not any("Get the app" in t or app_store.PRICE_COPY in t for t in inside)


def test_smart_app_banner_on_every_built_page_when_on(doc, tmp_path):
    pages = _build(doc, tmp_path, app_store_live=True)
    for rel, page in pages.items():
        banners = _banners(page)
        assert banners == [
            {"name": "apple-itunes-app", "content": f"app-id={app_store.APP_STORE_ID}"}
        ]
        assert _raw(tmp_path, rel).count(app_store.BANNER) == 1, rel


def test_app_store_step_does_not_add_a_second_banner_to_show_pages(doc, tmp_path):
    # snapshot.yml runs app_store.apply over the site after the show pages are
    # built; it reads only the top-level pages, so the show pages keep one tag.
    _build(doc, tmp_path, app_store_live=True)
    (tmp_path / "index.html").write_text(
        f"<html><head>{app_store.VIEWPORT}</head><body>{app_store.INDEX_SLOT}</body></html>",
        encoding="utf-8",
    )
    app_store.apply(tmp_path)
    for rel in ("shows/index.html", "shows/harbor-lights/index.html"):
        assert _raw(tmp_path, rel).count("apple-itunes-app") == 1, rel


# --- spoiler warning -----------------------------------------------------


def test_a_spoiler_warning_comes_before_the_answer(doc, tmp_path):
    pages = _build(doc, tmp_path)
    for rel, page in pages.items():
        if rel == "shows/index.html":
            continue
        raw = _raw(tmp_path, rel)
        warning = raw.find('<p class="spoiler-warning">')
        assert warning != -1, rel
        assert raw.count('<p class="spoiler-warning">') == 1, rel
        assert warning < raw.find("<details"), rel
        assert "Spoiler warning:" in page.outside and "Spoiler warning:" not in page.inside


def test_the_spoiler_warning_reveals_nothing(doc, tmp_path):
    pages = _build(doc, tmp_path)
    for slug in ("harbor-lights", "the-cartographers", "salt-and-ember"):
        raw = _raw(tmp_path, f"shows/{slug}/index.html")
        start = raw.find('<p class="spoiler-warning">')
        warning = raw[start : raw.find("</p>", start)]
        for sentence in _answers(doc, slug):
            assert sentence not in warning
        for name in (c.name for c in show_pages._characters(doc, _show(doc, slug))):
            assert name not in warning
    assert pages


# --- links between show pages ---------------------------------------------


def test_neighbors_wrap_and_never_repeat():
    shows = [{"slug": x, "title": x.upper()} for x in "abc"]
    assert show_pages.neighbors(shows, 0) == [shows[2], shows[1]]
    assert show_pages.neighbors(shows, 2) == [shows[1], shows[0]]
    assert show_pages.neighbors(shows[:2], 0) == [shows[1]]
    assert show_pages.neighbors(shows[:1], 0) == []


def test_each_show_page_links_to_its_neighbors_and_the_index(doc, tmp_path):
    pages = _build(doc, tmp_path)
    order = [s["slug"] for s in show_pages.select_shows(doc)]
    inbound: dict[str, int] = dict.fromkeys(order, 0)
    for i, slug in enumerate(order):
        page = pages[f"shows/{slug}/index.html"]
        hrefs = page.hrefs()
        for other in (order[i - 1], order[(i + 1) % len(order)]):
            assert f"{BASE}/shows/{other}/" in hrefs, (slug, other)
        assert f"All {len(order)} shows" in page.outside
        for other in order:
            if other != slug and f"{BASE}/shows/{other}/" in hrefs:
                inbound[other] += 1
        # A page never links to itself (its breadcrumb item is plain text).
        assert f"{BASE}/shows/{slug}/" not in hrefs, slug
    assert all(n >= 2 for n in inbound.values()), inbound


def test_more_shows_links_are_titles_only(doc, tmp_path):
    pages = _build(doc, tmp_path)
    titles = {s["title"] for s in show_pages.select_shows(doc)}
    raw = _raw(tmp_path, "shows/harbor-lights/index.html")
    block = raw[raw.find('<ul class="more">') : raw.find("</ul>", raw.find('<ul class="more">'))]
    for line in block.splitlines()[1:-1]:
        text = html.unescape(line.split(">", 2)[2].rsplit("</a>", 1)[0])
        assert text in titles, text
    assert pages


# --- command line --------------------------------------------------------


def test_cli_builds_and_refuses(doc, tmp_path, capsys):
    snap = tmp_path / "snap.json"
    snap.write_text(json.dumps(doc), encoding="utf-8")
    out = tmp_path / "out"
    assert show_pages.main([str(snap), str(out), "--base-url", BASE + "/", "--limit", "2"]) == 0
    assert "wrote 5 files" in capsys.readouterr().out
    assert (out / "shows" / "harbor-lights" / "index.html").is_file()
    assert not (out / "shows" / "salt-and-ember").exists()

    refused = tmp_path / "refused"
    for argv in (
        [str(snap), str(refused), "--app-store-live", "yes"],
        [str(snap), str(refused), "--base-url", "http://insecure.test"],
        [str(snap), str(refused), "--base-url", "https://x.test/?a=b"],
        [str(tmp_path / "missing.json"), str(refused)],
    ):
        assert show_pages.main(argv) == 1, argv
        assert "show_pages: refused" in capsys.readouterr().err
    assert not refused.exists()


# --- the policy pages stay true ------------------------------------------


def test_privacy_page_describes_the_website(tmp_path):
    page = htmlprobe.parse((REPO / "docs" / "site" / "privacy.html").read_text(encoding="utf-8"))
    text = " ".join(page.outside)
    assert "This website" in text
    for claim in ("no cookies", "no analytics", "runs no code", "GitHub", "other site"):
        assert claim in text
    # The claims it makes are the ones the pages keep: see
    # test_pages_load_nothing_and_set_nothing.


@pytest.mark.skipif(not BUNDLED.is_file(), reason="needs `make -C ios bundle-snapshot`")
def test_a_few_hundred_pages_from_the_real_snapshot(tmp_path):
    """DECISIONS 0025 on a published snapshot: the pinned list plus every
    show with 5 or more listed characters and a TVmaze match. That was 361
    pages on the 2026-09-18 file and 363 on 2026-10-29; the bundled file is
    refreshed on demand, so the count is derived and held to a range."""
    real = json.loads(BUNDLED.read_text(encoding="utf-8"))
    pins = show_pages.load_pinned(show_pages.DEFAULT_PINNED_PATH)
    pages = _build(real, tmp_path, pinned=pins)
    listed = show_pages._listed_characters(real)
    by_id = {s["lwtv_id"]: s for s in real["shows"]}
    want = {s["id"] for s in real["shows"] if show_pages.qualifies(s, listed)}
    want |= {
        by_id[p.lezwatch_id]["id"]
        for p in pins or []
        if p.lezwatch_id in by_id and listed.get(by_id[p.lezwatch_id]["id"])
    }
    assert 300 <= len(want) <= show_pages.DEFAULT_LIMIT  # a few hundred, not all 2,287
    assert len(pages) == len(want) + 1
    assert len({p.title for p in pages.values()}) == len(pages)
    assert len(htmlprobe.sitemap(_raw(tmp_path, "sitemap.xml"))["loc"]) == len(pages) + 1
    items = htmlprobe.ld_node(pages["shows/index.html"], "ItemList")["itemListElement"]
    assert len(items) == len(want)
    index_links = [h for h in pages["shows/index.html"].hrefs() if h.endswith("/")]
    for rel in pages:
        if rel != "shows/index.html":
            assert rel.removeprefix("shows/").removesuffix("index.html") in index_links, rel
    by_slug = {s["slug"]: s for s in real["shows"]}
    for rel, page in pages.items():
        assert len(page.title) <= 60 and len(page.description) <= 155, rel
        assert htmlprobe.no_for_unknown(page) == [], rel
        assert "FAQPage" not in "".join(page.ld_json), rel
        assert [s.get("type") for s in page.named("script")] == ["application/ld+json"], rel
        assert page.named("img") == [] and not _banners(page), rel
        text = " ".join(page.outside)
        for a in real["attribution"]:
            assert a["licence_url"] in page.hrefs() and a["url"] in page.hrefs(), rel
            assert a["text"] in text, rel
        if rel == "shows/index.html":
            continue
        assert htmlprobe.details_problems(page) == [], rel
        show = by_slug[rel.split("/")[1]]
        cast = show_pages._characters(real, show)
        answers = [show_pages._answer(show, cast).headline, *[c.status for c in cast]]
        assert htmlprobe.answer_leaks(page, answers) == [], rel


# --- words for search (DECISIONS 0024) -----------------------------------


def test_title_and_description_ask_the_question_and_name_the_characters(doc, tmp_path):
    page = _build(doc, tmp_path)["shows/the-cartographers/index.html"]
    assert page.title == "Do queer characters die in The Cartographers? Spoiler-free"
    # Regulars first, then recurring: the order never depends on a death.
    assert page.description == (
        "Does she die in The Cartographers? LezWatch.TV lists 2 LGBTQ characters: "
        "Odile Brandt and Thea Marsh. The answer stays hidden until you open it."
    )
    assert "Do any queer characters die in The Cartographers?" in page.outside
    assert "LGBTQ characters in The Cartographers" in page.outside
    assert any("bury-your-gays trope" in t for t in page.outside)


def test_description_lists_regulars_first_whatever_the_deaths(doc, tmp_path):
    # Swap who died: the description must not change, or it would be a hint.
    first = _build(doc, tmp_path / "a")["shows/the-cartographers/index.html"].description
    for c in doc["characters"]:
        if c["name"] in ("Odile Brandt", "Thea Marsh"):
            died = c["name"] == "Thea Marsh"
            c["death"] = {
                "death_known": died,
                "died": died if died else None,
                "years": [2017] if died else [],
                "dates": [],
            }
    second = _build(doc, tmp_path / "b")["shows/the-cartographers/index.html"].description
    assert first == second


def test_description_falls_back_to_fewer_names():
    names = ["Alexandra Longname", "Bernadette Longname", "Cordelia Long"]
    text = show_pages.show_description("A Fairly Long Show Title", names, 12)
    assert len(text) <= 155
    assert "lists include Alexandra Longname. The answer" in text
    assert show_pages.show_description("Solo", ["Ana"], 1) == (
        "Does she die in Solo? LezWatch.TV lists one LGBTQ character: Ana. "
        "The answer stays hidden until you open it."
    )
    assert show_pages.show_description("Bare") == (
        "Does she die in Bare? The answer stays hidden until you open it."
    )


def test_tvseries_structured_data_has_facts_and_no_answer(doc, tmp_path):
    pages = _build(doc, tmp_path)
    page = pages["shows/the-cartographers/index.html"]
    show = _show(doc, "the-cartographers")
    series = htmlprobe.ld_node(page, "TVSeries")
    assert series["url"] == page.canonical
    assert series["sameAs"] == [show["source_url"], show["schedule"]["tvmaze_url"]]
    assert series["startDate"] == "2016" and series["endDate"] == "2018"
    assert series["numberOfSeasons"] == 2
    assert [c["name"] for c in series["character"]] == ["Odile Brandt", "Thea Marsh"]
    assert set(series["character"][0]) == {"@type", "name"}
    ld = "".join(page.ld_json)
    for word in ("Dies", "dies", "dead", "Dead", "death", "Death", "Unknown"):
        assert word not in ld, word
    # No FAQPage: its answer would be the spoiler.
    for p in pages.values():
        assert "FAQPage" not in "".join(p.ld_json)
    # A show with nothing recorded gets no invented facts.
    bare = htmlprobe.ld_node(pages["shows/salt-and-ember/index.html"], "TVSeries")
    for key in ("startDate", "endDate", "numberOfSeasons", "countryOfOrigin"):
        assert key not in bare, key


def test_index_lists_every_show_in_structured_data(doc, tmp_path):
    pages = _build(doc, tmp_path)
    items = htmlprobe.ld_node(pages["shows/index.html"], "ItemList")["itemListElement"]
    built = [s["slug"] for s in show_pages.select_shows(doc)]
    assert [i["url"] for i in items] == [f"{BASE}/shows/{s}/" for s in built]
    assert [i["position"] for i in items] == list(range(1, len(built) + 1))


def _mini(slug: str, genres: list[str], similar: list[str] | None = None) -> dict:
    return {
        "id": slug,
        "slug": slug,
        "title": slug.upper(),
        "genres": [{"slug": g, "name": g} for g in genres],
        "similar_show_ids": similar or [],
    }


def test_related_prefers_lezwatch_similar_then_shared_genres():
    shows = [
        _mini("a", ["drama", "teen"], similar=["f", "b", "zz"]),
        _mini("b", ["drama"]),
        _mini("c", ["comedy"]),
        _mini("d", ["drama", "teen"]),
        _mini("e", ["drama"]),
        _mini("f", ["western"]),
        _mini("g", ["drama", "teen", "school"]),
        _mini("h", ["drama"]),
    ]
    got = [s["slug"] for s in show_pages.related(shows, 0)]
    # f is LezWatch-similar; b is similar but already a neighbor (as is h);
    # zz has no page; then the most shared genres, ties in published order;
    # c shares nothing and is never picked.
    assert got == ["f", "d", "g", "e"]
    assert len(show_pages.related(shows, 2)) == 0  # comedy shares with nobody


def test_similar_links_render_as_titles_only(doc, tmp_path):
    pages = _build(doc, tmp_path)
    # Three built shows: both others are neighbors, so no similar block.
    assert "Shows like Harbor Lights" not in pages["shows/harbor-lights/index.html"].outside
    big = copy.deepcopy(doc)
    for n in range(4):
        extra = copy.deepcopy(_show(big, "harbor-lights"))
        extra.update(id=f"lwtv:show:9{n}", lwtv_id=900 + n, slug=f"extra-{n}", title=f"Extra {n}")
        big["shows"].append(extra)
        for c in list(big["characters"]):
            if c["shows"][0]["show_id"] == "lwtv:show:101":
                twin = copy.deepcopy(c)
                twin["shows"][0]["show_id"] = extra["id"]
                twin["lwtv_id"] += 1000 * (n + 1)
                big["characters"].append(twin)
    page = _build(big, tmp_path / "big")["shows/the-cartographers/index.html"]
    assert "Shows like The Cartographers" not in page.outside  # shares no genre
    page = _build(big, tmp_path / "big2")["shows/extra-1/index.html"]
    assert "Shows like Extra 1" in page.outside
    raw = _raw(tmp_path / "big2", "shows/extra-1/index.html")
    block = raw[
        raw.find('<ul class="similar">') : raw.find("</ul>", raw.find('<ul class="similar">'))
    ]
    titles = {s["title"] for s in big["shows"]}
    lines = block.splitlines()[1:]
    assert lines
    for line in lines:
        assert html.unescape(line.split(">", 2)[2].rsplit("</a>", 1)[0]) in titles


def test_app_note_without_a_link_while_the_switch_is_off(doc, tmp_path):
    off = _build(doc, tmp_path / "off")["shows/harbor-lights/index.html"]
    note = "Queer Frame is also an iPhone app built from the same records. It is not on the App Store yet."
    assert note in off.outside
    on = _build(doc, tmp_path / "on", app_store_live=True)["shows/harbor-lights/index.html"]
    assert note not in on.outside
