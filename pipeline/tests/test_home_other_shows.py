"""The home page's second list, "Some of the other shows" (DECISIONS 0065).

Below the hand-picked titles the home page names twelve more shows, from a
fixed list of LezWatch.TV ids in ``site_index.OTHER_ON_HOME``. Each title is
the snapshot's own, so it is spelled exactly as the show's page spells it, and
a show is named only when its page was published. Titles only: the home
page's spoiler rule (DECISIONS 0026) is unchanged. The pages are read with
html.parser, never a regular expression. Every negative control asserts that
its sabotage changed the input before it asserts the outcome.
"""

from __future__ import annotations

import json
from html.parser import HTMLParser
from pathlib import Path

import pytest

from qtv_pipeline import show_pages, site_index
from tests import htmlprobe
from tests.test_show_pages_publish import _big_doc, _pinned_file

REPO = Path(__file__).resolve().parents[2]
FIXTURE = REPO / "ios" / "GuideCore" / "Tests" / "Fixtures" / "snapshot.fixture.json"
DOMAIN = "https://queerframe.app"
HAND_PICKED = "Some of the hand-picked shows"
OTHER = "Some of the other shows"
# The twelve the owner chose on 2026-11-17, in her order, as each page spells it.
APPROVED = (
    (98062, "FROM"),
    (84706, "Will Trent"),
    (91890, "The Mentalist"),
    (77, "The Fosters"),
    (61062, "The Owl House"),
    (1432, "The Vampire Diaries"),
    (72838, "Helluva Boss"),
    (17014, "SWAT"),
    (90168, "Elsbeth"),
    (32468, "Manifest"),
    (18740, "The Loud House"),
    (50486, "Craig of the Creek"),
)


class _Lists(HTMLParser):
    """Each ``<ul class="shows">`` on a page as (the <h3> before it, its
    (href, link text) pairs), in page order."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lists: list[tuple[str, list[tuple[str, str]]]] = []
        self._heading = ""
        self._in_h3 = False
        self._in_list = False
        self._href: str | None = None
        self._text = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        if tag == "h3":
            self._in_h3, self._heading = True, ""
        elif tag == "ul" and "shows" in (a.get("class") or "").split():
            self._in_list = True
            self.lists.append((self._heading.strip(), []))
        elif tag == "a" and self._in_list:
            self._href, self._text = a.get("href") or "", ""

    def handle_endtag(self, tag: str) -> None:
        if tag == "h3":
            self._in_h3 = False
        elif tag == "ul":
            self._in_list = False
        elif tag == "a" and self._in_list and self._href is not None:
            self.lists[-1][1].append((self._href, self._text))
            self._href = None

    def handle_data(self, data: str) -> None:
        if self._in_h3:
            self._heading += data
        elif self._href is not None:
            self._text += data


def _lists(text: str) -> list[tuple[str, list[tuple[str, str]]]]:
    probe = _Lists()
    probe.feed(text)
    probe.close()
    return probe.lists


def _other(text: str) -> list[tuple[str, str]]:
    """The (href, title) pairs under "Some of the other shows"; [] with no list."""
    found = [links for heading, links in _lists(text) if heading == OTHER]
    assert len(found) <= 1
    return found[0] if found else []


@pytest.fixture
def doc() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _site(doc: dict, tmp_path: Path, pins: list[int]) -> tuple[dict, Path, Path]:
    """Sixty shows published under tmp_path/site, with ``pins`` hand-picked."""
    big = _big_doc(doc)
    site = tmp_path / "site"
    site.mkdir()
    pinned = _pinned_file(tmp_path, pins)
    show_pages.build_site(big, site, pinned=show_pages.load_pinned(pinned))
    return big, site, pinned


def _home(big: dict, site: Path, pinned: Path, **kw) -> str:
    site_index.write_site(big, site / "index.html", pinned_path=pinned, **kw)
    return (site / "index.html").read_text(encoding="utf-8")


# ---- the fixed list ----------------------------------------------------------


def test_the_fixed_list_is_the_twelve_approved_shows_in_order():
    assert tuple(i for i, _ in APPROVED) == site_index.OTHER_ON_HOME
    assert len(set(site_index.OTHER_ON_HOME)) == 12


def test_none_of_the_twelve_is_a_hand_picked_show():
    pins = show_pages.load_pinned(show_pages.DEFAULT_PINNED_PATH) or []
    assert pins  # the real list was read
    assert not {p.lezwatch_id for p in pins} & set(site_index.OTHER_ON_HOME)


# ---- the home page -----------------------------------------------------------


def test_the_other_shows_follow_the_hand_picked_ones_in_the_lists_order(doc, tmp_path):
    big, site, pinned = _site(doc, tmp_path, [1007, 1003])
    text = _home(big, site, pinned, other_ids=(1010, 1005, 1012))
    headings = [heading for heading, _ in _lists(text)]
    assert headings == [HAND_PICKED, OTHER]
    assert _other(text) == [
        (f"{DOMAIN}/shows/show-010/", "Show 010"),
        (f"{DOMAIN}/shows/show-005/", "Show 005"),
        (f"{DOMAIN}/shows/show-012/", "Show 012"),
    ]


def test_each_title_is_spelled_as_its_own_page_spells_it(doc, tmp_path):
    big, site, pinned = _site(doc, tmp_path, [1007])
    by_id = {s["lwtv_id"]: s for s in big["shows"]}
    by_id[1010]["title"] = "SHOW ten & Co."  # an odd spelling, and a character to escape
    show_pages.build_site(big, site, pinned=show_pages.load_pinned(pinned))
    text = _home(big, site, pinned, other_ids=(1010, 1005))
    assert [title for _, title in _other(text)] == ["SHOW ten & Co.", "Show 005"]
    for href, title in _other(text):
        page_file = site / href.removeprefix(f"{DOMAIN}/") / "index.html"
        page = htmlprobe.parse(page_file.read_text(encoding="utf-8"))
        current = [a for a in page.named("span") if a.get("aria-current") == "page"]
        assert len(current) == 1
        assert title in page.outside  # the breadcrumb's last item is the title itself


def test_only_a_show_whose_page_was_published_is_named(doc, tmp_path):
    big, site, pinned = _site(doc, tmp_path, [1007])
    # 1999 is not in the snapshot; show-011's page is removed from the build.
    (site / "shows" / "show-011" / "index.html").unlink()
    text = _home(big, site, pinned, other_ids=(1999, 1011, 1010))
    assert _other(text) == [(f"{DOMAIN}/shows/show-010/", "Show 010")]
    for href, _ in _other(text):
        assert (site / href.removeprefix(f"{DOMAIN}/") / "index.html").is_file()


def test_a_hand_picked_show_is_never_named_again_as_an_other_show(doc, tmp_path):
    big, site, pinned = _site(doc, tmp_path, [1007, 1003])
    text = _home(big, site, pinned, other_ids=(1003, 1010, 1007))
    assert _other(text) == [(f"{DOMAIN}/shows/show-010/", "Show 010")]
    every = [href for _, links in _lists(text) for href, _ in links]
    assert len(every) == len(set(every))


def test_no_heading_without_a_show_to_name(doc, tmp_path):
    big, site, pinned = _site(doc, tmp_path, [1007])
    for ids in ((), (1999,), (1007,)):
        text = _home(big, site, pinned, other_ids=ids)
        assert OTHER not in htmlprobe.parse(text).outside, ids
        assert [heading for heading, _ in _lists(text)] == [HAND_PICKED], ids
    # Negative control: one publishable id brings the heading back.
    text = _home(big, site, pinned, other_ids=(1010,))
    assert OTHER in htmlprobe.parse(text).outside


def test_no_other_list_without_the_hand_picked_one_above_it(doc, tmp_path):
    """ "Other" means other than the hand-picked shows, so with no hand-picked
    list on the page there is no second list either."""
    big, site, pinned = _site(doc, tmp_path, [1999])  # no hand-picked show has a page
    text = _home(big, site, pinned, other_ids=(1010, 1005))
    assert _lists(text) == []
    assert OTHER not in htmlprobe.parse(text).outside


def test_no_list_when_the_shows_are_not_published(doc, tmp_path):
    big = _big_doc(doc)
    site = tmp_path / "bare"
    site.mkdir()
    pinned = _pinned_file(tmp_path, [1007])
    text = _home(big, site, pinned, other_ids=(1010, 1005))
    assert _lists(text) == [] and text == site_index.render_index(big)


def test_the_default_list_names_nothing_from_a_snapshot_without_those_shows(doc, tmp_path):
    """The real ids are not in the fixture, so the default changes no page
    built from it: the list never invents a title."""
    big, site, pinned = _site(doc, tmp_path, [1007])
    assert not {s["lwtv_id"] for s in big["shows"]} & set(site_index.OTHER_ON_HOME)
    text = _home(big, site, pinned)
    assert _other(text) == []


def test_the_second_list_holds_titles_only_and_the_page_still_has_no_answer(doc, tmp_path):
    big, site, pinned = _site(doc, tmp_path, [1007])
    text = _home(big, site, pinned, other_ids=(1010, 1005))
    page = htmlprobe.parse(text)
    titles = {s["title"] for s in big["shows"]}
    assert {title for _, title in _other(text)} <= titles
    assert page.named("details") == [] and page.inside == []
    names = {c["name"] for c in big["characters"]}
    visible = " ".join(page.outside)
    assert not [n for n in names if n in visible]
    assert page.headings.count(1) == 1
    assert all(b - a <= 1 for a, b in zip(page.headings, page.headings[1:], strict=False))


def test_the_heading_is_the_approved_wording(doc, tmp_path):
    big, site, pinned = _site(doc, tmp_path, [1007])
    text = _home(big, site, pinned, other_ids=(1010,))
    assert [heading for heading, _ in _lists(text)][-1] == "Some of the other shows"
