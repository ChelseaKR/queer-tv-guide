"""`make verify` and CI run the same gates (CI-CD-STANDARD §9, CICD-27).

The root Makefile's VERIFY_TARGETS is the gate list. Every one of them must be
run, by name, by a workflow that gates pull requests, and no such workflow may
call a root target that `make verify` does not run: either drift means a
contributor's green `make verify` and CI's verdict can disagree.

`make -C <dir> ...` and `make -f ...` calls are some other Makefile's targets
and are not counted.

PENDING lists verify targets CI does not call yet, with the issue that wires
them. An entry must still be unwired, so the list cannot outlive the fix.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import workflow_model

MAKEFILE = workflow_model.REPO / "Makefile"

# Verify targets CI does not call yet, with the issue that wires each one.
# Empty today: ci.yml runs `make pipeline` and `make guidecore`.
PENDING: dict[str, str] = {}


def verify_targets() -> list[str]:
    text = MAKEFILE.read_text()
    match = re.search(r"^VERIFY_TARGETS := (.+)$", text, re.M)
    if match is None:
        raise AssertionError("Makefile has no `VERIFY_TARGETS :=` line")
    if re.search(r"^verify: \$\(VERIFY_TARGETS\)\s*$", text, re.M) is None:
        raise AssertionError("`verify:` must depend on exactly $(VERIFY_TARGETS)")
    targets = match.group(1).split()
    for target in targets:
        if re.search(rf"^{re.escape(target)}:", text, re.M) is None:
            raise AssertionError(f"verify target {target!r} has no recipe")
    return targets


def recipe_lines(text: str) -> list[str]:
    """Each recipe command line, with backslash continuations joined."""
    logical: list[str] = []
    current = ""
    for line in text.splitlines():
        if not current and not line.startswith("\t"):
            continue
        current += line.lstrip("\t").rstrip("\\") + " "
        if not line.endswith("\\"):
            logical.append(" ".join(current.split()))
            current = ""
    return logical


def unguarded_recipes(text: str) -> list[str]:
    """Recipe lines that run several commands without enabling errexit/pipefail.

    Under the make 3.81 macOS ships, .SHELLFLAGS is ignored, so a line like
    `scan; cleanup` reports the cleanup's status and a failed scan passes.
    """
    bad = []
    for line in recipe_lines(text):
        body = line.lstrip("@-+")
        several = ";" in body or re.search(r"(?<![|])\|(?![|])", body) is not None
        if several and not body.startswith("set -euo pipefail;"):
            bad.append(line)
    return bad


def ci_make_targets() -> set[str]:
    """Root-Makefile targets called by any workflow that gates pull requests."""
    called: set[str] = set()
    for wf in workflow_model.load_all():
        if "pull_request" not in wf.triggers:
            continue
        for job in wf.jobs.values():
            for body in job.run_blocks():
                for line in body.splitlines():
                    for command in re.split(r"&&|;|\|\|", line):
                        words = command.split()
                        if not words or words[0] != "make":
                            continue
                        if any(
                            w in ("-C", "-f") or w.startswith(("--directory", "--file"))
                            for w in words
                        ):
                            continue
                        called.update(
                            w for w in words[1:] if not w.startswith("-") and "=" not in w
                        )
    return called


class CiParityTests(unittest.TestCase):
    def test_every_verify_target_runs_in_ci(self) -> None:
        targets = verify_targets()
        called = ci_make_targets()
        if "verify" in called:
            called |= set(targets)
        missing = sorted(set(targets) - called - set(PENDING))
        self.assertEqual(missing, [], "in `make verify` but no pull-request workflow runs them")

    def test_ci_runs_nothing_verify_does_not(self) -> None:
        extra = sorted(ci_make_targets() - set(verify_targets()) - {"verify"})
        self.assertEqual(extra, [], "run by CI but missing from VERIFY_TARGETS")

    def test_pending_entries_are_still_pending(self) -> None:
        targets = set(verify_targets())
        called = ci_make_targets()
        for target, issue in PENDING.items():
            self.assertIn(
                target, targets, f"PENDING names {target!r}, which is not a verify target"
            )
            self.assertNotIn(
                target, called, f"{target!r} is wired now; delete its PENDING entry ({issue})"
            )

    def test_multi_command_recipes_fail_on_the_first_failure(self) -> None:
        self.assertEqual(unguarded_recipes(MAKEFILE.read_text()), [])

    def test_the_recipe_guard_can_fail(self) -> None:
        probe = (
            "x:\n\tscan --strict; \\\n\t  cleanup\ny:\n\tset -euo pipefail; a; b\nz:\n\tone | two\n"
        )
        self.assertEqual(unguarded_recipes(probe), ["scan --strict; cleanup", "one | two"])

    def test_the_parser_sees_real_calls(self) -> None:
        # Denominator: at least the security workflow's targets are found.
        self.assertTrue({"policy", "workflows", "secrets", "sast", "sca"} <= ci_make_targets())


if __name__ == "__main__":
    unittest.main()
