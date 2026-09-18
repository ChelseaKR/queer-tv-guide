"""Code-hygiene gates that ruff does not enforce (CODE-QUALITY-STANDARD §6).

- CQ-34: a to-do, fix-me or hack marker comment names the issue that tracks
  it, as `(#NN)` or an issue URL on the same line.
- CQ-35: a `noqa` or `type: ignore` suppression names the rule it silences
  and the issue that justifies it.

Scans every .py file under src/ and tests/. The marker words are assembled at
run time so this file does not flag itself.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ISSUE = r"(?:\(#\d+\)|https?://\S+/issues/\d+)"
MARKER = re.compile(r"\b(" + "|".join(["TO" + "DO", "FIX" + "ME", "HA" + "CK"]) + r")\b")
NOQA = re.compile(r"#\s*" + "no" + r"qa\b(?P<rest>.*)$", re.IGNORECASE)
TYPE_IGNORE = re.compile(r"#\s*type:\s*" + "ig" + r"nore(?P<rest>.*)$")


def problems(text: str, name: str) -> list[str]:
    found: list[str] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if MARKER.search(line) and not re.search(ISSUE, line):
            found.append(f"{name}:{number}: marker without an issue reference")
        noqa = NOQA.search(line)
        if noqa and not (re.match(r":\s*[A-Z]+\d+", noqa["rest"]) and re.search(ISSUE, line)):
            found.append(f"{name}:{number}: suppression without a rule code and an issue")
        ignore = TYPE_IGNORE.search(line)
        if ignore and not (re.match(r"\[[a-z-]+", ignore["rest"]) and re.search(ISSUE, line)):
            found.append(f"{name}:{number}: type suppression without an error code and an issue")
    return found


def _sources() -> list[Path]:
    files = sorted((ROOT / "src").rglob("*.py")) + sorted((ROOT / "tests").rglob("*.py"))
    return files


def test_sources_were_found() -> None:
    # Denominator: a scan of nothing must not pass.
    assert len(_sources()) >= 20


def test_no_untracked_markers_or_bare_suppressions() -> None:
    found = [p for f in _sources() for p in problems(f.read_text(), str(f.relative_to(ROOT)))]
    assert found == []


@pytest.mark.parametrize(
    ("line", "flagged"),
    [
        ("# " + "TO" + "DO: tidy this", True),
        ("# " + "TO" + "DO(#12): tidy this", False),
        ("# " + "FIX" + "ME see https://github.com/o/r/issues/4", False),
        ("x = 1  # " + "no" + "qa", True),
        ("x = 1  # " + "no" + "qa: E501", True),
        ("x = 1  # " + "no" + "qa: E501 (#7)", False),
        ("x = f()  # type: " + "ig" + "nore", True),
        ("x = f()  # type: " + "ig" + "nore[attr-defined]  (#9)", False),
        ("todo_list = []  # a variable, not a marker", False),
    ],
)
def test_the_rules_can_fail(line: str, flagged: bool) -> None:
    assert bool(problems(line, "probe.py")) is flagged
