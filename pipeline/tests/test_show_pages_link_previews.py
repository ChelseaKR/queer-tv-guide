"""Link-preview tags on the show pages, the shows index and the airing page
(DECISIONS 0064).

The home, findings and press pages already carried Open Graph tags; the pages
people are most likely to share did not, so a pasted show link drew a bare
address. The tags repeat the page's own title, description and canonical
address and add nothing: no image, no answer, no new sentence. Every negative
control asserts that its sabotage changed the page before it asserts that the
check caught it.
"""

from __future__ import annotations

import html
import json
from pathlib import Path

import pytest

from qtv_pipeline import show_pages
from tests import htmlprobe

REPO = Path(__file__).resolve().parents[2]
FIXTURE = REPO / "ios" / "GuideCore" / "Tests" / "Fixtures" / "snapshot.fixture.json"
BASE = "https://example.test/qf"
EXPECTED = ("og:type", "og:site_name", "og:title", "og:description", "og:url", "og:locale")
NEVER = ("og:image", "og:video", "og:audio")


@pytest.fixture
def doc() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _files(doc: dict, **kw) -> dict[str, str]:
    return show_pages.render_site(doc, base_url=BASE, **kw)


def _pages(files: dict[str, str]) -> dict[str, htmlprobe.Page]:
    return {path: htmlprobe.parse(text) for path, text in files.items() if path.endswith(".html")}


def _og(page: htmlprobe.Page) -> list[tuple[str, str]]:
    return [
        (a.get("property") or "", a.get("content") or "")
        for a in page.named("meta")
        if a.get("property")
    ]


def preview_problems(page: htmlprobe.Page) -> list[str]:
    """What is wrong with one page's link-preview tags; empty when they repeat
    the page's own title, description and address and carry nothing else."""
    tags = _og(page)
    og = dict(tags)
    found = []
    if [k for k, _ in tags] != list(EXPECTED):
        found.append(f"tags are {[k for k, _ in tags]}")
    if og.get("og:title") != page.title:
        found.append("og:title is not the page title")
    if og.get("og:description") != page.description:
        found.append("og:description is not the page description")
    if og.get("og:url") != page.canonical or not page.canonical:
        found.append("og:url is not the canonical address")
    if og.get("og:site_name") != show_pages.SITE_NAME:
        found.append("og:site_name is not the site name")
    found += [f"{k} is present" for k in NEVER if k in og]
    cards = [a.get("content") for a in page.named("meta") if a.get("name") == "twitter:card"]
    if cards != ["summary"]:
        found.append(f"twitter:card is {cards}")
    return found


def test_every_show_page_the_index_and_the_airing_page_carry_the_tags(doc):
    pages = _pages(_files(doc))
    shows = [p for p in pages if p.startswith("shows/") and p != "shows/index.html"]
    assert len(shows) == len(show_pages.select_shows(doc)) and shows
    for path in [*shows, "shows/index.html", show_pages.AIRING_PATH]:
        assert preview_problems(pages[path]) == [], path


def test_the_tags_repeat_the_title_and_description_and_nothing_else(doc):
    page = _pages(_files(doc))["shows/harbor-lights/index.html"]
    og = dict(_og(page))
    assert og["og:title"] == page.title
    assert og["og:description"] == page.description
    assert og["og:url"] == f"{BASE}/shows/harbor-lights/"
    assert og["og:type"] == "website" and og["og:locale"] == "en_US"
    assert 0 < len(og["og:title"]) <= show_pages.TITLE_MAX
    assert 0 < len(og["og:description"]) <= show_pages.DESCRIPTION_MAX


def _secrets(doc: dict, show: dict) -> list[str]:
    """The sealed answer's sentences and each dying character's status."""
    cast = show_pages._characters(doc, show)
    answer = show_pages._answer(show, cast)
    return [answer.headline, *answer.notes, *(c.status for c in cast if c.dies)]


def leaked(doc: dict, show: dict, page: htmlprobe.Page) -> list[str]:
    """Every sealed sentence that appears in one of the page's preview tags."""
    return [s for s in _secrets(doc, show) for _, content in _og(page) if s in content]


def test_no_answer_reaches_a_link_preview(doc):
    """The sealed answer's sentences and each status appear in no preview tag,
    on a show where a listed character dies."""
    files = _files(doc)
    dying = []
    for show in show_pages.select_shows(doc):
        if not any(c.dies for c in show_pages._characters(doc, show)):
            continue
        dying.append(show["slug"])
        raw = files[f"shows/{show['slug']}/index.html"]
        assert leaked(doc, show, htmlprobe.parse(raw)) == [], show["slug"]
        # Negative control: the headline in the preview description is caught.
        headline = _secrets(doc, show)[0]
        marker = '<meta property="og:description" content="'
        broken = raw.replace(marker, f"{marker}{html.escape(headline)} ", 1)
        assert broken != raw
        assert leaked(doc, show, htmlprobe.parse(broken)) == [headline], show["slug"]
    assert dying  # the fixture has such a show, so the loop looked at one


def test_a_held_back_page_keeps_its_noindex_and_gets_the_same_tags(doc):
    show = show_pages.select_shows(doc)[0]
    shown = htmlprobe.parse(show_pages.render_show(doc, show, base_url=BASE, indexed=True))
    held = htmlprobe.parse(show_pages.render_show(doc, show, base_url=BASE, indexed=False))
    robots = [a.get("content") for a in held.named("meta") if a.get("name") == "robots"]
    assert robots == [show_pages.ROBOTS_HOLD]
    assert _og(held) == _og(shown) and preview_problems(held) == []


def test_the_page_still_loads_nothing(doc):
    """The tags are text. No page gained an image, a script or a request."""
    for path, page in _pages(_files(doc)).items():
        if not path.startswith("shows/") or path == "shows/index.html":
            continue
        assert page.named("img") == [], path
        assert [a for a in page.named("script") if a.get("src")] == [], path
        assert htmlprobe.foreign_links(page, BASE) == [], path


@pytest.mark.parametrize(
    ("old", "new", "problem"),
    [
        ('<meta property="og:title" content="', '<meta property="og:title" content="X ', "title"),
        (
            '<meta property="og:description" content="',
            '<meta property="og:description" content="X ',
            "description",
        ),
        (
            '<meta property="og:url" content="',
            '<meta property="og:url" content="https://elsewhere.test/',
            "canonical",
        ),
        (
            '<meta property="og:locale" content="en_US">',
            '<meta property="og:locale" content="en_US">\n'
            '<meta property="og:image" content="https://example.test/a.png">',
            "og:image",
        ),
        ('<meta property="og:site_name" content="Queer Frame">\n', "", "tags are"),
    ],
)
def test_negative_controls_a_wrong_or_extra_tag_is_caught(doc, old, new, problem):
    raw = _files(doc)["shows/harbor-lights/index.html"]
    assert preview_problems(htmlprobe.parse(raw)) == []
    broken = raw.replace(old, new, 1)
    assert broken != raw
    problems = preview_problems(htmlprobe.parse(broken))
    assert any(problem in p for p in problems), problems
