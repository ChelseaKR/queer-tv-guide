"""The home page's WebSite node: the site's name and address, nothing more.

Search engines read it for the site-name line. It states only what the page
already shows: the header's brand and the page's canonical URL. There is no
SearchAction because the site has no search page, and no other page carries
a WebSite node.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from qtv_pipeline import show_pages, site_index
from tests import htmlprobe

REPO = Path(__file__).resolve().parents[2]
FIXTURE = REPO / "ios" / "GuideCore" / "Tests" / "Fixtures" / "snapshot.fixture.json"
DOMAIN = "https://queerframe.app"
BRAND = re.compile(r'<p class="brand"><a href="([^"]+)">([^<]+)</a></p>')


@pytest.fixture
def doc() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def website_problems(text: str) -> list[str]:
    """Why the home page's WebSite node is missing, extra, or says more than the page shows."""
    page = htmlprobe.parse(text)
    sites = [n for n in htmlprobe.ld_nodes(page) if n.get("@type") == "WebSite"]
    if len(sites) != 1:
        return [f"{len(sites)} WebSite nodes"]
    brand = BRAND.search(text)
    if brand is None:
        return ["no visible brand"]
    href, name = brand.groups()
    expected = {"@context": "https://schema.org", "@type": "WebSite", "name": name, "url": href}
    problems = []
    if sites[0] != expected:
        problems.append(f"{sites[0]} != {expected}")
    if sites[0].get("url") != page.canonical:
        problems.append("url is not the canonical URL")
    return problems


@pytest.mark.parametrize("base", [DOMAIN, "https://chelseakr.github.io/queer-tv-guide"])
def test_the_home_page_names_the_site(doc, base):
    text = site_index.render_index(doc, base_url=base)
    assert website_problems(text) == []
    page = htmlprobe.parse(text)
    assert htmlprobe.ld_nodes(page) == [
        {
            "@context": "https://schema.org",
            "@type": "WebSite",
            "name": "Queer Frame",
            "url": f"{base}/",
        }
    ]
    assert "potentialAction" not in text and "SearchAction" not in text


def test_no_other_page_carries_a_website_node(doc, tmp_path):
    site = tmp_path / "site"
    show_pages.build_site(doc, site)
    (site / "data").mkdir(exist_ok=True)
    (site / "data" / "index.html").write_text(site_index.render_data_page(doc), encoding="utf-8")
    pages = sorted(site.rglob("*.html"))
    assert len(pages) > 2
    for f in pages:
        nodes = htmlprobe.ld_nodes(htmlprobe.parse(f.read_text(encoding="utf-8")))
        assert all(n.get("@type") != "WebSite" for n in nodes), f


def test_negative_control_a_website_node_that_differs_is_caught(doc):
    text = site_index.render_index(doc)
    assert website_problems(text) == []
    sabotage = {
        "wrong name": ('"name": "Queer Frame"', '"name": "Queer Frame TV"'),
        "wrong url": (f'"url": "{DOMAIN}/"', f'"url": "{DOMAIN}/shows/"'),
        "search action": (
            f'"url": "{DOMAIN}/"',
            f'"url": "{DOMAIN}/", "potentialAction": {{"@type": "SearchAction"}}',
        ),
        "second node": (
            "</head>",
            '<script type="application/ld+json">{"@type": "WebSite"}</script></head>',
        ),
        "no node": ('"@type": "WebSite"', '"@type": "WebPage"'),
    }
    for what, (old, new) in sabotage.items():
        assert text.count(old) == 1, what
        broken = text.replace(old, new)
        assert broken != text, f"the sabotage did not apply: {what}"
        assert website_problems(broken), what
