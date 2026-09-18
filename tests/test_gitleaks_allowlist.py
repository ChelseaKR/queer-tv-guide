"""Negative controls for the one gitleaks exemption in .gitleaks.toml.

The allowlist exists because `generic-api-key` reads the declaration of the
favourites UserDefaults key in FavouritesStore.swift as a credential. These
tests prove the exemption is exactly that narrow: it silences that one line,
and nothing a real secret could hide behind.

Each case copies the real FavouritesStore.swift into a scratch tree at its
real repository-relative path, applies one change, asserts the change landed,
and runs the pinned gitleaks binary over the scratch tree. `make policy` sets
$GITLEAKS; run through it rather than directly.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CONFIG = REPO / ".gitleaks.toml"
STORE = Path("ios/GuideCore/Sources/GuideCore/FavouritesStore.swift")
# The exempted declaration, assembled at run time: written out literally here it
# would be the same false positive in a path the allowlist (correctly) does
# not cover, and `make secrets` would fail on this file.
KEY_VALUE = "favourites" + ".v1"
ALLOWED_LINE = "    public static let defaultsKey = " + f'"{KEY_VALUE}"'
# Shaped like a real key (40 mixed-case alphanumerics), not a vendor's
# documented example credential: scanners deliberately skip those, which would
# make the planted-secret cases pass for the wrong reason. Assembled at run
# time so this file does not itself carry a key-shaped literal for `make
# secrets` to find.
PLANTED = "".join(["Zx9Q2vB7mK", "4pL8sT1wR6", "yU3nC5hJ0d", "FgEaVq2Lw8"])


def _gitleaks() -> str:
    path = os.environ.get("GITLEAKS", "")
    if not path or not Path(path).is_file():
        raise AssertionError(
            "GITLEAKS is not set to the pinned gitleaks binary; run `make policy`, "
            "which downloads and verifies it (a missing scanner is a failure, not a skip)"
        )
    return path


def _scan(tree: Path, config: Path) -> int:
    """gitleaks exit code for a file-mode scan run from inside `tree`, so the
    allowlist's repository-relative path pattern applies exactly as in CI."""
    result = subprocess.run(
        [
            _gitleaks(),
            "dir",
            "--no-banner",
            "--redact",
            "--exit-code",
            "1",
            "--config",
            str(config),
            ".",
        ],
        cwd=tree,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode not in (0, 1):
        raise AssertionError(
            f"gitleaks did not run cleanly (exit {result.returncode}): {result.stderr}"
        )
    return result.returncode


class GitleaksAllowlistTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="qtg-gitleaks-"))
        self.addCleanup(shutil.rmtree, self.tmp)
        self.tree = self.tmp / "tree"
        (self.tree / STORE.parent).mkdir(parents=True)
        shutil.copyfile(REPO / STORE, self.tree / STORE)
        self.original = (REPO / STORE).read_text()
        # A config that is upstream defaults only: our allowlist removed, every
        # rule still present. An empty file would be the wrong control; it has
        # no rules at all and passes everything.
        self.defaults_only = self.tmp / "defaults-only.toml"
        self.defaults_only.write_text("[extend]\nuseDefault = true\n")

    def _write(self, relative: Path, text: str) -> None:
        target = self.tree / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
        self.assertEqual(target.read_text(), text, "sabotage did not land")

    def test_the_real_file_still_carries_the_exempted_line(self) -> None:
        # If the key is renamed or moved, the exemption matches nothing and
        # should be deleted rather than left to excuse some later line.
        self.assertIn(ALLOWED_LINE + "\n", self.original)

    def test_unchanged_file_is_clean_with_the_allowlist(self) -> None:
        self.assertEqual(_scan(self.tree, CONFIG), 0)

    def test_the_allowlist_is_what_silences_it(self) -> None:
        # Control: with upstream rules only, the same untouched file is a
        # finding. Without this, the case above could pass because the rule
        # stopped firing, not because the exemption applied.
        self.assertEqual(_scan(self.tree, self.defaults_only), 1)

    def test_a_real_secret_elsewhere_in_the_same_file_is_still_found(self) -> None:
        planted = f'    private static let apiKey = "{PLANTED}"\n'
        text = self.original.replace(ALLOWED_LINE + "\n", ALLOWED_LINE + "\n" + planted, 1)
        self.assertIn(planted, text)
        self._write(STORE, text)
        self.assertEqual(_scan(self.tree, CONFIG), 1)

    def test_a_different_value_on_the_exempted_line_is_still_found(self) -> None:
        text = self.original.replace(f'"{KEY_VALUE}"', f'"{PLANTED}"', 1)
        self.assertNotEqual(text, self.original)
        self._write(STORE, text)
        self.assertEqual(_scan(self.tree, CONFIG), 1)

    def test_the_exempted_line_in_another_file_is_still_found(self) -> None:
        other = STORE.with_name("SomethingElse.swift")
        self._write(other, "enum SomethingElse {\n" + ALLOWED_LINE + "\n}\n")
        self.assertEqual(_scan(self.tree, CONFIG), 1)


if __name__ == "__main__":
    unittest.main()
