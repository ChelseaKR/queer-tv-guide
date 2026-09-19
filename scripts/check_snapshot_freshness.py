"""Alarm when the published snapshot is stale or the nightly run failed (DG-04, #25).

The app reads one file, which `snapshot.yml` rebuilds and publishes to GitHub
Pages every night. `freshness.yml` fetches that file and the nightly run
history, and this script judges them:

1. the published file's `generated_at`, against the current time;
2. the most recent completed run of `snapshot.yml` on `main`.

The thresholds come from the schedule. `snapshot.yml` runs once a day at
09:17 UTC. Measured 2026-09-15 to 2026-09-18, the scheduler started it 12 to
16 minutes late and each run took 16 to 18 minutes, so a healthy file is at
most about 24 h 10 min old when the next one replaces it. A full mirror takes
about 55 minutes, and the job's timeout is 90.

- Older than ALARM_AFTER (30 h): a nightly run has been missed. That is the
  24-hour cadence plus the 90-minute job timeout plus 4.5 hours for a late
  scheduler. SEV3, the incident README's "a nightly run fails and the
  previous snapshot keeps serving, correctly dated".
- Older than SLA (48 h): the data cards' staleness SLA is broken. SEV2, the
  README's "stale past the 48-hour SLA".
- The latest completed nightly run did not succeed (failed, canceled, timed
  out): SEV3, even while the file is still fresh.
- An answer nobody can give is never "fresh": a file that cannot be fetched
  or read, a date in the future, or no run history is an alarm too.

Usage:
    check_snapshot_freshness.py --snapshot FILE --runs FILE
        [--now ISO-8601] [--report FILE] [--github-output FILE]

`--runs` is the JSON array from `gh run list --json
databaseId,status,conclusion,event,createdAt,url`. A path that does not
exist means the fetch failed, and is judged as unknown.

Exit 0: fresh, and the last nightly run succeeded. Exit 1: an alarm; the
report says why.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

ALARM_AFTER = timedelta(hours=30)
SLA = timedelta(hours=48)
FUTURE_TOLERANCE = timedelta(minutes=10)
TITLE_PREFIX = "snapshot freshness:"
TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
SEVERITY_RANK = {"sev3": 1, "sev2": 2}


@dataclass(frozen=True)
class Finding:
    code: str
    severity: str
    message: str


@dataclass
class Verdict:
    now: datetime
    generated_at: datetime | None = None
    last_run: dict | None = None
    findings: list[Finding] = field(default_factory=list)

    @property
    def alarm(self) -> bool:
        return bool(self.findings)

    @property
    def severity(self) -> str:
        if not self.findings:
            return ""
        return max((f.severity for f in self.findings), key=SEVERITY_RANK.__getitem__)

    @property
    def age(self) -> timedelta | None:
        return None if self.generated_at is None else self.now - self.generated_at

    @property
    def title(self) -> str:
        if not self.findings:
            return f"{TITLE_PREFIX} fresh"
        worst = next(f for f in self.findings if f.severity == self.severity)
        return f"{TITLE_PREFIX} {worst.message}"

    @property
    def fingerprint(self) -> str:
        """Changes when the situation does, not as the file merely ages.

        The incident issue gets a new comment only when this changes: a new
        severity, a new reason, a newly published file, or a new nightly run.
        """
        run_id = (self.last_run or {}).get("databaseId")
        parts = [
            self.severity,
            ",".join(sorted(f.code for f in self.findings)),
            self.generated_at.strftime(TIMESTAMP_FORMAT) if self.generated_at else "unknown",
            str(run_id) if run_id is not None else "unknown",
        ]
        return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


def parse_timestamp(value: object) -> datetime | None:
    """A `YYYY-MM-DDTHH:MM:SSZ` string as a UTC datetime, else None."""
    if not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value, TIMESTAMP_FORMAT).replace(tzinfo=UTC)
    except ValueError:
        return None


def hours(delta: timedelta) -> str:
    return f"{delta.total_seconds() / 3600:.1f} hours"


def snapshot_findings(raw: bytes | None, now: datetime) -> tuple[datetime | None, list[Finding]]:
    """The published file's date and anything wrong with its age."""
    if raw is None:
        return None, [Finding("unreadable", "sev2", "the published snapshot could not be fetched")]
    try:
        document = json.loads(raw)
    except ValueError:
        return None, [Finding("unreadable", "sev2", "the published snapshot is not valid JSON")]
    stamp = document.get("generated_at") if isinstance(document, dict) else None
    generated_at = parse_timestamp(stamp)
    if generated_at is None:
        message = "the published snapshot has no readable generated_at, so its age is unknown"
        return None, [Finding("unreadable", "sev2", message)]
    age = now - generated_at
    if age < -FUTURE_TOLERANCE:
        message = f"the published snapshot is dated {stamp}, in the future, so its age is unknown"
        return generated_at, [Finding("future", "sev2", message)]
    if age > SLA:
        message = f"the published snapshot is {hours(age)} old, past the 48-hour SLA"
        return generated_at, [Finding("past-sla", "sev2", message)]
    if age > ALARM_AFTER:
        message = f"the published snapshot is {hours(age)} old; a nightly run was missed"
        return generated_at, [Finding("missed-run", "sev3", message)]
    return generated_at, []


def run_findings(runs: object) -> tuple[dict | None, list[Finding]]:
    """The latest completed nightly run and whether it succeeded."""
    if not isinstance(runs, list):
        return None, [
            Finding("runs-unreadable", "sev3", "the nightly run history could not be read")
        ]
    completed = [
        r
        for r in runs
        if isinstance(r, dict)
        and r.get("status") == "completed"
        and parse_timestamp(r.get("createdAt")) is not None
    ]
    if not completed:
        return None, [Finding("no-runs", "sev3", "no completed nightly run was found on main")]
    latest = max(completed, key=lambda r: parse_timestamp(r["createdAt"]))
    conclusion = latest.get("conclusion") or "unknown"
    if conclusion != "success":
        message = f"the last nightly run ended in {conclusion}"
        return latest, [Finding("run-failed", "sev3", message)]
    return latest, []


def evaluate(raw_snapshot: bytes | None, runs: object, now: datetime) -> Verdict:
    generated_at, found = snapshot_findings(raw_snapshot, now)
    last_run, run_found = run_findings(runs)
    return Verdict(
        now=now, generated_at=generated_at, last_run=last_run, findings=found + run_found
    )


def render_report(verdict: Verdict) -> str:
    """Markdown for the job summary and the incident issue. Unknowns say "unknown"."""
    state = f"ALARM ({verdict.severity})" if verdict.alarm else "fresh"
    published = "unknown"
    if verdict.generated_at is not None and verdict.age is not None:
        stamp = verdict.generated_at.strftime(TIMESTAMP_FORMAT)
        if verdict.age < -FUTURE_TOLERANCE:
            published = f"{stamp}, age unknown (later than the check's clock)"
        else:
            published = f"{stamp}, {hours(verdict.age)} old"
    run = verdict.last_run
    last_run = "unknown"
    if run is not None:
        last_run = (
            f"run {run.get('databaseId', 'unknown')} ({run.get('event', 'unknown')}), "
            f"{run.get('conclusion') or 'unknown'}, created {run.get('createdAt', 'unknown')}: "
            f"{run.get('url', 'no link')}"
        )
    lines = [
        f"## Snapshot freshness: {state}",
        "",
        f"Checked at {verdict.now.strftime(TIMESTAMP_FORMAT)}.",
        "",
        "| Check | Result |",
        "|---|---|",
        f"| Published snapshot `generated_at` | {published} |",
        f"| Alarm after | {hours(ALARM_AFTER)} (a nightly run missed) |",
        f"| Staleness SLA | {hours(SLA)} (`docs/data/lezwatch.md`, `docs/data/tvmaze.md`) |",
        f"| Last completed nightly run on main | {last_run} |",
    ]
    if verdict.alarm:
        lines += ["", "Why:", ""] + [f"- **{f.severity}** {f.message}." for f in verdict.findings]
        lines += [
            "",
            "Handle it as `docs/incidents/README.md` says. Recovery is a `snapshot.yml` "
            "dispatch (RTO about an hour, `docs/ROADMAP.md`). Close this issue once the "
            "published file is fresh again and the postmortem is written.",
        ]
    lines += ["", f"<!-- freshness-fingerprint: {verdict.fingerprint} -->", ""]
    return "\n".join(lines)


def read_optional(path: Path) -> bytes | None:
    try:
        return path.read_bytes()
    except OSError:
        return None


def load_runs(path: Path) -> object:
    raw = read_optional(path)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return None


def write_outputs(path: Path, verdict: Verdict) -> None:
    generated = verdict.generated_at.strftime(TIMESTAMP_FORMAT) if verdict.generated_at else ""
    values = {
        "alarm": "true" if verdict.alarm else "false",
        "severity": verdict.severity,
        "title": verdict.title,
        "fingerprint": verdict.fingerprint,
        "generated_at": generated,
    }
    with path.open("a", encoding="utf-8") as out:
        for key, value in values.items():
            out.write(f"{key}={value}\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--now", help="ISO-8601 UTC time to judge at (tests)")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args(argv)

    now = datetime.now(UTC) if args.now is None else parse_timestamp(args.now)
    if now is None:
        parser.error(f"--now must look like 2026-09-18T09:44:42Z, got {args.now!r}")
    verdict = evaluate(read_optional(args.snapshot), load_runs(args.runs), now)
    report = render_report(verdict)
    print(report)
    if args.report is not None:
        args.report.write_text(report, encoding="utf-8")
    if args.github_output is not None:
        write_outputs(args.github_output, verdict)
    return 1 if verdict.alarm else 0


if __name__ == "__main__":
    sys.exit(main())
