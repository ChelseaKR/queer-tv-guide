"""Every curl of the published snapshot follows a redirect, and only to https.

GitHub Pages answers the old github.io project URL with a 301 once a custom
domain is attached. Without `-L`, `curl -f` takes that 301 as success and
writes an empty file: `freshness.yml` would raise a false stale alarm every
night and `make bundle-snapshot` would fail on an empty sha256 file.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FILES = [".github/workflows/freshness.yml", "ios/Makefile", "android/Makefile"]


def _snapshot_curl_commands(text: str) -> list[str]:
    """Each curl invocation (joined across `\\` continuations) that fetches the snapshot URL."""
    joined = re.sub(r"\\\n\s*", " ", text)
    return [ln for ln in joined.splitlines() if "curl" in ln and re.search(r"SNAPSHOT_URL", ln)]


def _follows_safely(cmd: str) -> bool:
    flags = " ".join(re.findall(r"\s(-[A-Za-z]+|--[a-z0-9-]+(?:\s+\S+)?)", cmd))
    short = "".join(re.findall(r"\s-([A-Za-z]+)\b", cmd))
    return "L" in short and "--max-redirs" in flags and "--proto-redir =https" in cmd


@pytest.mark.parametrize("name", FILES)
def test_every_snapshot_curl_follows_redirects_to_https_only(name):
    commands = _snapshot_curl_commands((ROOT / name).read_text())
    assert commands, f"{name} no longer curls the snapshot URL; update this test"
    bad = [c.strip()[:120] for c in commands if not _follows_safely(c)]
    assert bad == []


def test_negative_control_a_curl_without_l_is_caught():
    old = 'curl -fsS --compressed -o "$$tmp/x" "$(SNAPSHOT_URL)" && \\\n  true'
    assert [c for c in _snapshot_curl_commands(old) if not _follows_safely(c)]
    old_ci = 'curl --proto \'=https\' -fsS --retry 3 -o "$RUNNER_TEMP/s" "$SNAPSHOT_URL"'
    assert [c for c in _snapshot_curl_commands(old_ci) if not _follows_safely(c)]
    no_cap = 'curl -fsSL --compressed -o "$$tmp/x" "$(SNAPSHOT_URL)"'
    assert [c for c in _snapshot_curl_commands(no_cap) if not _follows_safely(c)]


def test_a_correct_curl_passes():
    good = 'curl -fsSL --max-redirs 3 --proto-redir =https -o "$$tmp/x" "$(SNAPSHOT_URL)"'
    assert [c for c in _snapshot_curl_commands(good) if not _follows_safely(c)] == []
