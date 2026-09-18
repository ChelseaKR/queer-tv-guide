"""IR-07: every postmortem carries the required sections.

The required headings are INCIDENT-RESPONSE-STANDARD §3's list. The template
must carry all of them (it is what a postmortem is copied from), and so must
every dated postmortem in docs/incidents/. There are none yet; the template
check and the negative control keep the lint honest until there are.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

INCIDENTS = Path(__file__).resolve().parents[1] / "docs" / "incidents"
REQUIRED = (
    "## Summary",
    "## Timeline (UTC)",
    "## Impact",
    "## Detection",
    "## Root cause",
    "## What went well",
    "## What went poorly",
    "## Action items",
    "## Related",
)
DATED = re.compile(r"^\d{4}-\d{2}-\d{2}-[a-z0-9-]+\.md$")


def missing_sections(text: str) -> list[str]:
    headings = {line.strip() for line in text.splitlines() if line.startswith("## ")}
    missing = [h for h in REQUIRED if h not in headings]
    if not re.search(r"^\*\*Severity:\*\*", text, re.M):
        missing.append("**Severity:**")
    if not re.search(r"^\*\*Related issue:\*\*", text, re.M):
        missing.append("**Related issue:**")
    return missing


class PostmortemTests(unittest.TestCase):
    def test_the_template_carries_every_required_section(self) -> None:
        self.assertEqual(missing_sections((INCIDENTS / "TEMPLATE.md").read_text()), [])

    def test_every_postmortem_carries_every_required_section(self) -> None:
        for path in sorted(INCIDENTS.iterdir()):
            if DATED.match(path.name):
                with self.subTest(postmortem=path.name):
                    self.assertEqual(missing_sections(path.read_text()), [])

    def test_only_dated_postmortems_and_the_two_guides_live_here(self) -> None:
        # A misnamed postmortem would be skipped by the check above.
        stray = [
            p.name
            for p in INCIDENTS.iterdir()
            if p.name not in ("README.md", "TEMPLATE.md") and not DATED.match(p.name)
        ]
        self.assertEqual(stray, [])

    def test_a_missing_section_is_caught(self) -> None:
        template = (INCIDENTS / "TEMPLATE.md").read_text()
        without = template.replace("## Root cause\n", "", 1)
        self.assertNotEqual(without, template, "sabotage did not land")
        self.assertEqual(missing_sections(without), ["## Root cause"])


if __name__ == "__main__":
    unittest.main()
