"""REL-02: the pipeline's version lives in one place.

`[project].version` in pyproject.toml is the source. The package's
`__version__`, the User-Agent every request sends, and each snapshot's
`build.pipeline_version` all derive from it, and no source file repeats the
number by hand.
"""

from __future__ import annotations

import re
import tomllib
from importlib.metadata import version
from pathlib import Path

import qtv_pipeline
from qtv_pipeline import http

PIPELINE = Path(__file__).resolve().parents[1]


def _declared() -> str:
    data = tomllib.loads((PIPELINE / "pyproject.toml").read_text())
    return str(data["project"]["version"])


def hand_copied_versions(root: Path, declared: str) -> list[str]:
    """Source lines that spell the declared version as a string literal."""
    literal = re.compile(r"""["']""" + re.escape(declared) + r"""["']""")
    return [
        f"{path.relative_to(root)}:{number}"
        for path in sorted(root.rglob("*.py"))
        for number, line in enumerate(path.read_text().splitlines(), start=1)
        if literal.search(line)
    ]


def test_version_derives_from_pyproject() -> None:
    declared = _declared()
    assert re.fullmatch(r"\d+\.\d+\.\d+", declared)
    assert version("qtv-pipeline") == declared
    assert qtv_pipeline.__version__ == declared
    assert http.USER_AGENT.startswith(f"queer-tv-guide-pipeline/{declared} ")


def test_no_source_file_repeats_the_version() -> None:
    assert hand_copied_versions(PIPELINE / "src", _declared()) == []


def test_a_hand_copied_version_is_caught(tmp_path: Path) -> None:
    (tmp_path / "mod.py").write_text('__version__ = "9.8.7"\n')
    assert hand_copied_versions(tmp_path, "9.8.7") == ["mod.py:1"]
    assert hand_copied_versions(tmp_path, "9.8.8") == []
