"""IndexNow (qtv_pipeline/indexnow.py, DECISIONS 0034): the page manifest,
selection, submission and the snapshot workflow, with a fake HTTP client and
negative controls. Nothing here touches the network."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from qtv_pipeline import indexnow as ix
from qtv_pipeline import show_pages, site_index

BASE = "https://example.test"
DOMAIN = "https://queerframe.app"
# Deliberately low-entropy so the secret scanners do not read it as a key; a
# real IndexNow key is public by design anyway.
KEY = "ab" * 16
PAGE = "<html><head><title>t</title></head><body>x</body></html>"
NOINDEX = '<html><head><meta name="robots" content="noindex,follow"></head></html>'
REPO = Path(__file__).resolve().parents[2]
WORKFLOW = REPO / ".github" / "workflows" / "snapshot.yml"
FIXTURE = REPO / "ios" / "GuideCore" / "Tests" / "Fixtures" / "snapshot.fixture.json"
ASSETS = REPO / "pipeline" / "src" / "qtv_pipeline" / "assets"


class FakeClient:
    def __init__(self, status: int = 200, raises: Exception | None = None) -> None:
        self.status, self.raises = status, raises
        self.calls: list[tuple[str, dict[str, Any], dict[str, str]]] = []

    def post_json(self, url: str, body: bytes, headers: Mapping[str, str]) -> int:
        self.calls.append((url, json.loads(body), dict(headers)))
        if self.raises:
            raise self.raises
        return self.status


def _sitemap(urls: list[str]) -> str:
    rows = "\n".join(f"<url><loc>{u}</loc><lastmod>2026-11-01</lastmod></url>" for u in urls)
    return (
        '<?xml version="1.0"?>\n'
        f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{rows}\n</urlset>\n'
    )


def _manifest(d: Mapping[str, str]) -> str:
    return json.dumps({"schema": 1, "pages": {p: {"fingerprint": f} for p, f in d.items()}})


def _site(tmp_path: Path, pages: Mapping[str, str]) -> Path:
    root = tmp_path / "site"
    for rel, html in pages.items():
        f = root / rel / "index.html" if rel else root / "index.html"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(html, encoding="utf-8")
    (root / f"{KEY}.txt").write_text(KEY + "\n", encoding="utf-8")
    robots = f"User-agent: *\nAllow: /\n\nSitemap: {BASE}/sitemap.xml\n"
    (root / "robots.txt").write_text(robots, encoding="utf-8")
    return root


def _select(
    tmp_path: Path, site: Path, live: str | None, monkeypatch: pytest.MonkeyPatch, base: str = BASE
) -> dict[str, Any]:
    monkeypatch.setattr(ix, "fetch_text", lambda url, missing_is_empty: live)
    out = tmp_path / "urls.json"
    argv = ["select", "--site-dir", str(site), "--base-url", base, "--kind", "manifest"]
    assert ix.main([*argv, "--file", "lastmod.json", "--missing-is-empty", "--out", str(out)]) == 0
    payload: dict[str, Any] = json.loads(out.read_text(encoding="utf-8"))
    return payload


# -- the module ---------------------------------------------------------------


def test_new_and_changed_pages_are_selected_and_unchanged_are_not() -> None:
    prev = {f"{BASE}/a/": "1", f"{BASE}/b/": "1"}
    cur = {f"{BASE}/a/": "1", f"{BASE}/b/": "2", f"{BASE}/c/": "1"}
    assert ix.select_changed(prev, cur) == [f"{BASE}/b/", f"{BASE}/c/"]


def test_an_unreadable_live_site_selects_nothing_but_an_empty_one_selects_all() -> None:
    cur = {f"{BASE}/a/": "1"}
    assert ix.select_changed(None, cur) == []
    assert ix.select_changed({}, cur) == [f"{BASE}/a/"]


def test_filter_drops_noindex_foreign_host_and_unbuilt_pages(tmp_path: Path) -> None:
    site = _site(tmp_path, {"": PAGE, "a": PAGE, "thin": NOINDEX})
    urls = [
        f"{BASE}/a/",
        f"{BASE}/thin/",
        "https://evil.test/a/",
        f"{BASE}/missing/",
        "http://example.test/a/",
    ]
    kept, notes = ix.filter_submittable(urls, base_url=BASE, site_dir=site)
    assert kept == [f"{BASE}/a/"]
    assert len(notes) == 4


def test_negative_control_validate_rejects_over_cap_duplicates_and_foreign_hosts(
    tmp_path: Path,
) -> None:
    site = _site(tmp_path, {"a": PAGE})
    ix.validate_submission([f"{BASE}/a/"], base_url=BASE, site_dir=site)  # the clean list passes
    over = [f"{BASE}/p{i}/" for i in range(ix.MAX_URLS + 1)]
    with pytest.raises(ix.IndexNowError, match="exceeds"):
        ix.validate_submission(over, base_url=BASE, site_dir=site)
    with pytest.raises(ix.IndexNowError, match="duplicate"):
        ix.validate_submission([f"{BASE}/a/", f"{BASE}/a/"], base_url=BASE, site_dir=site)
    with pytest.raises(ix.IndexNowError, match="not on"):
        ix.validate_submission(["https://evil.test/a/"], base_url=BASE, site_dir=site)


def test_the_key_file_must_exist_once_and_match_its_name(tmp_path: Path) -> None:
    site = _site(tmp_path, {"": PAGE})
    assert ix.find_key(site) == KEY
    (site / f"{KEY}.txt").write_text("wrong\n", encoding="utf-8")
    with pytest.raises(ix.IndexNowError, match="body must equal"):
        ix.find_key(site)
    (site / f"{KEY}.txt").unlink()
    with pytest.raises(ix.IndexNowError, match="exactly one"):
        ix.find_key(site)


def test_submit_posts_the_documented_payload_and_never_raises() -> None:
    payload = ix.build_payload(BASE, KEY, [f"{BASE}/a/"])
    assert payload == {
        "host": "example.test",
        "key": KEY,
        "keyLocation": f"{BASE}/{KEY}.txt",
        "urlList": [f"{BASE}/a/"],
    }
    ok = FakeClient(200)
    assert "accepted 1 URLs" in ix.submit(payload, ok)
    assert ok.calls[0][0] == ix.ENDPOINT
    for client in (FakeClient(403), FakeClient(429), FakeClient(raises=OSError("down"))):
        assert "normal crawl" in ix.submit(payload, client)
        assert client.calls  # the failure path really ran


def test_submit_command_exits_zero_even_when_the_list_is_unreadable(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert ix.main(["submit", "--list", str(tmp_path / "nope.json")]) == 0
    assert "::notice" in capsys.readouterr().out


def test_the_fingerprint_ignores_only_the_build_date_sentence() -> None:
    def page(built: str, other: str) -> str:
        return f"<p>Terms read {other}.</p><p>{ix.BUILT_ON.format(date=built)}</p>"

    stamps_13 = ix.build_stamps({"generated_at": "2026-11-13T09:20:00Z"})
    stamps_14 = ix.build_stamps({"generated_at": "2026-11-14T09:20:00Z"})
    day_13 = ix.fingerprint(page("2026-11-13", "2026-11-13"), stamps_13)
    day_14 = ix.fingerprint(page("2026-11-14", "2026-11-13"), stamps_14)
    assert day_13 == day_14  # only the build date moved
    # Negative control: the same date elsewhere on the page is content.
    moved = ix.fingerprint(page("2026-11-14", "2026-11-14"), stamps_14)
    assert moved != day_14


def test_a_snapshot_without_a_timestamp_writes_no_manifest(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    site = _site(tmp_path, {"": PAGE})
    (site / "sitemap.xml").write_text(_sitemap([f"{BASE}/"]), encoding="utf-8")
    (site / "lastmod.json").write_text("stale", encoding="utf-8")
    snap = tmp_path / "snap.json"
    snap.write_text(json.dumps({"generated_at": "yesterday"}), encoding="utf-8")
    argv = ["manifest", "--site-dir", str(site), "--base-url", BASE, "--snapshot", str(snap)]
    assert ix.main(argv) == 0
    assert not (site / "lastmod.json").exists()
    assert "lastmod.json not written" in capsys.readouterr().out


def test_select_on_a_manifest_diff_announces_only_changed_sitemap_pages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    site = _site(tmp_path, {"": PAGE, "a": PAGE, "b": PAGE})
    (site / "sitemap.xml").write_text(_sitemap([f"{BASE}/a/", f"{BASE}/b/"]), encoding="utf-8")
    current = _manifest({"/a/": "x2", "/b/": "y", "/": "z"})
    (site / "lastmod.json").write_text(current, encoding="utf-8")
    payload = _select(tmp_path, site, _manifest({"/a/": "x1", "/b/": "y"}), monkeypatch)
    # "/" changed but is not in the sitemap, so it is not announced.
    assert payload["urlList"] == [f"{BASE}/a/"]
    assert payload["key"] == KEY


def test_select_with_an_unreadable_live_manifest_submits_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    site = _site(tmp_path, {"a": PAGE})
    (site / "sitemap.xml").write_text(_sitemap([f"{BASE}/a/"]), encoding="utf-8")
    (site / "lastmod.json").write_text(_manifest({"/a/": "1"}), encoding="utf-8")
    assert _select(tmp_path, site, None, monkeypatch)["urlList"] == []
    assert "submitting nothing" in capsys.readouterr().out


def test_negative_control_an_unchanged_site_sends_no_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Zero changed URLs end to end: select finds nothing and submit sends
    nothing. The same site with one changed fingerprint does send, so the
    empty case is not an accident of the fixture."""
    site = _site(tmp_path, {"": PAGE, "a": PAGE})
    (site / "sitemap.xml").write_text(_sitemap([f"{BASE}/", f"{BASE}/a/"]), encoding="utf-8")
    current = {"/": "h0", "/a/": "h1"}
    (site / "lastmod.json").write_text(_manifest(current), encoding="utf-8")
    same = _select(tmp_path, site, _manifest(current), monkeypatch)
    assert same["urlList"] == []
    quiet = FakeClient()
    assert "nothing to submit" in ix.submit(same, quiet)
    assert quiet.calls == []

    older = {**current, "/a/": "h-old"}
    assert older != current  # the sabotage applied
    changed = _select(tmp_path, site, _manifest(older), monkeypatch)
    assert changed["urlList"] == [f"{BASE}/a/"]
    sent = FakeClient()
    ix.submit(changed, sent)
    assert len(sent.calls) == 1


# -- the real build, run the way snapshot.yml runs it -------------------------


def _build(tmp_path: Path, name: str, doc: dict[str, Any]) -> Path:
    """show_pages, then site_index, then the key and the manifest, as in the
    workflow's steps."""
    snap = tmp_path / f"{name}.json"
    snap.write_text(json.dumps(doc), encoding="utf-8")
    site = tmp_path / name
    assert show_pages.main([str(snap), str(site), "--app-store-live", "false"]) == 0
    assert site_index.main([str(snap), str(site / "index.html")]) == 0
    key_files = [p for p in ASSETS.iterdir() if ix.KEY_FILE_RE.match(p.name)]
    assert len(key_files) == 1
    (site / key_files[0].name).write_bytes(key_files[0].read_bytes())
    argv = ["manifest", "--site-dir", str(site), "--base-url", DOMAIN, "--snapshot", str(snap)]
    assert ix.main(argv) == 0
    return site


def _doc(**changes: Any) -> dict[str, Any]:
    doc: dict[str, Any] = json.loads(FIXTURE.read_text(encoding="utf-8"))
    doc.update(changes)
    return doc


def _tokens(site: Path) -> dict[str, str]:
    return ix.tokens("manifest", (site / "lastmod.json").read_text(encoding="utf-8"), DOMAIN)


def test_the_build_has_one_key_file_and_robots_lets_bingbot_in(tmp_path: Path) -> None:
    site = _build(tmp_path, "site", _doc())
    key = ix.find_key(site)
    assert re.fullmatch(r"[0-9a-f]{32}", key)
    assert (site / f"{key}.txt").read_text(encoding="utf-8").strip() == key
    robots = (site / "robots.txt").read_text(encoding="utf-8")
    assert ix.check_robots(robots, DOMAIN) == []
    # The workflow copies exactly this file.
    assert f"src/qtv_pipeline/assets/{key}.txt site/" in WORKFLOW.read_text(encoding="utf-8")


def test_the_manifest_covers_exactly_the_sitemap_and_every_url_is_announceable(
    tmp_path: Path,
) -> None:
    site = _build(tmp_path, "site", _doc())
    locs = sorted(ix.parse_sitemap((site / "sitemap.xml").read_text(encoding="utf-8")))
    assert locs, "an empty sitemap would make this check prove nothing"
    assert sorted(_tokens(site)) == locs
    kept, notes = ix.filter_submittable(locs, base_url=DOMAIN, site_dir=site)
    assert notes == [] and kept == locs


def test_negative_control_a_rebuild_with_a_new_build_date_announces_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The nightly case: same data, next day's build. The pages differ
    (the footer date moved), but nothing is announced. Changing a show's
    title in the data does announce, so the quiet case is not an accident."""
    first = _build(tmp_path, "first", _doc(generated_at="2026-11-13T09:20:00Z"))
    again = _build(tmp_path, "again", _doc(generated_at="2026-11-14T09:20:00Z"))
    a = (first / "index.html").read_text(encoding="utf-8")
    b = (again / "index.html").read_text(encoding="utf-8")
    assert a != b  # the build date really is on the page
    assert ix.select_changed(_tokens(first), _tokens(again)) == []
    live = (first / "lastmod.json").read_text(encoding="utf-8")
    quiet = _select(tmp_path, again, live, monkeypatch, base=DOMAIN)
    assert quiet["urlList"] == []
    client = FakeClient()
    ix.submit(quiet, client)
    assert client.calls == []

    renamed = _doc(generated_at="2026-11-14T09:20:00Z")
    old_title = renamed["shows"][0]["title"]
    renamed["shows"][0]["title"] = old_title + " (renamed)"
    assert renamed["shows"][0]["title"] != old_title  # the sabotage applied
    changed = _build(tmp_path, "changed", renamed)
    assert ix.select_changed(_tokens(first), _tokens(changed))


# -- the workflow --------------------------------------------------------------


def _block(text: str, start: str, end: str | None) -> str:
    i = text.index(start)
    return text[i : text.index(end, i + len(start))] if end else text[i:]


def test_workflow_selects_before_the_deploy_and_submits_in_a_job_after_it() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    build = _block(text, "\n  build:\n", "\n  deploy:\n")
    order = [
        "- name: assemble the Pages site",
        "- name: pick the pages to announce",
        "- name: keep the IndexNow list",
        "- uses: actions/upload-pages-artifact",
    ]
    positions = [build.index(step) for step in order]
    assert positions == sorted(positions)
    assert build.index("indexnow manifest") < build.index("indexnow select")
    job = _block(text, "\n  indexnow:\n", None)
    assert "    needs: deploy\n" in job
    assert "indexnow.py submit" in job
    assert "indexnow.py submit" not in build
    assert "write" not in job.split("steps:")[0]  # read-only permissions
    assert "secrets." not in job and "id-token" not in job
    # The standards ban continue-on-error; indexnow.py exits 0 instead.
    code = [ln for ln in text.splitlines() if not ln.strip().startswith("#")]
    assert not [ln for ln in code if "continue-on-error" in ln]
    # Only the publish workflow calls it, never pull-request CI.
    ci = (REPO / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "indexnow" not in ci.lower()
