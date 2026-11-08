"""A death counts for a show only when it falls in that show (DECISIONS 0030).

LezWatch.TV records a death on the character, not on a show. Before this
rule, The L Word: Generation Q's page said "Yes. 1 of 42 listed characters
dies: Dana Fairbanks", whose recorded death (2007) is in The L Word; she is a
2022 guest in Generation Q. Supergirl and Batwoman counted Sara Lance's
Arrow and Legends deaths, and Supergirl counted Nora West-Allen's Flash
death. The fixtures below carry those characters' real years from the
2026-11-04 snapshot.

Also here: the list's scope sentence and heading (LezWatch.TV leaves out
cisgender gay and bisexual men), and ``data-nosnippet`` on the answer.
"""

from __future__ import annotations

import copy
import json
from html.parser import HTMLParser
from pathlib import Path

import pytest

from qtv_pipeline import show_pages
from tests import htmlprobe

REPO = Path(__file__).resolve().parents[2]
FIXTURE = REPO / "ios" / "GuideCore" / "Tests" / "Fixtures" / "snapshot.fixture.json"
BASE = "https://example.test/qf"

# (lwtv id, slug, title)
SHOWS = [
    (211, "the-l-word", "The L Word"),
    (51667, "the-l-word-generation-q", "The L Word: Generation Q"),
    (456, "arrow", "Arrow"),
    (1607, "legends-of-tomorrow", "Legends of Tomorrow"),
    (4063, "supergirl", "Supergirl"),
    (6003, "the-flash", "The Flash"),
    (48916, "batwoman", "Batwoman"),
]


def _years(*ys: int) -> list[str]:
    return [str(y) for y in ys]


# (lwtv id, name, death years or None for no recorded death, [(show lwtv id, years)])
CHARACTERS = [
    (
        9001,
        "Dana Fairbanks",
        [2007],
        [(211, _years(2004, 2005, 2006, 2007)), (51667, _years(2022))],
    ),
    (9002, "Bette Porter", None, [(211, _years(2004, 2009)), (51667, _years(2019, 2023))]),
    (
        9003,
        "Sara Lance",
        [2014, 2016, 2021],
        [
            (1607, _years(2016, 2017, 2018, 2019, 2020, 2021, 2022)),
            (456, _years(2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020)),
            (6003, _years(2016, 2017, 2019)),
            (4063, _years(2017, 2020)),
            (48916, _years(2019)),
        ],
    ),
    (
        9004,
        "Nora West-Allen",
        [2019],
        [(6003, _years(2018, 2019, 2021, 2022, 2023)), (4063, _years(2017))],
    ),
    (9005, "Alex Danvers", None, [(4063, _years(2015, 2021))]),
    (9006, "Kate Kane", None, [(48916, _years(2019, 2020)), (4063, _years(2019))]),
    # A one-show character's death is that show's, whatever its year.
    (9007, "Tatiana", [2021], [(48916, _years(2020))]),
]


@pytest.fixture
def doc() -> dict:
    base = json.loads(FIXTURE.read_text(encoding="utf-8"))
    template_show = base["shows"][1]
    template_char = base["characters"][0]
    shows = []
    for lwtv_id, slug, title in SHOWS:
        s = copy.deepcopy(template_show)
        s.update(
            id=f"lwtv:show:{lwtv_id}",
            lwtv_id=lwtv_id,
            slug=slug,
            title=title,
            alternate_names=[],
            source_url=f"https://lezwatchtv.com/show/{slug}/",
            similar_show_ids=[],
            tropes=[],
        )
        s["counts"] = {
            "characters": None,
            "deaths": None,
            "characters_source_reported": None,
            "deaths_source_reported": None,
        }
        shows.append(s)
    chars = []
    for lwtv_id, name, death_years, links in CHARACTERS:
        c = copy.deepcopy(template_char)
        slug = name.lower().replace(" ", "-")
        c.update(
            id=f"lwtv:character:{lwtv_id}",
            lwtv_id=lwtv_id,
            slug=slug,
            name=name,
            source_url=f"https://lezwatchtv.com/character/{slug}/",
            shows=[
                {"show_id": f"lwtv:show:{sid}", "role": "regular", "years": ys} for sid, ys in links
            ],
            death=(
                {"died": None, "death_known": False, "dates": [], "years": []}
                if death_years is None
                else {"died": True, "death_known": True, "dates": [], "years": death_years}
            ),
            # Every death here carries LezWatch's Dead status marker, so this
            # file tests the 0030 rule alone. On the real snapshot Sara Lance
            # and Nora West-Allen lack it (LezWatch lists them as alive), and
            # DECISIONS 0052 answers Unknown for them before 0030 is reached;
            # test_show_pages_listed_alive.py covers that.
            cliches=[{"name": "Dead", "slug": "dead"}] if death_years is not None else [],
        )
        chars.append(c)
    base["shows"], base["characters"] = shows, chars
    return base


def _show(doc: dict, slug: str) -> dict:
    return next(s for s in doc["shows"] if s["slug"] == slug)


def _answer(doc: dict, slug: str) -> tuple[show_pages.Answer, list[show_pages.CharacterView]]:
    show = _show(doc, slug)
    cast = show_pages._characters(doc, show)
    return show_pages._answer(show, cast), cast


def _status(cast: list[show_pages.CharacterView], name: str) -> show_pages.CharacterView:
    return next(c for c in cast if c.name == name)


# --- the three shows from the audit ----------------------------------------


def test_generation_q_does_not_count_danas_death_from_the_l_word(doc):
    answer, cast = _answer(doc, "the-l-word-generation-q")
    assert answer.headline.startswith(
        "Unknown. LezWatch.TV has no death on record in this show for any of the 2 listed"
    )
    assert "Dana Fairbanks" not in answer.headline
    dana = _status(cast, "Dana Fairbanks")
    assert dana.dies is False and dana.elsewhere is True
    assert dana.status.startswith("Unknown.")
    assert "not in a year the character appears in this show" in dana.status
    assert any("not counted here" in n for n in answer.notes)


def test_the_l_word_still_counts_danas_death(doc):
    answer, cast = _answer(doc, "the-l-word")
    assert answer.headline == "Yes. 1 of 2 listed characters dies: Dana Fairbanks."
    dana = _status(cast, "Dana Fairbanks")
    assert dana.dies is True
    assert "2007 is among this character's years in this show" in dana.status


def test_supergirl_counts_neither_sara_nor_nora(doc):
    answer, cast = _answer(doc, "supergirl")
    assert answer.headline.startswith("Unknown. LezWatch.TV has no death on record in this show")
    for name in ("Sara Lance", "Nora West-Allen"):
        c = _status(cast, name)
        assert c.dies is False and c.elsewhere is True
        assert c.status.startswith("Unknown.")
    assert any(n.startswith("2 listed characters have a recorded death") for n in answer.notes)


def test_batwoman_counts_its_own_death_but_not_saras(doc):
    answer, cast = _answer(doc, "batwoman")
    assert answer.headline == "Yes. 1 of 3 listed characters dies: Tatiana."
    assert _status(cast, "Sara Lance").dies is False
    # Tatiana's only show is Batwoman, so her death is Batwoman's even
    # though LezWatch's year (2021) is outside her link years.
    assert _status(cast, "Tatiana").dies is True


def test_a_death_in_the_years_of_two_shows_counts_in_both(doc):
    for slug in ("arrow", "legends-of-tomorrow", "the-flash"):
        _, cast = _answer(doc, slug)
        assert _status(cast, "Sara Lance").dies is True, slug
    _, flash = _answer(doc, "the-flash")
    assert _status(flash, "Nora West-Allen").dies is True


def test_no_death_year_or_no_link_years_is_unknown_never_a_guess():
    death = {"died": True, "death_known": True, "dates": [], "years": []}
    dies, text = show_pages._death_status(death, 1, ["2019"])
    assert dies is False and text.startswith("Unknown.") and "no year" in text
    death = {"died": True, "death_known": True, "dates": [], "years": [2019]}
    dies, text = show_pages._death_status(death, 1, [])
    assert dies is False and text.startswith("Unknown.") and "not the character's years" in text
    # One show only: the death is that show's, as before.
    assert show_pages._death_status(death, 0, []) == (True, "Dies (2019).")


def test_a_second_link_to_the_same_show_adds_its_years(doc):
    dana = next(c for c in doc["characters"] if c["name"] == "Dana Fairbanks")
    dana["shows"].append({"show_id": "lwtv:show:51667", "role": "guest", "years": ["2007"]})
    _, cast = _answer(doc, "the-l-word-generation-q")
    assert _status(cast, "Dana Fairbanks").dies is True


def test_negative_control_the_old_rule_would_have_said_yes(doc):
    # Sabotage: give Dana's Generation Q link The L Word's years. The page
    # must then count her, which shows the test above reads the link years.
    dana = next(c for c in doc["characters"] if c["name"] == "Dana Fairbanks")
    dana["shows"][1]["years"] = _years(2004, 2005, 2006, 2007)
    answer, _ = _answer(doc, "the-l-word-generation-q")
    assert answer.headline == "Yes. 1 of 2 listed characters dies: Dana Fairbanks."


def test_rendered_generation_q_page_says_unknown(doc, tmp_path):
    show_pages.build_site(doc, tmp_path, base_url=BASE)
    raw = (tmp_path / "shows/the-l-word-generation-q/index.html").read_text(encoding="utf-8")
    page = htmlprobe.parse(raw)
    assert [k for k, _ in page.statuses] == ["unknown", "unknown"]
    assert not any(t.startswith("Yes.") for t in page.inside)
    assert htmlprobe.no_for_unknown(page) == []


# --- scope sentence and heading ------------------------------------------


def test_every_page_states_the_lists_scope(doc, tmp_path):
    show_pages.build_site(doc, tmp_path, base_url=BASE)
    for path in sorted(tmp_path.glob("shows/*/index.html")):
        page = htmlprobe.parse(path.read_text(encoding="utf-8"))
        assert any(
            "this page does not list cisgender gay and bisexual men" in t for t in page.outside
        ), path
        assert not any(t.startswith("LGBTQ characters in") for t in page.outside), path
        title = next(s["title"] for s in doc["shows"] if s["slug"] == path.parent.name)
        assert f"Queer women, non-binary and trans characters in {title}" in page.outside


# --- data-nosnippet --------------------------------------------------------


class _AnswerBody(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.bodies: list[dict[str, str | None]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        if tag == "div" and "answer-body" in (a.get("class") or "").split():
            self.bodies.append(a)


def nosnippet_problems(raw: str) -> list[str]:
    probe = _AnswerBody()
    probe.feed(raw)
    if len(probe.bodies) != 1:
        return [f"{len(probe.bodies)} answer bodies"]
    return [] if "data-nosnippet" in probe.bodies[0] else ["answer body lacks data-nosnippet"]


def test_the_answer_carries_data_nosnippet(doc, tmp_path):
    show_pages.build_site(doc, tmp_path, base_url=BASE)
    pages = sorted(tmp_path.glob("shows/*/index.html"))
    assert pages
    for path in pages:
        assert nosnippet_problems(path.read_text(encoding="utf-8")) == [], path


def test_negative_control_a_missing_nosnippet_is_caught(doc, tmp_path):
    show_pages.build_site(doc, tmp_path, base_url=BASE)
    raw = (tmp_path / "shows/supergirl/index.html").read_text(encoding="utf-8")
    bad = raw.replace('<div class="answer-body" data-nosnippet>', '<div class="answer-body">')
    assert bad != raw  # the sabotage applied
    assert nosnippet_problems(bad) == ["answer body lacks data-nosnippet"]
