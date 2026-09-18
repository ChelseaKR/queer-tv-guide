"""The vendored standards are the pinned release, unedited (DOC-01, DOC-03).

docs/standards/ is a copy of a ChelseaKR/portfolio-standards release, and
docs/standards/.standards-version names which one. Two things can make that
marker lie, and CI cannot fetch the private standards repo to notice either:

- a standard is hand-edited in place (DOC-03 forbids forked standard text);
- Renovate's custom manager in renovate.json bumps `standards_version=` in the
  marker, but does not re-vendor the files, so the marker would name a release
  whose text is not here.

tests/fixtures/vendored-standards.sha256 records the release it was taken
from and the SHA-256 of every vendored file. This test fails if the marker
names a different release, a file changed, or a file was added or removed.

After re-vendoring a new release with the standards repo's
automation/vendor-standards.sh, regenerate the fixture from the new files in
the same PR (the header's first line names the release).
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
VENDORED = REPO / "docs" / "standards"
FIXTURE = REPO / "tests" / "fixtures" / "vendored-standards.sha256"


def pinned_version(directory: Path) -> str:
    for line in (directory / ".standards-version").read_text().splitlines():
        if line.startswith("standards_version="):
            return line.split("=", 1)[1].strip()
    raise AssertionError(".standards-version has no standards_version= line")


def recorded(fixture: Path) -> tuple[str, dict[str, str]]:
    lines = fixture.read_text().splitlines()
    header = re.fullmatch(r"# portfolio-standards (\S+)", lines[0])
    if header is None:
        raise AssertionError(f"{fixture.name}: first line must be '# portfolio-standards <tag>'")
    sums: dict[str, str] = {}
    for line in lines[1:]:
        if not line.strip() or line.startswith("#"):
            continue
        digest, name = line.split(maxsplit=1)
        sums[name] = digest
    return header.group(1), sums


def problems(directory: Path, fixture: Path) -> list[str]:
    """Every way `directory` differs from what `fixture` records; empty means identical."""
    found: list[str] = []
    version, sums = recorded(fixture)
    pinned = pinned_version(directory)
    if pinned != version:
        found.append(f".standards-version pins {pinned} but the vendored files are {version}")
    manifest = json.loads((directory / ".standards-manifest.json").read_text())
    expected = set(manifest["files"]) | {".standards-manifest.json"}
    if set(sums) != expected:
        found.append(f"fixture lists {sorted(set(sums) ^ expected)} differently from the manifest")
    on_disk = {p.name for p in directory.iterdir() if p.is_file()} - {".standards-version"}
    if on_disk != expected:
        found.append(f"files on disk differ from the manifest: {sorted(on_disk ^ expected)}")
    for name, digest in sorted(sums.items()):
        path = directory / name
        if not path.is_file():
            found.append(f"{name}: missing")
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != digest:
            found.append(f"{name}: sha256 {actual} != recorded {digest}")
    return found


class VendoredStandardsTests(unittest.TestCase):
    def test_pin_is_a_release_tag(self) -> None:
        # DOC-01: a released vMAJOR.MINOR.PATCH, never a branch.
        self.assertRegex(pinned_version(VENDORED), r"^v\d+\.\d+\.\d+$")

    def test_vendored_copy_matches_the_recorded_release(self) -> None:
        self.assertEqual(problems(VENDORED, FIXTURE), [])

    def test_an_edit_or_a_marker_only_bump_is_caught(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "standards"
            shutil.copytree(VENDORED, copy)
            self.assertEqual(problems(copy, FIXTURE), [], "control: the untouched copy must pass")

            target = copy / "CI-CD-STANDARD.md"
            edited = target.read_text().replace("CI/CD Standard", "CI/CD Standard (local edit)", 1)
            target.write_text(edited)
            self.assertIn("(local edit)", target.read_text(), "sabotage did not land")
            self.assertTrue(any(p.startswith("CI-CD-STANDARD.md") for p in problems(copy, FIXTURE)))

            shutil.copyfile(VENDORED / "CI-CD-STANDARD.md", target)
            marker = copy / ".standards-version"
            bumped = marker.read_text().replace(pinned_version(VENDORED), "v9.9.9")
            marker.write_text(bumped)
            self.assertIn("v9.9.9", marker.read_text(), "sabotage did not land")
            self.assertTrue(any("pins v9.9.9" in p for p in problems(copy, FIXTURE)))


if __name__ == "__main__":
    unittest.main()
