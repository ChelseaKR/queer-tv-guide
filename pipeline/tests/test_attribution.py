"""The published snapshot carries every credit its sources require, and the
Pages index shows them with links. Negative controls prove each check can
fail."""

from __future__ import annotations

import copy

import pytest

from qtv_pipeline import licence, site_index
from tests.test_build_end_to_end import _run


@pytest.fixture
def built_doc(tmp_path, mock_transport, no_sleep):
    """The same offline end-to-end build as test_build_end_to_end.py."""
    sleep, _ = no_sleep
    return _run(tmp_path, mock_transport, sleep)


def test_built_snapshot_meets_every_attribution_requirement(built_doc):
    doc, _cache, _out = built_doc
    assert licence.attribution_problems(doc) == []


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
            "TVmaze attribution does not link the CC BY-SA 4.0 licence",
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
    problems = licence.attribution_problems(broken)
    assert any(expected in p for p in problems), problems


def test_a_joined_schedule_without_a_tvmaze_url_is_caught(built_doc):
    doc, _cache, _out = built_doc
    broken = copy.deepcopy(doc)
    joined = next(s for s in broken["shows"] if s["schedule"]["schedule_known"])
    joined["schedule"]["tvmaze_url"] = None
    assert any(
        "schedule shown without a TVmaze URL" in p for p in licence.attribution_problems(broken)
    )


def test_pages_index_shows_licence_and_linked_credits(built_doc):
    doc, _cache, _out = built_doc
    page = site_index.render_index(doc)
    assert licence.LICENCE_NOTICE in page
    assert f'href="{licence.SNAPSHOT_LICENCE["url"]}"' in page
    for source in licence.ATTRIBUTION:
        assert f'href="{source["url"]}"' in page, source["name"]
        assert f'href="{source["licence_url"]}"' in page, source["name"]
    assert "does not endorse this app" in page
    assert 'href="privacy.html"' in page and 'href="support.html"' in page
    assert "<script" not in page.lower()


def test_pages_index_escapes_source_text(built_doc):
    doc, _cache, _out = built_doc
    hostile = copy.deepcopy(doc)
    hostile["attribution"][0]["text"] = "<script>alert(1)</script>"
    assert "<script>" not in site_index.render_index(hostile)


def test_site_index_cli_writes_the_page(built_doc, tmp_path):
    _doc, _cache, out_dir = built_doc
    target = tmp_path / "index.html"
    assert site_index.main([str(out_dir / "snapshot.v1.json"), str(target)]) == 0
    assert licence.LICENCE_NOTICE in target.read_text()
