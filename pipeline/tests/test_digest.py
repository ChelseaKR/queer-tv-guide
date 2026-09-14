from __future__ import annotations

import copy

from qtv_pipeline import digest

BASE_DOC = {
    "schema_version": "1",
    "generated_at": "2026-09-13T00:00:00Z",
    "build": {"pipeline_version": "0.1.0", "run": {"git_sha": "abc123", "workflow_run_id": "1"}},
    "sources": {
        "lezwatch": {"name": "LezWatch.TV", "fetched_at": "2026-09-13T00:00:00Z", "requests": 100, "bytes": 5000, "mode": "full"},
        "tvmaze": {"name": "TVmaze", "fetched_at": "2026-09-13T00:00:00Z", "requests": 50, "bytes": 2000, "mode": "full"},
    },
    "shows": [{"id": "lwtv:show:1", "title": "X"}],
}


def test_digest_ignores_generated_at_and_run_metadata():
    doc_a = copy.deepcopy(BASE_DOC)
    doc_b = copy.deepcopy(BASE_DOC)
    doc_b["generated_at"] = "2099-01-01T00:00:00Z"
    doc_b["build"]["run"] = {"git_sha": "different", "workflow_run_id": "999"}
    doc_b["sources"]["lezwatch"]["fetched_at"] = "2099-01-01T00:00:00Z"
    doc_b["sources"]["lezwatch"]["requests"] = 999
    doc_b["sources"]["tvmaze"]["bytes"] = 1
    doc_b["sources"]["tvmaze"]["mode"] = "incremental"

    assert digest.content_digest(doc_a) == digest.content_digest(doc_b)


def test_digest_changes_when_content_changes():
    doc_a = copy.deepcopy(BASE_DOC)
    doc_b = copy.deepcopy(BASE_DOC)
    doc_b["shows"][0]["title"] = "Y"

    assert digest.content_digest(doc_a) != digest.content_digest(doc_b)


def test_digest_format():
    d = digest.content_digest(BASE_DOC)
    assert d.startswith("sha256:")
    assert len(d) == len("sha256:") + 64
