"""The dated terms snapshots are the licence evidence (App Review 5.2.2:
"Authorization must be provided upon request"). Each dated directory's
SHA256SUMS was written when the page was read; this proves the committed
bytes still match it.

Not hypothetical: the 2026-09-13 lezwatchtv-robots.txt was fetched with CRLF
line endings, checksummed, and then committed through `core.autocrlf=input`,
which silently rewrote it to LF, so its recorded checksum stopped verifying.
`.gitattributes` now marks docs/terms-snapshots/** as -text.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SNAPSHOTS = REPO / "docs" / "terms-snapshots"


def verify_dir(directory: Path) -> list[str]:
    """Every problem with one dated snapshot directory, as readable strings.
    Empty means every file is listed in SHA256SUMS and matches it."""
    problems: list[str] = []
    sums_file = directory / "SHA256SUMS"
    if not sums_file.is_file():
        return [f"{directory.name}: no SHA256SUMS"]
    listed: dict[str, str] = {}
    for line in sums_file.read_text().splitlines():
        if not line.strip():
            continue
        digest, name = line.split(maxsplit=1)
        listed[name.lstrip("*")] = digest
    for name, digest in sorted(listed.items()):
        path = directory / name
        if not path.is_file():
            problems.append(f"{directory.name}/{name}: listed but missing")
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != digest:
            problems.append(f"{directory.name}/{name}: sha256 {actual} != recorded {digest}")
    for path in sorted(directory.iterdir()):
        if path.name != "SHA256SUMS" and path.is_file() and path.name not in listed:
            problems.append(f"{directory.name}/{path.name}: present but not in SHA256SUMS")
    return problems


def _dated_dirs() -> list[Path]:
    return sorted(p for p in SNAPSHOTS.iterdir() if p.is_dir())


def test_there_is_at_least_one_dated_terms_snapshot():
    assert _dated_dirs(), f"no dated directories under {SNAPSHOTS}"


@pytest.mark.parametrize("directory", _dated_dirs(), ids=lambda p: p.name)
def test_every_terms_snapshot_matches_its_recorded_checksum(directory: Path):
    assert verify_dir(directory) == []


def test_gitattributes_keeps_terms_snapshots_byte_exact():
    rules = (REPO / ".gitattributes").read_text().splitlines()
    assert "docs/terms-snapshots/** -text" in rules


# ---- negative controls: the verifier really catches each failure ----------------


def _one_file_dir(tmp_path: Path, body: bytes) -> Path:
    d = tmp_path / "2026-01-01"
    d.mkdir()
    (d / "robots.txt").write_bytes(body)
    digest = hashlib.sha256(body).hexdigest()
    (d / "SHA256SUMS").write_text(f"{digest}  robots.txt\n")
    return d


def test_verifier_passes_an_untouched_directory(tmp_path: Path):
    assert verify_dir(_one_file_dir(tmp_path, b"User-agent: *\r\nCrawl-delay: 10\r\n")) == []


def test_verifier_catches_crlf_rewritten_to_lf(tmp_path: Path):
    d = _one_file_dir(tmp_path, b"User-agent: *\r\nCrawl-delay: 10\r\n")
    (d / "robots.txt").write_bytes(b"User-agent: *\nCrawl-delay: 10\n")
    assert (d / "robots.txt").read_bytes().count(b"\r") == 0  # the sabotage landed
    problems = verify_dir(d)
    assert len(problems) == 1 and "robots.txt: sha256" in problems[0]


def test_verifier_catches_unlisted_and_missing_files(tmp_path: Path):
    d = _one_file_dir(tmp_path, b"x")
    (d / "extra.txt").write_bytes(b"y")
    (d / "robots.txt").unlink()
    problems = verify_dir(d)
    assert any("robots.txt: listed but missing" in p for p in problems)
    assert any("extra.txt: present but not in SHA256SUMS" in p for p in problems)
