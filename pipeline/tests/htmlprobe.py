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
    inside: list[str] = field(default_factory=list)  # text inside <details>
    outside: list[str] = field(default_factory=list)  # text anywhere else in <body>
    statuses: list[tuple[str, str]] = field(default_factory=list)  # (data-status, text)
    css: str = ""
    ids: set[str] = field(default_factory=set)
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
        self._details = 0
        self._status_kind: str | None = None
        self._li_status: str | None = None
        self._script_ld = False
        self._term: str | None = None
        self._cell = ""

    def _head(self, tag: str, a: dict[str, str | None]) -> None:
        p = self.page
        if tag == "html":
            p.lang = a.get("lang") or ""
        if tag == "meta" and a.get("name") == "description":
            p.description = a.get("content") or ""
        if tag == "link" and a.get("rel") == "canonical":
            p.canonical = a.get("href") or ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        p = self.page
        p.tags.append((tag, a))
        self._head(tag, a)
        if a.get("id"):
            p.ids.add(a["id"])
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            p.headings.append(int(tag[1]))
        if tag in {"dt", "dd"}:
            self._cell = tag
        if tag == "details":
            self._details += 1
        if tag == "li" and "data-status" in a:
            self._li_status = a["data-status"]
        if tag == "span" and a.get("class") == "status":
            self._status_kind = self._li_status or ""
        self._script_ld = tag == "script" and a.get("type") == "application/ld+json"
        if tag not in VOID:
            self._stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag == "details":
            self._details -= 1
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
            (p.inside if self._details else p.outside).append(text)
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


# --- checkers -------------------------------------------------------------


def details_problems(page: Page) -> list[str]:
    found = []
    details = page.named("details")
    if len(details) != 1:
        found.append(f"expected one <details>, found {len(details)}")
    found += ["a <details> is open on load" for a in details if "open" in a]
    return found


def answer_leaks(page: Page, answers: list[str]) -> list[str]:
    """Answer sentences that appear anywhere a closed <details> would not hide."""
    visible = [*page.outside, page.title, page.description, *page.ld_json]
    return [a for a in answers if any(a in v for v in visible)]


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
