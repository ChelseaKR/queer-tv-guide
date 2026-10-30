"""Publishing the show pages on the site's own domain (DECISIONS 0020).

What is checked here: every URL a page, the sitemap and robots.txt name is on
https://queerframe.app and nowhere on github.io; the sitemap lists the shows
index and every built page with the snapshot's own date (never the clock); the
robots.txt is allow-all and names that sitemap; the home page links to the
shows index only when the shows are published beside it; and the generator,
run the way snapshot.yml runs it, cannot fail the workflow.

Every negative control asserts that its sabotage landed (the fault is really
in the files) before it asserts that the checker caught it.
"""

from __future__ import annotations

import copy
import datetime as dt
import html
import json
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from qtv_pipeline import show_pages, site_index
from tests import htmlprobe

REPO = Path(__file__).resolve().parents[2]
FIXTURE = REPO / "ios" / "GuideCore" / "Tests" / "Fixtures" / "snapshot.fixture.json"
DOMAIN = "https://queerframe.app"
GITHUB_IO = "https://chelseakr.github.io/queer-tv-guide"
DATA_DATE = "2001-02-03"  # far from any wall clock the suite could run on


@pytest.fixture
def doc() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _big_doc(doc: dict, shows: int = 60) -> dict:
    """The fixture grown to `shows` shows, each with one listed character."""
    big = copy.deepcopy(doc)
    template_show = big["shows"][0]
    template_char = big["characters"][0]
    big["shows"], big["characters"] = [], []
    for i in range(shows):
        show = copy.deepcopy(template_show)
        show.update(
            id=f"lwtv:show:{1000 + i}",
            lwtv_id=1000 + i,
            slug=f"show-{i:03d}",
            title=f"Show {i:03d}",
        )
        char = copy.deepcopy(template_char)
        char.update(id=f"lwtv:character:{2000 + i}", lwtv_id=2000 + i, slug=f"char-{i:03d}")
        char["shows"] = [{**template_char["shows"][0], "show_id": show["id"]}]
        big["shows"].append(show)
        big["characters"].append(char)
    big["generated_at"] = f"{DATA_DATE}T04:05:06Z"
    return big


def _site(doc: dict, tmp_path: Path, **kw) -> dict[str, str]:
    show_pages.build_site(doc, tmp_path, **kw)
    return {
        str(p.relative_to(tmp_path)): p.read_text(encoding="utf-8")
        for p in sorted(tmp_path.rglob("*"))
        if p.is_file()
    }


# ---- checkers (each has a negative control below) ----------------------------


def host_problems(files: dict[str, str]) -> list[str]:
    """Any canonical, internal link, breadcrumb item, sitemap entry or robots
    Sitemap line that is not on the domain, and any github.io anywhere."""
    found = [f"{name}: github.io" for name, text in files.items() if "github.io" in text]
    for name, text in files.items():
        if name.endswith(".html"):
            page = htmlprobe.parse(text)
            urls = [page.canonical]
            urls += [h for h in page.hrefs() if urlsplit(h).hostname in (None, "queerframe.app")]
            for node in htmlprobe.ld_nodes(page):
                if node["@type"] == "BreadcrumbList":
                    urls += [i["item"] for i in node["itemListElement"]]
                elif node["@type"] == "ItemList":
                    urls += [i["url"] for i in node["itemListElement"]]
                else:
                    urls.append(node["url"])
            found += [
                f"{name}: {u}"
                for u in urls
                if u.startswith("http") and not u.startswith(DOMAIN + "/")
            ]
    for loc in htmlprobe.sitemap(files["sitemap.xml"])["loc"]:
        if not loc.startswith(DOMAIN + "/"):
            found.append(f"sitemap.xml: {loc}")
    for line in files["robots.txt"].splitlines():
        if line.startswith("Sitemap:") and line != f"Sitemap: {DOMAIN}/sitemap.xml":
            found.append(f"robots.txt: {line}")
    return found


def sitemap_problems(files: dict[str, str], doc: dict, limit: int = 50) -> list[str]:
    """The home page, the shows index and every built page are listed, with
    the data date."""
    entries = htmlprobe.sitemap(files["sitemap.xml"])
    pages = [n for n in files if n.endswith("index.html") and n.startswith("shows/")]
    want = {f"{DOMAIN}/", *(f"{DOMAIN}/{n.removesuffix('index.html')}" for n in pages)}
    found = [f"missing from the sitemap: {u}" for u in sorted(want - set(entries["loc"]))]
    found += [f"not a built page: {u}" for u in sorted(set(entries["loc"]) - want)]
    if len(pages) != min(limit, len(doc["shows"])) + 1:
        found.append(f"{len(pages)} pages built")
    date = doc["generated_at"][:10]
    found += [f"lastmod {d} is not the data date {date}" for d in entries["lastmod"] if d != date]
    return found


# ---- the domain -------------------------------------------------------------


def test_the_default_base_url_is_the_domain():
    assert show_pages.DEFAULT_BASE_URL == DOMAIN


def test_every_url_defaults_to_the_domain(doc, tmp_path):
    files = _site(_big_doc(doc), tmp_path)  # no base_url passed
    assert sum(n.endswith("index.html") for n in files) == 51
    assert host_problems(files) == []
    page = htmlprobe.parse(files["shows/show-007/index.html"])
    assert page.canonical == f"{DOMAIN}/shows/show-007/"
    crumbs = htmlprobe.ld_node(page, "BreadcrumbList")["itemListElement"]
    assert [c["item"] for c in crumbs] == [f"{DOMAIN}/", f"{DOMAIN}/shows/", page.canonical]
    assert f"{DOMAIN}/" in page.hrefs()
    assert f"{DOMAIN}/privacy.html" in page.hrefs()


def test_the_cli_default_is_the_domain(doc, tmp_path):
    snap = tmp_path / "snap.json"
    snap.write_text(json.dumps(_big_doc(doc)), encoding="utf-8")
    out = tmp_path / "out"
    assert show_pages.main([str(snap), str(out)]) == 0
    files = {
        str(p.relative_to(out)): p.read_text(encoding="utf-8")
        for p in out.rglob("*")
        if p.is_file()
    }
    assert host_problems(files) == []
    assert files["robots.txt"].endswith(f"Sitemap: {DOMAIN}/sitemap.xml\n")


def test_negative_control_a_github_io_canonical_is_caught(doc, tmp_path):
    files = _site(_big_doc(doc), tmp_path, base_url=GITHUB_IO)
    page = htmlprobe.parse(files["shows/show-001/index.html"])
    assert page.canonical.startswith("https://chelseakr.github.io/")  # the sabotage landed
    problems = host_problems(files)
    assert any("shows/show-001/index.html" in p for p in problems)
    assert any(p.startswith("sitemap.xml") for p in problems)
    assert any(p.startswith("robots.txt") for p in problems)


def test_negative_control_one_stray_internal_link_is_caught(doc, tmp_path):
    files = _site(_big_doc(doc), tmp_path)
    name = "shows/show-002/index.html"
    stray = files[name].replace(f'href="{DOMAIN}/shows/"', f'href="{GITHUB_IO}/shows/"')
    assert stray != files[name]  # the sabotage landed
    files[name] = stray
    assert host_problems(files)


# ---- the sitemap ------------------------------------------------------------


def test_the_sitemap_lists_the_index_and_the_fifty_pages_with_the_data_date(doc, tmp_path):
    big = _big_doc(doc)
    files = _site(big, tmp_path)
    assert sitemap_problems(files, big) == []
    entries = htmlprobe.sitemap(files["sitemap.xml"])
    assert len(entries["loc"]) == 52
    assert entries["loc"][0] == f"{DOMAIN}/"
    assert set(entries["lastmod"]) == {DATA_DATE}
    assert f"{DOMAIN}/shows/" in entries["loc"]
    assert f"{DOMAIN}/shows/show-000/" in entries["loc"]
    # 60 shows are in the snapshot, 50 are built: the other 10 are not listed.
    assert f"{DOMAIN}/shows/show-059/" not in entries["loc"]


def test_lastmod_is_the_snapshots_date_not_the_clock(doc, tmp_path, monkeypatch):
    class Frozen(dt.date):
        @classmethod
        def today(cls):
            return cls(2099, 12, 31)

    monkeypatch.setattr(dt, "date", Frozen)
    assert dt.date.today().isoformat() == "2099-12-31"  # the clock is far from the data
    files = _site(_big_doc(doc), tmp_path)
    assert "2099" not in files["sitemap.xml"]
    assert set(htmlprobe.sitemap(files["sitemap.xml"])["lastmod"]) == {DATA_DATE}


def test_negative_control_a_wall_clock_lastmod_is_caught(doc, tmp_path):
    big = _big_doc(doc)
    files = _site(big, tmp_path)
    clock = dt.datetime.now(dt.UTC).date().isoformat()
    assert clock != DATA_DATE
    files["sitemap.xml"] = files["sitemap.xml"].replace(DATA_DATE, clock)
    assert set(htmlprobe.sitemap(files["sitemap.xml"])["lastmod"]) == {clock}  # landed
    assert sitemap_problems(files, big)


def test_negative_control_a_page_missing_from_the_sitemap_is_caught(doc, tmp_path):
    big = _big_doc(doc)
    files = _site(big, tmp_path)
    before = htmlprobe.sitemap(files["sitemap.xml"])["loc"]
    kept = [line for line in files["sitemap.xml"].splitlines() if "/shows/show-010/" not in line]
    files["sitemap.xml"] = "\n".join(kept) + "\n"
    after = htmlprobe.sitemap(files["sitemap.xml"])["loc"]
    assert len(after) == len(before) - 1  # the sabotage landed
    assert any("show-010" in p for p in sitemap_problems(files, big))


def test_negative_control_an_unbuilt_page_in_the_sitemap_is_caught(doc, tmp_path):
    big = _big_doc(doc)
    files = _site(big, tmp_path)
    ghost = f"<url><loc>{DOMAIN}/shows/show-059/</loc><lastmod>{DATA_DATE}</lastmod></url>\n"
    files["sitemap.xml"] = files["sitemap.xml"].replace("</urlset>", ghost + "</urlset>")
    assert "show-059" in files["sitemap.xml"]  # landed
    assert any("show-059" in p for p in sitemap_problems(files, big))


# ---- robots.txt -------------------------------------------------------------

ROBOTS = "User-agent: *\nAllow: /\n\nSitemap: https://queerframe.app/sitemap.xml\n"


def test_robots_txt_allows_all_and_names_the_sitemap(doc, tmp_path):
    files = _site(_big_doc(doc), tmp_path)
    assert files["robots.txt"] == ROBOTS
    assert "Disallow" not in files["robots.txt"]
    assert show_pages.render_robots(base_url="https://x.test") == (
        "User-agent: *\nAllow: /\n\nSitemap: https://x.test/sitemap.xml\n"
    )


# ---- the home page (site_index.py, DECISIONS 0026) ----------------------------


def _pinned_file(tmp_path: Path, ids: list[int]) -> Path:
    body = {
        "how_chosen": "test list",
        "shows": [
            {"lezwatch_id": i, "slug": f"show-{i - 1000:03d}", "title": "t", "reason": "test"}
            for i in ids
        ],
    }
    path = tmp_path / "pinned.json"
    path.write_text(json.dumps(body), encoding="utf-8")
    return path


def _home_hrefs_into_shows(text: str) -> list[str]:
    return [h for h in htmlprobe.parse(text).hrefs() if "/shows/" in h]


def test_the_home_page_links_to_the_shows_only_when_they_are_published(doc, tmp_path):
    big = _big_doc(doc)
    site = tmp_path / "site"
    site.mkdir()
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text(json.dumps(big), encoding="utf-8")
    pinned = _pinned_file(tmp_path, [1007, 1003, 1999])  # 1999 is not in the snapshot

    # Shows not published: no link into them, and the page is still whole.
    site_index.write_site(big, site / "index.html", pinned_path=pinned)
    bare = (site / "index.html").read_text(encoding="utf-8")
    assert _home_hrefs_into_shows(bare) == []
    assert bare == site_index.render_index(big)
    assert "Queer Frame is a guide to TV shows" in bare

    # Shows published beside it: the hand-picked list first, then A to Z,
    # and each hand-picked show that has a page, in the list's order.
    show_pages.build_site(big, site, pinned=show_pages.load_pinned(pinned))
    assert (site / "shows" / "index.html").is_file()
    assert site_index.main([str(snapshot), str(site / "index.html")]) == 0  # default list
    site_index.write_site(big, site / "index.html", pinned_path=pinned)
    text = (site / "index.html").read_text(encoding="utf-8")
    assert _home_hrefs_into_shows(text) == [
        f"{DOMAIN}/shows/#hand-picked",
        f"{DOMAIN}/shows/#a-to-z",
        f"{DOMAIN}/shows/show-007/",
        f"{DOMAIN}/shows/show-003/",
    ]
    assert "Start with the 2 hand-picked shows" in text
    assert "Browse all 50 shows, A to Z" in text
    for href in _home_hrefs_into_shows(text):
        path = href.removeprefix(f"{DOMAIN}/").split("#")[0]
        assert (site / path / "index.html").is_file(), href
    assert "<script" not in text


def test_the_home_page_head_is_complete_and_within_limits(doc):
    page = htmlprobe.parse(site_index.render_index(doc))
    assert page.lang == "en"
    assert page.canonical == f"{DOMAIN}/"
    assert 0 < len(page.title) <= show_pages.TITLE_MAX
    assert 0 < len(page.description) <= show_pages.DESCRIPTION_MAX
    og = {a.get("property"): a.get("content") for a in page.named("meta") if a.get("property")}
    assert og["og:type"] == "website" and og["og:url"] == f"{DOMAIN}/"
    assert og["og:site_name"] == "Queer Frame"
    assert og["og:title"] and og["og:description"] == page.description
    assert not any(k in og for k in ("og:image", "og:video", "og:audio"))
    assert page.headings.count(1) == 1 and page.headings[0] == 1
    assert all(b - a <= 1 for a, b in zip(page.headings, page.headings[1:], strict=False))
    names = [t for t, _ in page.tags]
    for landmark in ("header", "main", "footer"):
        assert names.count(landmark) == 1, landmark
    skip = next(a for a in page.named("a") if a.get("class") == "skip")
    assert skip["href"] == "#main" and "main" in page.ids


def test_the_home_page_loads_nothing_from_anywhere(doc):
    page = htmlprobe.parse(site_index.render_index(doc))
    assert page.named("script") == []
    for forbidden in ("img", "iframe", "form", "input", "video", "audio", "object", "embed"):
        assert page.named(forbidden) == [], forbidden
    assert [a for a in page.named("link") if a.get("rel") != "canonical"] == []
    assert [a for t, a in page.tags if "src" in a or "srcset" in a] == []
    assert "url(" not in page.css and "@import" not in page.css
    hosts = {urlsplit(h).hostname for h in page.hrefs() if h.startswith("http")}
    assert hosts <= {"queerframe.app", "lezwatchtv.com", "www.tvmaze.com", "creativecommons.org"}


def _answers_for(doc: dict, shows: list[dict]) -> list[str]:
    found = []
    for show in shows:
        cast = show_pages._characters(doc, show)
        found.append(show_pages._answer(show, cast).headline)
        found += [c.status for c in cast if c.dies]
        found += [c.name for c in cast]
    return found


def home_spoilers(text: str, doc: dict) -> list[str]:
    """Anything on the home page, its title, description or Open Graph tags
    that answers "does she die" for any show, or a closed answer element."""
    page = htmlprobe.parse(text)
    meta = [a.get("content") or "" for a in page.named("meta")]
    visible = [*page.outside, *page.inside, page.title, page.description, *meta]
    found = [
        f"answer: {a}" for a in _answers_for(doc, doc["shows"]) if any(a in v for v in visible)
    ]
    found += [f"<details> x{len(page.named('details'))}"] if page.named("details") else []
    found += [
        f"word: {w}" for w in ("Dies", "died", "killed", "dead") if any(w in v for v in visible)
    ]
    return found


def test_the_home_page_answers_nothing(doc, tmp_path):
    site = tmp_path / "site"
    show_pages.build_site(doc, site)
    pinned = tmp_path / "pinned.json"
    pinned.write_text(
        json.dumps(
            {
                "how_chosen": "test",
                "shows": [
                    {"lezwatch_id": s["lwtv_id"], "slug": s["slug"], "title": "t", "reason": "r"}
                    for s in doc["shows"]
                ],
            }
        ),
        encoding="utf-8",
    )
    site_index.write_site(doc, site / "index.html", pinned_path=pinned)
    text = (site / "index.html").read_text(encoding="utf-8")
    # Denominator: the fixture has a recorded death and the home page names its show.
    assert any(c["death"]["died"] is True for c in doc["characters"])
    assert all(f"{DOMAIN}/shows/{s}/" in text for s in ("harbor-lights", "salt-and-ember"))
    assert home_spoilers(text, doc) == []


def test_negative_control_a_leaked_answer_on_the_home_page_is_caught(doc):
    text = site_index.render_index(doc)
    show = next(s for s in doc["shows"] if any(c.dies for c in show_pages._characters(doc, s)))
    headline = show_pages._answer(show, show_pages._characters(doc, show)).headline
    for where in ("</main>", "</title>"):
        leaked = text.replace(where, f"<p>{html.escape(headline)}</p>{where}", 1)
        assert leaked != text, "the sabotage did not apply"
        assert home_spoilers(leaked, doc), where
    in_meta = text.replace(
        'property="og:description" content="',
        f'property="og:description" content="{html.escape(headline)} ',
        1,
    )
    assert in_meta != text, "the sabotage did not apply"
    assert home_spoilers(in_meta, doc)


def test_the_data_page_keeps_the_old_index_content(doc, tmp_path):
    site = tmp_path / "site"
    site.mkdir()
    site_index.write_site(doc, site / "index.html")
    data = htmlprobe.parse((site / "data" / "index.html").read_text(encoding="utf-8"))
    hrefs = data.hrefs()
    for name in ("snapshot.v1.json", "snapshot.v1.json.sha256"):
        assert f"{DOMAIN}/{name}" in hrefs, name
    assert data.canonical == f"{DOMAIN}/data/"
    text = " ".join(data.outside)
    for fact in ("generated_at", "content_digest", "TVmaze joined", doc["content_digest"]):
        assert fact in text, fact
    assert [a.get("type") for a in data.named("script")] == ["application/ld+json"]


# ---- the step cannot block the deploy -------------------------------------------

NOTICE = "::notice title=show pages skipped::"


def _argv(snap: Path, out: Path, *extra: str) -> list[str]:
    return [str(snap), str(out), "--app-store-live", "false", *extra]


@pytest.mark.parametrize(
    "break_it",
    [
        pytest.param(lambda d, p: p.write_text("{ not json", encoding="utf-8"), id="invalid-json"),
        pytest.param(lambda d, p: p.write_text("[]", encoding="utf-8"), id="not-an-object"),
        pytest.param(lambda d, p: p.unlink(), id="missing-file"),
        pytest.param(
            lambda d, p: p.write_text(json.dumps({**d, "generated_at": "yesterday"})),
            id="bad-date",
        ),
        pytest.param(
            lambda d, p: p.write_text(json.dumps({k: v for k, v in d.items() if k != "shows"})),
            id="missing-key",
        ),
        pytest.param(
            lambda d, p: p.write_text(json.dumps({**d, "characters": []})), id="nothing-to-build"
        ),
        pytest.param(
            lambda d, p: p.write_text(
                json.dumps({**d, "shows": [{**d["shows"][0], "slug": "../etc"}, *d["shows"][1:]]})
            ),
            id="unsafe-slug",
        ),
    ],
)
def test_any_problem_prints_a_notice_exits_zero_and_writes_nothing(doc, tmp_path, capsys, break_it):
    snap = tmp_path / "snap.json"
    snap.write_text(json.dumps(doc), encoding="utf-8")
    break_it(doc, snap)
    out = tmp_path / "site"
    # Without the flag the same input is a failure (the sabotage landed), so
    # the step would have failed the workflow.
    rc = show_pages.main(_argv(snap, out))
    capsys.readouterr()
    assert rc == 1
    assert not out.exists()

    # With the flag, as snapshot.yml runs it.
    assert show_pages.main(_argv(snap, out, "--notice-on-failure")) == 0
    printed = capsys.readouterr()
    assert printed.out.startswith(NOTICE)
    assert printed.out.count("\n") == 1  # one workflow command, nothing injected
    assert not out.exists()


def test_an_unexpected_exception_is_also_a_notice(doc, tmp_path, capsys, monkeypatch):
    snap = tmp_path / "snap.json"
    snap.write_text(json.dumps(doc), encoding="utf-8")

    def boom(*a, **k):
        raise RuntimeError("template engine fell over\n::error::injected")

    monkeypatch.setattr(show_pages, "build_site", boom)
    out = tmp_path / "site"
    with pytest.raises(RuntimeError):  # without the flag it is not hidden
        show_pages.main(_argv(snap, out))
    assert show_pages.main(_argv(snap, out, "--notice-on-failure")) == 0
    printed = capsys.readouterr().out
    assert printed.startswith(NOTICE)
    assert printed.count("\n") == 1  # the newline in the message cannot start a second command


def test_a_failed_write_leaves_no_partial_site(doc, tmp_path, capsys, monkeypatch):
    snap = tmp_path / "snap.json"
    snap.write_text(json.dumps(_big_doc(doc)), encoding="utf-8")
    out = tmp_path / "site"
    out.mkdir()
    (out / "snapshot.v1.json").write_text("{}", encoding="utf-8")  # the snapshot's own file
    real = Path.write_text
    calls = []

    def flaky(self, *a, **k):
        if str(self).startswith(str(out)) and self.name != "snapshot.v1.json":
            calls.append(self)
            if len(calls) == 7:
                raise OSError("disk full")
        return real(self, *a, **k)

    monkeypatch.setattr(Path, "write_text", flaky)
    assert show_pages.main(_argv(snap, out, "--notice-on-failure")) == 0
    assert len(calls) == 7  # the fault landed after six files were written
    assert capsys.readouterr().out.startswith(NOTICE)
    assert sorted(p.name for p in out.rglob("*")) == ["snapshot.v1.json"]  # all six removed


def test_the_flagged_run_that_works_writes_the_site_and_no_notice(doc, tmp_path, capsys):
    snap = tmp_path / "snap.json"
    snap.write_text(json.dumps(_big_doc(doc)), encoding="utf-8")
    out = tmp_path / "site"
    assert show_pages.main(_argv(snap, out, "--notice-on-failure")) == 0
    assert "::notice" not in capsys.readouterr().out
    assert (out / "robots.txt").is_file() and (out / "sitemap.xml").is_file()
    assert len(list((out / "shows").iterdir())) == 51  # 50 directories and the index


def _workflow_argv(snap: Path, out: Path, app_store_live: str) -> list[str]:
    """The generator's arguments exactly as snapshot.yml's step passes them."""
    text = (REPO / ".github" / "workflows" / "snapshot.yml").read_text(encoding="utf-8")
    step = text[text.index("- name: build the per-show pages") :]
    run = step[step.index("uv run python -m qtv_pipeline.show_pages") :].split("env:")[0]
    words = run.replace("\\\n", " ").split()[5:]  # after: uv run python -m <module>
    swap = {
        "out/snapshot.v1.json": str(snap),
        "site": str(out),
        '"$APP_STORE_LIVE"': app_store_live,
    }
    return [swap.get(w, w) for w in words]


def test_the_command_in_the_workflow_cannot_fail_it_and_builds_when_it_can(doc, tmp_path, capsys):
    snap = tmp_path / "snapshot.v1.json"
    out = tmp_path / "site"
    snap.write_text(json.dumps(_big_doc(doc)), encoding="utf-8")
    argv = _workflow_argv(snap, out, "false")
    assert "--notice-on-failure" in argv and str(snap) in argv and str(out) in argv
    assert show_pages.main(argv) == 0
    assert (out / "robots.txt").is_file()
    assert "::notice" not in capsys.readouterr().out

    # The same command on a snapshot that is wrong, and on a bad switch value.
    snap.write_text("{ truncated", encoding="utf-8")
    broken = tmp_path / "broken-site"
    assert show_pages.main(_workflow_argv(snap, broken, "false")) == 0
    assert capsys.readouterr().out.startswith(NOTICE)
    assert not broken.exists()
    snap.write_text(json.dumps(_big_doc(doc)), encoding="utf-8")
    assert show_pages.main(_workflow_argv(snap, broken, "maybe")) == 0
    assert capsys.readouterr().out.startswith(NOTICE)
    assert not broken.exists()
    # Sabotage check: drop the flag from the workflow's own argv and it fails.
    unsafe = [a for a in _workflow_argv(snap, broken, "maybe") if a != "--notice-on-failure"]
    assert "--notice-on-failure" not in unsafe  # the sabotage landed
    assert show_pages.main(unsafe) == 1
