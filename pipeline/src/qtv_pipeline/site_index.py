"""The site's home page and its data page (DECISIONS 0026).

    python -m qtv_pipeline.site_index out/snapshot.v1.json site/index.html

writes two pages next to the snapshot files:

- ``index.html``, the home page: what Queer Frame is, how the answer stays
  closed, the privacy and data-source lines, links into the show pages, and
  one line saying the iPhone app is coming soon. That line is
  ``app_store.INDEX_SLOT``; with APP_STORE_LIVE on, ``app_store.apply``
  replaces it with the App Store badge, so this module never links to the
  App Store itself.
- ``data/index.html``, the page that describes the published data file:
  its CC BY-SA 4.0 license, the files, and this build's counts. A file
  published for anyone to take carries its license and credits where people
  find it, not only inside the JSON. The data files themselves keep their
  URLs at the site root (the app fetches ``snapshot.v1.json`` there).

Both pages carry the same footer as the show pages: the license, every
source credit with links, and the privacy, support and data links.

The spoiler rule holds on the home page as on every other: it names show
titles and nothing about any character's death, in the body, the title, the
description or the Open Graph tags. The links into the show pages appear
only when the shows index is published beside this page, so the home page
never links to a missing page (the show pages are built by a step that may
be skipped: qtv_pipeline/show_pages.py, --notice-on-failure).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from qtv_pipeline.app_store import INDEX_SLOT
from qtv_pipeline.show_pages import (
    _ENV,
    DEFAULT_BASE_URL,
    DEFAULT_PINNED_PATH,
    SITE_NAME,
    ShowPagesError,
    _breadcrumb,
    _clean_base_url,
    _common,
    _structured,
    load_pinned,
)

# The hand-picked shows the home page names by title (the rest are one link away).
FEATURED_ON_HOME = 12
HOME_TITLE = "Queer Frame: Do queer characters die? Spoiler-free TV guide"
HOME_OG_TITLE = "Queer Frame: queer TV, spoiler-free"
HOME_DESCRIPTION = (
    "TV shows with queer women, non-binary and trans characters, and a spoiler-free "
    'answer to "Do any queer characters die?" that stays hidden until you tap.'
)
DATA_TITLE = "Queer Frame data: the snapshot file and its license"
DATA_DESCRIPTION = (
    "The combined LezWatch.TV and TVmaze data file Queer Frame is built from, "
    "published under CC BY-SA 4.0 with its credits."
)
DATA_PATH = "data/index.html"


def _source_url(doc: dict[str, Any], source: str) -> str:
    return str(next(a["url"] for a in doc["attribution"] if a["source"] == source))


def render_index(
    doc: dict[str, Any],
    *,
    shows_link: bool = False,
    shows_total: int = 0,
    featured: list[dict[str, str]] | None = None,
    featured_total: int = 0,
    base_url: str = DEFAULT_BASE_URL,
) -> str:
    """The home page. ``shows_link`` is whether the shows index is published
    beside it; without it there is no link into the show pages at all.
    ``featured`` is the hand-picked shows to name (``{"title", "url"}``),
    ``featured_total`` how many hand-picked pages there are in all."""
    base = _clean_base_url(base_url)
    linked = shows_link and shows_total > 0
    return _ENV.get_template("home.html.j2").render(
        **_common(doc, base, False),
        title=HOME_TITLE,
        og_title=HOME_OG_TITLE,
        description=HOME_DESCRIPTION,
        canonical=f"{base}/",
        crumbs=[],
        breadcrumb=None,
        shows_total=shows_total if linked else 0,
        featured=(featured or [])[:FEATURED_ON_HOME] if linked else [],
        featured_total=featured_total if linked else 0,
        lezwatch_url=_source_url(doc, "lezwatch"),
        tvmaze_url=_source_url(doc, "tvmaze"),
        app_slot=INDEX_SLOT,
    )


def render_data_page(doc: dict[str, Any], *, base_url: str = DEFAULT_BASE_URL) -> str:
    """The data page: the snapshot's license, its files and this build."""
    base = _clean_base_url(base_url)
    cov = doc["coverage"]
    lw, tv = cov["lezwatch"], cov["tvmaze"]
    canonical = f"{base}/data/"
    crumbs = [(SITE_NAME, f"{base}/"), ("Data", canonical)]
    return _ENV.get_template("data.html.j2").render(
        **_common(doc, base, False),
        title=DATA_TITLE,
        description=DATA_DESCRIPTION,
        canonical=canonical,
        crumbs=crumbs,
        breadcrumb=_structured(_breadcrumb(crumbs)),
        build={
            "generated_at": doc["generated_at"],
            "content_digest": doc["content_digest"],
            "shows": f"{lw['shows']['fetched']} / {lw['shows']['available']} available",
            "characters": (
                f"{lw['characters']['fetched']} / {lw['characters']['available']} available"
            ),
            "tvmaze": f"{tv['joined']} / {tv['shows_total']} ({tv['join_rate'] * 100:.1f}%)",
        },
    )


def published_shows(
    doc: dict[str, Any], site_dir: Path, pinned_path: Path = DEFAULT_PINNED_PATH
) -> tuple[int, list[dict[str, str]], int]:
    """What the show-pages step published under ``site_dir/shows``: how many
    show pages, the hand-picked ones in the list's order (title and URL), and
    how many hand-picked pages there are. Only pages that exist are counted
    or named, so every link the home page makes resolves."""
    shows_dir = site_dir / "shows"
    total = sum(1 for p in shows_dir.glob("*/index.html"))
    try:
        pins = load_pinned(pinned_path) or []
    except ShowPagesError:
        pins = []
    by_id = {s["lwtv_id"]: s for s in doc["shows"]}
    featured = [
        {"title": by_id[p.lezwatch_id]["title"], "slug": by_id[p.lezwatch_id]["slug"]}
        for p in pins
        if p.lezwatch_id in by_id
        and (shows_dir / by_id[p.lezwatch_id]["slug"] / "index.html").is_file()
    ]
    return total, featured, len(featured)


def write_site(
    doc: dict[str, Any],
    target: Path,
    *,
    base_url: str = DEFAULT_BASE_URL,
    pinned_path: Path = DEFAULT_PINNED_PATH,
) -> list[Path]:
    """Write the home page to ``target`` and the data page beside it."""
    site_dir = target.parent
    base = _clean_base_url(base_url)
    shows_link = (site_dir / "shows" / "index.html").is_file()
    total, featured, featured_total = (
        published_shows(doc, site_dir, pinned_path) if shows_link else (0, [], 0)
    )
    home = render_index(
        doc,
        shows_link=shows_link,
        shows_total=total,
        featured=[{"title": f["title"], "url": f"{base}/shows/{f['slug']}/"} for f in featured],
        featured_total=featured_total,
        base_url=base,
    )
    data = render_data_page(doc, base_url=base)
    data_target = site_dir / DATA_PATH
    data_target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(home, encoding="utf-8")
    data_target.write_text(data, encoding="utf-8")
    return [target, data_target]


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python -m qtv_pipeline.site_index SNAPSHOT_JSON OUT_HTML", file=sys.stderr)
        return 2
    doc = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    write_site(doc, Path(argv[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
