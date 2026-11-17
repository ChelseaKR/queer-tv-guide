"""This repository's own Pages site (qtv_pipeline/github_io.py, DECISIONS 0062).

Built from the assembled website: the data file and its checksum byte for
byte, the privacy, support and terms pages with one added line that names
their address on the domain as canonical, a pointer page for every other
page, and a 404 page that asks not to be indexed. Nothing on it is an
indexable second copy of the website.

Every negative control asserts that its sabotage landed before it asserts
that the check caught it.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import shutil
from pathlib import Path

import pytest

from qtv_pipeline import app_store, github_io, show_pages, site_index
from tests import htmlprobe

REPO = Path(__file__).resolve().parents[2]
FIXTURE = REPO / "ios" / "GuideCore" / "Tests" / "Fixtures" / "snapshot.fixture.json"
DOCS_SITE = REPO / "docs" / "site"
DOMAIN = "https://queerframe.app"
KEPT_PAGES = ("privacy.html", "support.html", "terms.html")
DATA_FILES = ("snapshot.v1.json", "snapshot.v1.json.sha256")


@pytest.fixture
def site(tmp_path) -> Path:
    """The website as snapshot.yml assembles it, with the App Store switch on."""
    doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
    site_dir = tmp_path / "site"
    site_dir.mkdir()
    show_pages.build_site(doc, site_dir)
    data = json.dumps(doc).encode("utf-8")
    (site_dir / "snapshot.v1.json").write_bytes(data)
    (site_dir / "snapshot.v1.json.sha256").write_text(
        f"{hashlib.sha256(data).hexdigest()}  snapshot.v1.json\n", encoding="utf-8"
    )
    for name in KEPT_PAGES:
        shutil.copy(DOCS_SITE / name, site_dir / name)
    site_index.write_site(doc, site_dir / "index.html", app_store_live=True)
    app_store.apply(site_dir)
    return site_dir


def _built(site: Path, tmp_path: Path) -> dict[str, bytes]:
    out = tmp_path / "github-io"
    github_io.build(site, out)
    return {str(p.relative_to(out)): p.read_bytes() for p in sorted(out.rglob("*")) if p.is_file()}


def duplicate_problems(files: dict[str, bytes]) -> list[str]:
    """Every page that a search engine could file as a second copy of the
    website: a page with no canonical URL on the domain that does not ask to
    be left out, or a pointer that does not send the browser to its canonical
    URL at once."""
    found = []
    for name, data in files.items():
        if not name.endswith(".html"):
            continue
        page = htmlprobe.parse(data.decode("utf-8"))
        robots = [m.get("content") or "" for m in page.named("meta") if m.get("name") == "robots"]
        if not page.canonical:
            if not any("noindex" in r for r in robots):
                found.append(f"{name}: no canonical and no noindex")
            continue
        if not page.canonical.startswith(DOMAIN + "/"):
            found.append(f"{name}: canonical {page.canonical} is not on the domain")
        if name in KEPT_PAGES:
            continue
        refresh = [
            m.get("content") or "" for m in page.named("meta") if m.get("http-equiv") == "refresh"
        ]
        if refresh != [f"0; url={page.canonical}"]:
            found.append(f"{name}: does not send the browser to {page.canonical} at once")
    return found


def test_the_fixture_site_is_the_whole_website(site):
    names = {str(p.relative_to(site)) for p in site.rglob("*") if p.is_file()}
    assert {"index.html", "404.html", "sitemap.xml", "robots.txt", "shows/index.html"} <= names
    assert {"data/index.html", "press/index.html", "findings/finales/index.html"} <= names
    assert any(re.fullmatch(r"shows/[^/]+/index\.html", n) for n in names)


def test_the_data_file_and_its_checksum_are_byte_for_byte(site, tmp_path):
    files = _built(site, tmp_path)
    for name in DATA_FILES:
        assert files[name] == (site / name).read_bytes(), name
    digest = hashlib.sha256(files["snapshot.v1.json"]).hexdigest()
    assert files["snapshot.v1.json.sha256"].decode("utf-8").split()[0] == digest


def test_a_kept_page_is_the_websites_page_plus_one_canonical_line(site, tmp_path):
    files = _built(site, tmp_path)
    for name in KEPT_PAGES:
        source = (site / name).read_text(encoding="utf-8")
        line = f'<link rel="canonical" href="{DOMAIN}/{name}">\n'
        assert line not in source  # the website's page has none of its own
        built = files[name].decode("utf-8")
        assert built.count(line) == 1, name
        assert built.replace(line, "", 1) == source, name
        page = htmlprobe.parse(built)
        assert page.canonical == f"{DOMAIN}/{name}"
        # The one link element is the canonical: the page still loads nothing.
        assert [a.get("rel") for a in page.named("link")] == ["canonical"], name
        assert not {t for t, _ in page.tags} & {"script", "img", "iframe"}, name


def test_every_page_of_the_website_has_a_page_at_the_same_path(site, tmp_path):
    files = _built(site, tmp_path)
    website = {str(p.relative_to(site)) for p in site.rglob("*.html")}
    assert website == {n for n in files if n.endswith(".html")}
    assert len(website) >= 10  # the denominator: a site of nothing must not pass


def test_nothing_but_the_data_file_and_pages_is_published(site, tmp_path):
    files = _built(site, tmp_path)
    assert {n for n in files if not n.endswith(".html")} == set(DATA_FILES)
    for name in ("sitemap.xml", "robots.txt", "llms.txt", "favicon.svg"):
        assert (site / name).is_file(), name  # on the website, and not here
        assert name not in files


def test_no_page_is_an_indexable_second_copy(site, tmp_path):
    files = _built(site, tmp_path)
    assert duplicate_problems(files) == []


def test_a_pointer_names_the_page_it_stands_for(site, tmp_path):
    files = _built(site, tmp_path)
    for name, data in files.items():
        if not name.endswith(".html") or name in (*KEPT_PAGES, "404.html"):
            continue
        original = htmlprobe.parse((site / name).read_text(encoding="utf-8"))
        pointer = htmlprobe.parse(data.decode("utf-8"))
        assert pointer.canonical == original.canonical, name
        assert pointer.hrefs() == [original.canonical], name
    home = htmlprobe.parse(files["index.html"].decode("utf-8"))
    assert home.canonical == f"{DOMAIN}/"
    shows = htmlprobe.parse(files["shows/index.html"].decode("utf-8"))
    assert shows.canonical == f"{DOMAIN}/shows/"


def test_no_page_runs_code_or_loads_anything(site, tmp_path):
    files = _built(site, tmp_path)
    for name, data in files.items():
        if not name.endswith(".html") or name in KEPT_PAGES:
            continue
        page = htmlprobe.parse(data.decode("utf-8"))
        tags = {t for t, _ in page.tags}
        assert not tags & {"script", "img", "iframe", "style", "form"}, name
        links = [a for a in page.named("link") if a.get("rel") != "canonical"]
        assert links == [], name


def test_the_404_page_asks_not_to_be_indexed_and_links_to_the_domain(site, tmp_path):
    page = htmlprobe.parse(_built(site, tmp_path)["404.html"].decode("utf-8"))
    robots = [m.get("content") for m in page.named("meta") if m.get("name") == "robots"]
    assert robots == ["noindex"]
    assert page.hrefs() == [f"{DOMAIN}/"]
    assert not [m for m in page.named("meta") if m.get("http-equiv")]


def test_a_kept_page_that_already_names_the_domain_is_left_as_it_is():
    for name in KEPT_PAGES:
        source = (DOCS_SITE / name).read_text(encoding="utf-8")
        once = github_io.with_canonical(name, source)
        assert once != source
        assert github_io.with_canonical(name, once) == once


def test_a_page_with_no_canonical_points_to_its_own_path_on_the_domain(site, tmp_path):
    extra = site / "notes" / "a page" / "index.html"
    extra.parent.mkdir(parents=True)
    extra.write_text("<!doctype html><title>x</title>", encoding="utf-8")
    other = site / "notes" / "plain.html"
    other.write_text(
        '<!doctype html><link rel="canonical" href="https://example.com/plain.html">',
        encoding="utf-8",
    )
    files = _built(site, tmp_path)
    page = htmlprobe.parse(files["notes/a page/index.html"].decode("utf-8"))
    assert page.canonical == f"{DOMAIN}/notes/a%20page/"
    page = htmlprobe.parse(files["notes/plain.html"].decode("utf-8"))
    assert page.canonical == f"{DOMAIN}/notes/plain.html"
    assert duplicate_problems(files) == []


def test_a_url_is_escaped_in_the_pointer():
    target = f'{DOMAIN}/shows/a&b"c/'
    text = github_io.render_moved(target)
    page = htmlprobe.parse(text)
    assert page.canonical == target
    assert page.hrefs() == [target]
    assert 'a&b"c' not in text  # the raw characters never reach the markup


@pytest.mark.parametrize("name", [*DATA_FILES, *KEPT_PAGES])
def test_a_missing_file_refuses_and_writes_nothing(site, tmp_path, name):
    (site / name).unlink()
    out = tmp_path / "github-io"
    with pytest.raises(github_io.GithubIoError, match=re.escape(name)):
        github_io.build(site, out)
    assert not out.exists()


@pytest.mark.parametrize("name", KEPT_PAGES)
def test_a_kept_page_that_cannot_take_its_canonical_refuses(site, tmp_path, name):
    page = site / name
    text = page.read_text(encoding="utf-8")
    out = tmp_path / "github-io"
    elsewhere = f'<link rel="canonical" href="https://example.com/{name}">\n</head>'
    page.write_text(text.replace("</head>", elsewhere, 1), encoding="utf-8")
    assert page.read_text(encoding="utf-8") != text  # the sabotage landed
    with pytest.raises(github_io.GithubIoError, match="canonical"):
        github_io.build(site, out)
    page.write_text(text.replace("</head>", "", 1), encoding="utf-8")
    assert page.read_text(encoding="utf-8") != text
    with pytest.raises(github_io.GithubIoError, match="expected exactly one"):
        github_io.build(site, out)
    assert not out.exists()


def test_a_used_output_directory_refuses(site, tmp_path):
    out = tmp_path / "github-io"
    out.mkdir()
    github_io.build(site, out)  # empty: allowed
    before = sorted(p.name for p in out.iterdir())
    with pytest.raises(github_io.GithubIoError, match="not empty"):
        github_io.build(site, out)
    assert sorted(p.name for p in out.iterdir()) == before


def test_the_command_line(site, tmp_path, capsys):
    out = tmp_path / "github-io"
    assert github_io.main([str(site), str(out)]) == 0
    pages = len(list(site.rglob("*.html")))
    said = capsys.readouterr().out
    assert f"wrote {pages + 2} files" in said
    assert f"{pages - 4} pointers to {DOMAIN}" in said
    assert github_io.main([str(site)]) == 2
    assert "usage:" in capsys.readouterr().err
    (site / "privacy.html").unlink()
    assert github_io.main([str(site), str(tmp_path / "again")]) == 1
    assert "refused, nothing written" in capsys.readouterr().err
    assert not (tmp_path / "again").exists()


# ---- negative controls --------------------------------------------------------


def test_negative_control_a_full_copy_of_a_page_is_caught(site, tmp_path):
    files = _built(site, tmp_path)
    sabotaged = copy.copy(files)
    sabotaged["index.html"] = (site / "index.html").read_bytes()
    assert sabotaged["index.html"] != files["index.html"]
    assert any("index.html: does not send" in p for p in duplicate_problems(sabotaged))


def test_negative_control_a_page_with_no_canonical_is_caught(site, tmp_path):
    files = _built(site, tmp_path)
    sabotaged = copy.copy(files)
    stripped = re.sub(rb'<link rel="canonical"[^>]*>\n', b"", files["privacy.html"])
    assert stripped != files["privacy.html"]
    sabotaged["privacy.html"] = stripped
    assert duplicate_problems(sabotaged) == ["privacy.html: no canonical and no noindex"]


def test_negative_control_a_canonical_off_the_domain_is_caught(site, tmp_path):
    files = _built(site, tmp_path)
    sabotaged = copy.copy(files)
    moved = files["shows/index.html"].replace(DOMAIN.encode(), b"https://example.com")
    assert moved != files["shows/index.html"]
    sabotaged["shows/index.html"] = moved
    assert any("not on the domain" in p for p in duplicate_problems(sabotaged))
