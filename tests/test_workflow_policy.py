"""Workflow invariants that zizmor does not check.

zizmor (run by `make workflows`) owns SHA pinning, persist-credentials,
excessive permissions, template injection and dangerous triggers. This file
covers the CI-CD-STANDARD rules that are about how the gates behave rather
than how the YAML is written:

- a silenced step is not a gate (no `continue-on-error: true`, no `|| true`);
- every job has a timeout, so a hung scanner fails instead of queueing;
- a merge-gating workflow also runs on `main`, and its concurrency key gives
  every pushed commit its own group (CI-CD §11c), so no commit on `main` is
  left without a verdict;
- macOS runners stay off pull-request CI (CI-CD §11b);
- a `run:` body with a pipe sets pipefail (Actions' default shell does not);
- the job that runs gitleaks over history checks out the whole history.

A known violation that cannot be fixed yet goes in WAIVERS with the issue
that fixes it (none today). A waiver must still match a real violation: once
the workflow is fixed, test_every_waiver_is_still_needed fails until the
entry is deleted. The one sanctioned macOS pull-request job is listed in
MACOS_PR_ALLOWED with its ADR.
"""

from __future__ import annotations

import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import workflow_model

# (rule, workflow file, job or "*") -> issue that removes it. Empty today.
WAIVERS: dict[tuple[str, str, str], str] = {}

# macOS jobs allowed on pull-request CI despite CI-CD §11b, each with the ADR
# that records why. An allowed job must also be scope-gated: it `needs` a
# `changes` job and its `if:` reads that job's outputs, so a pull request that
# touches nothing it tests does not spend macOS minutes.
MACOS_PR_ALLOWED: dict[tuple[str, str], str] = {
    ("ci.yml", "guidecore"): "docs/adr/0012-guidecore-tests-on-macos-per-pr.md",
}

PIPE = re.compile(r"(?<![|])\|(?![|])")


def _workflow_violations(wf: workflow_model.Workflow) -> set[tuple[str, str, str]]:
    found: set[tuple[str, str, str]] = set()
    triggers = wf.triggers
    if re.search(r"continue-on-error:\s*true", wf.text):
        found.add(("continue-on-error", wf.name, "*"))
    if re.search(r"\|\|\s*true\b", wf.text):
        found.add(("or-true", wf.name, "*"))
    if not wf.has_top_level_permissions:
        found.add(("top-level-permissions", wf.name, "*"))
    if "pull_request" in triggers and "push" not in triggers:
        found.add(("pr-gate-skips-main", wf.name, "*"))
    ref_only = "github.sha" not in (wf.concurrency_group or "")
    if "push" in triggers and wf.cancel_in_progress is not False and ref_only:
        found.add(("ref-only-concurrency", wf.name, "*"))
    return found


def _job_violations(
    wf: workflow_model.Workflow, job: workflow_model.Job
) -> set[tuple[str, str, str]]:
    found: set[tuple[str, str, str]] = set()
    if not job.has_timeout:
        found.add(("job-timeout", wf.name, job.name))
    if "pull_request" in wf.triggers and job.runs_on.startswith("macos"):
        allowed = (wf.name, job.name) in MACOS_PR_ALLOWED
        gated = "needs: changes" in job.text and "needs.changes.outputs" in job.text
        if not (allowed and gated):
            found.add(("macos-on-pull-request", wf.name, job.name))
    bodies = job.run_blocks()
    unsafe_pipe = any(PIPE.search(b) and "pipefail" not in b for b in bodies)
    if unsafe_pipe and "shell: bash" not in job.text:
        found.add(("pipe-without-pipefail", wf.name, job.name))
    scans_history = any(re.search(r"\bmake\b[^\n]*\bsecrets\b", b) for b in bodies)
    full_clone = any("fetch-depth: 0" in c for c in job.checkout_blocks())
    if scans_history and not full_clone:
        found.add(("shallow-history-scan", wf.name, job.name))
    return found


def violations() -> set[tuple[str, str, str]]:
    found: set[tuple[str, str, str]] = set()
    for wf in workflow_model.load_all():
        found |= _workflow_violations(wf)
        for job in wf.jobs.values():
            found |= _job_violations(wf, job)
    return found


class WorkflowPolicyTests(unittest.TestCase):
    def test_workflows_were_read(self) -> None:
        workflows = workflow_model.load_all()
        jobs = sum(len(wf.jobs) for wf in workflows)
        # The denominator, stated: a reader that parsed nothing must not pass.
        self.assertGreaterEqual(len(workflows), 3, [wf.name for wf in workflows])
        self.assertGreaterEqual(jobs, 5)
        for wf in workflows:
            self.assertTrue(wf.triggers, f"{wf.name}: no triggers parsed")

    def test_no_unwaived_violations(self) -> None:
        unwaived = sorted(v for v in violations() if v not in WAIVERS)
        self.assertEqual(unwaived, [], "workflow policy violations (rule, file, job)")

    def test_every_waiver_is_still_needed(self) -> None:
        stale = sorted(w for w in WAIVERS if w not in violations())
        self.assertEqual(stale, [], "these waivers no longer match a violation; delete them")

    def test_every_macos_exception_has_its_adr(self) -> None:
        for (name, job), adr in MACOS_PR_ALLOWED.items():
            self.assertTrue(
                (workflow_model.REPO / adr).is_file(), f"{name}:{job} cites missing {adr}"
            )

    def test_the_macos_scope_gate_fails_closed(self) -> None:
        ci = workflow_model.load(workflow_model.WORKFLOWS / "ci.yml")
        text = ci.jobs["guidecore"].text
        # Runs unless `changes` succeeded AND said false; a failed or skipped
        # scope step must not skip the tests.
        self.assertIn("needs.changes.result != 'success'", text)
        self.assertIn("needs.changes.outputs.guidecore != 'false'", text)
        self.assertIn("!cancelled()", text)

    def test_security_workflow_gates_every_commit_on_main(self) -> None:
        security = workflow_model.load(workflow_model.WORKFLOWS / "security.yml")
        self.assertTrue(
            {"pull_request", "push", "schedule"} <= security.triggers, security.triggers
        )
        group = security.concurrency_group or ""
        self.assertIn("github.sha", group)
        self.assertIn("github.event_name == 'pull_request'", group)

    def test_the_rules_can_fail(self) -> None:
        # Each detector, fed workflows that break its rule, must report it;
        # otherwise the clean result above proves nothing.
        pr_only = (
            "name: probe\n"
            "on:\n"
            "  pull_request:\n"
            "jobs:\n"
            "  mac:\n"
            "    runs-on: macos-15\n"
            "    steps:\n"
            "      - uses: actions/checkout@0000000000000000000000000000000000000000 # v0\n"
            "      - run: |\n"
            "          make secrets\n"
            "          curl -s example.invalid | sh || true\n"
            "        continue-on-error: true\n"
        )
        push_ref_only = (
            "name: probe2\n"
            "on:\n"
            "  push:\n"
            "    branches: [main]\n"
            "permissions:\n"
            "  contents: read\n"
            "concurrency:\n"
            "  group: ${{ github.workflow }}-${{ github.ref }}\n"
            "  cancel-in-progress: true\n"
            "jobs:\n"
            "  ok:\n"
            "    runs-on: ubuntu-latest\n"
            "    timeout-minutes: 5\n"
            "    steps:\n"
            "      - run: make policy\n"
        )
        real = workflow_model.WORKFLOWS
        with tempfile.TemporaryDirectory() as probe_dir:
            (Path(probe_dir) / "probe.yml").write_text(pr_only)
            (Path(probe_dir) / "probe2.yml").write_text(push_ref_only)
            workflow_model.WORKFLOWS = Path(probe_dir)
            try:
                found = {v[0] for v in violations()}
            finally:
                workflow_model.WORKFLOWS = real
        self.assertEqual(
            found,
            {
                "continue-on-error",
                "or-true",
                "top-level-permissions",
                "pr-gate-skips-main",
                "ref-only-concurrency",
                "job-timeout",
                "macos-on-pull-request",
                "pipe-without-pipefail",
                "shallow-history-scan",
            },
        )


if __name__ == "__main__":
    unittest.main()
