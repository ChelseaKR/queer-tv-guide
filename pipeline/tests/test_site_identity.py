"""The site's visual identity (DECISIONS 0038): its palette holds WCAG AA in
light and dark, a forced-colors palette still wins, motion waits for
prefers-reduced-motion, nothing in the stylesheet can show a closed answer,
and the not-found page and favicon are published with the home page.

Each checker has a negative control that sabotages the real stylesheet and
asserts the checker notices, so a checker that cannot fail would fail here."""

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
DOCS_SITE = REPO / "docs" / "site"
BASE = "https://example.test/qf"

# (text or mark, background, minimum ratio): body text at 4.5:1, the focus
# ring and drawn borders at 3:1 (WCAG 1.4.3 and 1.4.11).
PAIRS = [
    ("ink", "paper", 4.5),
    ("muted", "paper", 4.5),
    ("link", "paper", 4.5),
    ("visited", "paper", 4.5),
    ("ink", "surface", 4.5),
    ("muted", "surface", 4.5),
    ("link", "surface", 4.5),
    ("visited", "surface", 4.5),
    ("on-seal", "seal", 4.5),
    ("focus", "paper", 3.0),
    ("line", "paper", 3.0),
    ("seal", "paper", 3.0),
]


@pytest.fixture
def doc() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture
def css(doc) -> str:
    files = show_pages.render_site(doc, base_url=BASE)
    return htmlprobe.parse(files["shows/harbor-lights/index.html"]).css


def _luminance(hex_color: str) -> float:
    rgb = [int(hex_color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a: str, b: str) -> float:
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def _tokens(block: str) -> dict[str, str]:
    return dict(re.findall(r"--([a-z-]+):\s*(#[0-9a-f]{6})\b", block))


def schemes(css: str) -> dict[str, dict[str, str]]:
    """The light tokens (the first :root block) and the dark ones (the :root
    inside prefers-color-scheme: dark), dark falling back to light."""
    light = _tokens(css.split("@media (prefers-color-scheme: dark)")[0])
    dark_part = css.split("@media (prefers-color-scheme: dark)", 1)
    dark = _tokens(dark_part[1].split("}")[0]) if len(dark_part) == 2 else {}
    return {"light": light, "dark": {**light, **dark}}


def contrast_problems(css: str) -> list[str]:
    problems = []
    for name, tokens in schemes(css).items():
        for fg, bg, floor in PAIRS:
            if fg not in tokens or bg not in tokens:
                problems.append(f"{name}: --{fg} or --{bg} is missing")
                continue
            ratio = contrast(tokens[fg], tokens[bg])
            if ratio < floor:
                problems.append(f"{name}: --{fg} on --{bg} is {ratio:.2f}:1, under {floor}:1")
    return problems


def test_every_text_pair_meets_wcag_aa_in_light_and_dark(css):
    assert "color-scheme: light dark" in css
    found = schemes(css)
    assert found["light"] != found["dark"]
    assert contrast_problems(css) == []


def test_contrast_control_a_faint_link_fails(css):
    faint = css.replace("--link: #6a2c9c", "--link: #b9a3cc", 1)
    assert faint != css
    assert any("--link on --paper" in p for p in contrast_problems(faint))
    dark_faint = css.replace("--link: #d9b8ff", "--link: #4a3a5a", 1)
    assert dark_faint != css
    assert any(p.startswith("dark: --link") for p in contrast_problems(dark_faint))


def motion_problems(css: str) -> list[str]:
    """Any animation or transition outside the reduced-motion guard."""
    guard = "@media (prefers-reduced-motion: no-preference) {"
    outside = css
    if guard in css:
        head, tail = css.split(guard, 1)
        # The guard's block ends at the first line that closes it at two spaces.
        outside = head + tail.split("\n  }\n", 1)[-1]
    return [w for w in ("animation", "transition") if w + ":" in outside]


def test_motion_only_when_reduced_motion_is_not_asked_for(css):
    assert "@media (prefers-reduced-motion: no-preference)" in css
    assert motion_problems(css) == []
    loose = css + "\n  .cast li { transition: color 1s; }\n"
    assert motion_problems(loose) == ["transition"]


def test_forced_colors_hand_back_to_the_system(css):
    forced = css.split("@media (forced-colors: active)", 1)
    assert len(forced) == 2
    for token in ("Canvas", "CanvasText", "Highlight", "LinkText"):
        assert token in forced[1], token


def reveal_problems(css: str) -> list[str]:
    """Stylesheet rules that could draw a closed answer, or put words on the
    page that the HTML does not have."""
    flat = " ".join(css.split())
    problems = []
    if "::details-content" in flat or "content-visibility" in flat:
        problems.append("styles the details content slot")
    if "attr(" in flat:
        problems.append("copies an attribute into the page")
    for value in re.findall(r"content:\s*([^;}]+)", flat):
        if value.strip() != '"/"':
            problems.append(f"generated text {value.strip()}")
    for rule in re.findall(r"([^{}]*(?:answer-body|details\s*>)[^{}]*)\{([^}]*)\}", flat):
        if "display" in rule[1] or "position" in rule[1]:
            problems.append(f"moves or shows {rule[0].strip()}")
    return problems


def test_nothing_in_the_stylesheet_can_show_a_closed_answer(css):
    assert reveal_problems(css) == []
    for sabotage, want in (
        ("details.answer::details-content { content-visibility: visible; }", "slot"),
        (".answer-body { display: block !important; }", "moves or shows"),
        ("summary::after { content: attr(data-answer); }", "attribute"),
    ):
        assert any(want in p for p in reveal_problems(css + sabotage)), sabotage


def test_the_static_pages_use_the_same_palette(css):
    ours = schemes(css)
    for name in ("privacy.html", "support.html", "terms.html"):
        page = (DOCS_SITE / name).read_text(encoding="utf-8")
        style = page.split("<style>", 1)[1].split("</style>", 1)[0]
        theirs = schemes(style)
        for scheme in ("light", "dark"):
            shared = theirs[scheme].keys() & ours[scheme].keys()
            assert {"ink", "paper", "link", "muted"} <= shared, (name, scheme)
            assert {k: theirs[scheme][k] for k in shared} == {k: ours[scheme][k] for k in shared}, (
                name,
                scheme,
            )
        assert '<p class="brand"><a href="./">Queer Frame</a></p>' in page, name
        # These two are the App Store's privacy and support URLs, held to no
        # requests of their own (AppStoreReadinessTests), so no favicon link.
        assert "<link" not in page, name


def test_a_favicon_from_another_host_is_a_foreign_link():
    own = '<link rel="icon" href="https://example.test/qf/favicon.svg" type="image/svg+xml">'
    other = '<link rel="icon" href="https://cdn.example.com/favicon.svg" type="image/svg+xml">'
    assert htmlprobe.foreign_links(htmlprobe.parse(own), BASE) == []
    assert len(htmlprobe.foreign_links(htmlprobe.parse(other), BASE)) == 1


# --- the not-found page and the favicon -----------------------------------


def test_the_not_found_page_is_kept_out_of_search_and_links_home(doc):
    page = htmlprobe.parse(site_index.render_not_found(doc, base_url=BASE))
    assert page.canonical == ""
    assert {"name": "robots", "content": "noindex"} in page.named("meta")
    assert page.title == site_index.NOT_FOUND_TITLE
    assert [n for n in page.headings if n == 1] == [1]
    # Without the show pages it links only to the home page in its body.
    body_links = [a.get("href") for a in page.named("a") if a.get("href", "").startswith(BASE)]
    assert f"{BASE}/" in body_links
    assert f"{BASE}/shows/#a-to-z" not in body_links
    assert f"{BASE}/airing/" not in body_links
    full = htmlprobe.parse(
        site_index.render_not_found(doc, shows_link=True, airing_link=True, base_url=BASE)
    )
    assert {f"{BASE}/shows/#a-to-z", f"{BASE}/airing/"} <= set(full.hrefs())
    # The airing page is linked only beside the shows, as on the home page.
    alone = site_index.render_not_found(doc, airing_link=True, base_url=BASE)
    assert f"{BASE}/airing/" not in alone
    # No link is relative: the page answers at any depth.
    assert all(urlsplit(h).scheme == "https" or h == "#main" for h in full.hrefs())
    assert htmlprobe.foreign_links(full, BASE) == []


def test_the_not_found_page_offers_the_app_only_when_the_switch_is_on(doc):
    # DECISIONS 0047: a visitor who lands on a dead link can still find the
    # app, by the same block every page uses, with an absolute badge address
    # (the 404 page answers at any depth). The banner tag is left to
    # app_store.apply, which adds it to every top-level page.
    off = site_index.render_not_found(doc, shows_link=True, base_url=BASE)
    assert not any(m in off for m in ("apps.apple.com", "app-store-badge", "apple-itunes-app"))
    on = site_index.render_not_found(doc, shows_link=True, base_url=BASE, app_store_live=True)
    assert on.count(app_store.get_app_block(f"{BASE}/{app_store.BADGE_FILE}")) == 1
    assert on.count(app_store.BADGE_STYLE) == 1
    assert "apple-itunes-app" not in on
    page = htmlprobe.parse(on)
    assert [a.get("href") for a in page.named("a")].count(app_store.APP_STORE_URL) == 1
    assert [a["src"] for a in page.named("img")] == [f"{BASE}/{app_store.BADGE_FILE}"]


def test_write_site_passes_the_switch_to_the_not_found_page(doc, tmp_path):
    show_pages.build_site(doc, tmp_path, base_url=BASE, app_store_live=True)
    site_index.write_site(doc, tmp_path / "index.html", base_url=BASE, app_store_live=True)
    text = (tmp_path / "404.html").read_text(encoding="utf-8")
    assert app_store.APP_STORE_URL in text
    # The step after it (app_store.apply) adds the banner and the home badge.
    app_store.apply(tmp_path)
    assert (tmp_path / "404.html").read_text(encoding="utf-8").count("apple-itunes-app") == 1
    home = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert home.count(app_store.BADGE_BLOCK) == 1 and home.count(app_store.BADGE_STYLE) == 1


def test_the_not_found_page_names_no_character_and_no_death(doc):
    text = site_index.render_not_found(doc, shows_link=True, base_url=BASE)
    page = htmlprobe.parse(text)
    assert page.named("details") == []
    names = {c["name"] for c in doc["characters"]}
    assert not any(n in text for n in names)
    assert "dies" not in " ".join(page.outside).lower()


def test_write_site_publishes_the_not_found_page_and_the_favicon(doc, tmp_path):
    show_pages.build_site(doc, tmp_path, base_url=BASE)
    written = site_index.write_site(doc, tmp_path / "index.html", base_url=BASE)
    assert tmp_path / "404.html" in written and tmp_path / "favicon.svg" in written
    not_found = (tmp_path / "404.html").read_text(encoding="utf-8")
    assert f'href="{BASE}/shows/#a-to-z"' in not_found
    svg = (tmp_path / "favicon.svg").read_text(encoding="utf-8")
    assert svg.startswith("<svg ") and 'xmlns="http://www.w3.org/2000/svg"' in svg
    for forbidden in ("<script", "href", "<image", "<foreignObject", "url("):
        assert forbidden not in svg, forbidden
    # Every page names it from this site, and the header draws the same mark.
    home = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert f'<link rel="icon" href="{BASE}/favicon.svg" type="image/svg+xml">' in home
    assert svg.strip() in home


def test_the_header_mark_is_hidden_from_assistive_tech(doc):
    files = show_pages.render_site(doc, base_url=BASE)
    text = files["shows/harbor-lights/index.html"]
    svg = text.split("<svg", 1)[1].split(">", 1)[0]
    assert 'aria-hidden="true"' in svg and 'focusable="false"' in svg
    assert text.count("<svg") == 1
