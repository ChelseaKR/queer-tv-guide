"""App Store campaign links (DECISIONS 0056): every App Store link the site
publishes carries Apple's provider token (pt) and one campaign token (ct) per
page type, once the provider token is filled in, and the site gains no
analytics: no script but structured data, nothing loaded from another host,
no cookie, no beacon.

The checkers are plain functions so the negative controls at the bottom can
sabotage a built page and prove each one fails."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from qtv_pipeline import app_store, show_pages, site_index
from tests import htmlprobe

REPO = Path(__file__).resolve().parents[2]
FIXTURE = REPO / "ios" / "GuideCore" / "Tests" / "Fixtures" / "snapshot.fixture.json"
BASE = "https://example.test/qf"
# Apple's own example provider token, from its campaign links help page. A
# test value only: the shipped constant is None until the owner pastes theirs.
TEST_PT = "123456"
APPLE_HOST = "apps.apple.com"

# Words that mean a page is measuring its visitors. None may appear in a
# built page, in any case.
ANALYTICS_MARKERS = (
    "googletagmanager",
    "google-analytics",
    "gtag(",
    "plausible",
    "posthog",
    "segment.com",
    "facebook.net",
    "fbq(",
    "sendbeacon",
    "document.cookie",
    "set-cookie",
    "<iframe",
    "<noscript",
)


@pytest.fixture
def doc() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _built_site(doc: dict, tmp_path: Path) -> dict[str, str]:
    """Build the whole site the way snapshot.yml does, switch on, and return
    every HTML page by its path."""
    show_pages.build_site(doc, tmp_path, base_url=BASE, app_store_live=True)
    site_index.write_site(doc, tmp_path / "index.html", base_url=BASE, app_store_live=True)
    app_store.apply(tmp_path)
    return {
        str(p.relative_to(tmp_path)): p.read_text(encoding="utf-8")
        for p in sorted(tmp_path.rglob("*.html"))
    }


def _expected_campaigns(rel: str) -> list[str]:
    """The campaign tokens a page's App Store links carry, in page order."""
    if rel == "index.html":
        return ["home"]
    if rel == "404.html":
        return ["notfound"]
    if rel == "shows/index.html":
        return ["shows"]
    if rel == "airing/index.html":
        return ["airing"]
    if rel == "press/index.html":
        return ["press"]
    if rel.startswith("shows/"):
        return ["show-top", "show"]
    return []


def campaign_problems(rel: str, text: str, pt: str) -> list[str]:
    """Every App Store link must carry the provider token, the page type's
    campaign token and Apple's media type, and nothing else."""
    found: list[str] = []
    links = [h for h in htmlprobe.parse(text).hrefs() if urlsplit(h).hostname == APPLE_HOST]
    campaigns = []
    for href in links:
        parts = urlsplit(href)
        query = parse_qs(parts.query)
        if f"{parts.scheme}://{parts.netloc}{parts.path}" != app_store.APP_STORE_URL:
            found.append(f"{rel}: {href} is not the listing URL")
        if query.get("pt") != [pt] or query.get("mt") != ["8"] or len(query.get("ct", [])) != 1:
            found.append(f"{rel}: {href} lacks pt, ct or mt")
            continue
        if set(query) != {"pt", "ct", "mt"}:
            found.append(f"{rel}: {href} carries another parameter")
        campaigns.append(query["ct"][0])
    if campaigns != _expected_campaigns(rel):
        found.append(f"{rel}: campaigns {campaigns}, expected {_expected_campaigns(rel)}")
    return found


def analytics_problems(rel: str, text: str) -> list[str]:
    """No script but structured data, nothing loaded from another host, and
    no analytics, cookie or beacon marker anywhere in the page."""
    found: list[str] = []
    page = htmlprobe.parse(text)
    for tag, attrs in page.tags:
        if tag == "script" and (attrs.get("type") != "application/ld+json" or attrs.get("src")):
            found.append(f"{rel}: a script that is not structured data")
        src = attrs.get("src")
        if src and not src.startswith(f"{BASE}/") and "/" in src:
            found.append(f"{rel}: {tag} loads {src}")
        if tag in {"iframe", "embed", "object", "form"}:
            found.append(f"{rel}: a {tag} element")
    found += [f"{rel}: <link> {a}" for a in htmlprobe.foreign_links(page, BASE)]
    lowered = text.lower()
    found += [f"{rel}: contains {m!r}" for m in ANALYTICS_MARKERS if m in lowered]
    return found


# --- the link helper ------------------------------------------------------


def test_every_campaign_token_is_plain_lowercase_and_within_apples_limit():
    # Apple: "You can use up to 30 alphanumeric characters and spaces".
    for token in app_store.CAMPAIGNS:
        assert 0 < len(token) <= app_store.CAMPAIGN_MAX == 30, token
        assert token == token.lower() and token.replace("-", "").isalnum(), token
    # One per page type, not per page: a short Campaigns list in App Store
    # Connect, each row reaching Apple's five-download floor sooner.
    assert len(app_store.CAMPAIGNS) <= 10


def test_the_shipped_provider_token_is_none_or_digits():
    # The owner pastes the digits from App Store Connect; a placeholder word
    # or an invented number must never ship as a link parameter.
    token = app_store.APP_STORE_PROVIDER_TOKEN
    assert token is None or token.isdigit()


def test_without_a_provider_token_every_link_is_the_plain_listing(monkeypatch):
    # A campaign token alone is not what Apple documents; publish nothing
    # half-measured.
    monkeypatch.setattr(app_store, "APP_STORE_PROVIDER_TOKEN", None)
    for token in app_store.CAMPAIGNS:
        assert app_store.app_store_link(token) == app_store.APP_STORE_URL


def test_with_a_provider_token_the_link_carries_pt_ct_and_mt():
    url = app_store.app_store_link("show", TEST_PT)
    parts = urlsplit(url)
    assert f"{parts.scheme}://{parts.netloc}{parts.path}" == app_store.APP_STORE_URL
    assert parse_qs(parts.query) == {"pt": [TEST_PT], "ct": ["show"], "mt": ["8"]}


@pytest.mark.parametrize("campaign", ["Show", "per-page-the-mentalist", "", "show top"])
def test_an_undeclared_campaign_token_is_refused(campaign):
    with pytest.raises(app_store.CampaignError):
        app_store.app_store_link(campaign, TEST_PT)


def test_a_provider_token_that_is_not_digits_is_refused():
    with pytest.raises(app_store.CampaignError):
        app_store.app_store_link("show", "PASTE_PROVIDER_TOKEN_HERE")


def test_a_declared_token_of_the_wrong_shape_is_refused(monkeypatch):
    # The shape check is a second wall behind the declared set.
    long = "a" * 31
    monkeypatch.setattr(app_store, "CAMPAIGNS", frozenset({long, "Upper"}))
    for bad in (long, "Upper"):
        with pytest.raises(app_store.CampaignError):
            app_store.app_store_link(bad, TEST_PT)


# --- the built site -------------------------------------------------------


def test_every_app_store_link_on_the_built_site_carries_pt_and_its_page_campaign(
    doc, tmp_path, monkeypatch
):
    monkeypatch.setattr(app_store, "APP_STORE_PROVIDER_TOKEN", TEST_PT)
    pages = _built_site(doc, tmp_path)
    problems = [p for rel, text in pages.items() for p in campaign_problems(rel, text, TEST_PT)]
    assert problems == []
    # Not vacuous: every page type that links to the App Store was built and
    # checked, and at least one show page.
    for rel in ("index.html", "404.html", "shows/index.html", "airing/index.html"):
        assert rel in pages, rel
    assert "press/index.html" in pages
    assert any(_expected_campaigns(r) == ["show-top", "show"] for r in pages)


def test_the_top_line_sits_before_the_answer_and_outside_it(doc, tmp_path, monkeypatch):
    """DECISIONS 0059: the line is above the "Does she die" paragraph, so on a
    phone's first screen, and still above the spoiler warning, the sealed
    answer and the badge."""
    monkeypatch.setattr(app_store, "APP_STORE_PROVIDER_TOKEN", TEST_PT)
    pages = _built_site(doc, tmp_path)
    shows = [r for r in pages if _expected_campaigns(r) == ["show-top", "show"]]
    assert len(shows) >= 3  # not vacuous: a running, an ended and an unscheduled show
    for rel in shows:
        text = pages[rel]
        assert text.count('<p class="app-line">') == 1, rel
        start = text.index('<p class="app-line">')
        line = text[start : text.index("</p>", start) + len("</p>")]
        assert line.count(app_store.app_store_link("show-top").replace("&", "&amp;")) == 1, rel
        # After the opening; above the paragraph that begins "Does she die
        # in", the spoiler warning, the sealed answer and the badge.
        assert (
            text.index('<p class="opening">')
            < start
            < text.index("<p>Does she die in ")
            < text.index('class="spoiler-warning"')
            < text.index('<details class="answer"')
            < text.index('<div class="get-app">')
        )
        page = htmlprobe.parse(text)
        assert not any("App Store" in t or app_store.PRICE in t for t in page.inside), rel
        # The price it states, before the tap, is the listing's one-time
        # price, named as the US price (DECISIONS 0058).
        assert f"a one-time purchase ({app_store.PRICE_US}), no subscription." in line, rel
        # The LezWatch.TV credit is untouched.
        assert "LezWatch.TV" in text


def test_the_built_site_has_no_analytics_and_loads_nothing_from_another_host(
    doc, tmp_path, monkeypatch
):
    monkeypatch.setattr(app_store, "APP_STORE_PROVIDER_TOKEN", TEST_PT)
    pages = _built_site(doc, tmp_path)
    assert [p for rel, text in pages.items() for p in analytics_problems(rel, text)] == []


def test_switch_off_publishes_no_app_store_link_at_all(doc, tmp_path, monkeypatch):
    monkeypatch.setattr(app_store, "APP_STORE_PROVIDER_TOKEN", TEST_PT)
    show_pages.build_site(doc, tmp_path, base_url=BASE)
    site_index.write_site(doc, tmp_path / "index.html", base_url=BASE)
    for p in tmp_path.rglob("*.html"):
        assert APPLE_HOST not in p.read_text(encoding="utf-8"), p


# --- negative controls ----------------------------------------------------


def test_negative_control_a_link_without_its_campaign_is_caught(doc, tmp_path, monkeypatch):
    monkeypatch.setattr(app_store, "APP_STORE_PROVIDER_TOKEN", TEST_PT)
    pages = _built_site(doc, tmp_path)
    rel = next(r for r in pages if _expected_campaigns(r) == ["show-top", "show"])
    good = app_store.app_store_link("show-top").replace("&", "&amp;")
    assert good in pages[rel]
    plain = pages[rel].replace(good, app_store.APP_STORE_URL, 1)
    assert plain != pages[rel]
    assert campaign_problems(rel, plain, TEST_PT)
    swapped = pages[rel].replace(good, good.replace("ct=show-top", "ct=show"), 1)
    assert swapped != pages[rel]
    assert campaign_problems(rel, swapped, TEST_PT)


@pytest.mark.parametrize(
    "planted",
    [
        '<script async src="https://www.googletagmanager.com/gtag/js?id=G-TEST"></script>',
        "<script>navigator.sendBeacon('/hit')</script>",
        '<img src="https://pixel.example.net/p.gif" width="1" height="1" alt="">',
        '<link rel="preconnect" href="https://cdn.example.net">',
    ],
)
def test_negative_control_planted_analytics_is_caught(doc, tmp_path, monkeypatch, planted):
    monkeypatch.setattr(app_store, "APP_STORE_PROVIDER_TOKEN", TEST_PT)
    pages = _built_site(doc, tmp_path)
    rel = "index.html"
    assert analytics_problems(rel, pages[rel]) == []
    sabotaged = pages[rel].replace("</head>", f"{planted}\n</head>", 1)
    assert sabotaged != pages[rel]
    assert analytics_problems(rel, sabotaged)
