from __future__ import annotations

import json
from pathlib import Path

import pytest

from qtv_pipeline import fields, normalize

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str):
    return json.loads((FIXTURES / name).read_text())


def _taxonomies():
    bases = ["trope", "cliche", "gender", "sexuality", "romantic", "station", "genre",
             "country", "format", "trigger", "intersection", "star"]
    schema_keys = ["tropes", "cliches", "genders", "sexualities", "romantic", "stations",
                   "genres", "countries", "formats", "triggers", "intersections", "stars"]
    return {
        key: fields.terms_by_id(_load(f"taxonomies/{base}.json"))
        for key, base in zip(schema_keys, bases, strict=True)
    }


TAX = _taxonomies()


# ---- death: died is true or null, NEVER false --------------------------------

def test_no_recorded_death_is_null_not_false():
    char = normalize.normalize_character(_load("lezwatch_character_camille.json"), TAX, {})
    assert char["death"]["died"] is None
    assert char["death"]["death_known"] is False
    assert char["death"]["dates"] == []
    assert char["death"]["years"] == []


def test_recorded_death_is_true_with_a_parsed_date():
    char = normalize.normalize_character(_load("lezwatch_character_marielle.json"), TAX, {})
    assert char["death"]["died"] is True
    assert char["death"]["death_known"] is True
    assert char["death"]["dates"] == [{"date": "2026-06-28", "year": 2026, "raw": "20260628"}]
    assert char["death"]["years"] == [2026]


def test_death_date_already_hyphenated_is_parsed_not_dropped():
    """The real mirror (2026-09-13) showed LezWatch stores most death dates as
    YYYY-MM-DD already (673/682), not the YYYYMMDD shape seen in the one
    sample this pipeline was first built against (9/682). Both must parse:
    a knowable date must never be reported as unknown."""
    result = normalize._normalize_death([{"date": "2013-08-15"}])
    assert result == {
        "died": True,
        "death_known": True,
        "dates": [{"date": "2013-08-15", "year": 2013, "raw": "2013-08-15"}],
        "years": [2013],
    }


@pytest.mark.parametrize("bogus", [False, "false", 0, "no", None, [], [{}], [{"date": ""}]])
def test_normalize_death_never_produces_false(bogus):
    """died is constrained to {true, null} by the schema; prove the normalizer
    itself cannot be coaxed into emitting False for any absent- or malformed-
    death shape a source might send."""
    result = normalize._normalize_death(bogus)
    assert result["died"] in (None, True)
    assert result["died"] is not False


# ---- actors: unresolved id -> name null, not a guess --------------------------

def test_actor_name_resolves_when_known():
    char = normalize.normalize_character(
        _load("lezwatch_character_camille.json"), TAX, {78146: "Nia Cassidy"}
    )
    assert char["actors"] == [{"lwtv_id": 78146, "slug": None, "name": "Nia Cassidy"}]


def test_actor_name_is_null_when_unresolved():
    char = normalize.normalize_character(_load("lezwatch_character_marielle.json"), TAX, {})
    assert char["actors"] == [{"lwtv_id": 98058, "slug": None, "name": None}]


# ---- watch links: empty list, never a guessed link -----------------------------

def test_no_watch_links_is_an_empty_list():
    show = normalize.normalize_show(_load("lezwatch_show_no_key.json"), TAX)
    assert show["watch_links"] == []


def test_watch_link_present_carries_host():
    show = normalize.normalize_show(_load("lezwatch_show_not_found.json"), TAX)
    assert show["watch_links"] == [{"url": "https://www.hulu.com/series/not-found-show", "host": "www.hulu.com"}]


# ---- ratings: LezWatch's 0 ("unrated") becomes null, not a real zero ----------

def test_unrated_quality_is_null_not_zero():
    show = normalize.normalize_show(_load("lezwatch_show_no_key.json"), TAX)
    assert show["ratings"]["quality"] is None
    assert show["ratings"]["realness"] is None
    assert show["ratings"]["screentime"] is None


def test_rated_show_keeps_its_rating():
    show = normalize.normalize_show(_load("lezwatch_show_derry_girls.json"), TAX)
    assert show["ratings"]["quality"] == 4
    assert show["ratings"]["worth_it"] == "Yes"


# ---- schedule: joined-but-nothing-scheduled vs never-joined are different -----

def test_schedule_unknown_when_not_joined():
    sched = normalize.normalize_schedule({"method": "none", "matched": False}, None)
    assert sched["schedule_known"] is False
    assert sched["next_episode"] is None
    assert sched["tvmaze_id"] is None


def test_schedule_known_with_no_upcoming_episode_is_a_positive_statement():
    tvmaze_show = {
        "id": 42, "url": "https://www.tvmaze.com/shows/42/x", "status": "Ended",
        "premiered": "2010-01-01", "ended": "2015-01-01", "network": None, "webChannel": None,
        "_embedded": {"nextepisode": None, "previousepisode": {
            "id": 1, "url": "https://www.tvmaze.com/episodes/1/x", "name": "Finale",
            "season": 5, "number": 10, "airdate": "2015-01-01", "airtime": "",
            "airstamp": "2015-01-01T20:00:00+00:00", "runtime": 60,
        }},
    }
    sched = normalize.normalize_schedule({"method": "lwtv_tvmaze_id", "matched": True}, tvmaze_show)
    assert sched["schedule_known"] is True
    assert sched["next_episode"] is None  # a real "nothing upcoming", not "unknown"
    assert sched["previous_episode"]["name"] == "Finale"
    assert sched["previous_episode"]["airtime"] is None  # empty string -> null, not ""


# ---- years / on_air: a blank finish year never becomes "ongoing" -------------

def test_on_air_defaults_to_unknown_when_field_absent():
    raw = _load("lezwatch_show_derry_girls.json")
    raw["meta"]["lezshows_on_air"] = []
    show = normalize.normalize_show(raw, TAX)
    assert show["years"]["on_air"] == "unknown"


def test_on_air_recorded_value_is_preserved():
    show = normalize.normalize_show(_load("lezwatch_show_no_key.json"), TAX)
    assert show["years"]["on_air"] == "no"


# ---- html_to_text -------------------------------------------------------------

def test_html_to_text_handles_lists_and_empty():
    assert normalize.html_to_text(None) is None
    assert normalize.html_to_text("") is None
    text = normalize.html_to_text("<ul>\r\n\t<li><strong>S1E6</strong> Erin does a thing.</li>\r\n</ul>")
    assert "S1E6" in text and "<" not in text


# Shapes copied from the real 2026-09-17 mirror (lezshows_plots, excerpt,
# lezshows_worthit_details), where the app was rendering "<p>" literally.
def test_html_to_text_paragraphs_become_paragraphs_not_tags():
    raw = "<p>It was suggested in season one.</p><p>By season two we were sure.</p>"
    assert normalize.html_to_text(raw) == "It was suggested in season one.\n\nBy season two we were sure."


def test_html_to_text_decodes_entities_and_keeps_link_and_emphasis_text():
    assert normalize.html_to_text("Cake &amp; Candles") == "Cake & Candles"
    raw = 'He went on to make <a href="https://lezwatchtv.com/show/sense8/">Sense8</a>, <em>twice</em>.'
    assert normalize.html_to_text(raw) == "He went on to make Sense8, twice."


def test_html_to_text_drops_images_so_no_image_url_reaches_the_snapshot():
    raw = '<p>Before <img class="x" src="https://lezwatchtv.com/wp-content/uploads/a.jpg" alt="" /> after</p>'
    text = normalize.html_to_text(raw)
    assert text == "Before after"
    assert "wp-content" not in text


def test_html_to_text_list_with_crlf_and_nbsp():
    raw = "<ul>\r\n<li>Season 3 we meet Maggie.</li>\r\n<li>Season 8, Kerry meets\xa0Sandy.</li>\r\n</ul>"
    assert normalize.html_to_text(raw) == "- Season 3 we meet Maggie.\n- Season 8, Kerry meets Sandy."


def test_html_to_text_never_eats_prose_that_merely_contains_angle_brackets():
    assert normalize.html_to_text("I <3 this show, and 2 < 3 > 1.") == "I <3 this show, and 2 < 3 > 1."


def test_html_to_text_plain_text_passes_through_with_crlf_normalised():
    raw = "The reveal is in the last episode.\r\n\r\nOrla is played as non-binary."
    assert normalize.html_to_text(raw) == "The reveal is in the last episode.\n\nOrla is played as non-binary."


def test_every_prose_field_is_plain_text():
    """Negative control: the raw fixture fields carry markup; if any one of
    the four prose fields stops going through html_to_text, this fails."""
    raw = _load("lezwatch_show_derry_girls.json")
    raw["acf"]["excerpt"] = "Cake &amp; <em>Candles</em>"
    raw["acf"]["lezshows_plots"] = "<p>Plot.</p>"
    raw["acf"]["lezshows_worthit_details"] = "<em>Yes</em> &amp; more"
    show = normalize.normalize_show(raw, TAX)
    prose = [show["summary"], show["notes"]["plot"], show["notes"]["queer_episodes"],
             show["ratings"]["worth_it_details"]]
    assert raw["acf"]["lezshows_plots"].startswith("<p>")  # the sabotage is really in the input
    for value in prose:
        assert value is not None
        assert "<" not in value and "&amp;" not in value, value
    assert show["summary"] == "Cake & Candles"
    assert show["notes"]["plot"] == "Plot."
    assert show["ratings"]["worth_it_details"] == "Yes & more"


# ---- seasons: LezWatch's 0 ("never filled in") becomes null, not "0 seasons" ----

@pytest.mark.parametrize("unset", [0, "0", "", None, [], -1])
def test_unset_season_count_is_null_not_zero(unset):
    raw = _load("lezwatch_show_derry_girls.json")
    raw["acf"]["lezshows_seasons"] = unset
    assert normalize.normalize_show(raw, TAX)["seasons"] is None


def test_recorded_season_count_is_kept():
    show = normalize.normalize_show(_load("lezwatch_show_derry_girls.json"), TAX)
    assert show["seasons"] == 3
