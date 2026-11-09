"""How snapshot.yml runs the Wikidata step (DECISIONS 0055).

It must sit between the fetch and the build, so a read reaches that night's
snapshot and the repacked mirror, and it must not be able to stop the run. The
workflow policy forbids silencing a step, so the command itself exits 0 (tested in
pipeline/tests/test_wikidata.py). Every negative control asserts its sabotage
changed the text before it asserts the check caught it.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import workflow_model

SNAPSHOT = workflow_model.WORKFLOWS / "snapshot.yml"
STEP = "      - name: refresh the Wikidata titles and seasons"
FETCH = "      - name: fetch (network;"
BUILD = "      - name: build (offline;"
REPACK = "      - name: repack mirror cache"
FORBIDDEN = {
    r"continue-on-error": "silenced with continue-on-error",
    r"\|\|": "silenced with ||",
    r"set \+e": "silenced with set +e",
    r"(?m)^\s+if:": "conditional: it would silently not run",
    r"secrets\.|GH_TOKEN|github\.token": "it needs no token",
}


def step_block(text: str) -> str:
    start = text.find(STEP)
    if start < 0:
        return ""
    nxt = re.search(r"^      - ", text[start + 1 :], re.M)
    return text[start : start + 1 + nxt.start()] if nxt else text[start:]


def problems(text: str) -> list[str]:
    whole = step_block(text)
    if not whole:
        return ["the Wikidata step is missing"]
    found: list[str] = []
    block = re.sub(r"(?m)^\s*#.*$", "", whole)
    if "uv run qtv wikidata --cache .cache" not in block:
        found.append("does not run qtv wikidata on the mirror cache")
    found += [why for needle, why in FORBIDDEN.items() if re.search(needle, block)]
    order = [text.find(FETCH), text.find(STEP), text.find(BUILD), text.find(REPACK)]
    if -1 in order or order != sorted(order):
        found.append("not between the fetch and the build, before the mirror is repacked")
    return found


class WikidataWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = SNAPSHOT.read_text(encoding="utf-8")

    def test_the_real_workflow_is_clean(self) -> None:
        self.assertEqual(problems(self.text), [])

    def test_the_fetch_step_does_not_read_wikidata(self) -> None:
        start = self.text.find(FETCH)
        self.assertGreater(start, 0)
        block = self.text[start : self.text.find(STEP)]
        self.assertIn("uv run qtv fetch", block)
        self.assertNotIn("wikidata", block.lower())

    def test_a_silenced_step_is_caught(self) -> None:
        run = "run: uv run qtv wikidata --cache .cache"
        broken = self.text.replace(run, run + " || echo failed")
        self.assertNotEqual(broken, self.text)
        self.assertIn("silenced with ||", problems(broken))

    def test_a_missing_step_is_caught(self) -> None:
        broken = self.text.replace(STEP, "      - name: something else")
        self.assertNotEqual(broken, self.text)
        self.assertEqual(problems(broken), ["the Wikidata step is missing"])

    def test_a_step_after_the_build_is_caught(self) -> None:
        block = step_block(self.text)
        broken = self.text.replace(block, "").replace(REPACK, block + REPACK)
        self.assertNotEqual(broken, self.text)
        self.assertIn(
            "not between the fetch and the build, before the mirror is repacked", problems(broken)
        )


if __name__ == "__main__":
    unittest.main()
