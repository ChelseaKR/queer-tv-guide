"""The freshness alarm's incident issue (DECISIONS 0066): scripts/freshness_issue.py.

One issue at a time; a comment only when the state changes; it closes itself
on recovery and reopens on a quick relapse; issues written before the change
are read correctly; the command line the workflow runs; and that
freshness.yml acts on every decision. The negative controls check that their
sabotage landed before they trust the result.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import workflow_model

REPO = workflow_model.REPO
SCRIPT = REPO / "scripts" / "freshness_issue.py"

_spec = importlib.util.spec_from_file_location("freshness_issue", SCRIPT)
assert _spec is not None and _spec.loader is not None
fi = importlib.util.module_from_spec(_spec)
sys.modules["freshness_issue"] = fi
_spec.loader.exec_module(fi)

NOW = datetime(2026, 11, 19, 12, 50, 0, tzinfo=UTC)
STAMP = "%Y-%m-%dT%H:%M:%SZ"
REPORT = "## Snapshot freshness: ALARM (sev3)\n\n<!-- freshness-fingerprint: 0123456789abcdef -->\n"
TITLE = "snapshot freshness: the last nightly run ended in failure"


def issue(
    *texts: str, state: str = "OPEN", closed: timedelta | None = None, sev: str = "sev3"
) -> dict:
    body, *comments = texts or ("",)
    return {
        "number": 91,
        "state": state,
        "closedAt": None if closed is None else (NOW - closed).strftime(STAMP),
        "labels": [{"name": "incident"}, {"name": sev}],
        "body": body,
        "comments": [{"body": c} for c in comments],
    }


def alarm(found: dict | None, severity: str = "sev3", codes: str = "run-failed") -> object:
    return fi.decide(found, "alarm", severity, codes, TITLE, REPORT, "https://run/1", NOW)


def fresh(found: dict | None) -> object:
    return fi.decide(found, "fresh", "", "", "", "", "https://run/2", NOW)


def written(decision: object) -> str:
    """The state marker a decision's body leaves on the issue."""
    return fi.STATE_MARKER.findall(decision.body)[-1]


class OneIssueTests(unittest.TestCase):
    def test_a_first_alarm_opens_one_issue_with_its_severity(self) -> None:
        d = alarm(None, "sev2", "past-sla")
        self.assertEqual(d.action, "create")
        self.assertEqual((d.title, d.severity), (TITLE, "sev2"))
        self.assertIn("ALARM (sev3)", d.body, "the checker's report is the body")
        self.assertIn("Run: https://run/1", d.body)
        self.assertEqual(written(d), "alarm sev2 past-sla")

    def test_pick_prefers_the_open_freshness_issue(self) -> None:
        issues = [
            {
                "number": 12,
                "title": "snapshot freshness: old",
                "state": "CLOSED",
                "closedAt": "2026-11-18T00:00:00Z",
            },
            {"number": 91, "title": TITLE, "state": "OPEN", "closedAt": None},
            {"number": 99, "title": "a leaked token", "state": "OPEN", "closedAt": None},
        ]
        self.assertEqual(fi.pick(issues), 91)

    def test_pick_falls_back_to_the_most_recently_closed_one(self) -> None:
        issues = [
            {
                "number": 12,
                "title": "snapshot freshness: a",
                "state": "CLOSED",
                "closedAt": "2026-11-18T00:00:00Z",
            },
            {
                "number": 8,
                "title": "snapshot freshness: b",
                "state": "CLOSED",
                "closedAt": "2026-11-19T00:00:00Z",
            },
            {"number": 99, "title": "a leaked token", "state": "OPEN", "closedAt": None},
        ]
        self.assertEqual(fi.pick(issues), 8)

    def test_pick_finds_nothing_in_nothing(self) -> None:
        for issues in (
            None,
            [],
            {"issues": []},
            [{"number": 99, "title": "other", "state": "OPEN"}],
        ):
            with self.subTest(issues=issues):
                self.assertIsNone(fi.pick(issues))


class QuietTests(unittest.TestCase):
    def test_the_same_state_again_says_nothing(self) -> None:
        first = alarm(None)
        open_issue = issue(first.body)
        for _ in range(3):
            self.assertEqual(alarm(open_issue).action, "none")

    def test_another_failed_run_for_the_same_reason_says_nothing(self) -> None:
        # The fingerprint in the report moves with every new run; the issue does not.
        open_issue = issue(alarm(None).body)
        other_run = fi.decide(
            open_issue,
            "alarm",
            "sev3",
            "run-failed",
            TITLE,
            REPORT.replace("0123456789abcdef", "fedcba9876543210"),
            "https://run/9",
            NOW,
        )
        self.assertEqual(other_run.action, "none")

    def test_reason_order_does_not_matter(self) -> None:
        open_issue = issue(alarm(None, "sev2", "run-failed,past-sla").body)
        self.assertEqual(alarm(open_issue, "sev2", "past-sla,run-failed").action, "none")

    def test_a_new_reason_comments_once(self) -> None:
        open_issue = issue(alarm(None).body)
        d = alarm(open_issue, "sev3", "missed-run,run-failed")
        self.assertEqual(d.action, "comment")
        self.assertEqual(d.number, 91)
        self.assertEqual((d.add_label, d.remove_label), ("", ""))
        again = alarm(issue(open_issue["body"], d.body), "sev3", "missed-run,run-failed")
        self.assertEqual(again.action, "none")

    def test_a_move_to_sev2_comments_and_swaps_the_label(self) -> None:
        d = alarm(issue(alarm(None).body), "sev2", "past-sla,run-failed")
        self.assertEqual(d.action, "comment")
        self.assertEqual((d.add_label, d.remove_label), ("sev2", "sev3"))

    def test_a_move_back_to_sev3_keeps_the_sev2_label(self) -> None:
        sev2 = alarm(None, "sev2", "past-sla")
        d = alarm(issue(sev2.body, sev="sev2"), "sev3", "run-failed")
        self.assertEqual(d.action, "comment")
        self.assertEqual((d.add_label, d.remove_label), ("", ""))

    def test_no_verdict_is_sev3_and_said_once(self) -> None:
        first = fi.decide(None, "no-verdict", "", "", "", "", "https://run/3", NOW)
        self.assertEqual(first.action, "create")
        self.assertEqual((first.title, first.severity), (fi.NO_VERDICT_TITLE, "sev3"))
        self.assertIn("no verdict", first.body)
        again = fi.decide(issue(first.body), "no-verdict", "", "", "", "", "https://run/4", NOW)
        self.assertEqual(again.action, "none")


class RecoveryTests(unittest.TestCase):
    def test_fresh_closes_the_open_issue_once(self) -> None:
        d = fresh(issue(alarm(None).body))
        self.assertEqual((d.action, d.number), ("close", 91))
        self.assertIn("Fresh again", d.body)
        self.assertIn("postmortem is still owed", d.body)
        self.assertIn(fi.AUTO_CLOSED, d.body)
        self.assertEqual(written(d), "fresh")

    def test_fresh_with_nothing_open_does_nothing(self) -> None:
        self.assertEqual(fresh(None).action, "none")
        closed = issue(alarm(None).body, state="CLOSED", closed=timedelta(hours=1))
        self.assertEqual(fresh(closed).action, "none")

    def test_a_quick_relapse_reopens_the_issue_this_workflow_closed(self) -> None:
        closing = fresh(issue(alarm(None).body)).body
        for hours in (1, 72):
            with self.subTest(hours=hours):
                closed = issue(
                    alarm(None).body, closing, state="CLOSED", closed=timedelta(hours=hours)
                )
                d = alarm(closed)
                self.assertEqual((d.action, d.number), ("reopen", 91))
                self.assertIn("ALARM", d.body)

    def test_a_late_relapse_opens_a_new_issue(self) -> None:
        closing = fresh(issue(alarm(None).body)).body
        closed = issue(
            alarm(None).body, closing, state="CLOSED", closed=timedelta(hours=72, seconds=1)
        )
        self.assertEqual(alarm(closed).action, "create")

    def test_an_issue_a_person_closed_is_never_reopened(self) -> None:
        closed = issue(alarm(None).body, state="CLOSED", closed=timedelta(hours=1))
        self.assertEqual(alarm(closed).action, "create")

    def test_a_reopened_issue_escalates_its_label_too(self) -> None:
        closing = fresh(issue(alarm(None).body)).body
        closed = issue(alarm(None).body, closing, state="CLOSED", closed=timedelta(hours=2))
        d = alarm(closed, "sev2", "past-sla")
        self.assertEqual((d.action, d.add_label, d.remove_label), ("reopen", "sev2", "sev3"))


class LegacyIssueTests(unittest.TestCase):
    """#91 was written by the old steps: fingerprint markers, no state markers."""

    OLD_ALARM = (
        "## Snapshot freshness: ALARM (sev3)\n\n<!-- freshness-fingerprint: 594607a4d6c894d7 -->\n"
    )
    OLD_FRESH = (
        "Fresh again: ...\n\n<!-- freshness-fingerprint: recovered-2026-11-19T09:36:33Z -->\n"
    )

    def test_an_old_recovery_note_reads_as_fresh_and_the_issue_closes(self) -> None:
        old = issue(self.OLD_ALARM, self.OLD_FRESH, self.OLD_FRESH)
        self.assertEqual(fi.recorded_state(old), "fresh")
        self.assertEqual(fresh(old).action, "close")

    def test_an_old_open_alarm_gets_one_comment_then_quiet(self) -> None:
        old = issue(self.OLD_ALARM)
        self.assertEqual(fi.recorded_state(old), fi.LEGACY_ALARM)
        d = alarm(old)
        self.assertEqual(d.action, "comment")
        self.assertEqual(alarm(issue(self.OLD_ALARM, d.body)).action, "none")

    def test_a_state_marker_wins_over_the_report_fingerprint_beside_it(self) -> None:
        # New bodies carry both: the checker's fingerprint and the state.
        self.assertEqual(fi.recorded_state(issue(alarm(None).body)), "alarm sev3 run-failed")

    def test_an_issue_with_no_markers_records_nothing(self) -> None:
        self.assertIsNone(fi.recorded_state(issue("written by hand")))
        self.assertEqual(alarm(issue("written by hand")).action, "comment")


class CommandLineTests(unittest.TestCase):
    def run_script(self, *args: str) -> subprocess.CompletedProcess:
        argv = [sys.executable, str(SCRIPT), *args]
        return subprocess.run(argv, capture_output=True, text=True, check=False)

    def decide(self, found: object, *extra: str) -> tuple[dict, str]:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "issue.json").write_text(json.dumps(found))
            (folder / "report.md").write_text(REPORT)
            done = self.run_script(
                "decide",
                "--issue",
                str(folder / "issue.json"),
                "--report",
                str(folder / "report.md"),
                "--now",
                NOW.strftime(STAMP),
                "--body",
                str(folder / "body.md"),
                "--decision",
                str(folder / "decision.json"),
                *extra,
            )
            self.assertEqual(done.returncode, 0, done.stderr)
            return (
                json.loads((folder / "decision.json").read_text()),
                (folder / "body.md").read_text(),
            )

    def test_pick_prints_a_number_or_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "issues.json"
            path.write_text(json.dumps([{"number": 91, "title": TITLE, "state": "OPEN"}]))
            self.assertEqual(self.run_script("pick", "--issues", str(path)).stdout, "91\n")
            path.write_text("[]")
            self.assertEqual(self.run_script("pick", "--issues", str(path)).stdout, "\n")
            missing = str(Path(tmp) / "missing.json")
            self.assertEqual(self.run_script("pick", "--issues", missing).stdout, "\n")

    def test_decide_writes_the_action_and_the_body(self) -> None:
        decision, body = self.decide(
            None,
            "--state",
            "alarm",
            "--severity",
            "sev2",
            "--codes",
            "past-sla",
            "--title",
            TITLE,
        )
        self.assertEqual(decision["action"], "create")
        self.assertEqual(decision["severity"], "sev2")
        self.assertEqual(decision["title"], TITLE)
        self.assertIn("<!-- freshness-state: alarm sev2 past-sla -->", body)

    def test_a_null_issue_and_fresh_is_nothing_with_an_empty_body(self) -> None:
        decision, body = self.decide(None, "--state", "fresh")
        self.assertEqual(decision["action"], "none")
        self.assertEqual(body, "")

    def test_an_empty_alarm_from_a_crashed_checker_is_no_verdict(self) -> None:
        decision, body = self.decide(None, "--state", "no-verdict")
        self.assertIn("no verdict", body)
        self.assertEqual((decision["action"], decision["severity"]), ("create", "sev3"))

    def test_bad_arguments_are_usage_errors(self) -> None:
        for extra in (("--state", "stale"), ("--state", "alarm", "--severity", "sev1")):
            with self.subTest(extra=extra):
                done = self.run_script(
                    "decide", "--issue", "x", "--body", "b", "--decision", "d", *extra
                )
                self.assertEqual(done.returncode, 2, done.stderr)


class NegativeControlTests(unittest.TestCase):
    def test_the_reopen_window_is_read_from_the_constant(self) -> None:
        closing = fresh(issue(alarm(None).body)).body
        closed = issue(alarm(None).body, closing, state="CLOSED", closed=timedelta(hours=100))
        real = fi.REOPEN_WITHIN
        fi.REOPEN_WITHIN = timedelta(hours=120)
        try:
            self.assertEqual(fi.REOPEN_WITHIN, timedelta(hours=120), "the sabotage did not land")
            widened = alarm(closed).action
        finally:
            fi.REOPEN_WITHIN = real
        self.assertEqual(widened, "reopen")
        self.assertEqual(alarm(closed).action, "create")

    def test_a_changed_state_is_not_mistaken_for_the_same_one(self) -> None:
        open_issue = issue(alarm(None).body)
        tampered = open_issue["body"].replace("run-failed -->", "missed-run -->")
        self.assertNotEqual(tampered, open_issue["body"], "the sabotage did not land")
        self.assertEqual(alarm(issue(tampered)).action, "comment")


class WorkflowWiringTests(unittest.TestCase):
    """freshness.yml asks the script, and acts on every answer it can give."""

    def setUp(self) -> None:
        self.job = workflow_model.load(workflow_model.WORKFLOWS / "freshness.yml").jobs["check"]
        self.bodies = "\n".join(self.job.run_blocks())

    def test_it_asks_the_script(self) -> None:
        self.assertIn("scripts/freshness_issue.py pick", self.bodies)
        self.assertIn("scripts/freshness_issue.py decide", self.bodies)
        self.assertIn("test_freshness_issue.py", self.bodies, "the self-test skips these tests")

    def test_every_action_has_a_branch(self) -> None:
        for action in ("none", "create", "comment", "reopen", "close"):
            with self.subTest(action=action):
                self.assertRegex(self.bodies, rf"\n\s*{action}\)\n")
        for command in (
            "gh issue create",
            "gh issue comment",
            "gh issue reopen",
            "gh issue close",
            "gh issue edit",
        ):
            with self.subTest(command=command):
                self.assertIn(command, self.bodies)
        self.assertIn("unknown action", self.bodies, "an unexpected answer must fail the job")

    def test_it_never_writes_to_issues_from_a_pull_request(self) -> None:
        self.assertIn("!cancelled() && (github.event_name == 'schedule' ||", self.job.text)
        self.assertNotIn("github.event_name == 'pull_request'", self.job.text)

    def test_the_old_recovery_comment_is_gone(self) -> None:
        self.assertNotIn("recovered-$GENERATED_AT", self.job.text)

    def test_the_checker_titles_the_issues_this_script_looks_for(self) -> None:
        path = REPO / "scripts" / "check_snapshot_freshness.py"
        spec = importlib.util.spec_from_file_location("check_snapshot_freshness_titles", path)
        assert spec is not None and spec.loader is not None
        checker = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = checker
        spec.loader.exec_module(checker)
        self.assertEqual(checker.TITLE_PREFIX, fi.TITLE_PREFIX)
        self.assertTrue(fi.NO_VERDICT_TITLE.startswith(fi.TITLE_PREFIX))


if __name__ == "__main__":
    unittest.main()
