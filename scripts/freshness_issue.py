"""What the freshness alarm does to its incident issue (DECISIONS 0066).

`freshness.yml` judges the published snapshot with
`check_snapshot_freshness.py`, then asks this script what to do on GitHub.
There is at most one open `snapshot freshness:` issue, and it speaks only when
the state changes:

- Stale (an alarm) and no open issue: open one, labeled `incident` and the
  severity. If the last freshness issue was closed by this workflow less than
  REOPEN_WITHIN ago, reopen that one instead, since a relapse that soon is
  most likely the same incident.
- Stale and the open issue already records this state (same severity, same
  reasons): nothing. A file that merely gets older, or another failed nightly
  run for the same reason, is not news.
- Stale in a new way (a new severity or a new reason): one comment. A move to
  SEV2 also swaps the `sev3` label for `sev2`; a move back down keeps `sev2`,
  the worst the incident reached (IR-02: labels are never silently dropped).
- Fresh and an issue is open: one comment saying so, then the issue closes
  itself. The postmortem is still owed (docs/incidents/README.md).
- Fresh and no open issue: nothing.

The state an issue records is the last `<!-- freshness-state: ... -->` marker
in its body and comments. Issues written before this script carry the older
`freshness-fingerprint` markers instead; a `recovered-` one reads as fresh and
any other as an alarm of unknown reasons, so the first run after the change
comments once on an old open alarm and then goes quiet.

Usage:
    freshness_issue.py pick --issues FILE
    freshness_issue.py decide --issue FILE --state alarm|fresh|no-verdict
        [--severity sev2|sev3] [--codes a,b] [--title TEXT] [--report FILE]
        [--run-url URL] [--now ISO-8601] --body FILE --decision FILE

`pick` reads `gh issue list --state all --label incident --json
number,title,state,closedAt` and prints the issue `decide` should look at, or
nothing. `decide` reads that issue as `gh issue view --json
number,state,closedAt,labels,body,comments` (or `null`), writes the comment or
issue body to --body and the action to --decision as JSON: action (none,
create, comment, reopen, close), number, title, severity, add_label,
remove_label.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

TITLE_PREFIX = "snapshot freshness:"
REOPEN_WITHIN = timedelta(hours=72)
TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
NO_VERDICT_TITLE = f"{TITLE_PREFIX} the check could not reach a verdict"
AUTO_CLOSED = "freshness-closed: automatic"
STATE_MARKER = re.compile(r"<!-- freshness-state: ([^>]*?) -->")
LEGACY_MARKER = re.compile(r"freshness-fingerprint: (\S+)")
FRESH = "fresh"
LEGACY_ALARM = "alarm unknown"


@dataclass(frozen=True)
class Decision:
    action: str
    number: int | None = None
    title: str = ""
    severity: str = ""
    add_label: str = ""
    remove_label: str = ""
    body: str = ""

    def as_json(self) -> str:
        fields = {
            "action": self.action,
            "number": self.number,
            "title": self.title,
            "severity": self.severity,
            "add_label": self.add_label,
            "remove_label": self.remove_label,
        }
        return json.dumps(fields, indent=2) + "\n"


def parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value, TIMESTAMP_FORMAT).replace(tzinfo=UTC)
    except ValueError:
        return None


def is_freshness(issue: object) -> bool:
    return isinstance(issue, dict) and str(issue.get("title", "")).startswith(TITLE_PREFIX)


def pick(issues: object) -> int | None:
    """The open freshness issue (the newest, if somehow two), else the last closed one."""
    if not isinstance(issues, list):
        return None
    ours = [i for i in issues if is_freshness(i) and isinstance(i.get("number"), int)]
    open_ = [i for i in ours if str(i.get("state", "")).upper() == "OPEN"]
    if open_:
        return max(i["number"] for i in open_)
    closed = [i for i in ours if parse_timestamp(i.get("closedAt")) is not None]
    if not closed:
        return None
    return max(closed, key=lambda i: parse_timestamp(i["closedAt"]))["number"]


def state_label(state: str, severity: str, codes: str) -> str:
    """The state as one comparable string: `fresh` or `alarm sev3 missed-run,run-failed`."""
    if state == FRESH:
        return FRESH
    reasons = ",".join(sorted(c for c in codes.split(",") if c)) or "unknown"
    return f"alarm {severity or 'sev3'} {reasons}"


def texts(issue: dict) -> list[str]:
    comments = issue.get("comments") or []
    return [str(issue.get("body") or "")] + [
        str(c.get("body") or "") for c in comments if isinstance(c, dict)
    ]


def recorded_state(issue: dict) -> str | None:
    """The last state the issue records, oldest text first; None if it records none."""
    last = None
    for text in texts(issue):
        states = STATE_MARKER.findall(text)
        if states:
            last = states[-1].strip()
            continue
        legacy = LEGACY_MARKER.findall(text)
        if legacy:
            last = FRESH if legacy[-1].startswith("recovered-") else LEGACY_ALARM
    return last


def labels(issue: dict) -> set[str]:
    return {
        str(label.get("name")) for label in issue.get("labels") or [] if isinstance(label, dict)
    }


def closed_by_us(issue: dict) -> bool:
    return any(AUTO_CLOSED in text for text in texts(issue))


def marker(state: str) -> str:
    return f"<!-- freshness-state: {state} -->"


def alarm_body(report: str, state: str, run_url: str) -> str:
    body = report.rstrip("\n") + "\n"
    if run_url:
        body += f"\nRun: {run_url}\n"
    return body + f"\n{marker(state)}\n"


def no_verdict_report() -> str:
    return (
        "## Snapshot freshness: no verdict\n\n"
        "The freshness job failed before it could judge the published snapshot, "
        "so its age is unknown. A silenced gate is SEV3 (docs/incidents/README.md).\n"
    )


def fresh_body(run_url: str) -> str:
    where = f" ({run_url})" if run_url else ""
    return (
        "Fresh again: the published snapshot is fresh and the last nightly run "
        f"succeeded{where}. This issue closes itself now; it reopens if the alarm "
        f"returns within {int(REOPEN_WITHIN.total_seconds() // 3600)} hours. The "
        "postmortem is still owed, as docs/incidents/README.md says.\n\n"
        f"{marker(FRESH)}\n<!-- {AUTO_CLOSED} -->\n"
    )


def decide(
    issue: dict | None,
    state: str,
    severity: str,
    codes: str,
    title: str,
    report: str,
    run_url: str,
    now: datetime,
) -> Decision:
    if state == "no-verdict":
        severity, codes, title = "sev3", "no-verdict", NO_VERDICT_TITLE
        report = no_verdict_report()
        state = "alarm"
    if state not in ("alarm", FRESH):
        raise ValueError(f"unknown state {state!r}")
    severity = severity or "sev3"
    current = state_label(state, severity, codes)
    is_open = issue is not None and str(issue.get("state", "")).upper() == "OPEN"
    number = issue.get("number") if issue is not None else None

    if state == FRESH:
        if not is_open:
            return Decision("none", number)
        return Decision("close", number, body=fresh_body(run_url))

    body = alarm_body(report, current, run_url)
    escalate = {}
    if issue is not None and severity == "sev2" and "sev2" not in labels(issue):
        escalate = {"add_label": "sev2", "remove_label": "sev3"}

    if is_open:
        if recorded_state(issue) == current:
            return Decision("none", number)
        return Decision("comment", number, severity=severity, body=body, **escalate)

    if issue is not None:
        closed_at = parse_timestamp(issue.get("closedAt"))
        recent = closed_at is not None and now - closed_at <= REOPEN_WITHIN
        if recent and closed_by_us(issue):
            return Decision("reopen", number, severity=severity, body=body, **escalate)

    title = title or f"{TITLE_PREFIX} alarm"
    return Decision("create", None, title=title, severity=severity, body=body)


def load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    pick_cmd = sub.add_parser("pick")
    pick_cmd.add_argument("--issues", type=Path, required=True)
    decide_cmd = sub.add_parser("decide")
    decide_cmd.add_argument("--issue", type=Path, required=True)
    decide_cmd.add_argument("--state", choices=("alarm", FRESH, "no-verdict"), required=True)
    decide_cmd.add_argument("--severity", default="")
    decide_cmd.add_argument("--codes", default="")
    decide_cmd.add_argument("--title", default="")
    decide_cmd.add_argument("--report", type=Path)
    decide_cmd.add_argument("--run-url", default="")
    decide_cmd.add_argument("--now", help="ISO-8601 UTC time (tests)")
    decide_cmd.add_argument("--body", type=Path, required=True)
    decide_cmd.add_argument("--decision", type=Path, required=True)
    args = parser.parse_args(argv)

    if args.command == "pick":
        number = pick(load_json(args.issues))
        print("" if number is None else number)
        return 0

    now = datetime.now(UTC) if args.now is None else parse_timestamp(args.now)
    if now is None:
        parser.error(f"--now must look like 2026-11-19T12:50:09Z, got {args.now!r}")
    if args.severity not in ("", "sev2", "sev3"):
        parser.error(f"--severity must be sev2 or sev3, got {args.severity!r}")
    issue = load_json(args.issue)
    report = ""
    if args.report is not None:
        try:
            report = args.report.read_text(encoding="utf-8")
        except OSError:
            report = ""
    decision = decide(
        issue if isinstance(issue, dict) else None,
        args.state,
        args.severity,
        args.codes,
        args.title,
        report,
        args.run_url,
        now,
    )
    args.body.write_text(decision.body, encoding="utf-8")
    args.decision.write_text(decision.as_json(), encoding="utf-8")
    print(decision.as_json(), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
