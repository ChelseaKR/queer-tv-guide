"""The `greenlight` gate (scripts/greenlight.sh) can pass, can fail, and says so.

A gate that cannot fail proves nothing, so each negative control seeds a real
violation into a temporary COPY of the app and widget targets, asserts the
copy actually changed, and only then expects the gate to fail with the
finding the seeding should cause. A positive control runs the real tree.

These run the pinned scanner, so they need Go and the network once (the build
is cached under QTG_TOOLS_DIR, shared with scripts/fetch-tool.sh). Locally a
machine that cannot install it skips them, loudly; in CI (CI or
GITHUB_ACTIONS set) that is a failure.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "greenlight.sh"
IN_CI = bool(os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"))


def run_gate(
    src: Path, out: Path, *, extra_env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "GREENLIGHT_SRC": str(src), "GREENLIGHT_OUT": str(out)}
    env.update(extra_env or {})
    return subprocess.run(
        [str(SCRIPT)], capture_output=True, text=True, env=env, check=False, timeout=900
    )


def installed() -> bool:
    """True when the pinned scanner is available (installing it if it can)."""
    with tempfile.TemporaryDirectory() as out:
        proc = run_gate(REPO / "ios", Path(out))
        return "SKIPPED: greenlight not installed" not in proc.stdout


class GreenlightGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.have_tool = installed()
        if not cls.have_tool and IN_CI:
            raise AssertionError("greenlight could not be installed in CI")

    def setUp(self) -> None:
        if not self.have_tool:
            self.skipTest("SKIPPED: greenlight not installed (no Go or no network)")
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.src = self.tmp / "ios"
        self.src.mkdir()
        for target in ("QueerTVGuide", "QueerTVGuideWidgets"):
            shutil.copytree(REPO / "ios" / target, self.src / target)
        self.out = self.tmp / "out"

    def titles(self, target: str = "QueerTVGuide") -> list[str]:
        report = json.loads((self.out / f"{target}.json").read_text())
        return [f["title"] for f in report.get("findings") or []]

    def test_positive_control_real_tree(self) -> None:
        with tempfile.TemporaryDirectory() as out:
            proc = run_gate(REPO / "ios", Path(out))
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            for target in ("QueerTVGuide", "QueerTVGuideWidgets"):
                report = json.loads((Path(out) / f"{target}.json").read_text())
                self.assertTrue(report["summary"]["passed"], target)
                self.assertEqual(report["summary"]["critical"], 0, target)
                self.assertEqual(report["summary"]["high"], 0, target)

    def test_unmodified_copy_passes(self) -> None:
        # The denominator for the negative controls: the copy passes until seeded.
        proc = run_gate(self.src, self.out)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_missing_privacy_manifest_fails(self) -> None:
        manifest = self.src / "QueerTVGuide" / "PrivacyInfo.xcprivacy"
        self.assertTrue(manifest.exists())
        manifest.unlink()
        self.assertFalse(manifest.exists(), "seeding did not change the copy")
        proc = run_gate(self.src, self.out)
        self.assertNotEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("No PrivacyInfo.xcprivacy found in project", self.titles())

    def test_undeclared_required_reason_api_fails(self) -> None:
        seed = self.src / "QueerTVGuide" / "App" / "SeededViolation.swift"
        self.assertFalse(seed.exists())
        seed.write_text(
            "import Foundation\n"
            "func seeded() -> Date? {\n"
            '    let a = try? FileManager.default.attributesOfItem(atPath: "/")\n'
            "    return a?[.modificationDate] as? Date\n"
            "}\n"
        )
        self.assertTrue(seed.exists(), "seeding did not change the copy")
        proc = run_gate(self.src, self.out)
        self.assertNotEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertTrue(any("File Timestamp" in t for t in self.titles()), self.titles())

    def test_waiver_is_by_path_not_by_rule(self) -> None:
        # ReviewRequest.swift is waived; the same rule must still fire in another file.
        seed = self.src / "QueerTVGuide" / "App" / "SeededStore.swift"
        seed.write_text("import StoreKit\nlet queue = SKPaymentQueue.default()\n")
        self.assertTrue(seed.exists(), "seeding did not change the copy")
        proc = run_gate(self.src, self.out)
        self.assertNotEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("In-app purchases without restore functionality", self.titles())

    def test_widget_target_is_scanned_too(self) -> None:
        (self.src / "QueerTVGuideWidgets" / "PrivacyInfo.xcprivacy").unlink()
        proc = run_gate(self.src, self.out)
        self.assertNotEqual(proc.returncode, 0, proc.stdout + proc.stderr)


class GreenlightSkipTests(unittest.TestCase):
    """The not-installed path needs no scanner: an empty tool cache and no Go."""

    # Everything scripts/greenlight.sh runs before it gives up, and nothing else:
    # in particular no `go`, which a CI runner puts in /usr/bin.
    TOOLS = ("bash", "dirname", "mkdir", "rm", "cp", "tr", "grep", "awk", "mktemp", "touch", "mv")

    def run_skip(self, **env: str) -> tuple[subprocess.CompletedProcess[str], Path]:
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        bindir = tmp / "bin"
        bindir.mkdir()
        for tool in self.TOOLS:
            real = shutil.which(tool)
            self.assertIsNotNone(real, tool)
            (bindir / tool).symlink_to(real)
        # CI and GITHUB_ACTIONS are scrubbed, then set only by the caller.
        full = {k: v for k, v in os.environ.items() if k not in ("CI", "GITHUB_ACTIONS", "PATH")}
        full.update(
            PATH=str(bindir),
            HOME=str(tmp / "home"),
            QTG_TOOLS_DIR=str(tmp / "empty-tools"),
            GREENLIGHT_OUT=str(tmp / "out"),
            **env,
        )
        full.pop("XDG_CACHE_HOME", None)
        self.assertIsNone(shutil.which("go", path=full["PATH"]), "go is on the test PATH")
        proc = subprocess.run(
            [str(bindir / "bash"), str(SCRIPT)],
            capture_output=True,
            text=True,
            env=full,
            check=False,
        )
        return proc, tmp / "out"

    def test_local_skip_is_loud_and_marked(self) -> None:
        proc, out = self.run_skip()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("SKIPPED: greenlight not installed", proc.stdout)
        self.assertTrue((out / "SKIPPED").exists())

    def test_skip_in_ci_fails(self) -> None:
        for var in ("CI", "GITHUB_ACTIONS"):
            proc, out = self.run_skip(**{var: "true"})
            self.assertNotEqual(proc.returncode, 0, var)
            self.assertNotIn("SKIPPED: greenlight not installed", proc.stdout)
            self.assertFalse((out / "SKIPPED").exists())

    def test_verify_summary_does_not_count_a_skip_as_passed(self) -> None:
        def summary(skipped: bool) -> str:
            tmp = Path(tempfile.mkdtemp())
            self.addCleanup(shutil.rmtree, tmp, True)
            if skipped:
                (tmp / "SKIPPED").write_text("seeded\n")
            targets = re.search(r"^VERIFY_TARGETS := (.+)$", (REPO / "Makefile").read_text(), re.M)
            self.assertIsNotNone(targets)
            # -o: treat every gate as up to date, so only the summary recipe runs.
            cmd = ["make", "--no-print-directory", f"GREENLIGHT_OUT={tmp}", "-C", str(REPO)]
            for gate in targets.group(1).split():
                cmd += ["-o", gate]
            proc = subprocess.run([*cmd, "verify"], capture_output=True, text=True, check=True)
            return proc.stdout.strip()

        match = re.search(r"^VERIFY_TARGETS := (.+)$", (REPO / "Makefile").read_text(), re.M)
        self.assertIsNotNone(match)
        count = len(match.group(1).split())
        self.assertTrue(summary(False).startswith(f"verify: {count} gates passed:"))
        skipped = summary(True)
        self.assertTrue(skipped.startswith(f"verify: {count - 1} gates passed, 1 SKIPPED"), skipped)
        self.assertNotIn("greenlight", skipped.split(":", 2)[2])


class GreenlightPinTests(unittest.TestCase):
    text = SCRIPT.read_text()
    code = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))

    def test_pinned_to_a_commit_never_latest(self) -> None:
        self.assertRegex(self.text, r"(?m)^GL_COMMIT=[0-9a-f]{40}$")
        self.assertRegex(self.text, r"(?m)^GL_MODULE_HASH=h1:[A-Za-z0-9+/=]+$")
        self.assertNotIn("@latest", self.code)

    def test_only_the_static_preflight_runs(self) -> None:
        commands = [line for line in self.code.splitlines() if line.lstrip().startswith('"$bin" ')]
        self.assertTrue(commands)
        for line in commands:
            self.assertIn(" preflight ", line)
            self.assertNotIn("--verify", line)
        self.assertNotRegex("\n".join(commands), r'"\$bin" +(scan|verify)\b')


if __name__ == "__main__":
    unittest.main()
