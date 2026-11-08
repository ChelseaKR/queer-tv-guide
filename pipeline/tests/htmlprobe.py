"""Read a built page with html.parser (never a regex over HTML) and answer the
questions the show-page tests ask: where is each piece of text, is the answer
element closed, what does a page load. The checkers at the bottom are the
ones the negative controls sabotage a page to prove they can fail."""

from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser

VOID = {"meta", "link", "br", "hr", "img", "input"}


@dataclass
class Page:
    title: str = ""
    description: str = ""
    canonical: str = ""
    lang: str = ""
    ld_json: list[str] = field(default_factory=list)
    tags: list[tuple[str, dict[str, str | None]]] = field(default_factory=list)
    headings: list[int] = field(default_factory=list)
    # Text inside the sealed answer, <details class="answer">. Any other
    # details element (the "Show all N characters" control, DECISIONS 0051)
    # hides nothing from a search engine, so its text counts as outside.
    inside: list[str] = field(default_factory=list)
    outside: list[str] = field(default_factory=list)  # text anywhere else in <body>
    statuses: list[tuple[str, str]] = field(default_factory=list)  # (data-status, text)
    css: str = ""
    ids: set[str] = field(default_factory=set)
    id_list: list[str] = field(default_factory=list)  # every id, repeats kept
    cast: list[str] = field(default_factory=list)  # text inside <ul class="cast">
    cast_ids: list[str] = field(default_factory=list)  # ids of its <li> items
    facts: dict[str, str] = field(default_factory=dict)  # <dt> text -> <dd> text

    def named(self, name: str) -> list[dict[str, str | None]]:
        return [a for t, a in self.tags if t == name]

    def hrefs(self) -> list[str]:
        return [a.get("href") or "" for a in self.named("a")]


class _Probe(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.page = Page()
        self._stack: list[str] = []
        self._details: list[bool] = []  # one entry per open <details>: is it the answer?
        self._status_kind: str | None = None
        self._li_status: str | None = None
        self._script_ld = False
        self._term: str | None = None
        self._cell = ""
        self._cast = 0

    def _head(self, tag: str, a: dict[str, str | None]) -> None:
        p = self.page
        if tag == "html":
            p.lang = a.get("lang") or ""
        if tag == "meta" and a.get("name") == "description":
            p.description = a.get("content") or ""
        if tag == "link" and a.get("rel") == "canonical":
            p.canonical = a.get("href") or ""

    def _cast_start(self, tag: str, a: dict[str, str | None]) -> None:
        if self._cast:
            self._cast += tag not in VOID
            if tag == "li" and self._cast == 2:
                self.page.cast_ids.append(a.get("id") or "")
        elif tag == "ul" and a.get("class") == "cast":
            self._cast = 1

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        p = self.page
        p.tags.append((tag, a))
        self._head(tag, a)
        if a.get("id"):
            p.ids.add(a["id"])
            p.id_list.append(a["id"])
        self._cast_start(tag, a)
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            p.headings.append(int(tag[1]))
        if tag in {"dt", "dd"}:
            self._cell = tag
        if tag == "details":
            self._details.append(a.get("class") == "answer")
        if tag == "li" and "data-status" in a:
            self._li_status = a["data-status"]
        if tag == "span" and a.get("class") == "status":
            self._status_kind = self._li_status or ""
        self._script_ld = tag == "script" and a.get("type") == "application/ld+json"
        if tag not in VOID:
            self._stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if self._cast:
            self._cast -= 1
        if tag == "details" and self._details:
            self._details.pop()
        if tag in {"dt", "dd"}:
            self._cell = ""
        if tag == "li":
            self._li_status = None
        if tag == "span":
            self._status_kind = None
        if tag == "script":
            self._script_ld = False
        if tag in self._stack:
            while self._stack.pop() != tag:
                pass

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if not text:
            return
        p = self.page
        top = self._stack[-1] if self._stack else ""
        if top == "title":
            p.title += text
        elif top == "style":
            p.css += data
        elif top == "script":
            if self._script_ld:
                p.ld_json.append(data)
        elif "body" in self._stack:
            (p.inside if any(self._details) else p.outside).append(text)
            self._cell_data(text)

    def _cell_data(self, text: str) -> None:
        p = self.page
        if self._cast:
            p.cast.append(text)
        if self._cell == "dt":
            self._term = text
        elif self._cell == "dd" and self._term is not None:
            p.facts[self._term] = text
        if self._status_kind is not None:
            p.statuses.append((self._status_kind, text))


def parse(html: str) -> Page:
    probe = _Probe()
    probe.feed(html)
    probe.close()
    return probe.page


def ld_nodes(page: Page) -> list[dict]:
    """Every schema.org node in the page's JSON-LD, flattening an @graph."""
    import json

    nodes: list[dict] = []
    for block in page.ld_json:
        data = json.loads(block)
        nodes += data.get("@graph", [data])
    return nodes


def ld_node(page: Page, kind: str) -> dict:
    """The one JSON-LD node of a type; fails if there is not exactly one."""
    found = [n for n in ld_nodes(page) if n.get("@type") == kind]
    assert len(found) == 1, (kind, [n.get("@type") for n in ld_nodes(page)])
    return found[0]


# --- checkers -------------------------------------------------------------


def details_problems(page: Page) -> list[str]:
    """Not exactly one sealed answer (``<details class="answer">``), or any
    details element at all open on load: the "Show all N characters" control
    (DECISIONS 0051) is allowed, closed, beside the one answer."""
    found = []
    details = page.named("details")
    answers = [a for a in details if a.get("class") == "answer"]
    if len(answers) != 1:
        found.append(f'expected one <details class="answer">, found {len(answers)}')
    found += ["a <details> is open on load" for a in details if "open" in a]
    return found


def answer_leaks(page: Page, answers: list[str]) -> list[str]:
    """Answer sentences that appear anywhere a closed <details> would not hide."""
    visible = [*page.outside, page.title, page.description, *page.ld_json]
    return [a for a in answers if any(a in v for v in visible)]


def duplicate_ids(page: Page) -> list[str]:
    """Ids that appear more than once on a page (a link anchor must be unique)."""
    return sorted({i for i in page.id_list if page.id_list.count(i) > 1})


def no_for_unknown(page: Page) -> list[str]:
    """Statuses that are not a recorded death yet do not say Unknown."""
    bad = []
    for kind, text in page.statuses:
        if kind == "unknown" and not text.startswith("Unknown"):
            bad.append(text)
        if kind == "dies" and not text.startswith("Dies"):
            bad.append(text)
        if kind not in {"unknown", "dies"}:
            bad.append(text)
    return bad


class _Sitemap(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.entries: dict[str, list[str]] = {"loc": [], "lastmod": []}
        self._open: str | None = None

    def _cast_start(self, tag: str, a: dict[str, str | None]) -> None:
        if self._cast:
            self._cast += tag not in VOID
            if tag == "li" and self._cast == 2:
                self.page.cast_ids.append(a.get("id") or "")
        elif tag == "ul" and a.get("class") == "cast":
            self._cast = 1

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._open = tag if tag in self.entries else None

    def handle_endtag(self, tag: str) -> None:
        self._open = None

    def handle_data(self, data: str) -> None:
        if self._open:
            self.entries[self._open].append(data)


def sitemap(xml: str) -> dict[str, list[str]]:
    """The <loc> and <lastmod> values of a sitemap, read with html.parser."""
    probe = _Sitemap()
    probe.feed(xml)
    probe.close()
    return probe.entries


def foreign_links(page: Page, base_url: str) -> list[dict[str, str | None]]:
    """Every <link> but the canonical and the site's own favicon (DECISIONS
    0038), the one icon a page may name, served from ``base_url`` itself."""
    icon = base_url.rstrip("/") + "/favicon.svg"
    return [
        a
        for a in page.named("link")
        if a.get("rel") != "canonical"
        and not (
            a.get("rel") == "icon" and a.get("href") == icon and a.get("type") == "image/svg+xml"
        )
    ]
