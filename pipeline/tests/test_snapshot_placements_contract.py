"""The placement fields are additive (DECISIONS 0041): a file without them is still a
valid v1 snapshot, a file with them is one too, the shipped 1.0.0 apps read it
(GuideCore's PlacementFieldsCompatibilityTests and Android's
PlacementFieldsCompatibilityTest decode the fixture checked here), and the
website renders exactly what it rendered before.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest

from qtv_pipeline import airing_page, show_pages, site_index
from qtv_pipeline import build as build_mod

REPO = Path(__file__).resolve().parents[2]
FIXTURES = REPO / "ios" / "GuideCore" / "Tests" / "Fixtures"
V1_FIXTURE = FIXTURES / "snapshot.fixture.json"
PLACEMENTS_FIXTURE = FIXTURES / "snapshot.placements.fixture.json"


def _validator() -> jsonschema.Draft202012Validator:
    return jsonschema.Draft202012Validator(json.loads(build_mod._find_schema_path().read_text()))


def _without_placements(doc: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(doc)
    out["coverage"].pop("placements", None)
    for show in out["shows"]:
        show.pop("episode_counts", None)
    for char in out["characters"]:
        for entry in char["death"]["dates"]:
            entry.pop("placements", None)
    return out


def test_schema_version_stays_1() -> None:
    """Additive fields keep the major version (schema/README.md); the 1.0.0 apps
    refuse any schema_version but "1", so bumping it would cut them off."""
    schema = json.loads(build_mod._find_schema_path().read_text())
    assert schema["properties"]["schema_version"] == {
        "const": "1",
        "description": schema["properties"]["schema_version"]["description"],
    }
    assert json.loads(PLACEMENTS_FIXTURE.read_text())["schema_version"] == "1"


def test_a_file_from_before_the_new_fields_still_validates() -> None:
    _validator().validate(json.loads(V1_FIXTURE.read_text()))


def test_the_placements_fixture_is_the_v1_fixture_plus_only_the_new_fields() -> None:
    """So the app tests that decode it prove exactly one thing: the new fields are
    ignored and nothing else changed."""
    with_fields = json.loads(PLACEMENTS_FIXTURE.read_text())
    _validator().validate(with_fields)
    assert _without_placements(with_fields) == json.loads(V1_FIXTURE.read_text())
    assert "placements" in with_fields["coverage"]
    assert all("episode_counts" in s for s in with_fields["shows"])


@pytest.mark.parametrize(
    ("edit", "why"),
    [
        (lambda p: p.update(precision="exact"), "precision outside the enum"),
        (lambda p: p.update(episodes=[1, 2, 3]), "more than two episodes"),
        (lambda p: p.update(episodes=[]), "an empty episode list instead of null"),
        (lambda p: p.pop("reason"), "a placement without its reason"),
        (lambda p: p.update(airdate="June"), "an airdate that is not a date"),
    ],
)
def test_the_schema_rejects_a_malformed_placement(edit, why) -> None:
    doc = json.loads(PLACEMENTS_FIXTURE.read_text())
    entry = next(e for c in doc["characters"] for e in c["death"]["dates"])
    edit(entry["placements"][0])
    assert list(_validator().iter_errors(doc)), f"schema accepted {why}"


def test_the_schema_rejects_zero_as_an_episode_count() -> None:
    doc = json.loads(PLACEMENTS_FIXTURE.read_text())
    doc["shows"][0]["episode_counts"] = [{"season": 1, "episodes": 0}]
    assert list(_validator().iter_errors(doc))
    doc["shows"][0]["episode_counts"] = []  # "no episodes" is null, never an empty list
    assert list(_validator().iter_errors(doc))


# ---- the end-to-end build carries them ------------------------------------------


def test_the_built_snapshot_places_the_fixture_death(tmp_path, mock_transport, no_sleep) -> None:
    from qtv_pipeline.http import PacedClient

    sleep, _ = no_sleep

    def client_factory(**kwargs):
        return PacedClient(transport=mock_transport, sleep=sleep, **kwargs)

    cache = tmp_path / "cache"
    build_mod.run_fetch(cache, full=True, log=lambda _m: None, client_factory=client_factory)
    lines: list[str] = []
    doc = build_mod.run_build(cache, tmp_path / "out", log=lines.append)
    _validator().validate(doc)

    dead = next(c for c in doc["characters"] if c["death"]["death_known"])
    [placement] = dead["death"]["dates"][0]["placements"]
    assert placement == {
        "show_id": dead["shows"][0]["show_id"],
        "precision": "episode",
        "reason": "exact_date",
        "season": 1,
        "episodes": [4],
        "airdate": None,
    }
    by_slug = {s["slug"]: s for s in doc["shows"]}
    assert by_slug["derry-girls"]["episode_counts"] == [{"season": 1, "episodes": 4}]
    # Joined, but no recorded death there, so no list was fetched: unknown, not zero.
    assert by_slug["imdb-only-show"]["episode_counts"] is None
    assert by_slug["no-key-show"]["episode_counts"] is None

    cov = doc["coverage"]["placements"]
    assert cov["death_events"] == 1
    assert cov["by_precision"]["episode"] == 1
    assert cov["episode_lists"] == {"wanted": 1, "cached": 1}
    assert any(line.startswith("death placement: 1/1") for line in lines)

    cached = (cache / "tvmaze" / "episodes" / "33320.json").read_text()
    assert "Invented" not in cached and "summary" not in cached and "image" not in cached


# ---- the website does not change ----------------------------------------------------


def _site(doc: dict[str, Any]) -> dict[str, str]:
    pages = dict(show_pages.render_site(doc, pinned=None))
    pages["index.html"] = site_index.render_index(
        doc, shows_link=True, shows_total=3, featured=[], featured_total=0, airing_link=True
    )
    pages["data/index.html"] = site_index.render_data_page(doc)
    pages[site_index.NOT_FOUND_PATH] = site_index.render_not_found(
        doc, shows_link=True, airing_link=True
    )
    shows, _notes = show_pages.plan_selection(doc, show_pages.DEFAULT_LIMIT, None)
    built = {s["id"]: f"/shows/{s['slug']}/" for s in shows}
    plan = airing_page.plan_airing(doc, built)
    pages["airing notes"] = "\n".join(plan.notes)
    return pages


def test_the_site_renders_the_same_with_or_without_the_new_fields() -> None:
    """This change adds data only. Every page, the 404 page, the sitemap, robots.txt and the
    airing-now plan come out byte for byte as they did."""
    with_fields = json.loads(PLACEMENTS_FIXTURE.read_text())
    before = _site(_without_placements(with_fields))
    after = _site(with_fields)
    assert len(before) > 3
    assert after == before


def test_the_site_check_would_notice_a_changed_page() -> None:
    """Negative control for the test above: a change that does reach a page is seen."""
    with_fields = json.loads(PLACEMENTS_FIXTURE.read_text())
    changed = copy.deepcopy(with_fields)
    changed["shows"][1]["title"] = changed["shows"][1]["title"] + " Renamed"
    assert _site(changed) != _site(with_fields)


def test_no_page_mentions_an_episode_placement() -> None:
    with_fields = json.loads(PLACEMENTS_FIXTURE.read_text())
    text = "\n".join(_site(with_fields).values())
    for word in ("placement", "exact_date", "episode_counts", "season 2, episode 7"):
        assert word not in text
