"""Validate the hand-kept store sales ledger, docs/metrics/store-sales.csv.

The app has no telemetry, so the ledger is the only record of sales. A bad row
would be worse than a missing one, so the check refuses: a wrong header, an
unknown store or source, a unit count that is not a whole number, a month that
has not ended when it was recorded, a duplicate month and store, and rows out
of order. A month with no row means "not recorded"; the check never fills one.

Usage:
    check_metrics.py [FILE]
"""

from __future__ import annotations

import csv
import re
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LEDGER = REPO / "docs" / "metrics" / "store-sales.csv"

HEADER = ["month", "store", "units", "source", "recorded_on"]
STORES = ["app-store", "google-play"]
SOURCES = {
    "app-store": "App Store Connect sales report",
    "google-play": "Play Console statistics",
}
_MONTH = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")
_UNITS = re.compile(r"^(0|[1-9]\d*)$")


def _month_end_exclusive(year: int, month: int) -> date:
    return date(year + (month == 12), month % 12 + 1, 1)


def _row_problems(row: list[str]) -> list[str]:
    """Problems within one row, judged on its own."""
    if len(row) != len(HEADER):
        return [f"expected {len(HEADER)} columns, found {len(row)}"]
    month, store, units, source, recorded = row
    problems: list[str] = []
    found = _MONTH.match(month)
    if not found:
        problems.append(f"month {month!r} is not YYYY-MM")
    if store not in STORES:
        problems.append(f"store {store!r} is not one of {STORES}")
    elif source != SOURCES[store]:
        problems.append(f"source for {store} must be {SOURCES[store]!r}")
    if not _UNITS.match(units):
        problems.append(f"units {units!r} is not a whole number")
    try:
        recorded_on = date.fromisoformat(recorded)
    except ValueError:
        problems.append(f"recorded_on {recorded!r} is not YYYY-MM-DD")
        return problems
    if found and recorded_on < _month_end_exclusive(int(found[1]), int(found[2])):
        problems.append(f"{month} had not ended on {recorded}")
    return problems


def check(text: str) -> list[str]:
    """Every problem in the ledger text; an empty list means it is valid."""
    rows = list(csv.reader(text.splitlines()))
    if not rows or rows[0] != HEADER:
        return [f"header must be exactly {','.join(HEADER)}"]
    problems: list[str] = []
    seen: set[tuple[str, str]] = set()
    previous: tuple[str, int] | None = None
    for number, row in enumerate(rows[1:], start=2):
        own = _row_problems(row)
        problems.extend(f"line {number}: {p}" for p in own)
        if len(row) != len(HEADER):
            continue
        month, store = row[0], row[1]
        if (month, store) in seen:
            problems.append(f"line {number}: {month} {store} appears twice")
        seen.add((month, store))
        if store in STORES:
            key = (month, STORES.index(store))
            if previous is not None and key < previous:
                problems.append(f"line {number}: rows must be in month order, then store order")
            previous = key
    return problems


def main(argv: list[str]) -> int:
    path = Path(argv[1]) if len(argv) > 1 else LEDGER
    problems = check(path.read_text(encoding="utf-8"))
    for problem in problems:
        print(f"{path.name}: {problem}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
