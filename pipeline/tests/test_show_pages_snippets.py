"""Search titles and descriptions never answer the question (DECISIONS 0045).

A show page's ``<title>`` and meta description are what Google shows in a
result, before anyone has chosen to see a spoiler. They lead with the count of
listed characters and the show, then ask whether anyone dies; they must never
say who does. Two checks:

* no answer word (``died``, ``dead``, ``survives`` and the like) and no
  recorded death year in a title or description of a show with a recorded
  death, outside the one fixed sentence every page shares;
* the titles and descriptions are byte-identical whether every listed
  character dies or none does.

Each negative control asserts that its sabotage changed the output before it
asserts the checker caught it, so a sabotage that silently no-ops cannot pass.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import pytest

from qtv_pipeline import show_pages
from tests import htmlprobe

REPO = Path(__file__).resolve().parents[2]
FIXTURE = REPO / "ios" / "GuideCore" / "Tests" / "Fixtures" / "snapshot.fixture.json"
BUNDLED = REPO / "ios" / "QueerTVGuide" / "Resources" / "snapshot.v1.json"
BASE = "https://example.test/qf"

# Words that answer "does she die". "die" in the question "Do any die?" and
# "dies" in DESCRIPTION_TAIL ask; they do not answer, so they are not here.
ANSWER_WORDS = re.compile(
    r"\b(dies|died|dead|death|deaths|deceased|killed|kills|murdered|survives?|survived|"
    r"survivors?|alive|buried|perish\w*|fatal\w*|rip|r\.i\.p\.?)\b",
    re.IGNORECASE,
)


@pytest.fixture
def doc() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _snippets(doc: dict, out: Path) -> dict[str, tuple[str, str]]:
    show_pages.build_site(doc, out, base_url=BASE)
    pages = {}
    for p in sorted((out / "shows").glob("*/index.html")):
        page = htmlprobe.parse(p.read_text(encoding="utf-8"))
        pages[p.parent.name] = (page.title, page.description)
    return pages


def _death_years(doc: dict, slug: str) -> set[str]:
    show = next(s for s in doc["shows"] if s["slug"] == slug)
    years: set[str] = set()
    for c in doc["characters"]:
        if any(link.get("show_id") == show["id"] for link in c.get("shows", [])):
            years |= {str(y) for y in c["death"].get("years", [])}
    return years


def _with_deaths(doc: dict) -> set[str]:
    return {
        s["slug"]
        for s in show_pages.select_shows(doc)
        if any(c.dies for c in show_pages._characters(doc, s))
    }


def answer_problems(doc: dict, snippets: dict[str, tuple[str, str]]) -> list[str]:
    """Every title or description of a show with a recorded death that holds
    an answer word or a death year, outside the shared fixed sentence and
    the show's own name."""
    problems = []
    titles = {s["slug"]: s["title"] for s in doc["shows"]}
    for slug in sorted(_with_deaths(doc) & snippets.keys()):
        years = _death_years(doc, slug)
        for kind, text in zip(("title", "description"), snippets[slug], strict=True):
            # The show's own name ("The Walking Dead") is not an answer.
            rest = text.replace(show_pages.DESCRIPTION_TAIL, "").replace(titles[slug], "")
            if m := ANSWER_WORDS.search(rest):
                problems.append(f"{slug} {kind}: answer word {m.group(0)!r}")
            for y in sorted(years):
                if re.search(rf"\b{y}\b", rest):
                    problems.append(f"{slug} {kind}: death year {y}")
    return problems


def _set_all_deaths(doc: dict, died: bool) -> dict:
    out = copy.deepcopy(doc)
    for c in out["characters"]:
        years = sorted({int(y) for link in c.get("shows", []) for y in link.get("years", [])})
        c["death"] = (
            {"death_known": True, "died": True, "years": years[-1:], "dates": []}
            if died
            else {"death_known": False, "died": None, "years": [], "dates": []}
        )
    return out


def invariance_problems(doc: dict, tmp: Path) -> list[str]:
    """Shows whose title or description changes with who dies."""
    base = _snippets(doc, tmp / "as-recorded")
    problems = []
    for label, flipped in (("all die", True), ("none die", False)):
        other = _snippets(_set_all_deaths(doc, flipped), tmp / label.replace(" ", "-"))
        for slug, pair in base.items():
            if other.get(slug) != pair:
                problems.append(f"{slug}: snippet changes when {label}")
    return problems


# --- the checks on the fixture --------------------------------------------


def test_fixture_has_a_show_with_a_recorded_death(doc):
    # Without one, the answer-word check below would pass on nothing.
    assert _with_deaths(doc) == {"the-cartographers"}


def test_no_answer_in_titles_or_descriptions(doc, tmp_path):
    snippets = _snippets(doc, tmp_path)
    assert _with_deaths(doc) <= snippets.keys()
    assert answer_problems(doc, snippets) == []


def test_snippets_do_not_change_with_who_dies(doc, tmp_path):
    # The flips really change the answers, or the comparison proves nothing.
    show = next(s for s in doc["shows"] if s["slug"] == "harbor-lights")
    before = show_pages._answer(show, show_pages._characters(doc, show)).headline
    flipped = _set_all_deaths(doc, True)
    after = show_pages._answer(show, show_pages._characters(flipped, show)).headline
    assert before != after
    assert invariance_problems(doc, tmp_path) == []


def test_snapshot_of_the_fixture_snippets(doc, tmp_path):
    tail = show_pages.DESCRIPTION_TAIL
    assert _snippets(doc, tmp_path) == {
        "harbor-lights": (
            "2 LGBTQ characters in Harbor Lights. Do any die? No spoilers",
            "LezWatch.TV lists 2 LGBTQ characters in Harbor Lights: Mara Quill (lesbian) and "
            f"Inés Varga (bisexual). {tail}",
        ),
        "salt-and-ember": (
            "LGBTQ characters in Salt & Ember. Do any die? No spoilers",
            "LezWatch.TV lists one LGBTQ character in Salt & Ember: Juno Adeyemi (non-binary). "
            f"{tail}",
        ),
        "the-cartographers": (
            "2 LGBTQ characters in The Cartographers. Do any die?",
            "LezWatch.TV lists 2 LGBTQ characters in The Cartographers: Odile Brandt (lesbian) "
            f"and Thea Marsh (queer). {tail}",
        ),
    }


@pytest.mark.parametrize(
    "name",
    ["ER", "FROM", "Will Trent", "The Good Wife", "Orange Is the New Black", "X" * 70],
)
@pytest.mark.parametrize("count", [0, 1, 2, 12, 61])
def test_lengths(name, count):
    title = show_pages.show_title(name, count)
    assert 0 < len(title) <= show_pages.TITLE_MAX
    names = ["Kerry Weaver", "Maggie Doyle", "Kim Legaspi"][: min(count, 3)]
    labels = ["lesbian", "lesbian", "bisexual"][: len(names)]
    text = show_pages.show_description(name, names, count, labels)
    assert len(text) <= show_pages.DESCRIPTION_MAX
    # Show pages list at least two characters in practice; one character and
    # a short title can leave a description a little under the floor.
    if len(name) < 40 and count != 1:
        assert len(text) >= show_pages.DESCRIPTION_MIN, text
    assert text.endswith((show_pages.DESCRIPTION_TAIL, show_pages.DESCRIPTION_PAD, "…"))


def test_the_fixed_sentences_answer_nothing():
    for text in (show_pages.DESCRIPTION_TAIL, show_pages.DESCRIPTION_PAD):
        assert not ANSWER_WORDS.search(text.replace("anyone dies", ""))
    assert not ANSWER_WORDS.search(show_pages.show_title("Any Show", 9))


# --- negative controls: the checkers catch a leak -------------------------


def _leaky_description(name: str, cast: list[show_pages.CharacterView]) -> str:
    dead = [c.name for c in cast if c.dies]
    text = show_pages.show_description(name, [c.name for c in cast], len(cast))
    return f"{dead[0]} died. {text}" if dead else text


def test_negative_control_answer_word_is_caught(doc, tmp_path, monkeypatch):
    clean = _snippets(doc, tmp_path / "clean")
    monkeypatch.setattr(show_pages, "_description", _leaky_description)
    leaky = _snippets(doc, tmp_path / "leaky")
    # The sabotage applied: the page with a death now says who died.
    assert leaky["the-cartographers"] != clean["the-cartographers"]
    assert leaky["the-cartographers"][1].startswith("Odile Brandt died.")
    assert answer_problems(doc, leaky) == ["the-cartographers description: answer word 'died'"]


def test_negative_control_death_year_is_caught(doc, tmp_path, monkeypatch):
    real = show_pages.show_title

    def leaky_title(name: str, count: int = 0) -> str:
        return f"{name} (2017)" if name == "The Cartographers" else real(name, count)

    for c in doc["characters"]:
        if c["name"] == "Odile Brandt":
            c["death"] = {"death_known": True, "died": True, "years": [2017], "dates": []}
    monkeypatch.setattr(show_pages, "show_title", leaky_title)
    leaky = _snippets(doc, tmp_path)
    assert leaky["the-cartographers"][0] == "The Cartographers (2017)"
    assert "the-cartographers title: death year 2017" in answer_problems(doc, leaky)


def test_negative_control_invariance_is_caught(doc, tmp_path, monkeypatch):
    monkeypatch.setattr(show_pages, "_description", _leaky_description)
    problems = invariance_problems(doc, tmp_path)
    # Every listed character dies in the "all die" build, so every page changes.
    assert {p.split(":")[0] for p in problems} == {
        "harbor-lights",
        "salt-and-ember",
        "the-cartographers",
    }


# --- the real snapshot, when it is bundled ---------------------------------


@pytest.mark.skipif(not BUNDLED.is_file(), reason="needs `make -C ios bundle-snapshot`")
def test_real_snapshot_snippets(tmp_path):
    real = json.loads(BUNDLED.read_text(encoding="utf-8"))
    snippets = _snippets(real, tmp_path)
    assert len(_with_deaths(real) & snippets.keys()) >= 50
    assert answer_problems(real, snippets) == []
    titles = [t for t, _ in snippets.values()]
    descriptions = [d for _, d in snippets.values()]
    assert all(len(t) <= show_pages.TITLE_MAX for t in titles)
    assert all(len(d) <= show_pages.DESCRIPTION_MAX for d in descriptions)
    assert sum(len(d) < show_pages.DESCRIPTION_MIN for d in descriptions) <= len(descriptions) // 50
    assert sum(t.endswith("…") for t in titles) <= len(titles) // 50
