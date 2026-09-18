from __future__ import annotations

import copy
import json

import jsonschema
import pytest

from qtv_pipeline import build as build_mod


def _run(tmp_path, transport, sleep):
    from qtv_pipeline.http import PacedClient

    cache_dir = tmp_path / "cache"
    out_dir = tmp_path / "out"

    def client_factory(**kwargs):
        return PacedClient(transport=transport, sleep=sleep, **kwargs)

    build_mod.run_fetch(cache_dir, full=True, log=lambda _msg: None, client_factory=client_factory)
    doc = build_mod.run_build(
        cache_dir, out_dir, git_sha="deadbeef", workflow_run_id="123", log=lambda _msg: None
    )
    return doc, cache_dir, out_dir


@pytest.fixture
def built_doc(tmp_path, mock_transport, no_sleep):
    sleep, _ = no_sleep
    doc, cache_dir, out_dir = _run(tmp_path, mock_transport, sleep)
    return doc, cache_dir, out_dir


def test_full_run_validates_against_the_schema(built_doc):
    doc, _cache, out_dir = built_doc
    schema = json.loads(build_mod._find_schema_path().read_text())
    jsonschema.Draft202012Validator(schema).validate(doc)
    assert (out_dir / "snapshot.v1.json").exists()
    assert (out_dir / "snapshot.v1.json.sha256").exists()
    assert (out_dir / "coverage.json").exists()


def test_shows_and_characters_counted(built_doc):
    doc, _cache, _out = built_doc
    assert len(doc["shows"]) == 5
    assert len(doc["characters"]) == 2
    assert [s["lwtv_id"] for s in doc["shows"]] == sorted(s["lwtv_id"] for s in doc["shows"])


def test_derry_girls_join_and_counts(built_doc):
    doc, _cache, _out = built_doc
    derry = next(s for s in doc["shows"] if s["slug"] == "derry-girls")
    assert derry["schedule"]["schedule_known"] is True
    assert derry["schedule"]["join"]["method"] == "lwtv_tvmaze_id"
    assert derry["schedule"]["tvmaze_id"] == 33320
    assert derry["counts"]["characters"] == 2
    assert derry["counts"]["deaths"] == 1  # marielle, not camille


def test_dangling_similar_show_ids_are_filtered(built_doc):
    """Derry Girls' real lezshows_similar_shows references ids not present in
    this fixture set; build.py must drop them rather than leave dangling refs."""
    doc, _cache, _out = built_doc
    derry = next(s for s in doc["shows"] if s["slug"] == "derry-girls")
    assert derry["similar_show_ids"] == []


def test_join_miss_reasons_all_represented(built_doc):
    doc, _cache, _out = built_doc
    tv = doc["coverage"]["tvmaze"]
    assert tv["shows_total"] == 5
    assert tv["joined"] == 2  # derry-girls (stored id) + imdb-only-show (imdb lookup)
    assert tv["misses"] == {"no_key": 1, "ignored_by_source": 1, "not_found": 1, "other": 0}
    assert tv["join_rate"] == pytest.approx(2 / 5)


def test_imdb_only_show_joined_via_lookup(built_doc):
    doc, _cache, _out = built_doc
    show = next(s for s in doc["shows"] if s["slug"] == "imdb-only-show")
    assert show["schedule"]["join"]["method"] == "imdb_lookup"
    assert show["schedule"]["tvmaze_id"] == 55555
    assert show["schedule"]["next_episode"]["name"] == "Episode 2"


def test_coverage_reports_fetched_vs_available(built_doc):
    doc, _cache, _out = built_doc
    lw = doc["coverage"]["lezwatch"]
    assert lw["shows"] == {"available": 5, "fetched": 5}
    assert lw["characters"] == {"available": 2, "fetched": 2}


def test_content_digest_is_stable_across_rebuilds(tmp_path, mock_transport, no_sleep):
    sleep, _ = no_sleep
    doc1, _cache1, _out1 = _run(tmp_path / "run1", mock_transport, sleep)
    doc2, _cache2, _out2 = _run(tmp_path / "run2", mock_transport, sleep)
    assert doc1["content_digest"] == doc2["content_digest"]


def test_no_death_ever_serializes_as_false(built_doc):
    doc, _cache, _out = built_doc
    for char in doc["characters"]:
        assert char["death"]["died"] is not False


# ---- negative control: prove the schema actually rejects died: false ----------


def test_schema_rejects_died_false(built_doc):
    """Sabotage a real, fully-built document by flipping one character's
    death.died to False (the exact bug this contract forbids), and confirm
    jsonschema actually catches it -- proving the constraint is live, not
    just documented."""
    doc, _cache, _out = built_doc
    schema = json.loads(build_mod._find_schema_path().read_text())
    validator = jsonschema.Draft202012Validator(schema)

    sabotaged = copy.deepcopy(doc)
    sabotaged["characters"][0]["death"]["died"] = False  # the forbidden value
    errors = list(validator.iter_errors(sabotaged))
    assert errors, "schema must reject died: false, but validation passed"
    assert any("died" in "/".join(str(p) for p in e.path) for e in errors)

    # and the untouched original still validates -- the sabotage, not the schema, was the problem
    validator.validate(doc)
