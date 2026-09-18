"""The `qtv` command line: each subcommand's exit status and what it prints.

Offline throughout. `fetch` and `terms-check` are driven through the same
fixture-backed MockTransport as the end-to-end build test, by swapping the
client factory the CLI uses; nothing reaches LezWatch or TVmaze.
"""

from __future__ import annotations

import json

import pytest

from qtv_pipeline import build as build_mod
from qtv_pipeline import cli
from qtv_pipeline import http as http_mod


def _fixture_client(transport, sleep):
    def factory(**kwargs):
        return http_mod.PacedClient(transport=transport, sleep=sleep, **kwargs)

    return factory


@pytest.fixture
def offline_fetch(monkeypatch, mock_transport, no_sleep):
    """Make `qtv fetch` use the fixture transport instead of the network."""
    sleep, _ = no_sleep
    real_run_fetch = build_mod.run_fetch

    def run_fetch(cache_dir, *, full, log):
        return real_run_fetch(
            cache_dir, full=full, log=log, client_factory=_fixture_client(mock_transport, sleep)
        )

    monkeypatch.setattr(build_mod, "run_fetch", run_fetch)


def test_no_subcommand_is_a_usage_error(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main([])
    assert exc.value.code == 2
    assert "usage: qtv" in capsys.readouterr().err


def test_fetch_build_validate_round_trip(tmp_path, offline_fetch, capsys):
    cache, out = tmp_path / "cache", tmp_path / "out"
    assert cli.main(["fetch", "--cache", str(cache), "--full"]) == 0
    args = ["build", "--cache", str(cache), "--out", str(out), "--git-sha", "abc123"]
    assert cli.main([*args, "--workflow-run-id", "7"]) == 0
    snapshot = out / "snapshot.v1.json"
    doc = json.loads(snapshot.read_text())
    assert doc["build"]["run"] == {"git_sha": "abc123", "workflow_run_id": "7"}
    capsys.readouterr()

    assert cli.main(["validate", str(snapshot)]) == 0
    assert f"ok: {snapshot} validates against" in capsys.readouterr().out


def test_build_takes_the_run_identity_from_the_environment(tmp_path, offline_fetch, monkeypatch):
    cache, out = tmp_path / "cache", tmp_path / "out"
    assert cli.main(["fetch", "--cache", str(cache)]) == 0
    monkeypatch.setenv("GITHUB_SHA", "f00d")
    monkeypatch.setenv("GITHUB_RUN_ID", "99")
    assert cli.main(["build", "--cache", str(cache), "--out", str(out)]) == 0
    doc = json.loads((out / "snapshot.v1.json").read_text())
    assert doc["build"]["run"] == {"git_sha": "f00d", "workflow_run_id": "99"}


def test_build_without_a_fetch_fails_and_writes_nothing(tmp_path, capsys):
    out = tmp_path / "out"
    assert cli.main(["build", "--cache", str(tmp_path / "empty"), "--out", str(out)]) == 1
    assert "build failed:" in capsys.readouterr().err
    assert not out.exists()


def test_validate_reports_each_error_and_fails(tmp_path, offline_fetch, capsys):
    cache, out = tmp_path / "cache", tmp_path / "out"
    assert cli.main(["fetch", "--cache", str(cache)]) == 0
    assert cli.main(["build", "--cache", str(cache), "--out", str(out)]) == 0
    doc = json.loads((out / "snapshot.v1.json").read_text())
    # The contract's own rule: a death is `true` or `null`, never `false`.
    doc["characters"][0]["death"]["died"] = False
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(doc))
    assert json.loads(bad.read_text())["characters"][0]["death"]["died"] is False
    capsys.readouterr()

    assert cli.main(["validate", str(bad)]) == 1
    err = capsys.readouterr().err
    assert "characters/0/death/died" in err
    assert "validation error(s)" in err


def test_validate_accepts_an_explicit_schema(tmp_path, capsys):
    schema = tmp_path / "schema.json"
    schema.write_text(json.dumps({"type": "object", "required": ["x"]}))
    doc = tmp_path / "doc.json"
    doc.write_text(json.dumps({"x": 1}))
    assert cli.main(["validate", str(doc), "--schema", str(schema)]) == 0
    assert str(schema) in capsys.readouterr().out


def test_fetch_failure_exits_1(tmp_path, monkeypatch, capsys):
    def refuse(cache_dir, *, full, log):
        raise build_mod.BuildError("terms changed")

    monkeypatch.setattr(build_mod, "run_fetch", refuse)
    assert cli.main(["fetch", "--cache", str(tmp_path)]) == 1
    assert "fetch failed: terms changed" in capsys.readouterr().err


def test_terms_check_reports_the_grant(monkeypatch, mock_transport, no_sleep, capsys):
    sleep, _ = no_sleep
    monkeypatch.setattr(cli, "PacedClient", _fixture_client(mock_transport, sleep))
    assert cli.main(["terms-check"]) == 0
    assert "still grants reuse" in capsys.readouterr().out


def test_terms_check_stops_when_the_grant_is_gone(monkeypatch, mock_transport_no_grant, no_sleep):
    from qtv_pipeline.terms import TermsChanged

    sleep, _ = no_sleep
    monkeypatch.setattr(cli, "PacedClient", _fixture_client(mock_transport_no_grant, sleep))
    with pytest.raises(TermsChanged):
        cli.main(["terms-check"])
