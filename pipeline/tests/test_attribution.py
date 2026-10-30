"""The published snapshot carries every credit its sources require, and the
Pages index shows them with links. Negative controls prove each check can
fail."""

from __future__ import annotations

import copy

import pytest

from qtv_pipeline import license, site_index
from tests.test_build_end_to_end import _run


@pytest.fixture
def built_doc(tmp_path, mock_transport, no_sleep):
    """The same offline end-to-end build as test_build_end_to_end.py."""
    sleep, _ = no_sleep
    return _run(tmp_path, mock_transport, sleep)


def test_built_snapshot_meets_every_attribution_requirement(built_doc):
    doc, _cache, _out = built_doc
    assert license.attribution_problems(doc) == []


@pytest.mark.parametrize(
    ("sabotage", "expected"),
    [
        (lambda d: d["attribution"].pop(0), "no LezWatch.TV attribution entry"),
        (lambda d: d["attribution"].pop(1), "no TVmaze attribution entry"),
        (
            lambda d: d["attribution"][0].update(
                text=d["attribution"][0]["text"].replace("does not endorse", "endorses")
            ),
            "LezWatch.TV attribution lacks the non-endorsement statement",
        ),
        (
            lambda d: d["attribution"][1].update(licence_url="https://example.org/"),
            "TVmaze attribution does not link the CC BY-SA 4.0 license",
        ),
        (lambda d: d["licence"]["snapshot"].update(spdx="CC-BY-4.0"), "licence.snapshot.spdx"),
        (lambda d: d["shows"][0].update(source_url=""), "no LezWatch.TV page to link"),
        (lambda d: d["characters"][0].update(source_url=""), "no LezWatch.TV page to link"),
    ],
)
def test_each_missing_credit_is_caught(built_doc, sabotage, expected):
    doc, _cache, _out = built_doc
    broken = copy.deepcopy(doc)
    sabotage(broken)
    assert broken != doc  # the sabotage landed
    problems = license.attribution_problems(broken)
    assert any(expected in p for p in problems), problems


def test_a_joined_schedule_without_a_tvmaze_url_is_caught(built_doc):
    doc, _cache, _out = built_doc
    broken = copy.deepcopy(doc)
    joined = next(s for s in broken["shows"] if s["schedule"]["schedule_known"])
    joined["schedule"]["tvmaze_url"] = None
    assert any(
        "schedule shown without a TVmaze URL" in p for p in license.attribution_problems(broken)
    )


@pytest.mark.parametrize("render", [site_index.render_index, site_index.render_data_page])
def test_home_and_data_pages_show_license_and_linked_credits(built_doc, render):
    doc, _cache, _out = built_doc
    page = render(doc)
    assert license.LICENSE_NOTICE in page
    assert f'href="{license.SNAPSHOT_LICENSE["url"]}"' in page
    for source in license.ATTRIBUTION:
        assert f'href="{source["url"]}"' in page, source["name"]
        assert f'href="{source["licence_url"]}"' in page, source["name"]
        assert source["text"] in page, source["name"]
    assert "does not endorse this app" in page
    for path in ("privacy.html", "support.html", "data/"):
        assert f'href="https://queerframe.app/{path}"' in page, path


def test_the_home_page_says_the_sources_do_not_endorse_the_app(built_doc):
    doc, _cache, _out = built_doc
    page = site_index.render_index(doc)
    assert "LezWatch.TV and TVmaze do not endorse this app." in page
    assert "<script" not in page.lower()


def test_the_data_page_links_the_files_at_their_unchanged_urls(built_doc):
    doc, _cache, _out = built_doc
    page = site_index.render_data_page(doc)
    for name in ("snapshot.v1.json", "snapshot.v1.json.sha256"):
        assert f'href="https://queerframe.app/{name}"' in page, name
    assert doc["content_digest"] in page and doc["generated_at"] in page
    assert '<link rel="canonical" href="https://queerframe.app/data/">' in page


def test_pages_index_escapes_source_text(built_doc):
    doc, _cache, _out = built_doc
    hostile = copy.deepcopy(doc)
    hostile["attribution"][0]["text"] = "<script>alert(1)</script>"
    assert "<script>" not in site_index.render_index(hostile)


def test_site_index_cli_writes_the_page(built_doc, tmp_path):
    _doc, _cache, out_dir = built_doc
    target = tmp_path / "index.html"
    assert site_index.main([str(out_dir / "snapshot.v1.json"), str(target)]) == 0
    assert license.LICENSE_NOTICE in target.read_text()
    assert license.LICENSE_NOTICE in (tmp_path / "data" / "index.html").read_text()
