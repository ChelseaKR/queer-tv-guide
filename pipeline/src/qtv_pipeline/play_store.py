"""The Google Play launch switch for the Pages site (PLAY_STORE_LIVE).

The Android twin of app_store.py (DECISIONS 0018). snapshot.yml assembles
the site, runs app_store.py over it, then runs this module:

    python -m qtv_pipeline.play_store SITE_DIR "$PLAY_STORE_LIVE"
    python -m qtv_pipeline.play_store --check "$PLAY_STORE_LIVE"

Off (PLAY_STORE_LIVE unset, empty or "false", which is how it stays until
the app is published on Google Play) it changes nothing: not a byte of any
page, and no file is added. On ("true") the index gets a plain text link to
the app's Play listing, with its price and Google's trademark line. Any
other value is refused (exit 1), so a typo can neither hide the link after
the owner believes it is on nor show it by accident. ``--check`` runs that
refusal early in the workflow, before anything is published.

There is no badge image and nothing in any page's head. Google's "Get it on
Google Play" artwork has terms of its own that were not read when this was
written, so the link is text; vendoring the badge is an owner step
(docs/play-store/OWNER-STEPS.md, step 11). Android has no counterpart to
Safari's Smart App Banner tag.

The link sits inside an android-app region, the markers the site's tests
use to keep Android wording out of the iPhone copy, and below the App Store
badge when that switch is on too, whichever step runs first.
"""

from __future__ import annotations

import sys
from pathlib import Path

from qtv_pipeline.app_store import BADGE_BLOCK as APP_STORE_BLOCK
from qtv_pipeline.app_store import INDEX_HEADING, PageShapeError

PACKAGE = "com.chelseakr.queertvguide"
PLAY_URL = f"https://play.google.com/store/apps/details?id={PACKAGE}"
PRICE_COPY = "for Android, $4.99."
TRADEMARK = "Google Play is a trademark of Google LLC."
ANDROID_BEGIN = "<!-- android-app:begin -->"
ANDROID_END = "<!-- android-app:end -->"

# One line, so a `grep -c play.google.com` over the live index reads 1.
PLAY_BLOCK = (
    f"{ANDROID_BEGIN}"
    f'<p class="play-store-cta"><a href="{PLAY_URL}">Queer Frame on Google Play</a>: '
    f"{PRICE_COPY}</p>"
    f"<p><small>{TRADEMARK}</small></p>"
    f"{ANDROID_END}"
)


class SwitchError(ValueError):
    """PLAY_STORE_LIVE holds something other than true, false or nothing."""


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
    raise SwitchError(f"PLAY_STORE_LIVE {value!r} is neither 'true' nor 'false'")


def apply(site_dir: Path) -> Path:
    """Add the Play link to the index, after the App Store badge when there
    is one and after the heading otherwise. The page is checked before it is
    written, so an index of the wrong shape is left as it was. Returns the
    file written."""
    index = site_dir / "index.html"
    if not index.is_file():
        raise PageShapeError(f"{site_dir}: no index.html")
    text = index.read_text(encoding="utf-8")
    if PLAY_URL in text:
        raise PageShapeError("index.html: already carries the Google Play link")
    anchor = APP_STORE_BLOCK if APP_STORE_BLOCK in text else INDEX_HEADING
    if text.count(anchor) != 1:
        raise PageShapeError(f"index.html: expected exactly one {anchor!r}")
    index.write_text(text.replace(anchor, f"{anchor}\n{PLAY_BLOCK}", 1), encoding="utf-8")
    return index


def main(argv: list[str]) -> int:
    usage = "usage: python -m qtv_pipeline.play_store (SITE_DIR | --check) PLAY_STORE_LIVE"
    if len(argv) != 2:
        print(usage, file=sys.stderr)
        return 2
    target, value = argv
    try:
        live = live_or_false(value)
        if target == "--check":
            print(f"PLAY_STORE_LIVE: {'on' if live else 'off'}")
            return 0
        if not live:
            print("PLAY_STORE_LIVE off: the site is unchanged")
            return 0
        apply(Path(target))
    except (SwitchError, PageShapeError) as exc:
        print(f"play_store: refused, nothing changed: {exc}", file=sys.stderr)
        return 1
    print("PLAY_STORE_LIVE on: Google Play link on index.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
