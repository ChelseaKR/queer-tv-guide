"""Other parties' affiliate tags and click trackers never reach the snapshot.

The URLs here are the real ones in the snapshot published on 2026-10-12
(LezWatch.TV where-to-watch links): three Amazon links carrying Associates
tags (DuckDuckGo's `duckduckgo-d-20`, IMDb's `imdbtag_tt_wbr_fdv-20`, and an
unknown `justus1ktp-20`), iTunes links with an affiliate token, and Hulu and
Paramount+ links with referral or campaign trackers. Each is stripped and
nothing is added; the parameters that make the link work stay byte for byte.

The negative controls run the whole build with stripping switched off and
assert the publish gate refuses it, after asserting the tagged link really
reached the gate.

One real link also carried a `SubscriptionId` that is an AWS access key id
(an old Amazon Product Advertising key, public in the source data). It is
replaced here by a placeholder so the repository holds no key; the build
strips the parameter either way.
"""

from __future__ import annotations

import copy

import httpx
import pytest

from qtv_pipeline import build as build_mod
from qtv_pipeline import links, normalize

from .conftest import _load, build_handler
from .test_build_end_to_end import _run

STRIPPED = [
    (
        "https://www.amazon.com/Episode-0001/dp/B003BOQVF0?SubscriptionId=EXAMPLE-SUBSCRIPTION-ID"
        "&tag=duckduckgo-d-20&linkCode=xm2&camp=2025&creative=165953&creativeASIN=B003BOQVF0",
        "https://www.amazon.com/Episode-0001/dp/B003BOQVF0",
    ),
    (
        "https://www.amazon.com/gp/video/detail/amzn1.dv.gti.4c53949f-a844-4e9f-ba57-0b4dba3cc3af"
        "?ref=imdb_web&autoplay=1&ref_=imdbref_tt_wbr_fdv&tag=imdbtag_tt_wbr_fdv-20",
        "https://www.amazon.com/gp/video/detail/amzn1.dv.gti.4c53949f-a844-4e9f-ba57-0b4dba3cc3af"
        "?autoplay=1",
    ),
    (
        "https://www.amazon.com/gp/video/detail/amzn1.dv.gti.a55547a4-609c-4d85-99cf-71c5a2474c52"
        "?tag=justus1ktp-20&token=ADE07EB7B9E7DB86DEEEF0D5D4FC5F0B5FB44D3F",
        "https://www.amazon.com/gp/video/detail/amzn1.dv.gti.a55547a4-609c-4d85-99cf-71c5a2474c52",
    ),
    (
        "https://www.amazon.com/gp/video/detail/amzn1.dv.gti.30b4f761-f76e-d67e-a77c-afe06562e92e"
        "?autoplay=1&ref_=atv_cf_strg_wb",
        "https://www.amazon.com/gp/video/detail/amzn1.dv.gti.30b4f761-f76e-d67e-a77c-afe06562e92e"
        "?autoplay=1",
    ),
    (
        "https://itunes.apple.com/us/tv-season/three-buckets/id1255983706?i=1256690774"
        "&at=1001l6hu&ct=gca_organic_tv-episode_1255983706",
        "https://itunes.apple.com/us/tv-season/three-buckets/id1255983706?i=1256690774",
    ),
    (
        "https://www.paramountplus.com/shows/csi/?searchReferral=google&ftag=PPM-23-10ahb7b",
        "https://www.paramountplus.com/shows/csi/",
    ),
    (
        "https://www.hulu.com/series/example?mbsy_source=a&mbsy=b&referral_reward_type=c"
        "&campaignid=d&dl=1#episodes",
        "https://www.hulu.com/series/example?dl=1#episodes",
    ),
    (
        "https://tv.youtube.com/browse/example?utm_source=x&utm_medium=y&fbclid=z",
        "https://tv.youtube.com/browse/example",
    ),
]

# Links that work by their query and carry no tracker: left exactly as they are.
UNCHANGED = [
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLZ4M4eic7acQUVnSQi8-4mKBQFYFYZo-j",
    "https://watch.amazon.com/detail?asin=B0B8T4ZZ6R",
    "https://tv.apple.com/us/show/example/umc.cmc.1?action=play",
    "https://www.netflix.com/title/80238565?source=35",
    "https://www.iq.com/play/example?lang=en_us",
    "https://www.netflix.com/title/80238565",
    # A query parameter merely named like an Amazon one, on another host.
    "https://www.example.org/watch?tag=drama&ref=home",
    "mailto:someone@example.org?subject=x",
]


@pytest.mark.parametrize(("tagged", "clean"), STRIPPED)
def test_a_tagged_link_is_stripped_and_nothing_is_added(tagged, clean):
    assert links.tracking_params(tagged), "the example carries no listed parameter"
    assert links.strip_tracking(tagged) == clean
    assert links.tracking_params(clean) == []
    # Stripped again, nothing moves.
    assert links.strip_tracking(clean) == clean


@pytest.mark.parametrize("url", UNCHANGED)
def test_a_clean_link_is_left_byte_for_byte(url):
    assert links.tracking_params(url) == []
    assert links.strip_tracking(url) == url


def test_every_affiliate_tag_from_the_published_snapshot_is_gone():
    for tagged, _clean in STRIPPED:
        stripped = links.strip_tracking(tagged)
        for tag in ("duckduckgo-d-20", "imdbtag_tt_wbr_fdv-20", "justus1ktp-20", "1001l6hu"):
            assert tag not in stripped


def test_watch_links_are_stripped_when_normalized():
    out = normalize._watch_links([{"url": STRIPPED[0][0]}, {"url": UNCHANGED[0]}])
    assert out == [
        {"url": STRIPPED[0][1], "host": "www.amazon.com"},
        {"url": UNCHANGED[0], "host": "www.youtube.com"},
    ]


def _tagged_show() -> dict:
    show = copy.deepcopy(_load("lezwatch_show_imdb_only.json"))
    show["id"] = 990001
    show["slug"] = "tagged-links"
    show["link"] = "https://lezwatchtv.com/show/tagged-links/"
    show["title"] = {"rendered": "Tagged Links"}
    show["meta"]["lezshows_tvmaze_id"] = [""]
    show["meta"]["lezshows_imdb"] = [""]
    show["acf"]["lezshows_imdb"] = ""
    show["acf"]["lezshows_waystowatch"] = [{"url": tagged} for tagged, _ in STRIPPED[:3]]
    return show


def test_the_build_publishes_the_tagged_shows_links_stripped(tmp_path, no_sleep):
    sleep, _ = no_sleep
    transport = httpx.MockTransport(build_handler(extra_shows=[_tagged_show()]))
    doc, _cache, out_dir = _run(tmp_path, transport, sleep)
    show = next(s for s in doc["shows"] if s["slug"] == "tagged-links")
    assert [w["url"] for w in show["watch_links"]] == [clean for _, clean in STRIPPED[:3]]
    published = (out_dir / "snapshot.v1.json").read_text(encoding="utf-8")
    assert "tag=" not in published and "linkCode" not in published


def test_negative_control_a_tagged_link_fails_the_publish_gate(tmp_path, no_sleep, monkeypatch):
    """With stripping switched off, the gate refuses the build and writes nothing."""
    seen: list[str] = []

    def no_strip(url: str) -> str:
        seen.append(url)
        return url

    monkeypatch.setattr(links, "strip_tracking", no_strip)
    sleep, _ = no_sleep
    transport = httpx.MockTransport(build_handler(extra_shows=[_tagged_show()]))
    with pytest.raises(build_mod.BuildError, match="affiliate or tracking parameters"):
        _run(tmp_path, transport, sleep)
    # The sabotage applied: the tagged link went through the switched-off strip.
    assert STRIPPED[0][0] in seen
    assert not (tmp_path / "out" / "snapshot.v1.json").exists()


def test_the_gate_names_where_the_tag_is():
    doc = {"shows": [{"watch_links": [{"url": STRIPPED[2][0], "host": "www.amazon.com"}]}]}
    with pytest.raises(build_mod.BuildError) as raised:
        build_mod._check_outbound_links(doc)
    assert "shows[0].watch_links[0].url: tag, token" in str(raised.value)
    build_mod._check_outbound_links({"shows": [{"watch_links": [{"url": STRIPPED[2][1]}]}]})
