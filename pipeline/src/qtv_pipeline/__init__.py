"""queer-tv-guide's snapshot pipeline.

`__version__` is read from the installed package's metadata, which comes from
`[project].version` in pyproject.toml: one source of version truth
(RELEASE-AND-VERSIONING-STANDARD §2, REL-02). There is deliberately no
fallback for an uninstalled source tree: a made-up version would be written
into every snapshot's `build.pipeline_version` and the HTTP User-Agent. Run the
pipeline through `uv run`, which installs the project first.
"""

from importlib.metadata import version

__version__ = version("qtv-pipeline")
