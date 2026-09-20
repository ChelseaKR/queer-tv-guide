"""Pagination and the "nothing changed" path of the LezWatch mirror.

Every other fetch test answers each list with `X-WP-TotalPages: 1`, so the
`page += 1` branches never run. Here a fake collection serves real pages, and
each test also proves its fault landed: the fake is asked for the later pages,
or (negative controls) the header that tells the client to continue is removed
and the client stops early, showing the header, not luck, drives the loop.

Offline: httpx.MockTransport and a recording sleep.
"""

from __future__ import annotations

import json
from urllib.parse import parse_qs

import httpx

from qtv_pipeline import lezwatch
from qtv_pipeline.http import PacedClient


class Collection:
    """A WP REST collection answered in pages, with a log of the requests."""

    def __init__(self, records, *, announce_pages: bool = True):
        self.records = records
        self.announce_pages = announce_pages
        self.requests: list[dict[str, str]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        params = {k: v[0] for k, v in parse_qs(str(request.url.query, "utf-8")).items()}
        self.requests.append(params)
        per_page = int(params.get("per_page", "100"))
        page = int(params.get("page", "1"))
        window = self.records[(page - 1) * per_page : page * per_page]
        headers = {"X-WP-Total": str(len(self.records))}
        if self.announce_pages:
            headers["X-WP-TotalPages"] = str(-(-len(self.records) // per_page))
        return httpx.Response(200, json=window, headers=headers)

    @property
    def pages(self) -> list[int]:
        return [int(r["page"]) for r in self.requests if "page" in r]


def _client(handler, sleep) -> PacedClient:
    return PacedClient(transport=httpx.MockTransport(handler), sleep=sleep)


def _shows(n: int, *, first_id: int = 1000) -> list[dict]:
    return [
        {"id": first_id + i, "slug": f"show-{i}", "modified_gmt": f"2026-09-01T00:{i % 60:02d}:00"}
        for i in range(n)
    ]


def test_a_collection_over_three_pages_is_mirrored_completely(tmp_path, no_sleep):
    sleep, _ = no_sleep
    site = Collection(_shows(250))
    with _client(site, sleep) as client:
        result, cursor = lezwatch.fetch_shows(client, tmp_path, full=True)
    assert site.pages == [1, 2, 3]  # the later pages were really requested
    assert result.fetched == 250
    assert result.available == 250
    cached = sorted((tmp_path / "lezwatch" / "shows").glob("*.json"))
    assert len(cached) == 250
    assert json.loads(cached[-1].read_text())["id"] == 1249  # the last record of the last page
    assert cursor["shows"] == max(r["modified_gmt"] for r in site.records)


def test_without_the_total_pages_header_only_the_first_page_is_read(tmp_path, no_sleep):
    """Negative control for the test above: the client follows X-WP-TotalPages.
    Take the header away and it stops after one page, so the complete mirror
    above came from the loop, not from the fake handing everything back."""
    sleep, _ = no_sleep
    site = Collection(_shows(250), announce_pages=False)
    with _client(site, sleep) as client:
        result, _cursor = lezwatch.fetch_shows(client, tmp_path, full=True)
    assert site.pages == [1]
    assert result.fetched == 100


def test_an_empty_page_ends_the_loop_even_if_more_pages_were_announced(tmp_path, no_sleep):
    sleep, _ = no_sleep
    site = Collection(_shows(100))

    def lying_total(request: httpx.Request) -> httpx.Response:
        # Always announces five pages; page 1 holds the 100 records, page 2 is empty.
        site(request)
        page = int(request.url.params.get("page", "1"))
        window = site.records if page == 1 else []
        return httpx.Response(
            200, json=window, headers={"X-WP-Total": "100", "X-WP-TotalPages": "5"}
        )

    with _client(lying_total, sleep) as client:
        result, _cursor = lezwatch.fetch_shows(client, tmp_path, full=True)
    assert site.pages == [1, 2]  # page 2 came back empty, so page 3 was never requested
    assert result.fetched == 100


def test_an_incremental_run_with_nothing_new_changes_nothing(tmp_path, no_sleep):
    """The nightly "0 fetched" path: a cursor is set, the server has nothing
    after it, and neither the cache nor the cursor moves."""
    sleep, _ = no_sleep
    root = tmp_path / "lezwatch"
    (root / "shows").mkdir(parents=True)
    (root / "shows" / "7.json").write_text('{"id": 7}')
    (root / "cursor.json").write_text('{"shows": "2026-09-17T19:07:39"}')
    site = Collection([])
    with _client(site, sleep) as client:
        result, cursor = lezwatch.fetch_shows(client, tmp_path)
    assert result.fetched == 0
    assert "modified_after" in site.requests[0]  # an incremental request is filtered
    assert cursor == {"shows": "2026-09-17T19:07:39"}
    assert (root / "shows" / "7.json").read_text() == '{"id": 7}'


def test_a_full_run_sends_no_modified_after(tmp_path, no_sleep):
    """Negative control for the test above: the filter is what makes a run
    incremental, so a full run over the same cursor must not carry it."""
    sleep, _ = no_sleep
    root = tmp_path / "lezwatch"
    root.mkdir(parents=True)
    (root / "cursor.json").write_text('{"shows": "2026-09-17T19:07:39"}')
    site = Collection(_shows(3))
    with _client(site, sleep) as client:
        result, _cursor = lezwatch.fetch_shows(client, tmp_path, full=True)
    assert result.fetched == 3
    assert all("modified_after" not in r for r in site.requests)


def _taxonomy_site(pages_for: str, terms: list[dict]):
    """Every taxonomy is a single short page except `pages_for`, which is `terms`
    served 100 to a page."""
    requests: list[tuple[str, int]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        base = request.url.path.rsplit("/", 1)[-1]
        page = int(request.url.params.get("page", "1"))
        requests.append((base, page))
        if base == pages_for:
            window = terms[(page - 1) * 100 : page * 100]
            return httpx.Response(
                200, json=window, headers={"X-WP-TotalPages": str(-(-len(terms) // 100))}
            )
        return httpx.Response(200, json=[], headers={"X-WP-TotalPages": "1"})

    return handler, requests


def test_a_taxonomy_over_two_pages_is_read_to_the_end(tmp_path, no_sleep):
    sleep, _ = no_sleep
    terms = [{"id": i, "slug": f"t{i}", "name": f"T {i}", "count": 1} for i in range(1, 151)]
    handler, requests = _taxonomy_site("trope", terms)
    with _client(handler, sleep) as client:
        out = lezwatch.fetch_taxonomies(client, tmp_path)
    assert [page for base, page in requests if base == "trope"] == [1, 2]
    assert len(out["tropes"]) == 150
    written = json.loads((tmp_path / "lezwatch" / "taxonomies" / "trope.json").read_text())
    assert len(written) == 150
    # every other taxonomy asked once, saw an empty first page, and stopped
    others = [(b, p) for b, p in requests if b != "trope"]
    assert len(others) == len(lezwatch.TAXONOMIES) - 1
    assert all(page == 1 for _base, page in others)
    assert all(out[key] == [] for _slug, base, key in lezwatch.TAXONOMIES if base != "trope")


def test_actor_names_are_merged_across_pages(tmp_path, no_sleep):
    sleep, _ = no_sleep
    seen: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        page = request.url.params.get("page")
        seen.append(page)
        if page is None:
            return httpx.Response(
                200, json=[{"uid": 1, "name": "A"}], headers={"X-WP-TotalPages": "3"}
            )
        if page == "2":
            return httpx.Response(
                200, json=[{"uid": 2, "name": "B"}, {"uid": 3}], headers={"X-WP-TotalPages": "3"}
            )
        return httpx.Response(200, json=[], headers={"X-WP-TotalPages": "3"})

    with _client(handler, sleep) as client:
        names = lezwatch.fetch_actor_names(client, tmp_path)
    assert seen == [None, "2", "3"]  # page 1 carries no page parameter; 3 came back empty
    assert names == {1: "A", 2: "B", 3: ""}  # an actor without a name is "", not dropped
    assert lezwatch.load_actor_names(tmp_path) == names
