"""A small, dependency-free reader for this repository's workflow files.

The policy tests need a handful of facts per workflow (triggers, the
concurrency group, and per job: runner, timeout, checkout options, `run:`
bodies). Pulling in a YAML library would add an unpinned download to the one
suite that checks pinning, so this reads the files the way GitHub's own
examples lay them out: two-space indentation, one key per line. A file with
no block-style `on:` section or no jobs raises, and the policy tests assert a
minimum count of workflows and jobs, so a reformatted workflow fails loudly
instead of being read as empty.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
WORKFLOWS = REPO / ".github" / "workflows"


@dataclass
class Job:
    name: str
    lines: list[str]

    @property
    def text(self) -> str:
        return "\n".join(self.lines)

    @property
    def runs_on(self) -> str:
        match = re.search(r"^    runs-on:\s*(\S.*?)\s*$", self.text, re.M)
        return match.group(1) if match else ""

    @property
    def has_timeout(self) -> bool:
        return re.search(r"^    timeout-minutes:\s*\d+", self.text, re.M) is not None

    def run_blocks(self) -> list[str]:
        """Every `run:` body in this job, inline or block scalar."""
        blocks: list[str] = []
        lines = self.lines
        i = 0
        while i < len(lines):
            match = re.match(r"^(\s*)(?:- )?run:\s*(.*)$", lines[i])
            if not match:
                i += 1
                continue
            indent = len(match.group(1))
            inline = match.group(2).strip()
            if inline and inline[0] not in "|>":
                blocks.append(inline)
                i += 1
                continue
            body: list[str] = []
            i += 1
            while i < len(lines) and (
                not lines[i].strip() or len(lines[i]) - len(lines[i].lstrip()) > indent
            ):
                body.append(lines[i].strip())
                i += 1
            blocks.append("\n".join(body).strip())
        return blocks

    def checkout_blocks(self) -> list[str]:
        """The text of every actions/checkout step (the `uses:` line and its `with:`)."""
        blocks: list[str] = []
        for i, line in enumerate(self.lines):
            if "uses: actions/checkout@" not in line:
                continue
            indent = len(line) - len(line.lstrip())
            body = [line]
            for follow in self.lines[i + 1 :]:
                stripped = follow.lstrip()
                if follow.strip() and len(follow) - len(stripped) <= indent - 2:
                    break
                if stripped.startswith("- ") and len(follow) - len(stripped) <= indent - 2:
                    break
                body.append(follow)
            blocks.append("\n".join(body))
        return blocks


@dataclass
class Workflow:
    path: Path
    text: str
    jobs: dict[str, Job] = field(default_factory=dict)

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def triggers(self) -> set[str]:
        block = re.search(r"^on:\s*\n((?:[ \t].*\n|\s*\n)+)", self.text, re.M)
        if block is None:
            raise ValueError(f"{self.name}: no block-style `on:` section")
        return set(re.findall(r"^  ([a-z_]+):", block.group(1), re.M))

    @property
    def concurrency_group(self) -> str | None:
        match = re.search(
            r"^concurrency:\s*\n(?:[ \t]*(?:#.*)?\n)*?  group:\s*(.+?)\s*$", self.text, re.M
        )
        return match.group(1) if match else None

    @property
    def cancel_in_progress(self) -> bool | None:
        match = re.search(
            r"^concurrency:\s*\n(?:  .*\n)*?  cancel-in-progress:\s*(true|false)", self.text, re.M
        )
        return None if match is None else match.group(1) == "true"

    @property
    def has_top_level_permissions(self) -> bool:
        return re.search(r"^permissions:", self.text, re.M) is not None


def load(path: Path) -> Workflow:
    text = path.read_text()
    workflow = Workflow(path=path, text=text)
    lines = text.splitlines()
    try:
        start = lines.index("jobs:")
    except ValueError as exc:
        raise ValueError(f"{path.name}: no top-level `jobs:`") from exc
    current: Job | None = None
    for line in lines[start + 1 :]:
        if line and not line.startswith(" ") and not line.startswith("#"):
            break
        header = re.match(r"^  ([A-Za-z0-9_-]+):\s*(?:#.*)?$", line)
        if header:
            current = Job(name=header.group(1), lines=[])
            workflow.jobs[current.name] = current
            continue
        if current is not None:
            current.lines.append(line)
    if not workflow.jobs:
        raise ValueError(f"{path.name}: parsed zero jobs")
    return workflow


def load_all() -> list[Workflow]:
    paths = sorted(WORKFLOWS.glob("*.yml")) + sorted(WORKFLOWS.glob("*.yaml"))
    if not paths:
        raise ValueError(f"no workflows under {WORKFLOWS}")
    return [load(p) for p in paths]
