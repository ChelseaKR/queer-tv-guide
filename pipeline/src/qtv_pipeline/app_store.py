"""The App Store launch switch for the Pages site (APP_STORE_LIVE).

snapshot.yml assembles the site (index.html from site_index, privacy.html and
support.html copied from docs/site/) and then runs this module over it:

    python -m qtv_pipeline.app_store SITE_DIR "$APP_STORE_LIVE"
    python -m qtv_pipeline.app_store --check "$APP_STORE_LIVE"

Off (APP_STORE_LIVE unset, empty or "false", which is how it stays until
Apple approves the app) it changes nothing: not a byte of any page, and no
file is added. On ("true") every page gets Safari's Smart App Banner tag,
and the index gets Apple's "Download on the App Store" badge linking to the
app's US listing, with its price. Any other value is refused (exit 1), so a
typo can neither hide the badge after the owner believes it is on nor show
it by accident. ``--check`` runs that refusal early in the workflow, before
anything is published.

The badge is Apple's preferred black US-English artwork, byte for byte as
Apple's marketing tools served it on 2026-10-02
(toolbox.marketingtools.apple.com/api/v2/badges/download-on-the-app-store/
black/en-us, SHA-256 BADGE_SHA256). Apple's App Store Marketing Artwork
License Agreement allows it only for an app that is available on the App
Store, which is why it is behind the switch; see NOTICE. It is shown at
40px tall, Apple's on-screen minimum, with a quarter of its height (10px)
of clear space, and never edited.
"""

from __future__ import annotations

import sys
from pathlib import Path

APP_STORE_ID = "6818637465"
APP_STORE_URL = f"https://apps.apple.com/us/app/id{APP_STORE_ID}"
BADGE_FILE = "app-store-badge.svg"
BADGE_SOURCE = Path(__file__).parent / "assets" / BADGE_FILE
BADGE_SHA256 = "a26fc5b38380272c92e9019a2eb8b45542a66814b3e2b203772db8904b9fb99f"

BANNER = f'<meta name="apple-itunes-app" content="app-id={APP_STORE_ID}">'
# Every page the site publishes has exactly this line; the banner goes after it.
VIEWPORT = '<meta name="viewport" content="width=device-width, initial-scale=1">'
# The index's heading (site_index.render_index); the badge goes after it.
INDEX_HEADING = "<h1>Queer Frame snapshot</h1>"
PRICE_COPY = "Queer Frame for iPhone. $4.99 on the App Store."

# The index has no stylesheet of its own, so the badge brings its rules. The
# img's width and height attributes reserve its box before the SVG loads, so
# nothing shifts. The link's padding is the badge's clear space, so the
# focus outline and the text sit outside it.
BADGE_STYLE = """<style>
  .app-store-cta { display: flex; flex-wrap: wrap; align-items: center; gap: 0.5rem; margin: 0.5rem 0; }
  .app-store-badge { display: inline-block; padding: 10px; line-height: 0; }
  .app-store-badge:focus-visible { outline: 3px solid LinkText; outline-offset: 2px; }
  .app-store-badge img { display: block; width: 120px; height: 40px; }
</style>"""
BADGE_BLOCK = (
    '<p class="app-store-cta">'
    f'<a class="app-store-badge" href="{APP_STORE_URL}">'
    f'<img src="{BADGE_FILE}" width="120" height="40" alt="Download on the App Store"></a>'
    f" <span>{PRICE_COPY}</span></p>"
)


class SwitchError(ValueError):
    """APP_STORE_LIVE holds something other than true, false or nothing."""


class PageShapeError(ValueError):
    """A page lacks the line the banner or badge is placed after."""


def live_or_false(value: str | None) -> bool:
    """Read the switch: "true" is on; None, "" or "false" is off (case and
    surrounding whitespace ignored). Anything else raises SwitchError."""
    if value is None:
        return False
    v = value.strip().lower()
    if v == "true":
        return True
    if v in ("", "false"):
        return False
    raise SwitchError(f"APP_STORE_LIVE {value!r} is neither 'true' nor 'false'")


def _insert_after(text: str, anchor: str, addition: str, page: str) -> str:
    if text.count(anchor) != 1:
        raise PageShapeError(f"{page}: expected exactly one {anchor!r}")
    return text.replace(anchor, f"{anchor}\n{addition}", 1)


def apply(site_dir: Path) -> list[Path]:
    """Add the banner to every page and the badge to the index. Every page is
    checked before any is written, so a page of the wrong shape leaves the
    site as it was. Returns the files written."""
    pages = sorted(site_dir.glob("*.html"))
    if not any(p.name == "index.html" for p in pages):
        raise PageShapeError(f"{site_dir}: no index.html")
    rendered: dict[Path, str] = {}
    for page in pages:
        text = page.read_text(encoding="utf-8")
        if "apple-itunes-app" in text:
            raise PageShapeError(f"{page.name}: already carries a Smart App Banner tag")
        head_addition = BANNER + ("\n" + BADGE_STYLE if page.name == "index.html" else "")
        text = _insert_after(text, VIEWPORT, head_addition, page.name)
        if page.name == "index.html":
            text = _insert_after(text, INDEX_HEADING, BADGE_BLOCK, page.name)
        rendered[page] = text
    for page, text in rendered.items():
        page.write_text(text, encoding="utf-8")
    badge = site_dir / BADGE_FILE
    badge.write_bytes(BADGE_SOURCE.read_bytes())
    return [*rendered, badge]


def main(argv: list[str]) -> int:
    usage = "usage: python -m qtv_pipeline.app_store (SITE_DIR | --check) APP_STORE_LIVE"
    if len(argv) != 2:
        print(usage, file=sys.stderr)
        return 2
    target, value = argv
    try:
        live = live_or_false(value)
        if target == "--check":
            print(f"APP_STORE_LIVE: {'on' if live else 'off'}")
            return 0
        if not live:
            print("APP_STORE_LIVE off: the site is unchanged")
            return 0
        written = apply(Path(target))
    except (SwitchError, PageShapeError) as exc:
        print(f"app_store: refused, nothing changed: {exc}", file=sys.stderr)
        return 1
    print(f"APP_STORE_LIVE on: banner on {len(written) - 1} page(s), badge on index.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
