"""The App Store launch switch for the Pages site (APP_STORE_LIVE).

snapshot.yml assembles the site (the home page index.html and data/index.html
from site_index, privacy.html and support.html copied from docs/site/) and then runs this module over it:

    python -m qtv_pipeline.app_store SITE_DIR "$APP_STORE_LIVE"
    python -m qtv_pipeline.app_store --check "$APP_STORE_LIVE"

Off (APP_STORE_LIVE unset, empty or "false", which is how it stays until
Apple approves the app) it changes nothing: not a byte of any page, and no
file is added. On ("true") every page gets Safari's Smart App Banner tag,
and the home page's "coming soon" line (INDEX_SLOT) is replaced by the
"Get the iPhone app" block (``get_app_block``): one sentence on what the app
adds over the website, then Apple's "Download on the App Store" badge linking
to the app's App Store listing, with its US price named as the US price. The
link names no country (DECISIONS 0058), so Apple opens the listing in the
visitor's own storefront. The show pages, the shows index,
the airing page and the 404 page render the same block themselves
(DECISIONS 0047), with the badge's address absolute so it resolves from any
directory. Any other value is refused (exit 1), so a
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

import html
import re
import sys
from pathlib import Path
from urllib.parse import urlencode

APP_STORE_ID = "6818637465"
# The listing with no country in its path (DECISIONS 0058). The app is sold in
# more storefronts than the United States since 2026-11-12, and a link with
# /us/ in it shows the US page and the US price to a desktop or Android
# visitor anywhere. Apple resolves this form in the visitor's own storefront.
# It does not promise the app is sold there: where it is not, Apple says so.
APP_STORE_URL = f"https://apps.apple.com/app/id{APP_STORE_ID}"

# App Store Connect campaign links (DECISIONS 0056). Apple counts App Store
# impressions, product page views and downloads per campaign token (ct) in
# App Store Connect > Analytics > Acquisition > Campaigns, for links that also
# carry the account's provider token (pt). This is the only measurement the
# site has: Apple counts what happens on its own pages, and the site still
# runs no script, sets no cookie and requests nothing from another host.
#
# The provider token is account-level and shown only in App Store Connect's
# campaign link generator (Apple: "You can't create one manually"). It was
# copied from a generated link on 2026-11-10. It is not a credential: it
# appears in every campaign link. With no token (None) every link stays the
# plain APP_STORE_URL; a link with a campaign token and no provider token, or
# an invented one, is never published.
APP_STORE_PROVIDER_TOKEN: str | None = "129452704"  # noqa: S105 public in every campaign link, not a credential (#143)
# Apple: "Media type token (identified by the mt= parameter)"; its own
# example campaign link carries mt=8.
APP_STORE_MEDIA_TYPE = "8"
# One campaign token per page type, never per page, so App Store Connect's
# Campaigns list stays short and each row clears Apple's five-download floor
# sooner. Apple allows up to 30 characters; these are plain lowercase.
CAMPAIGNS = frozenset(
    {
        "home",  # the home page's badge
        "show-top",  # the one line under a show page's opening (placement test)
        "show",  # a show page's badge, below the character questions
        "shows",  # the shows index
        "airing",  # the airing-now page
        "notfound",  # the 404 page
        "press",  # the press page's "On the App Store" link
    }
)
CAMPAIGN_MAX = 30  # Apple: "up to 30 alphanumeric characters and spaces"
_CAMPAIGN_SHAPE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_PROVIDER_SHAPE = re.compile(r"^[0-9]+$")


class CampaignError(ValueError):
    """A campaign token or provider token Apple would not accept, or one this
    site has not declared."""


def app_store_link(campaign: str, provider_token: str | None = None) -> str:
    """The App Store listing URL for one page type. With a provider token
    (``APP_STORE_PROVIDER_TOKEN`` unless one is passed) it carries Apple's
    pt, ct and mt parameters; without one it is the plain listing URL.
    ``campaign`` must be one of ``CAMPAIGNS`` either way, so a page type cannot
    quietly go unmeasured once the token is in."""
    if campaign not in CAMPAIGNS:
        raise CampaignError(f"{campaign!r} is not a declared campaign token")
    if len(campaign) > CAMPAIGN_MAX or not _CAMPAIGN_SHAPE.fullmatch(campaign):
        raise CampaignError(f"{campaign!r} is not a plain lowercase token of at most 30")
    token = APP_STORE_PROVIDER_TOKEN if provider_token is None else provider_token
    if token is None:
        return APP_STORE_URL
    if not _PROVIDER_SHAPE.fullmatch(token):
        raise CampaignError("the provider token is not all digits")
    query = urlencode({"pt": token, "ct": campaign, "mt": APP_STORE_MEDIA_TYPE})
    return f"{APP_STORE_URL}?{query}"


BADGE_FILE = "app-store-badge.svg"
BADGE_SOURCE = Path(__file__).parent / "assets" / BADGE_FILE
BADGE_SHA256 = "a26fc5b38380272c92e9019a2eb8b45542a66814b3e2b203772db8904b9fb99f"

BANNER = f'<meta name="apple-itunes-app" content="app-id={APP_STORE_ID}">'
# Every page the site publishes has exactly this line; the banner goes after it.
VIEWPORT = '<meta name="viewport" content="width=device-width, initial-scale=1">'
# The home page's one line about the app while the switch is off
# (site_index.render_index puts it there, with no link). On, the badge takes
# its place, so the page never says "coming soon" beside the badge.
INDEX_SLOT = (
    '<p class="app-soon">The Queer Frame iPhone app is coming soon. '
    "It is not on the App Store yet.</p>"
)
# The one-time price in the United States (docs/app-store-listing.json
# price_usd). Apple sets every other storefront's price from it, in that
# storefront's currency and with its tax, so the site never prints the figure
# without its country (DECISIONS 0058): "$4.99" alone reads as a lower price
# than the App Store then shows in Canada, Australia or New Zealand.
PRICE = "$4.99"
PRICE_US = f"{PRICE} in the US"
SITE_NAME_FOR_LINE = "Queer Frame"
# Under the badge on every page that carries it, and on /press/ (PRICE_US).
# True in every storefront: it names the one price the site knows, and says
# Apple shows the local one only where the app is sold, never that it is sold
# everywhere.
PRICE_COPY = (
    f"Queer Frame for iPhone. {PRICE_US}; "
    "the App Store shows the local price where the app is sold."
)

# What the app adds over the website, in one sentence. Every claim is a
# feature of the approved 1.0.0 build (docs/app-store-listing.json, the
# Up Next widget and ReminderScheduler in ios/); the iPhone is the only
# platform on the App Store. Not a pitch inside the spoiler: the block is
# always outside the answer.
APP_PITCH = (
    "Favorite the shows you follow and see each one's next episode at a glance, "
    "add the Up Next widget to your Home Screen, or turn on new-episode reminders. "
    "It works offline. No account, no ads, no subscription."
)
APP_PITCH_LEAD = "Get the iPhone app."


def get_app_block(badge_src: str, campaign: str) -> str:
    """The one "Get the app" block a page carries: the pitch, then Apple's
    unedited badge as the link, with the price. ``badge_src`` is where the
    page finds the badge file (the home page uses the bare file name, pages
    in subdirectories the absolute URL); ``campaign`` is the page type's
    campaign token (``app_store_link``). The badge's look comes from the
    block's own stylesheet, BADGE_STYLE: the img width and height attributes
    reserve its box before the SVG loads, so nothing shifts."""
    href = html.escape(app_store_link(campaign))
    return (
        '<div class="get-app">'
        f"<p><strong>{APP_PITCH_LEAD}</strong> {APP_PITCH}</p>"
        '<p class="app-store-cta">'
        f'<a class="app-store-badge" href="{href}">'
        f'<img src="{badge_src}" width="120" height="40" alt="Download on the App Store"></a>'
        f" <span>{PRICE_COPY}</span></p>"
        "</div>"
    )


BADGE_BLOCK = get_app_block(BADGE_FILE, "home")

# A show page's one line near the top (DECISIONS 0056). The badge sits below
# the character questions, out of sight on a phone for a visitor who came
# from search; this line says the app exists and what it costs in the US
# (PRICE_US, DECISIONS 0058), once, before the spoiler warning and never
# inside the answer. Its own campaign token
# (show-top) shows in App Store Connect whether the top line or the badge
# sends people.
APP_LINE_TEXT = (
    f"{SITE_NAME_FOR_LINE} is also an iPhone app: a one-time purchase ({PRICE_US}), "
    "no subscription, no in-app purchases."
)
APP_LINE_LINK_TEXT = "See it on the App Store"


def get_app_line(campaign: str = "show-top") -> str:
    """The one-line App Store mention near the top of a show page."""
    href = html.escape(app_store_link(campaign))
    return f'<p class="app-line">{APP_LINE_TEXT} <a href="{href}">{APP_LINE_LINK_TEXT}</a>.</p>'


# The block brings its own rules rather than relying on the page's
# stylesheet, so a page with the switch off carries no trace of the app. The
# home page gets them from apply(); the pages that render the block
# themselves put them in their head (base.html.j2). The link's padding is the
# badge's clear space, so the focus outline and the text sit outside it.
BADGE_STYLE = """<style>
  .get-app { margin: 1.5rem 0; padding: 0.75rem 1rem; border-left: 6px solid var(--coral); background: var(--surface); }
  .get-app p { margin: 0; }
  .app-store-cta { display: flex; flex-wrap: wrap; align-items: center; gap: 0.5rem; margin: 0.25rem 0 0; }
  .app-store-badge { display: inline-block; padding: 10px; line-height: 0; }
  .app-store-badge:focus-visible { outline: 3px solid LinkText; outline-offset: 2px; }
  .app-store-badge img { display: block; width: 120px; height: 40px; }
  @media (forced-colors: active) { .get-app { border-left-color: LinkText; } }
</style>"""


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
            if text.count(INDEX_SLOT) != 1:
                raise PageShapeError(f"{page.name}: expected exactly one {INDEX_SLOT!r}")
            text = text.replace(INDEX_SLOT, get_app_block(BADGE_FILE, "home"), 1)
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
