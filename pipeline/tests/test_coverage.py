from __future__ import annotations

from qtv_pipeline import coverage


def test_field_presence_counts_both_sides():
    shows = [
        {
            "watch_links": [{"url": "https://a", "host": "a"}],
            "ratings": {"worth_it": "Yes", "quality": 3},
            "external_ids": {"imdb": "tt1"},
            "years": {"end": 2020},
            "seasons": 3,
            "schedule": {"schedule_known": True, "next_episode": None},
            "networks": [],
            "tropes": [],
        },
        {
            "watch_links": [],
            "ratings": {"worth_it": None, "quality": None},
            "external_ids": {"imdb": None},
            "years": {"end": None},
            "seasons": None,
            "schedule": {"schedule_known": False, "next_episode": None},
            "networks": [],
            "tropes": [],
        },
    ]
    characters = [
        {
            "death": {"death_known": True},
            "gender": {"slug": "x"},
            "sexuality": None,
            "romantic": None,
            "actors": [],
        },
        {
            "death": {"death_known": False},
            "gender": None,
            "sexuality": None,
            "romantic": None,
            "actors": [],
        },
    ]
    fields_cov = coverage.field_presence(shows, characters)
    assert fields_cov["shows.watch_links"] == {"present": 1, "absent": 1}
    assert fields_cov["shows.ratings.worth_it"] == {"present": 1, "absent": 1}
    assert fields_cov["shows.seasons"] == {"present": 1, "absent": 1}
    assert fields_cov["characters.death"] == {"present": 1, "absent": 1}
    assert fields_cov["characters.gender"] == {"present": 1, "absent": 1}


def test_tvmaze_coverage_categorizes_every_miss_reason():
    shows = [
        {
            "schedule": {"schedule_known": True, "join": {"method": "lwtv_tvmaze_id"}},
            "_join_ignored_by_source": False,
        },
        {
            "schedule": {"schedule_known": False, "join": {"method": "none"}},
            "_join_ignored_by_source": False,
        },  # no_key
        {
            "schedule": {"schedule_known": False, "join": {"method": "none"}},
            "_join_ignored_by_source": True,
        },  # ignored
        {
            "schedule": {"schedule_known": False, "join": {"method": "lwtv_tvmaze_id"}},
            "_join_ignored_by_source": False,
        },  # not_found
    ]
    cov = coverage.tvmaze_coverage(shows)
    assert cov == {
        "shows_total": 4,
        "with_join_key": 2,
        "joined": 1,
        "join_rate": 0.25,
        "misses": {"no_key": 1, "ignored_by_source": 1, "not_found": 1, "other": 0},
    }


def test_summary_lines_report_two_numbers_for_every_source():
    coverage_doc = {
        "lezwatch": {
            "shows": {"available": 10, "fetched": 10},
            "characters": {"available": 20, "fetched": 18},
            "actors": {"available": None, "fetched": 5},
        },
        "tvmaze": {
            "shows_total": 10,
            "with_join_key": 8,
            "joined": 6,
            "join_rate": 0.6,
            "misses": {"no_key": 2, "ignored_by_source": 0, "not_found": 2, "other": 0},
        },
        "fields": {"shows.watch_links": {"present": 4, "absent": 6}},
    }
    lines = "\n".join(coverage.summary_lines(coverage_doc))
    assert "10 fetched / 10 available" in lines
    assert "18 fetched / 20 available" in lines
    assert "6/10 shows" in lines
    assert "shows.watch_links: 4/10 present" in lines
