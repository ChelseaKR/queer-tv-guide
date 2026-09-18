"""The snapshot staleness alarm (DG-04, #25): scripts/check_snapshot_freshness.py.

Its thresholds, each side of each boundary; unknowns that must alarm rather
than pass; the command line the workflow runs; that the thresholds still
follow from snapshot.yml's schedule and the data cards' SLA; and that
freshness.yml wires the check to an incident issue. The negative controls
check that their sabotage landed before they trust the result.
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import workflow_model

REPO = workflow_model.REPO
SCRIPT = REPO / "scripts" / "check_snapshot_freshness.py"

_spec = importlib.util.spec_from_file_location("check_snapshot_freshness", SCRIPT)
assert _spec is not None and _spec.loader is not None
freshness = importlib.util.module_from_spec(_spec)
sys.modules["check_snapshot_freshness"] = freshness
_spec.loader.exec_module(freshness)

NOW = datetime(2026, 9, 18, 15, 0, 0, tzinfo=UTC)
STAMP = "%Y-%m-%dT%H:%M:%SZ"


def snapshot(age: timedelta) -> bytes:
    return json.dumps({"generated_at": (NOW - age).strftime(STAMP), "shows": []}).encode()


def run(
    conclusion: str = "success", created: str = "2026-09-18T09:29:36Z", run_id: int = 1
) -> dict:
    return {
        "databaseId": run_id,
        "status": "completed",
        "conclusion": conclusion,
        "event": "schedule",
        "createdAt": created,
        "url": f"https://github.com/ChelseaKR/queer-tv-guide/actions/runs/{run_id}",
    }


def codes(verdict: object) -> list[str]:
    return sorted(f.code for f in verdict.findings)


class ThresholdTests(unittest.TestCase):
    def test_a_fresh_file_and_a_green_nightly_run_are_fresh(self) -> None:
        verdict = freshness.evaluate(snapshot(timedelta(hours=5)), [run()], NOW)
        self.assertFalse(verdict.alarm)
        self.assertEqual(verdict.severity, "")

    def test_the_missed_run_boundary(self) -> None:
        at = freshness.evaluate(snapshot(timedelta(hours=30)), [run()], NOW)
        past = freshness.evaluate(snapshot(timedelta(hours=30, seconds=1)), [run()], NOW)
        self.assertFalse(at.alarm, "exactly 30 hours old is still fresh")
        self.assertEqual(codes(past), ["missed-run"])
        self.assertEqual(past.severity, "sev3")

    def test_the_sla_boundary(self) -> None:
        at = freshness.evaluate(snapshot(timedelta(hours=48)), [run()], NOW)
        past = freshness.evaluate(snapshot(timedelta(hours=48, seconds=1)), [run()], NOW)
        self.assertEqual(codes(at), ["missed-run"], "48 hours exactly is late but within the SLA")
        self.assertEqual(at.severity, "sev3")
        self.assertEqual(codes(past), ["past-sla"])
        self.assertEqual(past.severity, "sev2")

    def test_a_failed_nightly_run_alarms_while_the_file_is_still_fresh(self) -> None:
        verdict = freshness.evaluate(snapshot(timedelta(hours=2)), [run("failure")], NOW)
        self.assertEqual(codes(verdict), ["run-failed"])
        self.assertEqual(verdict.severity, "sev3")

    def test_only_success_counts_as_success(self) -> None:
        for conclusion in ("cancelled", "timed_out", "startup_failure", "", None):
            with self.subTest(conclusion=conclusion):
                verdict = freshness.evaluate(snapshot(timedelta(hours=2)), [run(conclusion)], NOW)
                self.assertEqual(codes(verdict), ["run-failed"])

    def test_the_latest_completed_run_is_the_one_judged(self) -> None:
        older_failure = run("failure", "2026-09-17T09:31:16Z", 1)
        newer_success = run("success", "2026-09-18T09:29:36Z", 2)
        in_progress = {**run("", "2026-09-18T14:00:00Z", 3), "status": "in_progress"}
        runs = [older_failure, in_progress, newer_success]
        verdict = freshness.evaluate(snapshot(timedelta(hours=5)), runs, NOW)
        self.assertFalse(verdict.alarm, verdict.findings)
        self.assertEqual(verdict.last_run["databaseId"], 2)
        runs_reversed = [newer_success, run("failure", "2026-09-18T12:00:00Z", 4)]
        failed_later = freshness.evaluate(snapshot(timedelta(hours=5)), runs_reversed, NOW)
        self.assertEqual(codes(failed_later), ["run-failed"])
        self.assertEqual(failed_later.last_run["databaseId"], 4)

    def test_the_worst_severity_wins(self) -> None:
        verdict = freshness.evaluate(snapshot(timedelta(hours=60)), [run("failure")], NOW)
        self.assertEqual(codes(verdict), ["past-sla", "run-failed"])
        self.assertEqual(verdict.severity, "sev2")
        self.assertIn("48-hour SLA", verdict.title)


class UnknownIsNeverFreshTests(unittest.TestCase):
    def test_every_unreadable_snapshot_alarms_at_sev2(self) -> None:
        cases = {
            "not fetched": None,
            "not json": b"<html>404</html>",
            "not an object": b"[]",
            "no generated_at": b'{"shows": []}',
            "a number": b'{"generated_at": 1790000000}',
            "no time zone": b'{"generated_at": "2026-09-18T09:44:42"}',
            "not a date": b'{"generated_at": "yesterday"}',
        }
        for name, raw in cases.items():
            with self.subTest(name):
                verdict = freshness.evaluate(raw, [run()], NOW)
                self.assertEqual(codes(verdict), ["unreadable"])
                self.assertEqual(verdict.severity, "sev2")
                self.assertIsNone(verdict.generated_at)

    def test_a_future_date_is_an_unknown_age(self) -> None:
        near = freshness.evaluate(snapshot(-timedelta(minutes=10)), [run()], NOW)
        far = freshness.evaluate(snapshot(-timedelta(minutes=10, seconds=1)), [run()], NOW)
        self.assertFalse(near.alarm, "a few minutes of clock skew is not an alarm")
        self.assertEqual(codes(far), ["future"])
        self.assertEqual(far.severity, "sev2")
        self.assertIn("age unknown", freshness.render_report(far))
        self.assertNotIn("-0.2 hours", freshness.render_report(far))

    def test_no_run_history_alarms(self) -> None:
        cases = {
            "not read": None,
            "not a list": {"runs": []},
            "empty": [],
            "none completed": [{**run(), "status": "in_progress"}],
            "no usable date": [{**run(), "createdAt": "soon"}],
        }
        for name, runs in cases.items():
            with self.subTest(name):
                verdict = freshness.evaluate(snapshot(timedelta(hours=1)), runs, NOW)
                self.assertTrue(verdict.alarm)
                self.assertEqual(verdict.severity, "sev3")

    def test_the_report_says_unknown_rather_than_leaving_a_blank(self) -> None:
        report = freshness.render_report(freshness.evaluate(None, None, NOW))
        self.assertIn("| Published snapshot `generated_at` | unknown |", report)
        self.assertIn("| Last completed nightly run on main | unknown |", report)
        self.assertIn("ALARM (sev2)", report)


class FingerprintTests(unittest.TestCase):
    def test_it_holds_while_the_same_file_merely_ages(self) -> None:
        stamp = (NOW - timedelta(hours=50)).strftime(STAMP)
        raw = json.dumps({"generated_at": stamp}).encode()
        first = freshness.evaluate(raw, [run()], NOW)
        later = freshness.evaluate(raw, [run()], NOW + timedelta(hours=6))
        self.assertEqual(first.fingerprint, later.fingerprint)
        self.assertIn(first.fingerprint, freshness.render_report(first))

    def test_it_moves_when_the_situation_changes(self) -> None:
        base = freshness.evaluate(snapshot(timedelta(hours=31)), [run("failure", run_id=1)], NOW)
        new_run = freshness.evaluate(snapshot(timedelta(hours=31)), [run("failure", run_id=2)], NOW)
        escalated = freshness.evaluate(
            snapshot(timedelta(hours=31)), [run("failure", run_id=1)], NOW + timedelta(hours=18)
        )
        self.assertNotEqual(base.fingerprint, new_run.fingerprint)
        self.assertNotEqual(base.fingerprint, escalated.fingerprint)


class CommandLineTests(unittest.TestCase):
    def check(self, raw: bytes | None, runs: object) -> tuple[int, str, str]:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            snap, runs_file = folder / "snapshot.json", folder / "runs.json"
            output, report = folder / "output", folder / "report.md"
            if raw is not None:
                snap.write_bytes(raw)
            if runs is not None:
                runs_file.write_text(json.dumps(runs))
            argv = [
                sys.executable,
                str(SCRIPT),
                "--snapshot",
                str(snap),
                "--runs",
                str(runs_file),
                "--now",
                NOW.strftime(STAMP),
                "--report",
                str(report),
                "--github-output",
                str(output),
            ]
            done = subprocess.run(argv, capture_output=True, text=True, check=False)
            return done.returncode, output.read_text(), report.read_text()

    def test_fresh_exits_zero(self) -> None:
        code, output, report = self.check(snapshot(timedelta(hours=3)), [run()])
        self.assertEqual(code, 0, report)
        self.assertIn("alarm=false\n", output)
        self.assertIn("## Snapshot freshness: fresh", report)

    def test_stale_exits_one_with_the_severity_the_issue_needs(self) -> None:
        code, output, report = self.check(snapshot(timedelta(days=3)), [run()])
        self.assertEqual(code, 1, report)
        self.assertIn("alarm=true\n", output)
        self.assertIn("severity=sev2\n", output)
        self.assertRegex(
            output, r"title=snapshot freshness: the published snapshot is 72\.0 hours old"
        )
        self.assertRegex(output, r"fingerprint=[0-9a-f]{16}\n")
        self.assertIn("generated_at=2026-09-15T15:00:00Z\n", output)

    def test_missing_inputs_exit_one(self) -> None:
        code, output, _ = self.check(None, None)
        self.assertEqual(code, 1)
        self.assertIn("severity=sev2\n", output)
        self.assertIn("generated_at=\n", output)

    def test_a_bad_now_is_a_usage_error_not_a_verdict(self) -> None:
        argv = [sys.executable, str(SCRIPT), "--snapshot", "x", "--runs", "y", "--now", "noon"]
        done = subprocess.run(argv, capture_output=True, text=True, check=False)
        self.assertEqual(done.returncode, 2, done.stderr)


class ThresholdProvenanceTests(unittest.TestCase):
    """The numbers in the script still follow from the schedule and the SLA."""

    def test_alarm_after_covers_the_nightly_cadence_and_the_job_timeout(self) -> None:
        text = (REPO / ".github" / "workflows" / "snapshot.yml").read_text()
        crons = re.findall(r'-\s*cron:\s*"([^"]+)"', text)
        self.assertEqual(
            crons, ["17 9 * * *"], "snapshot.yml's schedule changed; revisit ALARM_AFTER"
        )
        build = workflow_model.load(workflow_model.WORKFLOWS / "snapshot.yml").jobs["build"]
        timeout = int(re.search(r"timeout-minutes:\s*(\d+)", build.text).group(1))
        healthy_worst = timedelta(days=1) + timedelta(minutes=timeout)
        self.assertGreater(freshness.ALARM_AFTER, healthy_worst)
        self.assertLess(freshness.ALARM_AFTER, freshness.SLA)

    def test_the_sla_is_the_data_cards_sla(self) -> None:
        for card in ("lezwatch.md", "tvmaze.md"):
            text = (REPO / "docs" / "data" / card).read_text()
            match = re.search(r"^\| Staleness SLA \| (\d+) hours", text, re.M)
            self.assertIsNotNone(match, f"{card} has no Staleness SLA row")
            self.assertEqual(timedelta(hours=int(match.group(1))), freshness.SLA, card)

    def test_the_severities_are_the_incident_readmes(self) -> None:
        text = (REPO / "docs" / "incidents" / "README.md").read_text()
        sev2 = next(line for line in text.splitlines() if line.startswith("| **SEV2**"))
        sev3 = next(line for line in text.splitlines() if line.startswith("| **SEV3**"))
        self.assertIn("stale past the 48-hour SLA", sev2)
        self.assertIn("A nightly run fails", sev3)


class NegativeControlTests(unittest.TestCase):
    def test_the_thresholds_are_read_from_the_constants(self) -> None:
        # Loosen the alarm threshold; a 31-hour-old file must then pass. If
        # it still alarmed, the boundary tests above would be passing on a
        # number hard-coded somewhere else.
        real = freshness.ALARM_AFTER
        freshness.ALARM_AFTER = timedelta(hours=40)
        try:
            self.assertEqual(
                freshness.ALARM_AFTER, timedelta(hours=40), "the sabotage did not land"
            )
            verdict = freshness.evaluate(snapshot(timedelta(hours=31)), [run()], NOW)
        finally:
            freshness.ALARM_AFTER = real
        self.assertFalse(verdict.alarm, verdict.findings)
        self.assertEqual(freshness.ALARM_AFTER, real)
        self.assertTrue(freshness.evaluate(snapshot(timedelta(hours=31)), [run()], NOW).alarm)

    def test_a_planted_old_file_fails_the_command(self) -> None:
        planted = json.dumps({"generated_at": "2020-01-01T00:00:00Z"}).encode()
        self.assertIn(b'"2020-01-01T00:00:00Z"', planted, "the plant did not land")
        code, output, _ = CommandLineTests().check(planted, [run()])
        self.assertEqual(code, 1)
        self.assertIn("severity=sev2\n", output)


class WorkflowWiringTests(unittest.TestCase):
    """freshness.yml runs the check on a schedule and raises the incident."""

    def setUp(self) -> None:
        self.wf = workflow_model.load(workflow_model.WORKFLOWS / "freshness.yml")
        self.job = self.wf.jobs["check"]

    def test_it_runs_on_a_schedule_at_least_every_twelve_hours(self) -> None:
        self.assertIn("schedule", self.wf.triggers)
        self.assertIn("workflow_dispatch", self.wf.triggers)
        crons = re.findall(r'-\s*cron:\s*"([^"]+)"', self.wf.text)
        self.assertEqual(len(crons), 1, crons)
        minute, hour, *_ = crons[0].split()
        self.assertTrue(minute.isdigit(), crons[0])
        self.assertRegex(hour, r"^\*/([1-9]|1[0-2])$", "check at least every 12 hours")

    def test_it_runs_the_script_and_its_own_controls(self) -> None:
        bodies = "\n".join(self.job.run_blocks())
        self.assertIn("scripts/check_snapshot_freshness.py", bodies)
        self.assertIn("test_snapshot_freshness.py", bodies)
        self.assertIn("2020-01-01T00:00:00Z", bodies, "the in-workflow negative control is gone")

    def test_an_alarm_opens_an_incident_issue_on_scheduled_runs(self) -> None:
        text = self.job.text
        self.assertIn("issues: write", text)
        self.assertIn("actions: read", text)
        self.assertIn("gh issue create", text)
        self.assertIn("--label incident", text)
        self.assertIn("github.event_name == 'schedule'", text)
        self.assertIn(freshness.TITLE_PREFIX, text)


if __name__ == "__main__":
    unittest.main()
