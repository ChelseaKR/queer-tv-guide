"""Character question blocks and the next-episode line on a show page
(DECISIONS 0051).

Each listed character gets "Is <name> <label> in <show>?" and "Does <name>
die in <show>?" as real H3s after the sealed answer, with LezWatch.TV's own
terms and never an invented label; the death answer stays behind the one
reveal. A page whose show has a TVmaze next episode says so in one line above
the app block, and says nothing when TVmaze lists none. Every negative control
asserts its sabotage changed the page before it asserts the checker caught it.
"""

from __future__ import annotations

import copy
import datetime as dt
import html as html_mod
import itertools
import json
import re
from pathlib import Path

import pytest

from qtv_pipeline import show_pages
from tests import htmlprobe

REPO = Path(__file__).resolve().parents[2]
FIXTURE = REPO / "ios" / "GuideCore" / "Tests" / "Fixtures" / "snapshot.fixture.json"
BASE = "https://example.test/qf"
HARBOR = "shows/harbor-lights/index.html"
CARTOGRAPHERS = "shows/the-cartographers/index.html"
SALT = "shows/salt-and-ember/index.html"
SEALED = "The answer is sealed above"
# The fixture's snapshot day; harbor-lights' next episode is 2026-09-20.
TODAY = dt.date(2026, 9, 13)


@pytest.fixture
def doc() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _build(doc: dict, tmp_path: Path, **kw) -> tuple[dict[str, htmlprobe.Page], dict[str, str]]:
    show_pages.build_site(doc, tmp_path, base_url=BASE, **kw)
    raws = {
        str(p.relative_to(tmp_path)): p.read_text(encoding="utf-8")
        for p in sorted((tmp_path / "shows").rglob("index.html"))
    }
    return {k: htmlprobe.parse(v) for k, v in raws.items()}, raws


def _show(doc: dict, slug: str) -> dict:
    return next(s for s in doc["shows"] if s["slug"] == slug)


def _character(doc: dict, slug: str) -> dict:
    return next(c for c in doc["characters"] if c["slug"] == slug)


def _section(raw: str) -> str:
    """The question section's markup: from its heading to the About heading."""
    start = raw.index("<h2>Questions about the characters in ")
    return raw[start : raw.index("<h2>About ", start)]


def _headings(raw: str) -> list[tuple[int, str]]:
    """(level, text) of every heading in ``raw``, in order."""
    return [
        (int(level), html_mod.unescape(text))
        for level, text in re.findall(r"<h([1-6])>(.*?)</h[1-6]>", raw)
    ]


def _h3s(raw: str) -> list[str]:
    return [text for level, text in _headings(raw) if level == 3]


def _line(raw: str) -> str:
    """The next-episode paragraph's markup."""
    start = raw.index('<p class="next-episode">')
    return raw[start : raw.index("</p>", start)]


def _with_many_characters(doc: dict, n: int) -> dict:
    """Harbor Lights with ``n`` listed characters: the two it has, then copies
    of the second with their own ids, slugs and names, all without a death."""
    template = _character(doc, "ines-varga")
    for i in range(n - 2):
        extra = copy.deepcopy(template)
        extra["lwtv_id"] = 900 + i
        extra["id"] = f"lwtv:character:{900 + i}"
        extra["slug"] = f"extra-character-{i:02d}"
        extra["name"] = f"Extra Character {i:02d}"
        extra["source_url"] = f"https://lezwatchtv.com/character/extra-character-{i:02d}/"
        extra["shows"][0]["role"] = "guest" if i % 2 else "recurring"
        extra["actors"] = [{"lwtv_id": 3000 + i, "slug": None, "name": f"Extra Actor {i:02d}"}]
        doc["characters"].append(extra)
    return doc


# --- the identity question, from LezWatch.TV's own terms ----------------------


@pytest.mark.parametrize(
    ("gender", "sexuality", "label"),
    [
        ("Cisgender", "Homosexual", "a lesbian"),
        ("Cisgender Woman", "Lesbian", "a lesbian"),
        ("Trans Woman", "Homosexual", "a lesbian"),
        ("Cisgender", "Bisexual", "bisexual"),
        ("Cisgender", "Pansexual", "pansexual"),
        ("Cisgender", "Queer", "queer"),
        ("Trans Woman", "Heterosexual", "a trans woman"),
        ("Trans Man", "Undefined", "a trans man"),
        ("Non-Binary", "Undefined", "non-binary"),
        ("Non-Binary (Intersex)", "Undefined", "non-binary"),
        ("Genderqueer", "Homosexual", "genderqueer"),
        ("Cisgender", "Not Straight", None),
        ("Cisgender", "Heterosexual", None),
        ("Cisgender", "Undefined", None),
        ("Cisgender (Intersex)", "Undefined", None),
        ("Unknown", "Not recorded", None),
    ],
)
def test_the_question_label_is_lezwatchs_term_with_its_article(gender, sexuality, label):
    assert show_pages.question_label(gender, sexuality) == label


def test_a_label_is_never_gay_or_invented():
    """Every label the question can ask about comes from the two terms; the
    words the page's rules forbid never appear (DECISIONS 0027, 0045)."""
    seen = set()
    for sexuality in [*show_pages.SEXUALITY_LABELS, "Homosexual", "Lesbian", "Undefined", "X"]:
        for gender in ("Cisgender", "Cisgender Woman", "Trans Woman", "Non-Binary", "Unknown"):
            label = show_pages.question_label(gender, sexuality)
            if label is not None:
                seen.add(label.removeprefix("a "))
    assert "gay" not in seen and "lgbtq" not in seen
    lezwatch_terms = {s.lower() for s in show_pages.SEXUALITY_LABELS} | {
        "lesbian",
        "trans woman",
        "non-binary",
    }
    assert seen <= lezwatch_terms, seen - lezwatch_terms


def test_each_character_gets_two_real_h3s_and_lezwatchs_terms(doc, tmp_path):
    pages, raws = _build(doc, tmp_path)
    section = _section(raws[HARBOR])
    assert _h3s(section) == [
        "Is Mara Quill a lesbian in Harbor Lights?",
        "Does Mara Quill die in Harbor Lights?",
        "Is Inés Varga bisexual in Harbor Lights?",
        "Does Inés Varga die in Harbor Lights?",
    ]
    text = " ".join(pages[HARBOR].outside)
    assert (
        "Yes, per LezWatch.TV : sexuality Lesbian, gender Cisgender Woman. "
        "Regular, played by Example Actor One." in text
    )
    assert (
        "Yes, per LezWatch.TV : sexuality Bisexual, gender Cisgender Woman. "
        "Regular, played by Example Actor Two." in text
    )
    # The cite is a link to the character's own LezWatch.TV page.
    assert (
        section.count('<a href="https://lezwatchtv.com/character/mara-quill/">LezWatch.TV</a>') == 1
    )
    # The page keeps its one H1, and no heading level is skipped.
    levels = pages[HARBOR].headings
    assert levels.count(1) == 1 and levels[0] == 1
    assert all(b - a <= 1 for a, b in itertools.pairwise(levels))


def test_a_gender_label_with_an_unstated_orientation_says_so(doc, tmp_path):
    pages, raws = _build(doc, tmp_path)
    section = _section(raws[SALT])
    assert "<h3>Is Juno Adeyemi non-binary in Salt &amp; Ember?</h3>" in section
    text = " ".join(pages[SALT].outside)
    assert (
        "Yes, per LezWatch.TV : gender Non-Binary. "
        "LezWatch.TV lists Juno Adeyemi without a stated orientation." in text
    )
    # No actor resolved and no role recorded: no clause, never a placeholder.
    block = section.split("<h3>Does Juno Adeyemi die")[0]
    assert "played by" not in block and "Not recorded" not in block and "None" not in block


@pytest.mark.parametrize("sexuality", [None, {"slug": "undefined", "name": "Undefined"}])
def test_no_label_at_all_asks_lgbtq_and_states_no_orientation(doc, tmp_path, sexuality):
    juno = _character(doc, "juno-adeyemi")
    juno["gender"] = {"slug": "cisgender", "name": "Cisgender"}
    juno["sexuality"] = sexuality
    pages, raws = _build(doc, tmp_path)
    assert "<h3>Is Juno Adeyemi LGBTQ in Salt &amp; Ember?</h3>" in _section(raws[SALT])
    text = " ".join(pages[SALT].outside)
    assert "LezWatch.TV lists Juno Adeyemi without a stated orientation; gender Cisgender." in text
    assert "Yes, per" not in _section(raws[SALT])


def test_a_stated_term_with_no_label_is_given_as_lezwatch_records_it(doc, tmp_path):
    juno = _character(doc, "juno-adeyemi")
    juno["gender"] = {"slug": "cisgender", "name": "Cisgender"}
    juno["sexuality"] = {"slug": "not-straight", "name": "Not Straight"}
    pages, raws = _build(doc, tmp_path)
    assert "<h3>Is Juno Adeyemi LGBTQ in Salt &amp; Ember?</h3>" in _section(raws[SALT])
    text = " ".join(pages[SALT].outside)
    assert (
        "LezWatch.TV lists Juno Adeyemi with the sexuality Not Straight and the gender Cisgender."
        in text
    )
    assert "without a stated orientation" not in _section(raws[SALT])


def test_blocks_are_regulars_first_and_never_in_an_order_a_death_could_set(doc, tmp_path):
    _, raws = _build(doc, tmp_path)
    assert _h3s(_section(raws[CARTOGRAPHERS]))[::2] == [
        "Is Odile Brandt a lesbian in The Cartographers?",
        "Is Thea Marsh queer in The Cartographers?",
    ]
    _character(doc, "odile-brandt")["shows"][0]["role"] = "guest"
    _, raws = _build(doc, tmp_path / "again")
    assert _h3s(_section(raws[CARTOGRAPHERS]))[::2] == [
        "Is Thea Marsh queer in The Cartographers?",
        "Is Odile Brandt a lesbian in The Cartographers?",
    ]


# --- placement: after the sealed answer, before the app block -----------------


def test_blocks_follow_the_answer_and_precede_the_app_block(doc, tmp_path):
    _, raws = _build(doc, tmp_path, app_store_live=True)
    raw = raws[HARBOR]
    answer_end = raw.index("</details>")
    questions = raw.index("<h2>Questions about the characters in Harbor Lights</h2>")
    line = raw.index('<p class="next-episode">')
    app = raw.index('<div class="get-app">')
    about = raw.index("<h2>About Harbor Lights</h2>")
    assert answer_end < questions < line < app < about
    # The death question links to the one sealed answer, which has that id.
    assert '<details class="answer" id="answer">' in raw
    assert raw.count('href="#answer"') == 2  # two characters, one death question each
    assert "answer" in show_pages.RESERVED_IDS


def test_the_death_question_carries_no_status_and_points_at_the_reveal(doc, tmp_path):
    pages, raws = _build(doc, tmp_path)
    page = pages[CARTOGRAPHERS]
    section = _section(raws[CARTOGRAPHERS])
    assert "<h3>Does Odile Brandt die in The Cartographers?</h3>" in section
    assert (
        f'{SEALED}: open <a href="#answer">Show the answer (spoilers)</a> '
        "and find Odile Brandt in the list." in section
    )
    block = section.split('<div class="character-questions">')[1]
    assert "Odile Brandt" in block
    for word in ("Dies", "dies", "Unknown", "2017", "Dead", "Bury", "died"):
        assert word not in block, word
    # The real answer is still there, inside the sealed element only.
    assert any("Dies (2017)." in t for t in page.inside)
    assert not any("Dies" in t for t in page.outside)


# --- many characters: the first eight, then a closed "Show all" control ------


def test_thirty_characters_show_eight_then_collapse_the_rest(doc, tmp_path):
    pages, raws = _build(_with_many_characters(doc, 30), tmp_path)
    page, raw = pages[HARBOR], raws[HARBOR]
    section = _section(raw)
    assert section.count('<div class="character-questions">') == 30
    assert len(_h3s(section)) == 60
    control = section.index('<details class="more-characters">')
    assert section.count('<details class="more-characters">') == 1
    assert "<summary>Show all 30 characters</summary>" in section
    assert section[:control].count('<div class="character-questions">') == 8
    assert section[control:].count('<div class="character-questions">') == 22
    # Two details elements, both closed on load; still exactly one sealed answer.
    details = page.named("details")
    assert [d.get("class") for d in details] == ["answer", "more-characters"]
    assert not any("open" in d for d in details)
    assert htmlprobe.details_problems(page) == []
    assert len(page.named("summary")) == 2
    # The control is markup, not script: the page still runs nothing.
    assert [s.get("type") for s in page.named("script")] == ["application/ld+json"]
    assert htmlprobe.duplicate_ids(page) == []
    levels = page.headings
    assert levels.count(1) == 1 and all(b - a <= 1 for a, b in itertools.pairwise(levels))


def test_eight_or_fewer_characters_get_no_control(doc, tmp_path):
    _, raws = _build(_with_many_characters(doc, 8), tmp_path)
    assert _section(raws[HARBOR]).count('<div class="character-questions">') == 8
    assert '<details class="more-characters">' not in raws[HARBOR]
    assert "<summary>Show all" not in raws[HARBOR]


def test_the_collapsed_blocks_are_visible_to_the_leak_checker(doc, tmp_path):
    """A closed "Show all" control hides nothing from a search engine, so the
    probe counts its text as outside the sealed answer."""
    pages, _ = _build(_with_many_characters(doc, 30), tmp_path)
    page = pages[HARBOR]
    question = "Is Extra Character 27 bisexual in Harbor Lights?"
    assert question in page.outside
    assert question not in page.inside


# --- negative controls -------------------------------------------------------


@pytest.mark.parametrize("where", ["visible", "collapsed"])
def test_negative_control_a_death_answer_in_a_block_is_caught(doc, tmp_path, where):
    many = _with_many_characters(doc, 30)
    _character(many, "extra-character-27")["death"] = {
        "died": True,
        "death_known": True,
        "dates": [{"date": "2025-05-05", "year": 2025, "raw": "20250505"}],
        "years": [2025],
    }
    pages, raws = _build(many, tmp_path)
    raw = raws[HARBOR]
    victim = "Inés Varga" if where == "visible" else "Extra Character 27"
    status = (
        "Dies (2025)." if where == "collapsed" else "Unknown. LezWatch.TV has not recorded a death."
    )
    show = _show(many, "harbor-lights")
    cast = show_pages._characters(many, show)
    answers = [show_pages._answer(show, cast).headline, *[c.status for c in cast]]
    assert status in answers
    needle = f"and find {victim} in the list."
    assert raw.count(needle) == 1
    bad = raw.replace(needle, f"{needle} {status}", 1)
    assert bad != raw  # the sabotage applied
    assert htmlprobe.answer_leaks(pages[HARBOR], answers) == []
    leaked = htmlprobe.answer_leaks(htmlprobe.parse(bad), answers)
    assert status in leaked, where
    if where == "collapsed":
        # The planted status sits inside the closed control, and is still seen.
        assert bad.index(f"{needle} {status}") > bad.index('<details class="more-characters">')


def test_swapping_every_death_record_leaves_every_block_byte_for_byte(doc, tmp_path):
    many = _with_many_characters(doc, 30)
    _, before = _build(copy.deepcopy(many), tmp_path / "before")
    swapped = copy.deepcopy(many)
    for c in swapped["characters"]:
        dead = c["death"]["died"] is True
        c["death"] = (
            {"died": None, "death_known": False, "dates": [], "years": []}
            if dead
            else {
                "died": True,
                "death_known": True,
                "dates": [{"date": "2020-01-01", "year": 2020, "raw": "20200101"}],
                "years": [2020],
            }
        )
    _, after = _build(swapped, tmp_path / "after")
    assert before[CARTOGRAPHERS] != after[CARTOGRAPHERS]  # the swap reached the page
    for name in before:
        if "<h2>Questions about the characters in " in before[name]:
            assert _section(before[name]) == _section(after[name]), name


def test_title_description_h1_and_structured_data_do_not_change(doc, tmp_path):
    pages, raws = _build(doc, tmp_path)
    page = pages[HARBOR]
    show = _show(doc, "harbor-lights")
    cast = show_pages._characters(doc, show)
    assert page.title == show_pages.show_title(show["title"], len(cast))
    assert page.description == show_pages._description(show["title"], cast)
    assert _headings(raws[HARBOR])[0] == (1, "Do any queer characters die in Harbor Lights?")
    assert "FAQPage" not in "".join(page.ld_json)
    series = htmlprobe.ld_node(page, "TVSeries")
    # The structured data names the same characters the blocks ask about.
    names = sorted(c["name"] for c in series["character"])
    blocks = show_pages.character_questions(show, cast)
    assert names == sorted(q.name for q in blocks) == ["Inés Varga", "Mara Quill"]
    assert _h3s(_section(raws[HARBOR])) == [
        h for q in blocks for h in (q.question, q.death_question)
    ]


# --- the next-episode line ----------------------------------------------------


def test_a_dated_next_episode_is_one_line_above_the_app_block(doc, tmp_path):
    pages, raws = _build(doc, tmp_path, app_store_live=True)
    raw = raws[HARBOR]
    assert (
        '<p class="next-episode"><strong>Next episode:</strong> '
        '<time datetime="2026-09-20">Sunday, September 20, 2026</time>, per TVmaze. '
        "Get a reminder in the app.</p>" in raw
    )
    assert raw.count('class="next-episode"') == 1
    text = " ".join(pages[HARBOR].outside)
    assert (
        "Next episode: Sunday, September 20, 2026 , per TVmaze. Get a reminder in the app." in text
    )
    # The 0037 facts row is still there too; the line does not replace it.
    assert pages[HARBOR].facts[show_pages.NEXT_EPISODE_LABEL].endswith("Sunday, September 20, 2026")


def test_with_the_switch_off_the_line_offers_no_app(doc, tmp_path):
    _, raws = _build(doc, tmp_path)
    raw = raws[HARBOR]
    assert (
        '<p class="next-episode"><strong>Next episode:</strong> '
        '<time datetime="2026-09-20">Sunday, September 20, 2026</time>, per TVmaze.</p>' in raw
    )
    assert "Get a reminder in the app" not in raw


def test_an_ended_show_with_no_next_episode_gets_no_line_and_no_placeholder(doc, tmp_path):
    pages, raws = _build(doc, tmp_path, app_store_live=True)
    page, raw = pages[CARTOGRAPHERS], raws[CARTOGRAPHERS]
    assert _show(doc, "the-cartographers")["schedule"]["status"] == "Ended"
    assert 'class="next-episode"' not in raw and "Next episode" not in raw
    text = " ".join(page.outside).lower()
    for phrase in ("no upcoming", "no next episode", "to be announced", "none scheduled"):
        assert phrase not in text, phrase
    assert page.facts["Years"] == "2016 to 2018"  # the Years row already says it ended


def test_a_running_show_tvmaze_lists_nothing_for_gets_no_line(doc, tmp_path):
    show = _show(doc, "harbor-lights")
    show["schedule"]["next_episode"] = None
    assert show["schedule"]["status"] == "Running"
    pages, raws = _build(doc, tmp_path, app_store_live=True)
    assert 'class="next-episode"' not in raws[HARBOR] and "Next episode" not in raws[HARBOR]
    assert "upcoming" not in " ".join(pages[HARBOR].outside).lower()
    # The app block still stands on its own, with its own reminder sentence.
    assert "turn on new-episode reminders" in raws[HARBOR]


def test_an_episode_listed_without_a_date_is_to_be_announced(doc, tmp_path):
    show = _show(doc, "harbor-lights")
    show["schedule"]["next_episode"]["airdate"] = None
    show["schedule"]["next_episode"]["airstamp"] = None
    pages, raws = _build(doc, tmp_path, app_store_live=True)
    raw = raws[HARBOR]
    assert (
        '<p class="next-episode"><strong>Next episode:</strong> date to be announced, per TVmaze. '
        "Get a reminder in the app.</p>" in raw
    )
    assert "<time" not in _section(raw) and '<time datetime=""' not in raw
    # The 0037 facts row needs a date, so it is left out, as before.
    assert show_pages.NEXT_EPISODE_LABEL not in pages[HARBOR].facts


def test_the_line_follows_the_facts_rows_absence_rules(doc):
    show = _show(doc, "harbor-lights")
    assert show_pages.next_episode_line(show, TODAY) == ("Sunday, September 20, 2026", "2026-09-20")
    for broken in ("past", "unreadable", "missing", "unscheduled"):
        s = copy.deepcopy(show)
        if broken == "past":
            s["schedule"]["next_episode"]["airdate"] = "2026-09-12"
        elif broken == "unreadable":
            s["schedule"]["next_episode"]["airdate"] = "soon"
        elif broken == "missing":
            s["schedule"]["next_episode"] = None
        else:
            s["schedule"]["schedule_known"] = False
        assert show_pages.next_episode_line(s, TODAY) is None, broken
    tba = copy.deepcopy(show)
    tba["schedule"]["next_episode"]["airdate"] = ""
    assert show_pages.next_episode_line(tba, TODAY) == (show_pages.TO_BE_ANNOUNCED, None)


def test_the_line_prints_tvmazes_day_not_a_converted_one(doc):
    """TVmaze's airdate is the network's own calendar day; the airstamp's
    offset is never applied to it."""
    show = _show(doc, "harbor-lights")
    # The same moment as the fixture's 21:00 -04:00, written in UTC: the next day.
    show["schedule"]["next_episode"]["airstamp"] = "2026-09-21T01:00:00+00:00"
    assert show_pages.next_episode_line(show, TODAY) == ("Sunday, September 20, 2026", "2026-09-20")


def test_the_line_never_prints_the_episode_name_and_ignores_deaths(doc, tmp_path):
    show = _show(doc, "harbor-lights")
    name = show["schedule"]["next_episode"]["name"]
    assert name  # the fixture has a name to leak
    _, raws = _build(doc, tmp_path, app_store_live=True)
    assert name not in raws[HARBOR]
    before = raws[HARBOR]
    for c in doc["characters"]:
        c["death"] = {
            "died": True,
            "death_known": True,
            "dates": [{"date": "2026-01-01", "year": 2026, "raw": "20260101"}],
            "years": [2026],
        }
    _, after = _build(doc, tmp_path / "again", app_store_live=True)
    assert after[HARBOR] != before  # the swap reached the page
    assert _line(after[HARBOR]) == _line(before)
