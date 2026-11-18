"""/llms.txt while the app is on the App Store (the owner's wording W1,
approved 2026-11-18): it no longer says the app is coming, it links the app
with the campaign token ``llms``, and it links the findings and press pages.
With the switch off the file is what it was.

The built file is read as plain text, line by line; the app link is taken
apart with urllib.parse. No pattern is run over HTML."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from qtv_pipeline import app_store, show_pages, site_index

REPO = Path(__file__).resolve().parents[2]
FIXTURE = REPO / "ios" / "GuideCore" / "Tests" / "Fixtures" / "snapshot.fixture.json"
SITE = "https://queerframe.app"

# The approved text, word for word (README section 5 of
# growth/bing-ai-2026-11-17, approved by the owner on 2026-11-18).
APPROVED_CADENCE = "Update cadence: the data is rebuilt once a day (09:17 UTC)."
OLD_CADENCE = (
    "Update cadence: the data is rebuilt once a day (09:17 UTC). The iPhone app is "
    "linked from the home page once it is on the App Store."
)
APPROVED_LINES = [
    "- [Queer Frame for iPhone](https://apps.apple.com/app/id6818637465?pt=129452704&ct=llms&mt=8): "
    "covers 2,200+ shows offline: a one-time purchase ($4.99 in the US), no subscription",
    "- [When queer TV characters die: season finales](https://queerframe.app/findings/finales/): "
    "a dated analysis of LezWatch.TV and TVmaze data",
    "- [Press](https://queerframe.app/press/)",
]


@pytest.fixture
def doc() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def with_shows(doc: dict, count: int) -> dict:
    """The fixture with ``count`` shows, the size of the live snapshot. Only
    the number of shows feeds the app line."""
    big = dict(doc)
    big["shows"] = [dict(doc["shows"][i % len(doc["shows"])]) for i in range(count)]
    return big


def pages_section(text: str) -> list[str]:
    lines = text.split("\n")
    start = lines.index("## Pages") + 1
    end = lines.index("## Sources")
    return [line for line in lines[start:end] if line]


def test_on_the_file_carries_the_approved_text_word_for_word(doc):
    text = site_index.render_llms(with_shows(doc, 2231), base_url=SITE, app_store_live=True)
    lines = text.split("\n")
    assert APPROVED_CADENCE in lines
    assert OLD_CADENCE not in text
    assert "once it is on the App Store" not in text
    assert pages_section(text)[-3:] == APPROVED_LINES
    for line in APPROVED_LINES:
        assert lines.count(line) == 1, line


def test_off_the_file_is_what_it_was(doc):
    off = site_index.render_llms(with_shows(doc, 2231), base_url=SITE)
    on = site_index.render_llms(with_shows(doc, 2231), base_url=SITE, app_store_live=True)
    assert OLD_CADENCE in off.split("\n")
    for line in APPROVED_LINES:
        assert line not in off
    assert "apps.apple.com" not in off
    # The two files differ by exactly the approved changes and nothing else.
    restored = on.replace(APPROVED_CADENCE, OLD_CADENCE, 1)
    for line in APPROVED_LINES:
        restored = restored.replace(line + "\n", "", 1)
    assert restored == off


def test_the_app_link_carries_the_llms_campaign_token(doc):
    text = site_index.render_llms(with_shows(doc, 2231), base_url=SITE, app_store_live=True)
    line = next(x for x in pages_section(text) if x.startswith("- [Queer Frame for iPhone]("))
    url = line.removeprefix("- [Queer Frame for iPhone](").split("): ", 1)[0]
    parts = urlsplit(url)
    assert f"{parts.scheme}://{parts.netloc}{parts.path}" == app_store.APP_STORE_URL
    assert parse_qs(parts.query) == {
        "pt": [app_store.APP_STORE_PROVIDER_TOKEN],
        "ct": ["llms"],
        "mt": ["8"],
    }
    assert "llms" in app_store.CAMPAIGNS


@pytest.mark.parametrize(
    ("count", "covers"),
    [
        (2231, "covers 2,200+ shows offline"),
        (2299, "covers 2,200+ shows offline"),
        (100, "covers 100+ shows offline"),
    ],
)
def test_the_show_count_is_rounded_down_as_on_the_show_pages(doc, count, covers):
    text = site_index.render_llms(with_shows(doc, count), base_url=SITE, app_store_live=True)
    assert f"): {covers}: a one-time purchase ($4.99 in the US), no subscription\n" in text
    top = app_store.app_line_text(None, count)
    assert covers in top  # the same words as a show page's top line


def test_under_one_hundred_shows_no_count_is_given(doc):
    assert len(doc["shows"]) < 100
    text = site_index.render_llms(doc, base_url=SITE, app_store_live=True)
    assert "): works offline: a one-time purchase ($4.99 in the US), no subscription\n" in text
    assert "0+" not in text and "covers" not in text


def test_the_pages_the_new_lines_link_are_published(doc, tmp_path):
    """privacy.html and support.html come from docs/site/ in the workflow, so
    only the two pages these lines add are checked against write_site."""
    show_pages.build_site(doc, tmp_path, base_url=SITE)
    site_index.write_site(doc, tmp_path / "index.html", base_url=SITE, app_store_live=True)
    text = (tmp_path / "llms.txt").read_text(encoding="utf-8")
    new = [line for line in pages_section(text) if line in APPROVED_LINES[1:]]
    assert new == APPROVED_LINES[1:]
    for line in new:
        rel = line.split("](", 1)[1].split(")", 1)[0].removeprefix(SITE + "/")
        assert (tmp_path / rel / "index.html").is_file(), rel


def test_on_the_file_still_names_no_show_and_no_answer(doc, tmp_path):
    show_pages.build_site(doc, tmp_path, base_url=SITE)
    site_index.write_site(doc, tmp_path / "index.html", base_url=SITE, app_store_live=True)
    text = (tmp_path / "llms.txt").read_text(encoding="utf-8")

    def named(t: str) -> list[str]:
        names = [s["title"] for s in doc["shows"]] + [c["name"] for c in doc["characters"]]
        return [n for n in names if n and n in t]

    assert named(text) == []
    for word in (" dies", " died", " is killed", " survives"):
        assert word not in text.lower(), word
    # Negative control: the check notices a named show.
    title = doc["shows"][0]["title"]
    assert named(text + "\n" + title + "\n") == [title]


def test_the_switch_reaches_the_file_through_main(doc, tmp_path):
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text(json.dumps(with_shows(doc, 2231)), encoding="utf-8")
    out = tmp_path / "site"
    out.mkdir()
    assert site_index.main([str(snapshot), str(out / "index.html"), "true"]) == 0
    on = (out / "llms.txt").read_text(encoding="utf-8")
    assert APPROVED_LINES[0] in on
    assert site_index.main([str(snapshot), str(out / "index.html"), "false"]) == 0
    off = (out / "llms.txt").read_text(encoding="utf-8")
    assert OLD_CADENCE in off and "apps.apple.com" not in off
