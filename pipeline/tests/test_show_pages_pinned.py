"""The hand-picked list of show pages (qtv_pipeline/show_pages.py, DECISIONS 0021).

`data/show_pages_pinned.json` names up to 50 shows in the order they are
built. A pin missing from the snapshot, or listing no character, is skipped
and named in the log, and the freed slots go to the character-count rule.
Without the file the character-count rule is the whole rule. Every negative
control asserts its sabotage changed the data, and the result, before it
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
IDS = [1000 + i for i in range(60)]  # _big_doc's LezWatch ids, show-000 .. show-059


@pytest.fixture
def doc() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _pins(ids: list[int], tmp_path: Path, **extra) -> Path:
    body = {
        "how_chosen": "test list",
        "shows": [
            {
                "lezwatch_id": i,
                "slug": f"show-{i - 1000:03d}",
                "title": f"Show {i - 1000:03d}",
                "reason": "test",
            }
            for i in ids
        ],
        **extra,
    }
    path = tmp_path / "pinned.json"
    path.write_text(json.dumps(body), encoding="utf-8")
    return path


def _slugs(doc: dict, pinned: Path | None, limit: int = 50) -> list[str]:
    pins = show_pages.load_pinned(pinned) if pinned else None
    return [s["slug"] for s in show_pages.select_shows(doc, limit, pins)]


# ---- the order is honored ----------------------------------------------------


def test_the_pinned_order_is_honored_and_beats_the_character_count(doc, tmp_path):
    big = _big_doc(doc)
    template = big["characters"][0]
    for k in range(3):  # show-030 lists the most characters of all
        char = copy.deepcopy(template)
        char.update(id=f"lwtv:character:{9000 + k}", lwtv_id=9000 + k, slug=f"x-{k}")
        char["shows"] = [{**template["shows"][0], "show_id": "lwtv:show:1030"}]
        big["characters"].append(char)
    plain = _slugs(big, None)
    assert plain[0] == "show-030"  # the old rule would lead with it
    pinned = [1044, 1007, 1030, 1001]
    path = _pins(pinned, tmp_path)
    chosen = _slugs(big, path)
    assert chosen[:4] == ["show-044", "show-007", "show-030", "show-001"]  # the file's order
    assert chosen[:4] != plain[:4]  # the sabotage (a different order) is real
    assert len(chosen) == 50 and len(set(chosen)) == 50  # slots 5.. filled, no repeats
    assert chosen[4] == next(s for s in plain if s not in chosen[:4])


def test_pages_sitemap_and_index_follow_the_list(doc, tmp_path):
    big = _big_doc(doc)
    pins = show_pages.load_pinned(_pins([1044, 1007], tmp_path))
    show_pages.build_site(big, tmp_path / "out", pinned=pins)
    sitemap = htmlprobe.sitemap((tmp_path / "out" / "sitemap.xml").read_text())["loc"]
    assert sitemap[:3] == [
        "https://queerframe.app/shows/",
        "https://queerframe.app/shows/show-044/",
        "https://queerframe.app/shows/show-007/",
    ]
    index = (tmp_path / "out" / "shows" / "index.html").read_text()
    assert index.index("show-044/") < index.index("show-007/") < index.index("show-000/")


# ---- missing and empty pins ------------------------------------------------------


def test_a_pin_missing_from_the_snapshot_is_skipped_logged_and_replaced(doc, tmp_path):
    big = _big_doc(doc)
    path = _pins([1005, 4242, 1006], tmp_path)  # 4242 is nowhere in the snapshot
    assert 4242 not in {s["lwtv_id"] for s in big["shows"]}  # the fault is real
    pins = show_pages.load_pinned(path)
    chosen, notes = show_pages.plan_selection(big, 50, pins)
    assert [s["slug"] for s in chosen[:2]] == ["show-005", "show-006"]
    assert len(chosen) == 50  # the freed slot is filled, deterministically
    assert "show_pages: pinned list: skipped Show 3242 (id 4242): not in the snapshot" in notes
    assert notes[0] == (
        "show_pages: selection rule: pinned list (2 of 3 built), "
        "then most listed characters, then lower LezWatch id"
    )
    again = show_pages.plan_selection(big, 50, pins)
    assert [s["slug"] for s in again[0]] == [s["slug"] for s in chosen]


def test_a_pinned_show_with_no_listed_character_is_not_built(doc, tmp_path):
    big = _big_doc(doc)
    target = next(s for s in big["shows"] if s["lwtv_id"] == 1010)
    big["characters"] = [c for c in big["characters"] if c["shows"][0]["show_id"] != target["id"]]
    assert show_pages._listed_characters(big).get(target["id"]) is None  # landed
    pins = show_pages.load_pinned(_pins([1010, 1011], tmp_path))
    chosen, notes = show_pages.plan_selection(big, 50, pins)
    assert "show-010" not in [s["slug"] for s in chosen]
    assert chosen[0]["slug"] == "show-011"
    assert any("skipped Show 010 (id 1010): the snapshot lists no character" in n for n in notes)
    show_pages.build_site(big, tmp_path / "out", pinned=pins)
    assert not (tmp_path / "out" / "shows" / "show-010").exists()


def test_the_limit_applies_to_the_pinned_list(doc, tmp_path):
    big = _big_doc(doc)
    path = _pins([1003, 1002, 1001, 1000], tmp_path)
    assert _slugs(big, path, 2) == ["show-003", "show-002"]


# ---- without the file --------------------------------------------------------------


def test_without_the_file_the_old_rule_is_the_whole_rule(doc, tmp_path, monkeypatch, capsys):
    big = _big_doc(doc)
    snap = tmp_path / "snap.json"
    snap.write_text(json.dumps(big), encoding="utf-8")
    pinned_file = _pins([1044, 1007], tmp_path)
    monkeypatch.setattr(show_pages, "DEFAULT_PINNED_PATH", pinned_file)
    with_file = show_pages.main([str(snap), str(tmp_path / "a"), "--pinned", str(pinned_file)])
    first = capsys.readouterr().out
    assert with_file == 0 and "pinned list (2 of 2 built)" in first
    assert (tmp_path / "a" / "shows" / "show-044").is_dir()

    pinned_file.unlink()
    assert not pinned_file.exists()  # the sabotage landed
    assert show_pages.main([str(snap), str(tmp_path / "b"), "--pinned", str(pinned_file)]) == 0
    second = capsys.readouterr().out
    assert "selection rule: most listed characters, then lower LezWatch id" in second
    assert "pinned list" not in second
    expected = [s["slug"] for s in show_pages.select_shows(big)]
    built = sorted(p.parent.name for p in (tmp_path / "b" / "shows").glob("*/index.html"))
    assert built == sorted(expected)
    assert show_pages.load_pinned(pinned_file) is None


def test_no_pinned_flag_ignores_the_file(doc, tmp_path, capsys):
    big = _big_doc(doc)
    snap = tmp_path / "snap.json"
    snap.write_text(json.dumps(big), encoding="utf-8")
    path = _pins([1044], tmp_path)
    assert (
        show_pages.main([str(snap), str(tmp_path / "o"), "--pinned", str(path), "--no-pinned"]) == 0
    )
    assert "pinned list" not in capsys.readouterr().out


# ---- determinism ---------------------------------------------------------------------


def test_two_builds_are_byte_identical(doc, tmp_path):
    big = _big_doc(doc)
    pins = show_pages.load_pinned(_pins([1044, 4242, 1007, 1030], tmp_path))
    show_pages.build_site(big, tmp_path / "a", pinned=pins)
    show_pages.build_site(copy.deepcopy(big), tmp_path / "b", pinned=pins)
    names = sorted(
        p.relative_to(tmp_path / "a") for p in (tmp_path / "a").rglob("*") if p.is_file()
    )
    assert names == sorted(
        p.relative_to(tmp_path / "b") for p in (tmp_path / "b").rglob("*") if p.is_file()
    )
    assert len(names) == 53
    for name in names:
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes()
    # Control: a different list gives a different sitemap, so identity is not vacuous.
    other = show_pages.load_pinned(_pins([1007, 1044], tmp_path))
    show_pages.build_site(big, tmp_path / "c", pinned=other)
    assert (tmp_path / "c" / "sitemap.xml").read_bytes() != (
        tmp_path / "a" / "sitemap.xml"
    ).read_bytes()


# ---- validation -------------------------------------------------------------------------


def _write(tmp_path: Path, body: dict) -> Path:
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(body), encoding="utf-8")
    return path


def _entry(i: int, **over) -> dict:
    return {"lezwatch_id": i, "slug": f"s-{i}", "title": f"T {i}", "reason": "r", **over}


def test_a_valid_file_loads_and_a_bad_one_fails(tmp_path):
    good = {"how_chosen": "x", "shows": [_entry(1), _entry(2)]}
    assert [p.lezwatch_id for p in show_pages.load_pinned(_write(tmp_path, good))] == [1, 2]
    bad_cases = {
        "repeated lezwatch_id": {**good, "shows": [_entry(1), _entry(1, slug="other")]},
        "repeated slug": {**good, "shows": [_entry(1), _entry(2, slug="s-1")]},
        "at most 50": {**good, "shows": [_entry(i) for i in range(1, 52)]},
        "no reason": {**good, "shows": [_entry(1, reason="")]},
        "no reason ": {**good, "shows": [_entry(1, reason=None)]},
        "no title": {**good, "shows": [_entry(1, title=" ")]},
        "no slug": {**good, "shows": [_entry(1, slug=None)]},
        "no integer lezwatch_id": {**good, "shows": [_entry("1")]},
        "no integer lezwatch_id ": {**good, "shows": [_entry(True)]},
        "how_chosen": {"shows": [_entry(1)]},
        "not an object": {**good, "shows": ["x"]},
    }
    for message, body in bad_cases.items():
        path = _write(tmp_path, body)
        assert json.loads(path.read_text()) != good  # the sabotage landed
        with pytest.raises(show_pages.ShowPagesError, match=message.strip()):
            show_pages.load_pinned(path)
    broken = tmp_path / "broken.json"
    broken.write_text("{ nope", encoding="utf-8")
    with pytest.raises(show_pages.ShowPagesError, match="not a pinned list"):
        show_pages.load_pinned(broken)


def test_a_bad_file_fails_the_build_but_the_workflow_flag_turns_it_into_a_notice(
    doc, tmp_path, capsys
):
    snap = tmp_path / "snap.json"
    snap.write_text(json.dumps(_big_doc(doc)), encoding="utf-8")
    path = _write(tmp_path, {"how_chosen": "x", "shows": [_entry(1), _entry(1)]})
    assert show_pages.main([str(snap), str(tmp_path / "o"), "--pinned", str(path)]) == 1
    capsys.readouterr()
    assert not (tmp_path / "o").exists()
    args = [str(snap), str(tmp_path / "o"), "--pinned", str(path), "--notice-on-failure"]
    assert show_pages.main(args) == 0
    assert capsys.readouterr().out.startswith("::notice title=show pages skipped::")


# ---- the real file -------------------------------------------------------------------------


def test_the_real_pinned_file_is_valid_and_documents_every_pick():
    pins = show_pages.load_pinned(show_pages.DEFAULT_PINNED_PATH)
    assert pins is not None and len(pins) == 50
    assert all("search" not in p.reason.lower() or "none claims" in p.reason for p in pins)
    for p in pins:
        assert show_pages.SLUG.fullmatch(p.slug), p
    assert [p.title for p in pins[:3]] == [
        "The L Word",
        "The L Word: Generation Q",
        "Orange is the New Black",
    ]
    header = json.loads(show_pages.DEFAULT_PINNED_PATH.read_text(encoding="utf-8"))["how_chosen"]
    assert "search volume" in header  # says it makes no claim about it
