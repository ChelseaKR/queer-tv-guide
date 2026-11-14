"""Country-neutral App Store links and price wording (DECISIONS 0058).

The app is sold in more storefronts than the United States since 2026-11-12,
and not in all of them. So on the built site: no App Store link names a
country, the US price is never printed without "in the US", and no sentence
about the app says it is available everywhere.

The checkers are plain functions so the negative controls at the bottom can
sabotage a built page and prove each one fails.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from qtv_pipeline import app_store, show_pages, site_index
from tests import htmlprobe

REPO = Path(__file__).resolve().parents[2]
FIXTURE = REPO / "ios" / "GuideCore" / "Tests" / "Fixtures" / "snapshot.fixture.json"
LISTING = REPO / "docs" / "app-store-listing.json"
BASE = "https://example.test/qf"
APPLE_HOST = "apps.apple.com"

# The one path an App Store link may have: no storefront segment (/us/, /gb/)
# before /app/.
NEUTRAL_PATH = f"/app/id{app_store.APP_STORE_ID}"
# A currency figure: a symbol or code, then digits. Any on the site must be
# the US price with its country.
_FIGURE = re.compile(r"(?:[$£€₹]|\b(?:USD|CAD|AUD|NZD|GBP|EUR)\s?)\d[\d.,]*")
# Words that would say the app is sold in every country. The EU storefronts
# and others are off, so none may sit in a sentence about the app.
EVERYWHERE = (
    "worldwide",
    "everywhere",
    "all countries",
    "every country",
    "any country",
    "globally",
    "around the world",
    "your local price",
    "your country",
)

# Both forms of a show page's top line (DECISIONS 0059), with a count.
_TOP_LINES = (
    app_store.app_line_text(None, 2293),
    app_store.app_line_text(("Sunday, September 20, 2026", "2026-09-20"), 2293),
)


@pytest.fixture
def doc() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture
def pages(doc, tmp_path) -> dict[str, str]:
    """The whole site the way snapshot.yml builds it, switch on."""
    show_pages.build_site(doc, tmp_path, base_url=BASE, app_store_live=True)
    site_index.write_site(doc, tmp_path / "index.html", base_url=BASE, app_store_live=True)
    app_store.apply(tmp_path)
    return {
        str(p.relative_to(tmp_path)): p.read_text(encoding="utf-8")
        for p in sorted(tmp_path.rglob("*.html"))
    }


def _apple_links(text: str) -> list[str]:
    return [h for h in htmlprobe.parse(text).hrefs() if urlsplit(h).hostname == APPLE_HOST]


def _body_text(text: str) -> str:
    page = htmlprobe.parse(text)
    return " ".join([*page.outside, *page.inside])


def link_problems(rel: str, text: str) -> list[str]:
    """Every App Store link is the listing with no country in its path."""
    return [
        f"{rel}: {href} names a storefront"
        for href in _apple_links(text)
        if urlsplit(href).path != NEUTRAL_PATH
    ]


def price_problems(rel: str, text: str) -> list[str]:
    """Every currency figure a page prints is the US price, followed by its
    country."""
    found: list[str] = []
    body = _body_text(text)
    for m in _FIGURE.finditer(body):
        if m.group(0).rstrip(".,") != app_store.PRICE:
            found.append(f"{rel}: prints {m.group(0)!r}, which is not the US price")
        elif not body.startswith(app_store.PRICE_US, m.start()):
            found.append(f"{rel}: prints {app_store.PRICE} without its country")
    return found


def everywhere_problems(rel: str, text: str) -> list[str]:
    """No sentence that names the App Store or the app's price says the app
    is sold everywhere."""
    found: list[str] = []
    for sentence in re.split(r"(?<=[.?!])\s+", _body_text(text)):
        if "App Store" not in sentence and app_store.PRICE not in sentence:
            continue
        lowered = sentence.lower()
        found += [f"{rel}: {word!r} in {sentence!r}" for word in EVERYWHERE if word in lowered]
    return found


# --- the constants --------------------------------------------------------


def test_the_listing_url_names_no_country():
    parts = urlsplit(app_store.APP_STORE_URL)
    assert (parts.scheme, parts.hostname, parts.path) == ("https", APPLE_HOST, NEUTRAL_PATH)
    assert parts.query == ""
    for campaign in app_store.CAMPAIGNS:
        assert urlsplit(app_store.app_store_link(campaign)).path == NEUTRAL_PATH


def test_the_price_is_the_listings_us_price_and_says_so():
    listing = json.loads(LISTING.read_text(encoding="utf-8"))
    assert f"${listing['price_usd']}" == app_store.PRICE
    assert app_store.PRICE_US.startswith(app_store.PRICE)
    assert app_store.PRICE_US.removeprefix(app_store.PRICE) == " in the US"
    for copy in (app_store.PRICE_COPY, *_TOP_LINES):
        assert copy.count(app_store.PRICE) == copy.count(app_store.PRICE_US) == 1, copy


def test_the_smart_app_banner_still_names_no_country():
    # Not changed by 0058: app-id only, so Safari resolves it in the
    # visitor's own storefront.
    banner = htmlprobe.parse(f"<head>{app_store.BANNER}</head>").named("meta")
    assert banner == [{"name": "apple-itunes-app", "content": f"app-id={app_store.APP_STORE_ID}"}]


# --- the built site -------------------------------------------------------


def test_no_app_store_link_on_the_built_site_names_a_storefront(pages):
    assert [p for rel, text in pages.items() for p in link_problems(rel, text)] == []
    # Not vacuous: every page type that links to the App Store was checked.
    linked = {rel for rel, text in pages.items() if _apple_links(text)}
    for rel in ("index.html", "404.html", "shows/index.html", "airing/index.html"):
        assert rel in linked, rel
    assert "press/index.html" in linked
    assert sum(len(_apple_links(pages[rel])) == 2 for rel in linked) >= 1  # a show page


def test_every_price_on_the_built_site_is_the_us_price_with_its_country(pages):
    assert [p for rel, text in pages.items() for p in price_problems(rel, text)] == []
    # Not vacuous: the badge block, the show-page line and the press page
    # each print it.
    priced = {rel for rel, text in pages.items() if app_store.PRICE in _body_text(text)}
    assert {"index.html", "404.html", "shows/index.html", "airing/index.html"} <= priced
    assert "press/index.html" in priced
    assert any(_body_text(pages[rel]).count(app_store.PRICE_US) == 2 for rel in priced)


def test_no_page_says_the_app_is_sold_everywhere(pages):
    assert [p for rel, text in pages.items() for p in everywhere_problems(rel, text)] == []
    for copy in (app_store.PRICE_COPY, app_store.APP_PITCH, *_TOP_LINES):
        assert not any(word in copy.lower() for word in EVERYWHERE), copy


def test_the_press_page_names_the_price_as_the_us_price(pages):
    assert f"iPhone, {app_store.PRICE_US}, one-time purchase." in _body_text(
        pages["press/index.html"]
    )


# --- negative controls ----------------------------------------------------


def test_negative_control_a_us_storefront_link_is_caught(pages):
    rel = "index.html"
    neutral = f"https://{APPLE_HOST}{NEUTRAL_PATH}"
    assert neutral in pages[rel]
    sabotaged = pages[rel].replace(neutral, f"https://{APPLE_HOST}/us{NEUTRAL_PATH}", 1)
    assert sabotaged != pages[rel]  # the sabotage landed
    assert link_problems(rel, sabotaged)


@pytest.mark.parametrize(
    ("old", "new"),
    [
        (" in the US", ""),  # the bare figure
        ("$4.99", "C$6.99"),  # another storefront's price, typed by hand
        ("$4.99", "$2.99"),  # not the listing's price
    ],
)
def test_negative_control_a_price_without_its_country_is_caught(pages, old, new):
    rel = "index.html"
    assert price_problems(rel, pages[rel]) == []
    sabotaged = pages[rel].replace(old, new, 1)
    assert sabotaged != pages[rel]  # the sabotage landed
    assert price_problems(rel, sabotaged)


@pytest.mark.parametrize("claim", ["worldwide", "in every country", "at your local price"])
def test_negative_control_an_everywhere_claim_is_caught(pages, claim):
    rel = "index.html"
    assert everywhere_problems(rel, pages[rel]) == []
    sabotaged = pages[rel].replace(
        "the App Store shows the local price where the app is sold.",
        f"on the App Store {claim}.",
        1,
    )
    assert sabotaged != pages[rel]  # the sabotage landed
    assert everywhere_problems(rel, sabotaged)
