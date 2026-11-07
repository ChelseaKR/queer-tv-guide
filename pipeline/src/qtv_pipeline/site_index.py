"""The site's home page and its data page (DECISIONS 0026).

    python -m qtv_pipeline.site_index out/snapshot.v1.json site/index.html

writes these next to the snapshot files:

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
- ``llms.txt``, the site described for AI assistants (llmstxt.org), with
  no show named and no answer given.
- ``404.html``, which GitHub Pages serves for an address with no page
  (with the App Store switch on, it ends with the "Get the iPhone app"
  block, DECISIONS 0047), and
  ``favicon.svg``, the header's brand mark as the browser-tab icon
  (DECISIONS 0038).

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
from importlib import resources
from pathlib import Path
from typing import Any

from qtv_pipeline import findings
from qtv_pipeline.app_store import INDEX_SLOT, PRICE, live_or_false
from qtv_pipeline.show_pages import (
    _ENV,
    AIRING_PATH,
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
# Names the source, since the searches that find the home page so far are for
# LezWatch.TV itself (DECISIONS 0027). Built from it, not endorsed by it: the
# footer of every page says so.
HOME_DESCRIPTION = (
    "A spoiler-free guide to TV shows with queer women, non-binary and trans characters, "
    "built from LezWatch.TV records. Does she die? Tap to see the answer."
)
DATA_TITLE = "Queer Frame data: the snapshot file and its license"
DATA_DESCRIPTION = (
    "The combined LezWatch.TV and TVmaze data file Queer Frame is built from, "
    "published under CC BY-SA 4.0 with its credits."
)
DATA_PATH = "data/index.html"
# GitHub Pages serves this file for any address that has no page
# (DECISIONS 0038). Its links are absolute, since it answers at any depth.
NOT_FOUND_PATH = "404.html"
NOT_FOUND_TITLE = "Page not found: Queer Frame"
NOT_FOUND_DESCRIPTION = "This address has no page on Queer Frame."
# The brand mark as the browser-tab icon, served from this site only.
FAVICON_PATH = "favicon.svg"
# /llms.txt (llmstxt.org): what the site is, for AI assistants. GitHub Pages
# serves a .txt file as text/plain. Like every page, it never states an answer.
LLMS_PATH = "llms.txt"
LLMS_SPEC_URL = "https://llmstxt.org/"


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
    airing_link: bool = False,
) -> str:
    """The home page. ``shows_link`` is whether the shows index is published
    beside it; without it there is no link into the show pages at all.
    ``featured`` is the hand-picked shows to name (``{"title", "url"}``),
    ``featured_total`` how many hand-picked pages there are in all.
    ``airing_link`` is whether the airing-now page (DECISIONS 0033) is
    published beside it; it is linked only then, and only with the shows."""
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
        airing_link=linked and airing_link,
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


def render_not_found(
    doc: dict[str, Any],
    *,
    shows_link: bool = False,
    airing_link: bool = False,
    base_url: str = DEFAULT_BASE_URL,
    app_store_live: bool = False,
) -> str:
    """The page for an address with no page: no canonical, kept out of
    search, and links only to pages published beside it. With the App Store
    switch on it ends with the "Get the iPhone app" block (DECISIONS 0047);
    the Smart App Banner tag is left to ``app_store.apply``, which adds it to
    every top-level page."""
    base = _clean_base_url(base_url)
    common = _common(doc, base, app_store_live)
    common["app_store_banner"] = None
    return _ENV.get_template("404.html.j2").render(
        **common,
        title=NOT_FOUND_TITLE,
        description=NOT_FOUND_DESCRIPTION,
        canonical=None,
        crumbs=[],
        breadcrumb=None,
        shows_link=shows_link,
        airing_link=shows_link and airing_link,
    )


def render_llms(
    doc: dict[str, Any],
    *,
    shows_link: bool = False,
    shows_total: int = 0,
    airing_link: bool = False,
    base_url: str = DEFAULT_BASE_URL,
) -> str:
    """/llms.txt: an H1, a blockquote summary, plain text, then H2 sections of
    ``[name](url): note`` links (llmstxt.org). It names no show and no
    character, so it cannot give an answer away, and it links only to pages
    published beside it."""
    base = _clean_base_url(base_url)
    linked = shows_link and shows_total > 0
    snapshot = doc["licence"]["snapshot"]
    lines = [
        f"# {SITE_NAME}",
        "",
        f"> {SITE_NAME} is a spoiler-free guide to TV shows with queer women, "
        "non-binary and trans characters, on the web and as an iPhone app. For each "
        "show it answers one question: do any queer characters die? The answer stays "
        "hidden until the reader taps to reveal it.",
        "",
        "Please keep the answer closed: each show page puts it in a closed box below a "
        "spoiler warning, and nothing in a page's title, description or character list "
        "gives it away. When you point someone to a show page, do not state the answer "
        "for them; let them open it. This file names no show for the same reason.",
        "",
        "Unknown is not the same as lives: LezWatch.TV records deaths, not survival. A "
        "character with no recorded death is shown as Unknown, never as alive.",
        "",
        "Scope: shows with queer women, non-binary and trans characters, as LezWatch.TV "
        "lists them. Episode schedules, run status and networks come from TVmaze.",
        "",
        "Privacy: the website sets no cookies, runs no analytics and loads nothing from "
        "any other site. The app has no account, no analytics and no ads.",
        "",
        "Update cadence: the data is rebuilt once a day (09:17 UTC). The iPhone app is "
        "linked from the home page once it is on the App Store.",
        "",
        f"How to cite: name {SITE_NAME} and link the show page, and credit LezWatch.TV "
        f"and TVmaze. The data file is published under {snapshot['name']} "
        f"({snapshot['url']}).",
        "",
        f"This file follows the llms.txt format described at {LLMS_SPEC_URL}.",
        "",
        "## Pages",
        "",
        f"- [Home]({base}/): what {SITE_NAME} is and how the answer stays closed",
    ]
    if linked:
        lines += [
            f"- [All shows, A to Z]({base}/shows/): {shows_total} show "
            f"{'page' if shows_total == 1 else 'pages'}, one per show under /shows/<show>/",
        ]
        if airing_link:
            lines.append(f"- [Airing now]({base}/airing/): queer TV with new episodes coming up")
    lines += [
        f"- [Data]({base}/data/): the snapshot file, its license and this build's counts",
        f"- [Privacy policy]({base}/privacy.html)",
        f"- [Support]({base}/support.html)",
        "",
        "## Sources",
        "",
    ]
    for a in doc["attribution"]:
        lines.append(
            f"- [{a['name']}]({a['url']}): {a['text']} License: {a['licence_name']} "
            f"({a['licence_url']}). {a['name']} does not endorse {SITE_NAME}."
        )
    lines.append("")
    return "\n".join(lines)


def favicon() -> str:
    """The brand mark as a standalone SVG file, the same drawing the header shows."""
    return resources.files("qtv_pipeline").joinpath("templates/mark.svg").read_text("utf-8")


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
    findings_path: Path = findings.DEFAULT_FINDINGS_PATH,
    repo_root: Path = findings.REPO_ROOT,
    app_store_live: bool = False,
) -> list[Path]:
    """Write the home page to ``target``, and the data page, the not-found
    page, the favicon, the findings page with its CSV and the press page
    (DECISIONS 0042) beside it."""
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
        airing_link=(site_dir / AIRING_PATH).is_file(),
    )
    data = render_data_page(doc, base_url=base)
    data_target = site_dir / DATA_PATH
    data_target.parent.mkdir(parents=True, exist_ok=True)
    not_found = render_not_found(
        doc,
        shows_link=shows_link,
        airing_link=(site_dir / AIRING_PATH).is_file(),
        base_url=base,
        app_store_live=app_store_live,
    )
    target.write_text(home, encoding="utf-8")
    data_target.write_text(data, encoding="utf-8")
    (site_dir / NOT_FOUND_PATH).write_text(not_found, encoding="utf-8")
    (site_dir / FAVICON_PATH).write_text(favicon(), encoding="utf-8")
    llms = render_llms(
        doc,
        shows_link=shows_link,
        shows_total=total,
        airing_link=(site_dir / AIRING_PATH).is_file(),
        base_url=base,
    )
    (site_dir / LLMS_PATH).write_text(llms, encoding="utf-8")
    return [
        target,
        data_target,
        site_dir / NOT_FOUND_PATH,
        site_dir / FAVICON_PATH,
        site_dir / LLMS_PATH,
        *write_findings_and_press(
            doc,
            site_dir,
            base_url=base,
            findings_path=findings_path,
            repo_root=repo_root,
            app_store_live=app_store_live,
        ),
    ]


def write_findings_and_press(
    doc: dict[str, Any],
    site_dir: Path,
    *,
    base_url: str,
    findings_path: Path,
    repo_root: Path,
    app_store_live: bool,
) -> list[Path]:
    """The findings page, its CSV, the press page and the press images."""
    data = findings.load(findings_path)
    page = site_dir / findings.FINDINGS_PATH
    table = site_dir / findings.CSV_PATH
    press = site_dir / findings.PRESS_PATH
    page.parent.mkdir(parents=True, exist_ok=True)
    press.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(
        findings.render_findings(doc, data, base_url=base_url, app_store_live=app_store_live),
        encoding="utf-8",
    )
    table.write_text(
        findings.findings_csv(data, licence_url=doc["licence"]["snapshot"]["url"]),
        encoding="utf-8",
    )
    images = findings.copy_press_assets(press.parent, repo_root)
    press.write_text(
        findings.render_press(
            doc,
            data,
            base_url=base_url,
            app_store_live=app_store_live,
            price=PRICE,
            platform="iPhone",
            images=images,
        ),
        encoding="utf-8",
    )
    return [page, table, press, *(press.parent / name for name in sorted(images))]


def main(argv: list[str]) -> int:
    """``SNAPSHOT_JSON OUT_HTML [APP_STORE_LIVE]``: the third argument is the
    same switch app_store.py reads; on, the press page links to the App Store."""
    if len(argv) not in (2, 3):
        print(
            "usage: python -m qtv_pipeline.site_index SNAPSHOT_JSON OUT_HTML [APP_STORE_LIVE]",
            file=sys.stderr,
        )
        return 2
    doc = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    live = live_or_false(argv[2]) if len(argv) == 3 else False
    write_site(doc, Path(argv[1]), app_store_live=live)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
