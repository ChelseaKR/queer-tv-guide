"""How snapshot.yml publishes the website to its own repository (DECISIONS 0062).

The website is pushed to a second repository, which serves it on the domain.
This repository's Pages site becomes the small one (the data file, three
pages, pointers to the domain) only when the domain is seen to serve this
run's website. Three things must hold, and each is checked two ways here:

- the workflow text keeps the wiring (the checks in `problems`, each with a
  negative control that asserts its sabotage landed first);
- the push step's own script, run against a local repository, never removes a
  domain, never sets one by itself, and never overwrites a branch that moved;
- the wait step's own script, run against a stand-in for the domain, says
  "serving" only when the domain serves this run's data file byte for byte.

The scripts are taken from the workflow file as written, so a change to
either is what gets run.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import workflow_model

SNAPSHOT = workflow_model.WORKFLOWS / "snapshot.yml"
SHOW_PAGES = workflow_model.REPO / "pipeline" / "src" / "qtv_pipeline" / "show_pages.py"
BUILD_STEP = "build this repository's own Pages site"
PUSH_STEP = "push the website to its own Pages repository"
WAIT_STEP = "wait for the domain to serve this run's website"
UPLOAD = "      - uses: actions/upload-pages-artifact@"
ARTIFACT_PATH = (
    "          path: ${{ steps.domain-serving.outputs.serving == 'true' "
    "&& 'pipeline/site-github-io' || 'pipeline/site' }}\n"
)
SITE_REPO = "someone/website"
REMOTE = f"git@github.com:{SITE_REPO}.git"
HOST = "queerframe.app"
# Full paths, found once: the scripts are run with these, not by bare name.
BASH, GIT, SSH_KEYGEN = (shutil.which(tool) or "" for tool in ("bash", "git", "ssh-keygen"))


def step_block(text: str, name: str) -> str:
    """The text of one step: from its `- name:` line to the next step or job."""
    start = text.find(f"      - name: {name}")
    if start < 0:
        return ""
    nxt = re.search(r"^(?:      - |  [a-z-]+:\n)", text[start + 1 :], re.M)
    return text[start : start + 1 + nxt.start()] if nxt else text[start:]


def run_body(block: str) -> str:
    """The step's `run: |` script, dedented."""
    lines = block.split("        run: |\n", 1)[1].splitlines()
    return textwrap.dedent("\n".join(lines)) + "\n"


def code(block: str) -> str:
    """A step without its comment lines; a comment proves nothing."""
    return re.sub(r"(?m)^\s*#.*$", "", block)


def _steps(text: str) -> tuple[str, str, str]:
    build, push, wait = (step_block(text, n) for n in (BUILD_STEP, PUSH_STEP, WAIT_STEP))
    return build, push, wait


def _wiring_problems(text: str) -> list[str]:
    """The steps' order, conditions and what the Pages artifact is."""
    build, push, wait = _steps(text)
    found: list[str] = []
    order = [text.find(build), text.find(push), text.find(wait), text.find(UPLOAD)]
    if order != sorted(order) or -1 in order:
        found.append("the steps are not in order: build, push, wait, upload")
    if ARTIFACT_PATH not in text:
        found.append("the Pages artifact is not chosen by what the domain was seen to serve")
    if text.count("actions/upload-pages-artifact@") != 1:
        found.append("more than one Pages artifact")
    if "python -m qtv_pipeline.github_io site site-github-io" not in code(build):
        found.append("the small site is not built by qtv_pipeline.github_io")
    if re.search(r"(?m)^\s+if:", code(build)):
        found.append("the small site is not built on every run")
    if "        if: vars.DOMAIN_SITE_REPO != ''\n" not in push:
        found.append("the push does not wait for DOMAIN_SITE_REPO")
    if "        if: steps.domain-site.outputs.cname == 'present'\n" not in wait:
        found.append("the wait does not depend on the branch holding the domain")
    return found


def _push_problems(text: str) -> list[str]:
    """The push step: one secret, a pinned host, a lease, the branch's CNAME."""
    _, push, wait = _steps(text)
    found: list[str] = []
    if code(text).count("secrets.") != 1 or "${{ secrets.DOMAIN_SITE_DEPLOY_KEY }}" not in push:
        found.append("a secret is read outside the push step's env")
    script = code(run_body(push))
    if "${{" in script or "${{" in code(run_body(wait)):
        found.append("an expression is interpolated into a script")
    if "StrictHostKeyChecking=yes" not in script or "UserKnownHostsFile=" not in script:
        found.append("the push does not pin github.com's host key")
    if '--force-with-lease="gh-pages:${tip}"' not in script:
        found.append("the push can overwrite a branch that moved")
    if re.search(r"--force(?!-with-lease)", script) or re.search(r"push[^\n]* -f\b", script):
        found.append("the push is forced without a lease")
    if "FETCH_HEAD:CNAME" not in script:
        found.append("the CNAME file on the branch is not read")
    return found


def _wait_problems(text: str) -> list[str]:
    """The wait step: https only, no redirect, and it cannot fail the job."""
    waiting = code(run_body(_steps(text)[2]))
    found: list[str] = []
    curls = [ln for ln in waiting.splitlines() if "curl" in ln]
    if len(curls) != 2 or not all("--proto '=https'" in c and "-fsS " in c for c in curls):
        found.append("the wait does not read the checksum and the data file over https only")
    if any(re.search(r"\s-[A-Za-z]*L|--location", c) for c in curls):
        found.append("the wait follows a redirect")
    if "exit 1" in waiting:
        found.append("the wait can fail the build job, which would stop the data file")
    return found


def _job_problems(text: str) -> list[str]:
    """The jobs: the build reports, the deploy waits on the build only, and
    domain-site turns the run red after the deploy."""
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / "snapshot.yml"
        copy.write_text(text, encoding="utf-8")
        jobs = {name: job.text + "\n" for name, job in workflow_model.load(copy).jobs.items()}
    found: list[str] = []
    if "domain_serving: ${{ steps.domain-serving.outputs.serving }}" not in jobs["build"]:
        found.append("the build job does not report what the domain served")
    red = jobs.get("domain-site")
    if red is None:
        found.append("the domain-site job is missing")
    else:
        if "    needs: [build, deploy]\n" not in red:
            found.append("domain-site does not run after the deploy")
        if "    if: needs.build.outputs.domain_serving == 'false'\n" not in red:
            found.append("domain-site does not depend on what the domain served")
        if "    permissions: {}\n" not in red or "exit 1" not in red:
            found.append("domain-site is not a bare failing job")
    if "    needs: build\n" not in jobs["deploy"] or re.search(r"(?m)^    if:", jobs["deploy"]):
        found.append("the deploy waits on more than the build")
    return found


def problems(text: str) -> list[str]:
    """What is wrong with how the workflow publishes the two sites."""
    missing = [
        f"the step is missing: {name}"
        for name in (BUILD_STEP, PUSH_STEP, WAIT_STEP)
        if not step_block(text, name)
    ]
    if missing:
        return missing
    return [
        *_wiring_problems(text),
        *_push_problems(text),
        *_wait_problems(text),
        *_job_problems(text),
    ]


class WiringTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = SNAPSHOT.read_text(encoding="utf-8")

    def test_the_two_sites_are_wired_correctly(self) -> None:
        self.assertEqual(problems(self.text), [])

    def test_the_workflow_and_the_generator_name_the_same_address(self) -> None:
        workflow = re.search(r"(?m)^  SITE_URL: (\S+)$", self.text)
        generator = re.search(r'(?m)^DEFAULT_BASE_URL = "([^"]+)"$', SHOW_PAGES.read_text())
        self.assertIsNotNone(workflow)
        self.assertIsNotNone(generator)
        self.assertEqual(workflow.group(1), generator.group(1))
        self.assertEqual(workflow.group(1), f"https://{HOST}")

    def test_every_action_is_still_pinned_to_a_sha(self) -> None:
        for line in self.text.splitlines():
            match = re.match(r"\s*(?:- )?uses:\s*(\S+)", line)
            if match:
                self.assertRegex(match.group(1), r"@[0-9a-f]{40}$", line)


class WiringNegativeControlTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = SNAPSHOT.read_text(encoding="utf-8")
        self.assertEqual(problems(self.text), [])

    def _sabotage(self, old: str, new: str) -> list[str]:
        sabotaged = self.text.replace(old, new, 1)
        self.assertNotEqual(sabotaged, self.text, "the sabotage did not land")
        return problems(sabotaged)

    def _caught(self, old: str, new: str, want: str) -> None:
        found = self._sabotage(old, new)
        self.assertTrue(any(want in p for p in found), found)

    def test_an_unconditional_small_site_is_caught(self) -> None:
        self._caught(ARTIFACT_PATH, "          path: pipeline/site-github-io\n", "not chosen by")

    def test_a_push_that_does_not_wait_for_the_variable_is_caught(self) -> None:
        self._caught("        if: vars.DOMAIN_SITE_REPO != ''\n", "", "DOMAIN_SITE_REPO")

    def test_a_wait_on_every_run_is_caught(self) -> None:
        self._caught("        if: steps.domain-site.outputs.cname == 'present'\n", "", "the wait")

    def test_a_plain_force_push_is_caught(self) -> None:
        self._caught('--force-with-lease="gh-pages:${tip}"', "--force", "branch that moved")

    def test_a_second_secret_is_caught(self) -> None:
        self._caught(
            "          DOMAIN_SITE_REPO: ${{ vars.DOMAIN_SITE_REPO }}\n",
            "          DOMAIN_SITE_REPO: ${{ secrets.DOMAIN_SITE_REPO }}\n",
            "a secret is read",
        )

    def test_an_unpinned_host_is_caught(self) -> None:
        self._caught("StrictHostKeyChecking=yes", "StrictHostKeyChecking=no", "host key")

    def test_a_wait_that_follows_redirects_is_caught(self) -> None:
        self._caught(
            "curl -fsS --proto '=https' --max-time 20", "curl -fsSL --max-time 20", "https only"
        )

    def test_a_wait_that_can_fail_the_build_is_caught(self) -> None:
        self._caught(
            '          echo "serving=${serving}" >> "$GITHUB_OUTPUT"\n',
            '          echo "serving=${serving}" >> "$GITHUB_OUTPUT"\n'
            '          if [ "$serving" = "false" ]; then exit 1; fi\n',
            "stop the data file",
        )

    def test_a_deploy_that_waits_on_the_domain_is_caught(self) -> None:
        self._caught(
            "  deploy:\n    needs: build\n",
            "  deploy:\n    needs: [build, domain-site]\n",
            "deploy",
        )

    def test_a_missing_red_job_is_caught(self) -> None:
        self._caught("  domain-site:\n", "  something-else:\n", "domain-site job is missing")

    def test_a_missing_step_is_caught(self) -> None:
        self.assertEqual(
            self._sabotage(f"- name: {WAIT_STEP}", "- name: something else"),
            [f"the step is missing: {WAIT_STEP}"],
        )


def _git(*args: str, cwd: Path | None = None, env: dict[str, str] | None = None) -> str:
    proc = subprocess.run(
        [GIT, *args], cwd=cwd, env=env, capture_output=True, text=True, check=True
    )
    return proc.stdout.strip()


@unittest.skipUnless(
    all(shutil.which(tool) for tool in ("bash", "git", "ssh-agent", "ssh-add", "ssh-keygen")),
    "needs bash, git and the OpenSSH tools",
)
class PushScriptTests(unittest.TestCase):
    """The push step's script, run against a local repository that stands in
    for the website's repository. git is told to read the GitHub address from
    a local path; the key is made for the test and never leaves its folder."""

    def setUp(self) -> None:
        # ssh-agent keeps its socket under HOME, and a Unix socket path is at
        # most 104 bytes on macOS, where the default temporary folder is long.
        base = Path(tempfile.gettempdir())
        if len(str(base)) > 40:
            base = Path(os.sep, "tmp")
        self.tmp = Path(tempfile.mkdtemp(dir=base))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.script = run_body(step_block(SNAPSHOT.read_text(encoding="utf-8"), PUSH_STEP))
        self.bare = self.tmp / "website.git"
        self.env = {
            "PATH": os.environ["PATH"],
            "HOME": str(self.tmp / "h"),
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": f"url.{self.bare}.insteadOf",
            "GIT_CONFIG_VALUE_0": REMOTE,
        }
        (self.tmp / "h").mkdir()
        _git("init", "-q", "--bare", "-b", "gh-pages", str(self.bare), env=self.env)
        key = self.tmp / "key"
        subprocess.run(
            [SSH_KEYGEN, "-q", "-t", "ed25519", "-N", "", "-C", "test", "-f", str(key)],
            check=True,
            capture_output=True,
        )
        self.key = key.read_text(encoding="utf-8")
        self.checkout = self.tmp / "checkout"
        site = self.checkout / "pipeline" / "site"
        (site / "shows").mkdir(parents=True)
        (site / "index.html").write_text("home 1\n", encoding="utf-8")
        (site / "shows" / "index.html").write_text("shows\n", encoding="utf-8")
        (site / "snapshot.v1.json").write_text("{}\n", encoding="utf-8")
        (site / "snapshot.v1.json.sha256").write_text("0  snapshot.v1.json\n", encoding="utf-8")
        self.runs = 0

    def push(self, **overrides: str) -> tuple[subprocess.CompletedProcess[str], str]:
        """Run the step once; returns the process and what it wrote to GITHUB_OUTPUT."""
        self.runs += 1
        temp = self.tmp / f"runner-{self.runs}"
        temp.mkdir()
        output = temp / "output"
        output.touch()
        env = {
            **self.env,
            "RUNNER_TEMP": str(temp),
            "GITHUB_OUTPUT": str(output),
            "GITHUB_REPOSITORY": "someone/data",
            "GITHUB_RUN_ID": str(self.runs),
            "SITE_URL": f"https://{HOST}",
            "DOMAIN_SITE_REPO": SITE_REPO,
            "DOMAIN_SITE_LIVE": "",
            "DOMAIN_SITE_DEPLOY_KEY": self.key,
            **overrides,
        }
        proc = subprocess.run(
            [BASH, "-c", self.script],
            cwd=self.checkout,
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        return proc, output.read_text(encoding="utf-8")

    def branch_files(self) -> dict[str, str]:
        names = _git("ls-tree", "-r", "--name-only", "gh-pages", cwd=self.bare, env=self.env)
        return {
            name: _git("show", f"gh-pages:{name}", cwd=self.bare, env=self.env)
            for name in names.splitlines()
        }

    def settings_save_the_domain(self, host: str = HOST) -> None:
        """What the Pages settings do when the owner saves a custom domain: a
        commit on the branch that adds a CNAME file."""
        clone = self.tmp / f"settings-{self.runs}-{host}"
        _git("clone", "-q", str(self.bare), str(clone), env=self.env)
        (clone / "CNAME").write_text(host + "\n", encoding="utf-8")
        _git("add", "CNAME", cwd=clone, env=self.env)
        _git(
            *("-c", "user.name=settings", "-c", "user.email=settings@example.invalid"),
            *("commit", "-q", "-m", "Create CNAME"),
            cwd=clone,
            env=self.env,
        )
        _git("push", "-q", "origin", "gh-pages", cwd=clone, env=self.env)

    def test_the_first_push_carries_the_website_and_sets_no_domain(self) -> None:
        proc, output = self.push()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(output, "cname=absent\n")
        files = self.branch_files()
        data = ["snapshot.v1.json", "snapshot.v1.json.sha256"]
        self.assertEqual(sorted(files), [".nojekyll", "index.html", "shows/index.html", *data])
        self.assertEqual(files["index.html"], "home 1")
        self.assertEqual(_git("rev-list", "--count", "gh-pages", cwd=self.bare, env=self.env), "1")

    def test_a_later_push_replaces_the_branch_with_one_commit(self) -> None:
        self.push()
        (self.checkout / "pipeline" / "site" / "index.html").write_text("home 2\n")
        (self.checkout / "pipeline" / "site" / "shows" / "index.html").unlink()
        proc, output = self.push()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(output, "cname=absent\n")
        files = self.branch_files()
        self.assertEqual(files["index.html"], "home 2")
        self.assertNotIn("shows/index.html", files)
        self.assertEqual(_git("rev-list", "--count", "gh-pages", cwd=self.bare, env=self.env), "1")

    def test_a_domain_saved_in_the_settings_is_kept(self) -> None:
        self.push()
        self.settings_save_the_domain()
        for _ in range(2):  # and kept again on the run after
            proc, output = self.push()
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(output, "cname=present\n")
            self.assertEqual(self.branch_files()["CNAME"], HOST)

    def test_the_owner_switch_sets_the_domain_on_an_empty_repository(self) -> None:
        proc, output = self.push(DOMAIN_SITE_LIVE="true")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(output, "cname=present\n")
        self.assertEqual(self.branch_files()["CNAME"], HOST)

    def test_the_switch_off_does_not_remove_a_saved_domain(self) -> None:
        self.push()
        self.settings_save_the_domain()
        proc, output = self.push(DOMAIN_SITE_LIVE="false")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(output, "cname=present\n")
        self.assertEqual(self.branch_files()["CNAME"], HOST)

    def test_another_domain_on_the_branch_stops_the_push(self) -> None:
        self.push()
        self.settings_save_the_domain("example.com")
        before = _git("rev-parse", "gh-pages", cwd=self.bare, env=self.env)
        proc, output = self.push()
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertIn("does not name queerframe.app", proc.stdout)
        self.assertEqual(output, "")
        self.assertEqual(_git("rev-parse", "gh-pages", cwd=self.bare, env=self.env), before)

    def test_a_branch_that_moved_during_the_run_is_not_overwritten(self) -> None:
        self.push()
        # The domain is saved after the step read the branch and before it
        # pushed: the read is replaced by one that also moves the branch.
        hook = self.tmp / "hook.sh"
        clone = self.tmp / "racing-clone"
        hook.write_text(
            "#!/bin/bash\nset -euo pipefail\n"
            f'git clone -q "{self.bare}" "{clone}"\n'
            f'echo {HOST} > "{clone}/CNAME"\n'
            f'git -C "{clone}" add CNAME\n'
            f'git -C "{clone}" -c user.name=s -c user.email=s@example.invalid '
            "commit -q -m 'Create CNAME'\n"
            f'git -C "{clone}" push -q origin gh-pages\n',
            encoding="utf-8",
        )
        hook.chmod(0o755)
        read = 'git -C "$work" fetch -q --depth 1 "$remote" gh-pages\n'
        self.assertIn(read, self.script)
        self.script = self.script.replace(read, read + f'  "{hook}"\n', 1)
        proc, output = self.push()
        saved = _git("rev-parse", "gh-pages", cwd=self.bare, env=self.env)
        self.assertNotEqual(proc.returncode, 0, proc.stdout)
        self.assertEqual(output, "")
        self.assertEqual(self.branch_files()["CNAME"], HOST)  # the saved domain survived
        self.assertEqual(_git("rev-list", "--count", saved, cwd=self.bare, env=self.env), "2")

    def test_bad_settings_stop_the_step_before_anything_is_pushed(self) -> None:
        cases = {
            "must name the website's repository": {"DOMAIN_SITE_REPO": "not a repository"},
            "a different repository": {"DOMAIN_SITE_REPO": "someone/data"},
            "neither 'true' nor 'false'": {"DOMAIN_SITE_LIVE": "yes"},
            "DOMAIN_SITE_DEPLOY_KEY secret is required": {"DOMAIN_SITE_DEPLOY_KEY": ""},
        }
        for message, overrides in cases.items():
            with self.subTest(message):
                proc, output = self.push(**overrides)
                self.assertEqual(proc.returncode, 1, proc.stderr)
                self.assertIn(message, proc.stdout)
                self.assertEqual(output, "")
        self.assertEqual(_git("for-each-ref", cwd=self.bare, env=self.env), "")

    def test_the_key_is_never_printed_or_written(self) -> None:
        proc, _ = self.push()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        secret = self.key.splitlines()[1]
        self.assertNotIn(secret, proc.stdout + proc.stderr)
        for path in (self.tmp / "runner-1").rglob("*"):
            if path.is_file() and ".git" not in path.parts:
                self.assertNotIn(secret, path.read_text(encoding="utf-8", errors="replace"), path)


@unittest.skipUnless(shutil.which("bash"), "needs bash")
class WaitScriptTests(unittest.TestCase):
    """The wait step's script, run with a stand-in for curl that serves files
    from a folder as if it were the domain, and no real sleeping."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.script = run_body(step_block(SNAPSHOT.read_text(encoding="utf-8"), WAIT_STEP))
        self.domain = self.tmp / "domain"
        self.domain.mkdir()
        self.checkout = self.tmp / "checkout"
        site = self.checkout / "pipeline" / "site"
        site.mkdir(parents=True)
        self.data = b'{"generated_at": "this run"}\n'
        (site / "snapshot.v1.json").write_bytes(self.data)
        bindir = self.tmp / "bin"
        bindir.mkdir()
        self.calls = self.tmp / "curl-calls"
        self.calls.touch()
        (bindir / "curl").write_text(
            "#!/bin/bash\n"
            'for arg in "$@"; do url="$arg"; done\n'
            f'echo "$*" >> "{self.calls}"\n'
            f'case "$url" in https://{HOST}/*) ;; *) exit 7 ;; esac\n'
            f'path="${{url#https://{HOST}/}}"\n'
            f'file="{self.domain}/${{path%%\\?*}}"\n'
            'if [ -f "$file" ]; then cat "$file"; else exit 22; fi\n',
            encoding="utf-8",
        )
        (bindir / "sleep").write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
        if not shutil.which("sha256sum"):  # macOS: the runner image has it
            (bindir / "sha256sum").write_text(
                '#!/bin/bash\nexec shasum -a 256 "$@"\n', encoding="utf-8"
            )
        for tool in bindir.iterdir():
            tool.chmod(0o755)
        self.path = f"{bindir}{os.pathsep}{os.environ['PATH']}"

    def serve(self, data: bytes, *, listed: bytes | None = None) -> None:
        (self.domain / "snapshot.v1.json").write_bytes(data)
        digest = hashlib.sha256(data if listed is None else listed).hexdigest()
        (self.domain / "snapshot.v1.json.sha256").write_text(f"{digest}  snapshot.v1.json\n")

    def wait(self) -> tuple[subprocess.CompletedProcess[str], str]:
        output = self.tmp / "output"
        output.write_text("")
        proc = subprocess.run(
            [BASH, "-c", self.script],
            cwd=self.checkout,
            env={
                "PATH": self.path,
                "GITHUB_OUTPUT": str(output),
                "GITHUB_RUN_ID": "77",
                "SITE_URL": f"https://{HOST}",
            },
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        return proc, output.read_text(encoding="utf-8")

    def test_the_domain_serving_this_runs_file_is_serving(self) -> None:
        self.serve(self.data)
        proc, output = self.wait()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(output, "serving=true\n")
        self.assertEqual(len(self.calls.read_text().splitlines()), 2)  # first try

    def test_the_previous_deploy_is_not_serving(self) -> None:
        self.serve(b'{"generated_at": "the run before"}\n')
        proc, output = self.wait()
        self.assertEqual(proc.returncode, 0, proc.stderr)  # never fails the build job
        self.assertEqual(output, "serving=false\n")
        self.assertIn("::error::", proc.stdout)
        self.assertEqual(len(self.calls.read_text().splitlines()), 44)  # every try, checksum only

    def test_a_matching_checksum_over_other_bytes_is_not_serving(self) -> None:
        self.serve(b'{"generated_at": "the run before"}\n', listed=self.data)
        proc, output = self.wait()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(output, "serving=false\n")
        self.assertEqual(len(self.calls.read_text().splitlines()), 88)

    def test_a_domain_that_does_not_answer_is_not_serving(self) -> None:
        proc, output = self.wait()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(output, "serving=false\n")

    def test_every_request_is_https_only_to_the_domain_and_never_cached(self) -> None:
        self.serve(self.data)
        self.wait()
        calls = self.calls.read_text().splitlines()
        self.assertEqual(len(calls), 2)
        for call in calls:
            self.assertIn("--proto =https", call)
            self.assertRegex(call, rf"https://{re.escape(HOST)}/snapshot\.v1\.json\S*\?run=77-1$")
            self.assertNotRegex(call, r"(^|\s)-[A-Za-z]*L")


if __name__ == "__main__":
    unittest.main()
