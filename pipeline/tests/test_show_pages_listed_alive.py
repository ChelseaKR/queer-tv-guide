"""A death date for a character LezWatch.TV lists as alive is not a yes
(DECISIONS 0052).

LezWatch.TV keeps two things on a character: death dates, and a status it
shows as "Status: Dead" or "Status: Alive" and counts on its show pages
("13 queer characters listed for this show; none are dead"). The status is
the "Dead Queers" cliché (slug ``dead``); a date alone leaves it Alive. The
2026-11-08 cross-check of the 100 indexable pages found four that answered
"Yes" on a date whose character LezWatch lists as alive: Holby City (Bernie
Wolfe, "believed to have died in an explosion", back on screen 2021 and
2022), Warrior Nun (Ava Silva, dead before the first scene and resurrected
in it), Legends of Tomorrow and The Flash (Sara Lance; and on The Flash Nora
West-Allen, restored after Crisis). LezWatch's own pages for all four shows
say "none are dead". The records below are those characters' real ones from
the 2026-11-07 snapshot: death years, show years and clichés.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from qtv_pipeline import show_pages
from tests import htmlprobe

REPO = Path(__file__).resolve().parents[2]
FIXTURE = REPO / "ios" / "GuideCore" / "Tests" / "Fixtures" / "snapshot.fixture.json"
BASE = "https://example.test/qf"

# (lwtv id, slug, title, LezWatch's own death tally for the show)
SHOWS = [
    (5407, "holby-city", "Holby City", 0),
    (62130, "warrior-nun", "Warrior Nun", 0),
    (1607, "legends-of-tomorrow", "Legends of Tomorrow", 0),
    (6003, "the-flash", "The Flash", 0),
    (31130, "euphoria", "Euphoria", 1),
]

DEAD = {"name": "Dead", "slug": "dead"}


def _years(*ys: int) -> list[str]:
    return [str(y) for y in ys]


# (lwtv id, name, death years or None, cliché slugs, [(show lwtv id, years)])
CHARACTERS = [
    (
        5417,
        "Bernie Wolfe",
        [2019],
        ["leo", "parent", "science"],
        [(5407, _years(2016, 2017, 2018, 2021, 2022))],
    ),
    (5418, "Serena Campbell", None, ["parent"], [(5407, _years(2012, 2022))]),
    (
        7001,
        "Ava Silva",
        [2020],
        ["disabled", "superhuman", "undead"],
        [(62130, _years(2020, 2022))],
    ),
    (7002, "Sister Beatrice", None, [], [(62130, _years(2020, 2022))]),
    (
        9003,
        "Sara Lance",
        [2014, 2016, 2021],
        ["inhuman", "leo", "criminal", "promiscuous"],
        [
            (1607, _years(2016, 2017, 2018, 2019, 2020, 2021, 2022)),
            (6003, _years(2016, 2017, 2019)),
        ],
    ),
    (
        9004,
        "Nora West-Allen",
        [2019],
        ["news", "science", "superhuman"],
        [(6003, _years(2018, 2019, 2021, 2022, 2023))],
    ),
    (9005, "Ava Sharpe", None, [], [(1607, _years(2017, 2022))]),
    # The control: LezWatch marks Rue dead, so her date is still a yes.
    (
        8001,
        "Rue Bennett",
        [2026],
        ["addict", "dead"],
        [(31130, _years(2019, 2020, 2021, 2022, 2026))],
    ),
    (8002, "Jules Vaughn", None, [], [(31130, _years(2019, 2026))]),
]


@pytest.fixture
def doc() -> dict:
    base = json.loads(FIXTURE.read_text(encoding="utf-8"))
    template_show = base["shows"][1]
    template_char = base["characters"][0]
    shows = []
    for lwtv_id, slug, title, tally in SHOWS:
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
            "deaths_source_reported": tally,
        }
        shows.append(s)
    chars = []
    for lwtv_id, name, death_years, cliches, links in CHARACTERS:
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
            cliches=[{"name": s.replace("-", " ").title(), "slug": s} for s in cliches],
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


def _view(cast: list[show_pages.CharacterView], name: str) -> show_pages.CharacterView:
    return next(c for c in cast if c.name == name)


def _build(doc: dict, tmp_path: Path) -> dict[str, htmlprobe.Page]:
    show_pages.build_site(doc, tmp_path, base_url=BASE)
    return {
        str(p.relative_to(tmp_path)): htmlprobe.parse(p.read_text(encoding="utf-8"))
        for p in sorted((tmp_path / "shows").rglob("index.html"))
    }


# --- the four pages from the cross-check -----------------------------------


def test_holby_city_does_not_count_a_death_lezwatch_lists_as_alive(doc):
    answer, cast = _answer(doc, "holby-city")
    assert answer.headline == (
        "Unknown. LezWatch.TV does not list any of the 2 listed characters as dead. "
        "It records deaths and nothing else, so this does not say anyone lives."
    )
    bernie = _view(cast, "Bernie Wolfe")
    assert bernie.dies is False and bernie.listed_alive is True and bernie.elsewhere is False
    assert bernie.status == (
        "Unknown. LezWatch.TV records a death date (2019) for this character but lists the"
        " character as alive, so it is not counted here."
    )
    assert (
        "One listed character has a recorded death date, but LezWatch.TV lists the character"
        " as alive, so it is not counted here."
    ) in answer.notes
    # LezWatch's own tally (0) now agrees with the page, so no tally note.
    assert not any("own tally" in n for n in answer.notes)


def test_warrior_nun_ava_is_unknown_not_yes(doc):
    answer, cast = _answer(doc, "warrior-nun")
    assert answer.headline.startswith("Unknown. LezWatch.TV does not list any of the 2 listed")
    assert _view(cast, "Ava Silva").dies is False


def test_legends_and_the_flash_sara_and_nora(doc):
    legends, cast = _answer(doc, "legends-of-tomorrow")
    assert legends.headline.startswith("Unknown.")
    sara = _view(cast, "Sara Lance")
    assert sara.dies is False
    assert sara.status.startswith(
        "Unknown. LezWatch.TV records death dates (2014, 2016, 2021) for this character but"
    )
    flash, cast = _answer(doc, "the-flash")
    assert flash.headline.startswith("Unknown. LezWatch.TV does not list any of the 2 listed")
    assert [c.listed_alive for c in cast] == [True, True]
    assert (
        "2 listed characters have a recorded death date, but LezWatch.TV lists them as alive,"
        " so they are not counted here."
    ) in flash.notes
    # The status rule answers before 0030's cross-show rule, so no 0030 note.
    assert not any("does not place in this show" in n for n in flash.notes)


def test_a_marked_death_is_still_a_yes(doc):
    answer, cast = _answer(doc, "euphoria")
    assert answer.headline == "Yes. 1 of 2 listed characters dies: Rue Bennett."
    rue = _view(cast, "Rue Bennett")
    assert rue.dies is True and rue.listed_alive is False
    assert not any("lists" in n and "alive" in n for n in answer.notes)


# --- the marker --------------------------------------------------------------


def test_only_the_dead_cliche_is_the_marker():
    assert show_pages.marked_dead({"cliches": [{"name": "Dead", "slug": "dead"}]}) is True
    assert show_pages.marked_dead({"cliches": [DEAD, {"name": "Undead", "slug": "undead"}]}) is True
    assert show_pages.marked_dead({"cliches": [{"name": "Undead", "slug": "undead"}]}) is False
    assert show_pages.marked_dead({"cliches": []}) is False


@pytest.mark.parametrize(
    ("years", "dated"),
    [
        ([], "a death but no date"),
        ([2019], "a death date (2019)"),
        ([2014, 2021], "death dates (2014, 2021)"),
    ],
)
def test_the_sentence_names_what_is_recorded(years, dated):
    death = {"died": True, "death_known": True, "dates": [], "years": years}
    dies, text = show_pages._death_status(death, 0, (), status_dead=False)
    assert dies is False
    assert text == (
        f"Unknown. LezWatch.TV records {dated} for this character but lists the character as"
        " alive, so it is not counted here."
    )
    # The same record, marked dead, stays a yes.
    assert show_pages._death_status(death, 0, (), status_dead=True)[0] is True


def test_no_recorded_death_is_unchanged_by_the_marker():
    none = {"died": None, "death_known": False, "dates": [], "years": []}
    for status_dead in (True, False):
        assert show_pages._death_status(none, 0, (), status_dead) == (
            False,
            "Unknown. LezWatch.TV has not recorded a death.",
        )


# --- the rendered page --------------------------------------------------------


def test_rendered_pages_show_unknown_and_never_no(doc, tmp_path):
    pages = _build(doc, tmp_path)
    holby = pages["shows/holby-city/index.html"]
    assert [k for k, _ in holby.statuses] == ["unknown", "unknown"]
    assert all(t.startswith("Unknown.") for _, t in holby.statuses)
    euphoria = pages["shows/euphoria/index.html"]
    assert [k for k, _ in euphoria.statuses] == ["dies", "unknown"]
    for page in pages.values():
        assert htmlprobe.no_for_unknown(page) == []


# --- negative control ---------------------------------------------------------


def test_negative_control_without_the_status_check_the_page_says_yes(doc, monkeypatch):
    """The rule is load-bearing: with the marker check switched off, every one
    of the four pages flips back to "Yes". A rule whose removal changed
    nothing would prove nothing."""
    before = {slug: _answer(doc, slug)[0].headline for _id, slug, *_ in SHOWS}
    monkeypatch.setattr(show_pages, "marked_dead", lambda _c: True)
    after = {slug: _answer(doc, slug)[0].headline for _id, slug, *_ in SHOWS}
    assert after != before  # the sabotage applied
    assert after["holby-city"] == "Yes. 1 of 2 listed characters dies: Bernie Wolfe."
    assert after["warrior-nun"] == "Yes. 1 of 2 listed characters dies: Ava Silva."
    assert after["legends-of-tomorrow"] == "Yes. 1 of 2 listed characters dies: Sara Lance."
    assert after["the-flash"] == "Yes. 2 of 2 listed characters die: Sara Lance, Nora West-Allen."
    assert after["euphoria"] == before["euphoria"]  # the control never moved
    for slug in ("holby-city", "warrior-nun", "legends-of-tomorrow", "the-flash"):
        assert before[slug].startswith("Unknown.")
