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
    """The shows index and every built page are listed, with the data date."""
    entries = htmlprobe.sitemap(files["sitemap.xml"])
    pages = [n for n in files if n.endswith("index.html") and n.startswith("shows/")]
    want = {f"{DOMAIN}/{n.removesuffix('index.html')}" for n in pages}
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
    assert len(entries["loc"]) == 51
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


# ---- the home page ----------------------------------------------------------


def test_the_home_page_links_to_the_shows_index_only_when_it_is_published(doc, tmp_path):
    big = _big_doc(doc)
    site = tmp_path / "site"
    site.mkdir()
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text(json.dumps(doc), encoding="utf-8")

    # Shows not published: no link, and the page is what it was before.
    assert site_index.main([str(snapshot), str(site / "index.html")]) == 0
    bare = htmlprobe.parse((site / "index.html").read_text(encoding="utf-8"))
    assert "shows/" not in bare.hrefs()
    assert (site / "index.html").read_text(encoding="utf-8") == site_index.render_index(doc)

    # Shows published beside it: a plain relative link that resolves.
    show_pages.build_site(big, site)
    assert (site / "shows" / "index.html").is_file()
    assert site_index.main([str(snapshot), str(site / "index.html")]) == 0
    text = (site / "index.html").read_text(encoding="utf-8")
    page = htmlprobe.parse(text)
    assert page.hrefs().count("shows/") == 1
    assert (
        '<p><a href="shows/">Does she die? Queer TV shows</a>: '
        "pages that keep the answer closed until you open it.</p>" in text
    )
    assert "<script" not in text


def test_negative_control_a_dead_link_would_be_written_without_the_check(doc, tmp_path):
    # With the shows directory gone (the show-pages step skipped), the same
    # command must not write the link. If it did, the home page would point at 404.
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text(json.dumps(doc), encoding="utf-8")
    site = tmp_path / "site"
    show_pages.build_site(_big_doc(doc), site)
    for p in sorted((site / "shows").rglob("*"), reverse=True):
        p.unlink() if p.is_file() else p.rmdir()
    (site / "shows").rmdir()
    assert not (site / "shows").exists()  # the sabotage landed
    assert "shows/" in htmlprobe.parse(site_index.render_index(doc, shows_link=True)).hrefs()
    site_index.main([str(snapshot), str(site / "index.html")])
    assert "shows/" not in htmlprobe.parse((site / "index.html").read_text()).hrefs()


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
