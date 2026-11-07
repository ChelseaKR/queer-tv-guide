"""The findings page, its CSV and the press page (findings.py, DECISIONS 0042).

What must hold:

- ``compute`` places a death only on one unambiguous episode, and its
  counts and baselines are right on a hand-built show.
- Every figure on the pages comes from the committed data file through
  ``findings.view``: the templates hold no digit, and changing the data
  changes the page.
- No character, show or episode is named; the data file holds counts only.
- The non-binary result is not on the page or in the data.
- LezWatch.TV and TVmaze are credited and linked, and the page and the CSV
  carry CC BY-SA 4.0.
- The accessibility basics hold: one H1, no skipped heading level, captioned
  tables with header scopes, images with alt text and sizes, no script but
  structured data, nothing loaded from another host.

Every negative control asserts that its sabotage changed the page before it
asserts that the check caught it.
"""

from __future__ import annotations

import copy
import json
import re
from importlib import resources
from itertools import pairwise
from pathlib import Path

import pytest

from qtv_pipeline import findings, show_pages, site_index
from qtv_pipeline.app_store import APP_STORE_URL, PRICE
from tests import htmlprobe

REPO = Path(__file__).resolve().parents[2]
FIXTURE = REPO / "ios" / "GuideCore" / "Tests" / "Fixtures" / "snapshot.fixture.json"
BASE = "https://example.test"


@pytest.fixture
def doc() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture
def data() -> dict:
    return findings.load()


def _findings(doc: dict, data: dict) -> str:
    return findings.render_findings(doc, data, base_url=BASE)


def _press(doc: dict, data: dict, **kw) -> str:
    kw.setdefault("price", PRICE)
    kw.setdefault("platform", "iPhone")
    return findings.render_press(doc, data, base_url=BASE, **kw)


def _main(text: str) -> str:
    return text.split('<main id="main">', 1)[1].split("</main>", 1)[0]


def _main_text(text: str) -> str:
    return " ".join(htmlprobe.parse(f"<body>{_main(text)}</body>").outside)


# --- compute, on a hand-built show ------------------------------------------------


def _ep(season, number, airdate, kind="regular"):
    return {"season": season, "number": number, "airdate": airdate, "type": kind}


# Two seasons of four episodes, weekly; the last episode of season 2 airs the
# same day as a special, and a double bill closes season 1.
EPISODES = [
    _ep(1, 1, "2020-01-01"),
    _ep(1, 2, "2020-01-08"),
    _ep(1, 3, "2020-01-15"),
    _ep(1, 4, "2020-01-15"),
    _ep(2, 1, "2021-01-06"),
    _ep(2, 2, "2021-01-13"),
    _ep(2, 3, "2021-01-20"),
    _ep(2, 4, "2021-01-27"),
    _ep(2, None, "2021-02-03", kind="significant_special"),
]


def _toy(*deaths: tuple[str, str], status: str = "Ended") -> dict:
    """One show, one character per (date, role)."""
    show = {
        "id": "lwtv:show:1",
        "schedule": {"tvmaze_id": 7, "status": status, "network": {"name": "N"}},
    }
    chars = []
    for i, (date, role) in enumerate(deaths):
        year = int(date[:4])
        chars.append(
            {
                "death": {"died": True, "dates": [{"date": date, "year": year}]},
                "shows": [
                    {"show_id": "lwtv:show:1", "role": role, "years": ["2020", "2021"]},
                ],
                "name": f"c{i}",
            }
        )
    return {
        "generated_at": "2026-11-06T00:00:00Z",
        "content_digest": "sha256:x",
        "shows": [show],
        "characters": chars,
    }


def test_place_needs_one_unambiguous_regular_episode():
    assert findings.place("2020-01-08", EPISODES) == (1, 2)  # exact
    assert findings.place("2020-01-09", EPISODES) == (1, 2)  # one within a day
    assert findings.place("2020-01-15", EPISODES) is None  # double bill
    assert findings.place("2020-01-04", EPISODES) is None  # nothing near
    assert findings.place("2021-02-03", EPISODES) is None  # a special


def test_compute_counts_finales_baselines_and_series_finales():
    doc = _toy(
        ("2021-01-27", "regular"),  # season 2 finale and series finale
        ("2020-01-08", "regular"),  # mid-season
        ("2021-01-13", "guest"),  # mid-season
        ("2020-01-15", "guest"),  # double bill: not placed
        ("2019-05-05", "guest"),  # year outside the character's years: no event
    )
    out = findings.compute(doc, {7: EPISODES}, fetched_on="2026-11-06")
    assert out["death_events"] == 4 and out["placed"] == 3 and out["placed_shows"] == 1
    sf = out["season_finale"]
    assert (sf["all"]["deaths"], sf["all"]["in_position"]) == (3, 1)
    assert (sf["role:regular"]["deaths"], sf["role:regular"]["in_position"]) == (2, 1)
    assert (sf["role:guest"]["deaths"], sf["role:guest"]["in_position"]) == (1, 0)
    # 2 seasons over 8 regular episodes: a quarter of episodes are finales.
    assert sf["all"]["baseline"] == 0.25
    assert out["series_finale"] == {"deaths": 3, "in_position": 1, "baseline": 0.125}
    assert out["season_order"]["1"] == {"deaths": 3, "in_position": 1, "baseline": 0.5}
    assert out["season_order"]["2"]["in_position"] == 2
    assert out["regular_ci95"][0] < 0.5 < out["regular_ci95"][1]


def test_a_running_show_has_no_series_finale():
    out = findings.compute(
        _toy(("2021-01-27", "regular"), status="Running"), {7: EPISODES}, fetched_on="x"
    )
    assert out["series_finale"]["deaths"] == 0


def test_negative_control_shifted_dates_are_not_placed():
    """A matcher that places everything would pass the counts above by luck;
    moving every date three days must leave nothing placed."""
    real = _toy(("2021-01-27", "regular"), ("2020-01-08", "guest"))
    moved = copy.deepcopy(real)
    for c in moved["characters"]:
        d = c["death"]["dates"][0]
        d["date"] = d["date"][:-2] + f"{int(d['date'][-2:]) - 3:02d}"
    assert findings.compute(real, {7: EPISODES}, fetched_on="x")["placed"] == 2
    with pytest.raises(findings.FindingsError):  # no regular placed: no interval
        findings.compute(moved, {7: EPISODES}, fetched_on="x")


# --- the committed data file ----------------------------------------------------


def _strings(value) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for k, v in value.items() for s in (k, *_strings(v))]
    if isinstance(value, list):
        return [s for v in value for s in _strings(v)]
    return []


def test_the_data_file_holds_counts_only(data):
    allowed = re.compile(
        r"^(format|snapshot_generated_at|snapshot_content_digest|episodes_fetched_on|"
        r"death_events|placed|placed_shows|season_finale|regular_ci95|"
        r"most_finale_deaths_one_show|most_regular_finale_deaths_one_show|season_order|"
        r"series_finale|deaths|in_position|baseline|all|1|2|3\+|"
        r"role:(regular|recurring|guest)|(regular-)?era:(before 2010|2010 or later)|"
        r"(regular-)?release:(broadcast|streaming)|"
        r"\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2}Z)?|sha256:[0-9a-f]{64})$"
    )
    assert [s for s in _strings(data) if not allowed.match(s)] == []


def test_the_non_binary_result_is_not_published(doc, data):
    raw = findings.DEFAULT_FINDINGS_PATH.read_text(encoding="utf-8").lower()
    page = _findings(doc, data).lower()
    table = findings.findings_csv(data, licence_url="https://x.test/").lower()
    for word in ("non-binary", "nonbinary", "gender", "trans "):
        assert word not in raw and word not in page and word not in table, word


def test_load_refuses_a_file_of_another_shape(tmp_path, data):
    bad = copy.deepcopy(data)
    bad["season_finale"]["all"]["name"] = "someone"
    path = tmp_path / "f.json"
    path.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(findings.FindingsError):
        findings.load(path)


# --- figures come from the build ------------------------------------------------


@pytest.mark.parametrize("name", ["findings.html.j2", "press.html.j2"])
def test_the_templates_hold_no_typed_figure(name):
    src = resources.files("qtv_pipeline").joinpath(f"templates/{name}").read_text("utf-8")
    prose = re.sub(r"\{\{.*?\}\}|\{%.*?%\}|\{#.*?#\}|<[^>]*>", "", src, flags=re.S)
    assert re.findall(r"\d", prose) == []


def test_negative_control_a_typed_figure_is_caught():
    src = "<p>{{ v.regular.share }} of regulars, against 8% of episodes</p>"
    prose = re.sub(r"\{\{.*?\}\}|\{%.*?%\}|\{#.*?#\}|<[^>]*>", "", src, flags=re.S)
    assert re.findall(r"\d", prose) == ["8"]


def test_the_page_states_the_committed_figures(doc, data):
    text = _main_text(_findings(doc, data))
    reg = data["season_finale"]["role:regular"]
    assert findings.pct(reg["in_position"], reg["deaths"]) in text
    assert f"{reg['in_position']} of {reg['deaths']}" in text
    assert findings.pct(reg["baseline"]) in text
    s = data["series_finale"]
    assert f"{s['in_position']} of {s['deaths']}" in text


def test_changing_the_data_changes_the_page(doc, data):
    before = _findings(doc, data)
    changed = copy.deepcopy(data)
    changed["season_finale"]["role:regular"].update(deaths=200, in_position=20)
    changed["season_order"]["1"]["in_position"] = 1
    after = _findings(doc, changed)
    assert after != before
    assert "10% of queer TV regulars" in after and "20 of 200" in after


def test_published_figures_are_the_recomputed_ones(data):
    """The figures Chelsea approved on 2026-11-06, recomputed from that day's
    snapshot: if the data file is regenerated, this test is updated with it."""
    v = findings.view(data)
    assert (v["regular"]["share"], v["regular"]["baseline"]) == ("35%", "8%")
    assert (v["first_season"]["share"], v["first_season"]["episodes"]) == ("27%", "28%")
    assert (v["series"]["times"], v["guest"]["share"]) == ("3", "7%")


# --- spoilers, credits, license -------------------------------------------------


def named(text: str, doc: dict) -> list[str]:
    """Every character name and show title of ``doc`` on the page."""
    names = [c["name"] for c in doc["characters"]] + [s["title"] for s in doc["shows"]]
    return [n for n in names if n in text]


def test_no_character_or_show_is_named(doc, data):
    for text in (_findings(doc, data), _press(doc, data)):
        assert named(text, doc) == []
    assert named(findings.findings_csv(data, licence_url="https://x.test/"), doc) == []


def test_negative_control_a_planted_name_is_caught(doc, data):
    text = _findings(doc, data)
    planted = text.replace("</main>", f"<p>{doc['characters'][0]['name']}</p></main>")
    assert planted != text and named(planted, doc) == [doc["characters"][0]["name"]]


def test_credits_and_license_are_on_the_page_and_in_the_csv(doc, data):
    text = _findings(doc, data)
    main = _main(text)
    for a in doc["attribution"]:
        assert f'href="{a["url"]}"' in main, a["source"]
    assert "LezWatch.TV" in main and "TVmaze" in main
    licence = doc["licence"]["snapshot"]
    assert f'href="{licence["url"]}"' in main and licence["name"] in main
    assert f'href="{BASE}/{findings.CSV_PATH}"' in main
    table = findings.findings_csv(data, licence_url=licence["url"])
    head = table.splitlines()[0]
    assert "LezWatch.TV" in head and "TVmaze" in head and "CC BY-SA 4.0" in head
    assert licence["url"] in head


def test_the_page_is_dated_and_states_its_method_and_caveats(doc, data):
    text = _main_text(_findings(doc, data))
    v = findings.view(data)
    assert v["as_of"] in text and v["episodes_on"] in text
    for heading in ("How we counted", "Caveats", "A death", "A regular", "A season finale"):
        assert heading in text, heading


# --- titles, accessibility, requests ----------------------------------------------


def _heading_levels(text: str) -> list[int]:
    return [int(t[1]) for t, _ in htmlprobe.parse(text).tags if re.fullmatch(r"h[1-6]", t)]


@pytest.mark.parametrize("which", ["findings", "press"])
def test_accessibility_basics(doc, data, which):
    if which == "findings":
        text = _findings(doc, data)
    else:
        text = _press(doc, data, images=frozenset({"app-icon.png"}))
    page = htmlprobe.parse(text)
    assert page.lang == "en"
    levels = _heading_levels(_main(text))
    assert levels[0] == 1 and levels.count(1) == 1
    assert all(b - a <= 1 for a, b in pairwise(levels)), levels
    assert htmlprobe.duplicate_ids(page) == []
    for img in page.named("img"):
        assert img.get("alt") and img.get("width") and img.get("height")
    tables = page.named("table")
    assert len(page.named("caption")) == len(tables)
    assert all(th.get("scope") in {"col", "row"} for th in page.named("th"))
    assert [a.get("type") for a in page.named("script")] == ["application/ld+json"]
    assert htmlprobe.foreign_links(page, BASE) == []
    for img in page.named("img"):
        assert (img.get("src") or "").startswith(f"{BASE}/press/")


def test_negative_control_a_skipped_heading_level_is_caught(doc, data):
    text = _findings(doc, data)
    bad = text.replace('<h2 id="finales">', '<h4 id="finales">', 1)
    assert bad != text
    levels = _heading_levels(_main(bad))
    assert not all(b - a <= 1 for a, b in pairwise(levels))


def test_titles_h1_and_descriptions_are_their_own(doc, data):
    f, p = htmlprobe.parse(_findings(doc, data)), htmlprobe.parse(_press(doc, data))
    home = htmlprobe.parse(site_index.render_index(doc, base_url=BASE))
    assert len({f.title, p.title, home.title}) == 3
    assert len({f.description, p.description, home.description}) == 3
    for page in (f, p):
        assert len(page.title) <= show_pages.TITLE_MAX
        assert len(page.description) <= show_pages.DESCRIPTION_MAX
    assert f.canonical == f"{BASE}/findings/finales/" and p.canonical == f"{BASE}/press/"


# --- the press page ---------------------------------------------------------------


def test_press_page_facts(doc, data):
    text = _press(doc, data)
    main = _main_text(text)
    assert PRICE in main and "iPhone" in main and "one-time purchase" in main
    assert f'href="mailto:{findings.CONTACT_EMAIL}"' in text
    assert findings.headline(findings.view(data)) in main
    assert "None." in main  # data collected
    for a in doc["attribution"]:
        assert f'href="{a["url"]}"' in _main(text)
    assert APP_STORE_URL not in text and "Coming soon" in main


def test_press_page_links_the_app_store_when_the_switch_is_on(doc, data):
    text = _press(doc, data, app_store_live=True)
    assert f'href="{APP_STORE_URL}"' in _main(text) and "Coming soon" not in text


def test_press_images_are_the_repository_icon_and_screenshots(tmp_path):
    names = findings.copy_press_assets(tmp_path / "press")
    assert names == {n for n, *_ in findings.PRESS_ASSETS}
    for name, source, *_ in findings.PRESS_ASSETS:
        assert (tmp_path / "press" / name).read_bytes() == (REPO / source).read_bytes()
        assert source.startswith(("ios/QueerTVGuide/Assets.xcassets/AppIcon", "docs/app-store/"))


def test_a_missing_image_is_left_off_the_page(doc, data, tmp_path):
    assert findings.copy_press_assets(tmp_path / "press", tmp_path) == frozenset()
    assert htmlprobe.parse(_press(doc, data)).named("img") == []


# --- publishing ---------------------------------------------------------------------


def test_write_site_publishes_both_pages_the_csv_and_the_images(doc, tmp_path):
    written = site_index.write_site(doc, tmp_path / "index.html", base_url=BASE)
    for rel in (findings.FINDINGS_PATH, findings.CSV_PATH, findings.PRESS_PATH):
        assert tmp_path / rel in written and (tmp_path / rel).is_file()
    for name, *_ in findings.PRESS_ASSETS:
        assert (tmp_path / "press" / name).is_file()
    home = (tmp_path / "index.html").read_text(encoding="utf-8")
    footer = home.split("<footer>", 1)[1]
    assert f'href="{BASE}/findings/finales/"' in footer and f'href="{BASE}/press/"' in footer


def test_the_sitemap_lists_both_pages(doc):
    files = show_pages.render_site(doc, base_url=BASE)
    locs = htmlprobe.sitemap(files["sitemap.xml"])["loc"]
    assert f"{BASE}/findings/finales/" in locs and f"{BASE}/press/" in locs
    assert f'href="{BASE}/press/"' in files["shows/index.html"]


def test_negative_control_a_sitemap_without_them_is_refused(doc):
    files = show_pages.render_site(doc, base_url=BASE)
    bad = dict(files)
    bad["sitemap.xml"] = files["sitemap.xml"].replace(f"<loc>{BASE}/press/</loc>", "")
    assert bad["sitemap.xml"] != files["sitemap.xml"]
    assert f"the sitemap does not list {BASE}/press/" in show_pages.index_problems(
        bad, base_url=BASE
    )


def test_main_passes_the_switch_to_the_press_page(doc, tmp_path):
    snap = tmp_path / "s.json"
    snap.write_text(json.dumps(doc), encoding="utf-8")
    assert site_index.main([str(snap), str(tmp_path / "index.html"), "true"]) == 0
    assert APP_STORE_URL in (tmp_path / findings.PRESS_PATH).read_text(encoding="utf-8")
    assert site_index.main([str(snap)]) == 2
