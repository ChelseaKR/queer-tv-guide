"""The hand-kept store sales ledger: scripts/check_metrics.py (roadmap Stage 0).

The checked-in ledger must be valid; each rule refuses its own bad row; and
every negative control asserts its sabotage landed before it trusts the result.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import workflow_model

REPO = workflow_model.REPO
SCRIPT = REPO / "scripts" / "check_metrics.py"
_spec = importlib.util.spec_from_file_location("check_metrics", SCRIPT)
assert _spec is not None and _spec.loader is not None
metrics = importlib.util.module_from_spec(_spec)
sys.modules["check_metrics"] = metrics
_spec.loader.exec_module(metrics)

HEADER = "month,store,units,source,recorded_on\n"
APP = "App Store Connect sales report"
PLAY = "Play Console statistics"
GOOD = (
    HEADER
    + f"2026-11,app-store,3,{APP},2026-12-02\n"
    + f"2026-11,google-play,0,{PLAY},2026-12-02\n"
    + f"2026-12,app-store,12,{APP},2027-01-03\n"
)


def sabotage(text: str, old: str, new: str) -> str:
    """Replace `old` and prove the text changed, so a no-op cannot read as a pass."""
    assert old in text, f"sabotage target {old!r} is not in the text"
    changed = text.replace(old, new, 1)
    assert changed != text
    return changed


class LedgerTests(unittest.TestCase):
    def test_checked_in_ledger_is_valid(self) -> None:
        self.assertEqual(metrics.check(metrics.LEDGER.read_text(encoding="utf-8")), [])

    def test_checked_in_ledger_invents_no_rows(self) -> None:
        # No store report has been copied in yet; any row must come from the owner.
        lines = metrics.LEDGER.read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines[0], ",".join(metrics.HEADER))
        self.assertEqual(len(lines), 1, "rows are added by hand from a store report")

    def test_good_fixture_is_valid(self) -> None:
        self.assertEqual(metrics.check(GOOD), [])

    def test_zero_units_is_valid_but_blank_is_not(self) -> None:
        self.assertEqual(metrics.check(GOOD), [])
        bad = sabotage(GOOD, "google-play,0,", "google-play,,")
        self.assertTrue(any("units" in p for p in metrics.check(bad)))

    def test_header_must_match(self) -> None:
        bad = sabotage(GOOD, "units", "downloads")
        self.assertEqual(len(metrics.check(bad)), 1)
        self.assertIn("header", metrics.check(bad)[0])

    def test_empty_text_is_refused(self) -> None:
        self.assertIn("header", metrics.check("")[0])

    def test_unknown_store_and_wrong_source(self) -> None:
        self.assertTrue(
            any("store" in p for p in metrics.check(sabotage(GOOD, "google-play", "fdroid")))
        )
        self.assertTrue(
            any("source" in p for p in metrics.check(sabotage(GOOD, f",{PLAY},", f",{APP},")))
        )

    def test_units_must_be_whole_non_negative(self) -> None:
        for value in ("-1", "1.5", "03", "ten"):
            with self.subTest(value=value):
                bad = sabotage(GOOD, "app-store,3,", f"app-store,{value},")
                self.assertTrue(any("units" in p for p in metrics.check(bad)))

    def test_month_must_be_a_month(self) -> None:
        for value in ("2026-13", "2026-00", "26-11", "2026-1"):
            with self.subTest(value=value):
                bad = sabotage(GOOD, "2026-12,", f"{value},")
                self.assertTrue(any("YYYY-MM" in p for p in metrics.check(bad)))

    def test_month_cannot_be_recorded_before_it_ends(self) -> None:
        self.assertEqual(metrics.check(GOOD), [])
        # 2026-11 ends on 2026-11-30, so recording it on 2026-11-30 is too early.
        early = sabotage(
            GOOD,
            "app-store,3,App Store Connect sales report,2026-12-02",
            "app-store,3,App Store Connect sales report,2026-11-30",
        )
        self.assertTrue(any("had not ended" in p for p in metrics.check(early)))
        # Recording on the first of the next month is the earliest allowed day.
        ok = sabotage(
            GOOD, "report,2026-12-02\n2026-11,google", "report,2026-12-01\n2026-11,google"
        )
        self.assertEqual(metrics.check(ok), [])

    def test_december_rolls_into_january(self) -> None:
        text = HEADER + f"2026-12,app-store,1,{APP},2027-01-01\n"
        self.assertEqual(metrics.check(text), [])
        self.assertTrue(
            any(
                "had not ended" in p
                for p in metrics.check(sabotage(text, "2027-01-01", "2026-12-31"))
            )
        )

    def test_duplicates_and_order(self) -> None:
        dup = GOOD + f"2026-12,app-store,13,{APP},2027-01-04\n"
        self.assertTrue(any("twice" in p for p in metrics.check(dup)))
        lines = GOOD.splitlines(keepends=True)
        swapped = "".join([lines[0], lines[3], lines[1], lines[2]])
        self.assertNotEqual(swapped, GOOD)
        self.assertTrue(any("order" in p for p in metrics.check(swapped)))
        play_first = "".join([lines[0], lines[2], lines[1], lines[3]])
        self.assertNotEqual(play_first, GOOD)
        self.assertTrue(any("order" in p for p in metrics.check(play_first)))

    def test_short_row_is_refused(self) -> None:
        self.assertTrue(any("columns" in p for p in metrics.check(GOOD + "2027-01,app-store\n")))

    def test_command_line_exit_codes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            good = Path(tmp) / "good.csv"
            bad = Path(tmp) / "bad.csv"
            good.write_text(GOOD, encoding="utf-8")
            bad.write_text(sabotage(GOOD, "app-store,3,", "app-store,x,"), encoding="utf-8")
            self.assertNotEqual(good.read_text(), bad.read_text())
            ok = subprocess.run(
                [sys.executable, str(SCRIPT), str(good)],
                capture_output=True,
                text=True,
                check=False,
            )
            refused = subprocess.run(
                [sys.executable, str(SCRIPT), str(bad)], capture_output=True, text=True, check=False
            )
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertEqual(refused.returncode, 1)
        self.assertIn("units", refused.stderr)

    def test_readme_names_the_same_columns_stores_and_sources(self) -> None:
        readme = (REPO / "docs" / "metrics" / "README.md").read_text(encoding="utf-8")
        for name in (*metrics.HEADER, *metrics.STORES, *metrics.SOURCES.values()):
            self.assertIn(name, readme)


if __name__ == "__main__":
    unittest.main()
