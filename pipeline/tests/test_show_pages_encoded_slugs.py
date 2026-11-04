"""A show whose LezWatch slug carries percent-encoding gets a page that answers.

LezWatch publishes a non-Latin title's slug percent-encoded
("the-air-%e0%b9%80..."). The static host decodes a request's path before it
looks for the file, so a page written under the encoded name answers only a
double-encoded URL, and the URL in the sitemap and the shows index gets a 404.
On the 2026-11-03 live site that was 10 of 365 sitemap URLs.

Each check here resolves URLs the way the host does (decode the path, then
look for ``index.html`` under it), and every negative control asserts that
its sabotage changed something before it concludes anything.
"""

from __future__ import annotations

import urllib.parse

import pytest

from qtv_pipeline import show_pages
from tests import htmlprobe
from tests.test_show_pages_rule import _by_id, _sixty

BASE = "https://example.test"
# A real slug from the 2026-11-03 snapshot ("The Air" with its Thai title).
THAI = "the-air-%e0%b9%80%e0%b8%aa%e0%b8%99%e0%b9%88%e0%b8%ab%e0%b8%b2%e0%b8%a7%e0%b8%b2%e0%b9%82%e0%b8%a2"
THAI_DIR = urllib.parse.unquote(THAI)


def _unresolved(files: dict[str, str]) -> list[str]:
    """Every sitemap URL under /shows/ that does not resolve to a written
    page once decoded, as a static host resolves it."""
    missing = []
    for loc in htmlprobe.sitemap(files["sitemap.xml"])["loc"]:
        path = urllib.parse.urlsplit(loc).path
        if not path.startswith("/shows/"):
            continue
        name = urllib.parse.unquote(path).lstrip("/") + "index.html"
        if name not in files:
            missing.append(loc)
    return missing


def _thai_site() -> dict[str, str]:
    big = _sixty()
    _by_id(big, 1010)["slug"] = THAI
    assert _by_id(big, 1010)["slug"] == THAI  # the data change landed
    return show_pages.render_site(big, base_url=BASE)


def test_an_encoded_slug_is_written_decoded_and_linked_encoded():
    files = _thai_site()
    assert f"shows/{THAI_DIR}/index.html" in files
    assert f"shows/{THAI}/index.html" not in files
    assert f"{BASE}/shows/{THAI}/" in htmlprobe.sitemap(files["sitemap.xml"])["loc"]
    page = files[f"shows/{THAI_DIR}/index.html"]
    assert f'href="{BASE}/shows/{THAI}/"' in page  # the canonical keeps the encoded URL
    assert f"{THAI}/" in files["shows/index.html"]
    assert _unresolved(files) == []


def test_every_sitemap_url_resolves_on_a_plain_slug_site_too():
    files = show_pages.render_site(_sixty(), base_url=BASE)
    assert len(htmlprobe.sitemap(files["sitemap.xml"])["loc"]) == 62  # home, index, 60 shows
    assert _unresolved(files) == []


def test_negative_control_the_old_encoded_directory_is_caught(monkeypatch):
    monkeypatch.setattr(
        show_pages, "slug_dir", lambda slug: slug if show_pages.SLUG.fullmatch(slug) else None
    )
    files = _thai_site()
    assert f"shows/{THAI}/index.html" in files  # the sabotage landed
    assert _unresolved(files) == [f"{BASE}/shows/{THAI}/"]


def test_build_site_writes_the_decoded_directory(tmp_path):
    big = _sixty()
    _by_id(big, 1010)["slug"] = THAI
    show_pages.build_site(big, tmp_path, base_url=BASE, pinned=None)
    assert (tmp_path / "shows" / THAI_DIR / "index.html").is_file()
    assert not (tmp_path / "shows" / THAI).exists()


@pytest.mark.parametrize(
    "slug",
    [
        "a%2fb",  # decodes to a separator
        "a%5cb",  # a backslash
        "a%2525b",  # a second level of encoding
        "%2e%2e",  # a dot segment
        "a%20b",  # white space
        "a%00b",  # a control character
        "a%ffb",  # not UTF-8
    ],
)
def test_a_slug_that_decodes_to_something_unsafe_is_skipped(slug):
    assert show_pages.SLUG.fullmatch(slug)  # the old check alone would build it
    assert show_pages.slug_dir(slug) is None
    big = _sixty()
    _by_id(big, 1010)["slug"] = slug
    chosen, notes = show_pages.plan_selection(big)
    assert 1010 not in {s["lwtv_id"] for s in chosen} and len(chosen) == 59
    assert any("id 1010" in n and "unsafe slug for a path" in n for n in notes)


def test_a_plain_slug_is_its_own_directory():
    assert show_pages.slug_dir("the-l-word") == "the-l-word"
    assert show_pages.slug_dir("../escape") is None
