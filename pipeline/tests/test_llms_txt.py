"""/llms.txt: published with the home page, served by GitHub Pages as
text/plain, crediting both sources, and never naming a show, a character or
an answer. The spoiler check has a negative control: a file that names a
show must fail it."""

from __future__ import annotations

import json
import mimetypes
import re
from pathlib import Path

import pytest

from qtv_pipeline import show_pages, site_index

REPO = Path(__file__).resolve().parents[2]
FIXTURE = REPO / "ios" / "GuideCore" / "Tests" / "Fixtures" / "snapshot.fixture.json"
BASE = "https://example.test/qf"


@pytest.fixture
def doc() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture
def built(doc, tmp_path) -> str:
    show_pages.build_site(doc, tmp_path, base_url=BASE)
    written = site_index.write_site(doc, tmp_path / "index.html", base_url=BASE)
    assert tmp_path / "llms.txt" in written
    return (tmp_path / "llms.txt").read_text(encoding="utf-8")


def names_in(text: str, doc: dict) -> list[str]:
    """Every show title or character name the text contains."""
    names = [s["title"] for s in doc["shows"]] + [c["name"] for c in doc["characters"]]
    return [n for n in names if n and re.search(rf"\b{re.escape(n)}\b", text)]


def test_llms_txt_is_text_and_follows_the_format(built):
    assert mimetypes.guess_type("llms.txt")[0] == "text/plain"
    assert built.startswith("# Queer Frame\n\n> ")
    assert "\n## Pages\n" in built and "\n## Sources\n" in built
    assert f"[All shows, A to Z]({BASE}/shows/)" in built
    for phrase in ("queer women, non-binary and trans characters", "hidden until", "no analytics"):
        assert phrase in built, phrase


def test_llms_txt_credits_both_sources(built, doc):
    for a in doc["attribution"]:
        assert f"[{a['name']}]({a['url']})" in built
        assert a["licence_name"] in built
    assert "CC BY-SA 4.0" in built


def test_llms_txt_never_names_a_show_or_states_an_answer(built, doc):
    assert names_in(built, doc) == []
    assert not re.search(r"\b(dies|died|is killed|survives)\b", built, re.I)
    # Negative control: the check notices a named show.
    title = doc["shows"][0]["title"]
    assert names_in(built + f"\n{title}\n", doc) == [title]


def test_llms_txt_has_no_placeholder(built):
    for bad in ("TO" + "DO", "T" + "BD", "lorem", "X" * 3, "None", "{", "}"):
        assert bad not in built, bad


def test_llms_txt_without_shows_links_no_show_page(doc):
    bare = site_index.render_llms(doc, base_url=BASE)
    assert "/shows/" not in bare
