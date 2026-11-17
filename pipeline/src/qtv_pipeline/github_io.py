"""This repository's own Pages site, once the website has a repository of its own.

DECISIONS 0062. The website (the home page, the show pages, the sitemap) is
served on its domain from a second repository. This repository's Pages site
has no custom domain and is small. snapshot.yml builds it from the assembled
website:

    python -m qtv_pipeline.github_io SITE_DIR OUT_DIR

It holds:

- the data file and its checksum, byte for byte, at the address the apps
  fetch;
- the privacy, support and terms pages at the addresses the apps and the
  store listings open: the website's own pages with one line added to the
  head, which names the page's address on the domain as its canonical URL,
  so a search engine files it under the domain. The line loads nothing;
- for every other page of the website, a small page at the same path that
  names the page on the domain as canonical and sends a browser there at once
  (a refresh of 0 seconds, which search engines read as a permanent move);
- a 404 page that links to the domain and asks not to be indexed.

There is no sitemap, robots file, image or script. Every file is rendered
before the first is written, and OUT_DIR must be empty or absent, so a
refusal writes nothing.
"""

from __future__ import annotations

import html
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote

from qtv_pipeline.show_pages import DEFAULT_BASE_URL

# Served byte for byte: what the apps fetch.
DATA_FILES = ("snapshot.v1.json", "snapshot.v1.json.sha256")
# Served as the website's own page plus a canonical line: what the apps and
# the store listings open.
KEPT_PAGES = ("privacy.html", "support.html", "terms.html")
HEAD_END = "</head>"
NOT_FOUND = "404.html"
MOVED_TITLE = "Queer Frame: this page is on queerframe.app"
NOT_FOUND_TITLE = "Page not found: Queer Frame"


class GithubIoError(ValueError):
    """The assembled website cannot be turned into this repository's Pages site."""


class _Canonical(HTMLParser):
    """The href of a page's first <link rel="canonical">, or ""."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.href = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        if tag == "link" and a.get("rel") == "canonical" and not self.href:
            self.href = a.get("href") or ""


def canonical_of(page: str) -> str:
    """The canonical URL a page declares, or "" when it declares none."""
    parser = _Canonical()
    parser.feed(page)
    return parser.href


def with_canonical(name: str, page: str, base_url: str = DEFAULT_BASE_URL) -> str:
    """A kept page with its address on the domain as its canonical URL: one
    line added before the end of the head. A page that already names that
    address is returned as it is; one that names another is refused."""
    want = f"{base_url.rstrip('/')}/{name}"
    got = canonical_of(page)
    if got == want:
        return page
    if got:
        raise GithubIoError(f"{name}: canonical is {got!r}, not {want!r}")
    if page.count(HEAD_END) != 1:
        raise GithubIoError(f"{name}: expected exactly one {HEAD_END}")
    line = f'<link rel="canonical" href="{html.escape(want, quote=True)}">\n'
    return page.replace(HEAD_END, line + HEAD_END, 1)


def domain_url(rel: Path, base_url: str = DEFAULT_BASE_URL) -> str:
    """The address on the domain of the page at ``rel`` in the site directory.
    A directory's index.html is the directory, as the website links it."""
    parts = list(rel.parts)
    if parts[-1] == "index.html":
        parts[-1] = ""
    return f"{base_url.rstrip('/')}/" + "/".join(quote(p) for p in parts)


def render_moved(target: str) -> str:
    """The page left at an address whose page is on the domain."""
    url = html.escape(target, quote=True)
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{MOVED_TITLE}</title>\n"
        f'<link rel="canonical" href="{url}">\n'
        f'<meta http-equiv="refresh" content="0; url={url}">\n'
        "</head>\n"
        "<body>\n"
        f'<p>This page is at <a href="{url}">{url}</a>.</p>\n'
        "</body>\n"
        "</html>\n"
    )


def render_not_found(base_url: str = DEFAULT_BASE_URL) -> str:
    """The 404 page: a link to the domain, and a request not to be indexed."""
    url = html.escape(f"{base_url.rstrip('/')}/", quote=True)
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{NOT_FOUND_TITLE}</title>\n"
        '<meta name="robots" content="noindex">\n'
        "</head>\n"
        "<body>\n"
        "<h1>Page not found</h1>\n"
        f'<p>Queer Frame is at <a href="{url}">{url}</a>.</p>\n'
        "</body>\n"
        "</html>\n"
    )


def render(site_dir: Path, base_url: str = DEFAULT_BASE_URL) -> dict[Path, bytes]:
    """Every file of this repository's Pages site, keyed by its relative path.
    Raises GithubIoError when the website lacks a file the apps rely on, or a
    kept page cannot be given its address on the domain as canonical."""
    base = base_url.rstrip("/")
    files: dict[Path, bytes] = {}
    for name in (*DATA_FILES, *KEPT_PAGES):
        source = site_dir / name
        if not source.is_file():
            raise GithubIoError(f"{site_dir}: no {name}")
        files[Path(name)] = source.read_bytes()
    for name in KEPT_PAGES:
        page = files[Path(name)].decode("utf-8")
        files[Path(name)] = with_canonical(name, page, base).encode("utf-8")
    for source in sorted(site_dir.rglob("*.html")):
        rel = source.relative_to(site_dir)
        if rel in files or rel == Path(NOT_FOUND):
            continue
        declared = canonical_of(source.read_text(encoding="utf-8"))
        target = declared if declared.startswith(f"{base}/") else domain_url(rel, base)
        files[rel] = render_moved(target).encode("utf-8")
    files[Path(NOT_FOUND)] = render_not_found(base).encode("utf-8")
    return files


def build(site_dir: Path, out_dir: Path, base_url: str = DEFAULT_BASE_URL) -> list[Path]:
    """Write this repository's Pages site into ``out_dir`` and return the
    files written. ``out_dir`` must be empty or absent."""
    if out_dir.exists() and any(out_dir.iterdir()):
        raise GithubIoError(f"{out_dir}: not empty")
    files = render(site_dir, base_url)
    written = []
    for rel, data in files.items():
        target = out_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        written.append(target)
    return written


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python -m qtv_pipeline.github_io SITE_DIR OUT_DIR", file=sys.stderr)
        return 2
    try:
        written = build(Path(argv[0]), Path(argv[1]))
    except GithubIoError as exc:
        print(f"github_io: refused, nothing written: {exc}", file=sys.stderr)
        return 1
    moved = len(written) - len(DATA_FILES) - len(KEPT_PAGES) - 1
    print(
        f"github_io: wrote {len(written)} files to {argv[1]}: the data file and its checksum, "
        f"{len(KEPT_PAGES)} pages, {moved} pointers to {DEFAULT_BASE_URL}, and a 404 page"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
