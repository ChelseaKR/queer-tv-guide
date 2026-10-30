"""Which shows get a page beyond the hand-picked 50 (DECISIONS 0025).

The rule: every show with at least 5 listed characters and a TVmaze match,
after the pinned list, most listed first, ties by lower LezWatch id. Below
50 pages the most-listed other shows fill the gap; above ``DEFAULT_LIMIT``
the fewest-listed are cut, with a log line either way. The shows index
lists the pinned shows first and then every show A to Z by letter.

Every negative control asserts its sabotage changed the data before it
concludes anything.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from qtv_pipeline import show_pages
from tests import htmlprobe
from tests.test_show_pages_publish import _big_doc

REPO = Path(__file__).resolve().parents[2]
FIXTURE = REPO / "ios" / "GuideCore" / "Tests" / "Fixtures" / "snapshot.fixture.json"


@pytest.fixture
def doc() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _grow(big: dict, lwtv_id: int, extra: int) -> None:
    """Give show `lwtv_id` `extra` more listed characters."""
    show = next(s for s in big["shows"] if s["lwtv_id"] == lwtv_id)
    template = big["characters"][0]
    for k in range(extra):
        char = copy.deepcopy(template)
        n = 10_000 + lwtv_id * 10 + k
        char.update(id=f"lwtv:character:{n}", lwtv_id=n, slug=f"extra-{n}")
        char["shows"] = [{**template["shows"][0], "show_id": show["id"]}]
        big["characters"].append(char)


def _qualified(shows: int = 80, rich: dict[int, int] | None = None) -> dict:
    """`shows` shows with one listed character each; `rich` maps a LezWatch id
    to its listed-character total."""
    big = _big_doc(json.loads(FIXTURE.read_text(encoding="utf-8")), shows)
    for lwtv_id, total in (rich or {}).items():
        _grow(big, lwtv_id, total - 1)
    return big


def _slugs(shows: list[dict]) -> list[str]:
    return [s["slug"] for s in shows]


# ---- the rule ----------------------------------------------------------------


def test_five_listed_characters_and_a_tvmaze_match_qualify():
    big = _qualified(rich={1001: 5, 1002: 4, 1003: 9})
    listed = show_pages._listed_characters(big)
    by_id = {s["lwtv_id"]: s for s in big["shows"]}
    assert show_pages.qualifies(by_id[1001], listed)
    assert not show_pages.qualifies(by_id[1002], listed)  # 4 is one short
    assert show_pages.qualifies(by_id[1003], listed)
    by_id[1003]["schedule"]["tvmaze_url"] = None
    assert not show_pages.qualifies(by_id[1003], listed)  # no TVmaze match
    assert not show_pages.qualifies(by_id[1000], listed)  # one character


def test_every_qualifying_show_is_built_past_fifty():
    rich = {1000 + i: 5 + (i % 3) for i in range(70)}  # 70 of 80 shows qualify
    big = _qualified(80, rich)
    chosen, notes = show_pages.plan_selection(big)
    assert len(chosen) == 70  # all of them, more than the old 50
    assert {s["lwtv_id"] for s in chosen} == set(rich)
    listed = show_pages._listed_characters(big)
    counts = [listed[s["id"]] for s in chosen]
    assert counts == sorted(counts, reverse=True)  # most listed first
    seven = [s["lwtv_id"] for s in chosen if listed[s["id"]] == 7]
    assert seven == sorted(seven)  # ties by lower LezWatch id
    assert notes[-1] == "show_pages: 70 pages: 0 pinned, 70 by the rule, 0 to reach the floor"


def test_a_show_without_tvmaze_is_left_out_even_with_many_characters():
    rich = {1000 + i: 6 for i in range(60)}
    big = _qualified(80, rich)
    target = next(s for s in big["shows"] if s["lwtv_id"] == 1010)
    before = _slugs(show_pages.select_shows(big))
    assert "show-010" in before
    target["schedule"]["tvmaze_url"] = None
    assert target["schedule"]["tvmaze_url"] is None  # the sabotage landed
    after = _slugs(show_pages.select_shows(big))
    assert "show-010" not in after and len(after) == 59


def test_pins_come_first_then_the_rule_and_none_twice(tmp_path):
    rich = {1000 + i: 5 for i in range(55)} | {1070: 8}
    big = _qualified(80, rich)
    path = tmp_path / "pinned.json"
    path.write_text(
        json.dumps(
            {
                "how_chosen": "test",
                "shows": [
                    {"lezwatch_id": i, "slug": f"show-{i - 1000:03d}", "title": "t", "reason": "r"}
                    for i in (1075, 1003)  # 1075 lists one character; 1003 also qualifies
                ],
            }
        ),
        encoding="utf-8",
    )
    chosen, notes = show_pages.plan_selection(big, pinned=show_pages.load_pinned(path))
    slugs = _slugs(chosen)
    assert slugs[:3] == ["show-075", "show-003", "show-070"]  # pins, then most listed
    assert len(slugs) == len(set(slugs)) == 57  # 2 pins + 55 others that qualify
    assert notes[-1] == "show_pages: 57 pages: 2 pinned, 55 by the rule, 0 to reach the floor"


# ---- the floor and the cap ------------------------------------------------------


def test_below_fifty_the_most_listed_others_fill_the_gap():
    big = _qualified(80, {1000 + i: 5 for i in range(10)} | {1040: 3, 1041: 2})
    chosen, notes = show_pages.plan_selection(big)
    slugs = _slugs(chosen)
    assert len(slugs) == 50
    assert set(slugs[:10]) == {f"show-{i:03d}" for i in range(10)}
    assert slugs[10:12] == ["show-040", "show-041"]  # 3, then 2 listed characters
    assert (
        "show_pages: only 10 shows are pinned or meet the rule; "
        "40 more with the most listed characters make up 50 pages"
    ) in notes
    assert notes[-1] == "show_pages: 50 pages: 0 pinned, 10 by the rule, 40 to reach the floor"


def test_the_limit_cuts_the_fewest_listed_and_says_so():
    rich = {1000 + i: 5 + (i < 20) for i in range(70)}  # 20 with 6, 50 with 5
    big = _qualified(80, rich)
    chosen, notes = show_pages.plan_selection(big, limit=60)
    assert len(chosen) == 60
    listed = show_pages._listed_characters(big)
    assert sum(listed[s["id"]] == 6 for s in chosen) == 20  # none of the richest cut
    assert "show_pages: the limit of 60 pages cut 10 shows with the fewest listed characters" in (
        notes
    )


def test_the_sitemap_refuses_more_urls_than_one_file_may_hold(doc, monkeypatch):
    monkeypatch.setattr(show_pages, "SITEMAP_MAX_URLS", 3)
    shows = show_pages.select_shows(doc)
    assert len(shows) + 1 > 3  # the sabotage makes the cap bite
    with pytest.raises(show_pages.ShowPagesError, match="one sitemap file"):
        show_pages.render_sitemap(doc, shows, base_url="https://queerframe.app")


# ---- the shows index, A to Z -------------------------------------------------------


def _titled(titles: list[str]) -> list[dict]:
    return [{"lwtv_id": i, "slug": f"s-{i}", "title": t, "years": {}} for i, t in enumerate(titles)]


def test_letters_drop_a_leading_article_fold_accents_and_put_others_first():
    shows = _titled(
        [
            "The L Word",
            "Élite",
            "#Luimelia",
            "The 100",
            "A Million Little Things",
            "Anne with an E",
            "Theodosia",
            "เพราะเราคู่กัน",
        ]
    )
    groups = show_pages.letter_groups(shows)
    got = {g["label"]: [s["title"] for s in g["shows"]] for g in groups}
    assert [g["label"] for g in groups] == ["#", "A", "E", "L", "M", "T"]
    assert got["#"] == ["#Luimelia", "The 100", "เพราะเราคู่กัน"]
    assert got["L"] == ["The L Word"] and got["E"] == ["Élite"]
    assert got["M"] == ["A Million Little Things"] and got["A"] == ["Anne with an E"]
    assert got["T"] == ["Theodosia"]  # "The" only as a whole word
    assert [g["anchor"] for g in groups][:2] == ["letter-other", "letter-a"]


def test_the_index_lists_pins_first_then_every_show_by_letter(tmp_path):
    big = _qualified(80, {1000 + i: 5 for i in range(60)})
    pins_path = tmp_path / "pinned.json"
    pins_path.write_text(
        json.dumps(
            {
                "how_chosen": "test",
                "shows": [
                    {"lezwatch_id": 1044, "slug": "show-044", "title": "t", "reason": "r"},
                    {"lezwatch_id": 1007, "slug": "show-007", "title": "t", "reason": "r"},
                ],
            }
        ),
        encoding="utf-8",
    )
    pins = show_pages.load_pinned(pins_path)
    show_pages.build_site(big, tmp_path / "out", pinned=pins)
    raw = (tmp_path / "out" / "shows" / "index.html").read_text(encoding="utf-8")
    page = htmlprobe.parse(raw)
    built = show_pages.select_shows(big, pinned=pins)
    assert "60 shows have a page." in page.outside
    hand = raw[raw.index('id="hand-picked"') : raw.index('id="a-to-z"')]
    assert hand.index("show-044/") < hand.index("show-007/")
    assert hand.count("<li>") == 2
    a_to_z = raw[raw.index('id="a-to-z"') :]
    for s in built:  # every page is in the A to Z list, the pinned ones too
        assert f'href="{s["slug"]}/"' in a_to_z, s["slug"]
    assert "Jump to a letter" in raw
    letters = [a["href"] for a in page.named("a") if a.get("href", "").startswith("#letter-")]
    assert letters and all(h.removeprefix("#") in page.ids for h in letters)


def test_without_pins_the_index_has_no_hand_picked_section(doc, tmp_path):
    show_pages.build_site(doc, tmp_path)
    raw = (tmp_path / "shows" / "index.html").read_text(encoding="utf-8")
    assert 'id="hand-picked"' not in raw
    assert 'id="a-to-z"' in raw


def test_cast_index_matches_a_scan_of_every_character(doc):
    index = show_pages.cast_index(doc)
    for show in doc["shows"]:
        scanned = [
            c["name"]
            for c in sorted(doc["characters"], key=lambda c: c["lwtv_id"])
            if any(x["show_id"] == show["id"] for x in c["shows"])
        ]
        assert [c.name for c in show_pages._characters(doc, show, index)] == scanned
