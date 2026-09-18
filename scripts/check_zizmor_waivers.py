"""Fail when a waiver in .github/zizmor.yml no longer matches a real finding.

`make workflows` runs zizmor twice. The first run honours .github/zizmor.yml
and is the gate: any finding at medium severity or above that is not waived
fails it. This script is the second run. It reads zizmor's JSON output for
the same workflows with every waiver switched off, and checks that each
(rule, file) pair the config waives still produces at least one finding.

Without this, a waiver outlives the defect it excuses: the workflow gets
fixed, the ignore line stays, and the next regression in that file for that
rule passes silently. With it, the PR that fixes a workflow must also delete
its waiver.

Usage: python3 scripts/check_zizmor_waivers.py <zizmor-json-no-config> [config]
Exit 0: every waiver still matches. Exit 1: a stale or malformed waiver, or
input that proves nothing was scanned.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SEVERITY_ORDER = {"unknown": 0, "informational": 1, "low": 2, "medium": 3, "high": 4}
GATE_FLOOR = "medium"  # must match --min-severity in the Makefile's `workflows` target

RULE_RE = re.compile(r"^  ([a-z0-9-]+):\s*(?:#.*)?$")
IGNORE_RE = re.compile(r"^    ignore:\s*(?:#.*)?$")
ENTRY_RE = re.compile(r"^      - ([A-Za-z0-9_.-]+\.ya?ml)(?::\d+(?::\d+)?)?\s*(?:#.*)?$")


def _meaningful(text: str) -> list[tuple[int, str]]:
    """(line number, line) for every line that is not blank or a comment."""
    return [
        (number, line)
        for number, line in enumerate(text.splitlines(), start=1)
        if line.strip() and not line.strip().startswith("#")
    ]


def parse_waivers(text: str) -> list[tuple[str, str]]:
    """(rule, workflow file name) for every `ignore:` entry.

    Raises ValueError on any non-blank, non-comment line the constrained
    format does not recognise, so a reformatted config cannot make the
    checker see zero waivers and pass.
    """
    lines = _meaningful(text)
    if not lines or lines[0][1].rstrip() not in ("rules:", "rules: {}"):
        raise ValueError("the first entry must be `rules:` or `rules: {}`")
    if lines[0][1].rstrip() == "rules: {}":
        if len(lines) > 1:
            raise ValueError(f"line {lines[1][0]}: nothing may follow `rules: {{}}`")
        return []
    waivers: list[tuple[str, str]] = []
    rule: str | None = None
    for number, line in lines[1:]:
        if match := RULE_RE.match(line):
            rule = match.group(1)
        elif IGNORE_RE.match(line) and rule is not None:
            continue
        elif (match := ENTRY_RE.match(line)) and rule is not None:
            waivers.append((rule, match.group(1)))
        else:
            raise ValueError(f"line {number}: unrecognised line {line!r}")
    return waivers


def findings(report: list[dict]) -> set[tuple[str, str]]:
    """(rule, workflow file name) for every finding at or above the gate floor."""
    found: set[tuple[str, str]] = set()
    floor = SEVERITY_ORDER[GATE_FLOOR]
    for finding in report:
        severity = str(finding["determinations"]["severity"]).lower()
        if SEVERITY_ORDER.get(severity, 0) < floor:
            continue
        for location in finding["locations"]:
            key = location["symbolic"]["key"]
            path = key.get("Local", {}).get("verbatim_path")
            if path:
                found.add((finding["ident"], Path(path).name))
    return found


def main(argv: list[str]) -> int:
    if len(argv) not in (2, 3):
        print(__doc__, file=sys.stderr)
        return 2
    report_path = Path(argv[1])
    config_path = Path(argv[2]) if len(argv) == 3 else Path(".github/zizmor.yml")
    report = json.loads(report_path.read_text())
    if not isinstance(report, list):
        print("zizmor JSON is not a list of findings", file=sys.stderr)
        return 1
    try:
        waivers = parse_waivers(config_path.read_text())
    except ValueError as exc:
        print(f"{config_path}: {exc}", file=sys.stderr)
        return 1
    actual = findings(report)
    stale = [w for w in waivers if w not in actual]
    print(
        f"zizmor waivers: {len(waivers)} in {config_path}; "
        f"{len(actual)} (rule, file) findings at >= {GATE_FLOOR} without config; "
        f"{len(stale)} stale"
    )
    for rule, name in stale:
        print(
            f"  STALE: {rule} is waived for {name} but zizmor no longer reports it there. "
            "Delete the waiver in the PR that fixed the workflow.",
            file=sys.stderr,
        )
    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
