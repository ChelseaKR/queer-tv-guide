"""How snapshot.yml publishes the show pages (DECISIONS 0020).

The step is an extra beside the snapshot. It must not be able to stop the
snapshot from publishing, and the workflow policy forbids the usual tool for
that (`continue-on-error`, `|| true`), so the generator itself exits 0 with a
`::notice::` on any problem (`--notice-on-failure`, tested in
pipeline/tests/test_show_pages_publish.py). This file holds the workflow to
that: the step has the flag, no silencing, runs before the index and the
upload, reads the same APP_STORE_LIVE value, and leaves the rest alone.

Every negative control asserts its sabotage changed the text before it
asserts the check caught it.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import workflow_model

SNAPSHOT = workflow_model.WORKFLOWS / "snapshot.yml"
STEP_NAME = "build the per-show pages into the Pages site"


def step_block(text: str) -> str:
    """The text of the show-pages step: from its `- name:` line to the next step."""
    start = text.find(f"      - name: {STEP_NAME}")
    if start < 0:
        return ""
    nxt = re.search(r"^      - ", text[start + 1 :], re.M)
    return text[start : start + 1 + nxt.start()] if nxt else text[start:]


REQUIRED = {
    "--notice-on-failure": "no --notice-on-failure: a generator failure would fail the workflow",
    "APP_STORE_LIVE: ${{ vars.APP_STORE_LIVE }}": "does not read the APP_STORE_LIVE variable",
    '--app-store-live "$APP_STORE_LIVE"': "does not pass APP_STORE_LIVE to the generator",
}
FORBIDDEN = {
    r"continue-on-error": "silenced with continue-on-error",
    r"\|\|": "silenced with ||",
    r"set \+e": "silenced with set +e",
    r";\s*true\b": "silenced with ; true",
    r"(?m)^\s+if:": "conditional: the pages would silently not build",
    r"--base-url": "sets --base-url: the domain is the generator's default",
}


def problems(text: str) -> list[str]:
    """What is wrong with how the workflow wires in the show pages."""
    whole = step_block(text)
    if not whole:
        return ["the show-pages step is missing"]
    block = re.sub(r"(?m)^\s*#.*$", "", whole)  # comments prove nothing
    found = [why for needle, why in REQUIRED.items() if needle not in block]
    found += [why for pattern, why in FORBIDDEN.items() if re.search(pattern, block)]
    if "${{" in re.sub(r"(?m)^\s*APP_STORE_LIVE: .*$", "", block):
        found.append("interpolates an expression into the script")
    if (
        not text.find(whole)
        < text.find("qtv_pipeline.site_index")
        < text.find("upload-pages-artifact")
    ):
        found.append("not before the index is written and the Pages artifact uploaded")
    return found


class ShowPagesStepTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = SNAPSHOT.read_text(encoding="utf-8")

    def test_the_step_is_wired_correctly(self) -> None:
        self.assertEqual(problems(self.text), [])

    def test_the_step_is_in_the_build_job_before_the_artifact_upload(self) -> None:
        build = workflow_model.load(SNAPSHOT).jobs["build"]
        self.assertIn(STEP_NAME, build.text)
        self.assertLess(build.text.index(STEP_NAME), build.text.index("upload-pages-artifact"))

    def test_the_snapshot_publishing_is_untouched(self) -> None:
        # The artifact is still the one directory the snapshot files go in, and
        # the deploy still waits on the build and on nothing else.
        self.assertIn("          path: pipeline/site\n", self.text)
        self.assertEqual(self.text.count("actions/upload-pages-artifact@"), 1)
        deploy = workflow_model.load(SNAPSHOT).jobs["deploy"]
        self.assertIn("needs: build", deploy.text)
        for kept in (
            "cp out/snapshot.v1.json site/",
            "cp out/snapshot.v1.json.sha256 site/",
            "qtv_pipeline.site_index out/snapshot.v1.json site/index.html",
            'qtv_pipeline.app_store site "$APP_STORE_LIVE"',
            'qtv_pipeline.play_store site "$PLAY_STORE_LIVE"',
            "gh release upload",
        ):
            self.assertIn(kept, self.text)
        self.assertEqual(re.findall(r'-\s*cron:\s*"([^"]+)"', self.text), ["17 9 * * *"])

    def test_every_action_is_still_pinned_to_a_sha(self) -> None:
        for line in self.text.splitlines():
            match = re.match(r"\s*(?:- )?uses:\s*(\S+)", line)
            if match:
                self.assertRegex(match.group(1), r"@[0-9a-f]{40}$", line)


class NegativeControlTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = SNAPSHOT.read_text(encoding="utf-8")
        self.assertEqual(problems(self.text), [])

    def _sabotage(self, old: str, new: str) -> list[str]:
        sabotaged = self.text.replace(old, new, 1)
        self.assertNotEqual(sabotaged, self.text, "the sabotage did not land")
        return problems(sabotaged)

    def test_a_step_without_the_flag_would_fail_the_workflow(self) -> None:
        found = self._sabotage('"$APP_STORE_LIVE" --notice-on-failure', '"$APP_STORE_LIVE"')
        self.assertTrue(any("--notice-on-failure" in p for p in found), found)

    def test_continue_on_error_is_caught(self) -> None:
        found = self._sabotage(
            f"      - name: {STEP_NAME} (never blocks the deploy)\n",
            f"      - name: {STEP_NAME} (never blocks the deploy)\n        continue-on-error: true\n",
        )
        self.assertTrue(any("continue-on-error" in p for p in found), found)

    def test_or_true_is_caught(self) -> None:
        found = self._sabotage(
            "--notice-on-failure\n        env:", "--notice-on-failure || true\n        env:"
        )
        self.assertTrue(any("silenced" in p for p in found), found)

    def test_a_step_after_the_index_is_caught(self) -> None:
        block = step_block(self.text)
        moved = self.text.replace(block, "", 1).replace(
            "      - uses: actions/upload-pages-artifact",
            block + "      - uses: actions/upload-pages-artifact",
            1,
        )
        self.assertNotEqual(moved, self.text, "the sabotage did not land")
        self.assertTrue(any("before the index" in p for p in problems(moved)))

    def test_a_missing_step_is_caught(self) -> None:
        self.assertEqual(
            problems(self.text.replace(f"- name: {STEP_NAME}", "- name: something else", 1)),
            ["the show-pages step is missing"],
        )

    def test_a_different_app_store_value_is_caught(self) -> None:
        found = self._sabotage('--app-store-live "$APP_STORE_LIVE"', "--app-store-live true")
        self.assertTrue(any("pass APP_STORE_LIVE" in p for p in found), found)


if __name__ == "__main__":
    unittest.main()
