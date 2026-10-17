"""The developer's own Apple affiliate token (DECISIONS 0019).

After every other party's tag is stripped, the configured token goes on
Apple TV and iTunes where-to-watch links only, as one `at=` parameter, the
same in every link for every reader. With no token configured the snapshot
is byte for byte what it was before this feature; these tests hold both.
"""

from __future__ import annotations

import copy
import json

import httpx
import pytest

from qtv_pipeline import build as build_mod
from qtv_pipeline import cli, links

from .conftest import _load, build_handler

# A made-up affiliate value: public in every link by design, not a credential.
AFFILIATE_AT = "1l3vabc"

APPLE_TV = "https://tv.apple.com/us/show/example/umc.cmc.4ty2qd8ilbgi7fa0hi1hd9k3f?action=play"
ITUNES_TAGGED = (
    "https://itunes.apple.com/us/tv-season/three-buckets/id1255983706?i=1256690774"
    "&at=1001l6hu&ct=gca_organic_tv-episode_1255983706"
)
ITUNES_STRIPPED = "https://itunes.apple.com/us/tv-season/three-buckets/id1255983706?i=1256690774"
OTHERS = [
    "https://www.netflix.com/title/80238565",
    "https://www.amazon.com/gp/video/detail/amzn1.dv.gti.a55547a4?autoplay=1",
    "https://music.apple.com/us/album/example/123",
    "http://itunes.apple.com/us/tv-season/old/id1",
]


def test_no_token_changes_nothing():
    for url in [APPLE_TV, ITUNES_STRIPPED, *OTHERS]:
        assert links.add_apple_token(url, "") == url


def test_the_token_goes_on_apple_tv_and_itunes_links_only():
    assert links.add_apple_token(APPLE_TV, AFFILIATE_AT) == APPLE_TV + f"&at={AFFILIATE_AT}"
    assert (
        links.add_apple_token(ITUNES_STRIPPED, AFFILIATE_AT)
        == ITUNES_STRIPPED + f"&at={AFFILIATE_AT}"
    )
    bare = "https://tv.apple.com/us/movie/example/umc.cmc.1"
    assert links.add_apple_token(bare, AFFILIATE_AT) == bare + f"?at={AFFILIATE_AT}"
    for url in OTHERS:
        assert links.add_apple_token(url, AFFILIATE_AT) == url


def test_a_third_party_token_is_replaced_by_stripping_first_never_kept():
    out = links.add_apple_token(links.strip_tracking(ITUNES_TAGGED), AFFILIATE_AT)
    assert out == ITUNES_STRIPPED + f"&at={AFFILIATE_AT}"
    assert "1001l6hu" not in out and "ct=" not in out


def test_the_gate_allows_only_the_configured_token_once():
    own = ITUNES_STRIPPED + f"&at={AFFILIATE_AT}"
    assert links.tracking_params(own, AFFILIATE_AT) == []
    # Not configured, another token, a second copy, or on another Apple host: all caught.
    assert links.tracking_params(own) == ["at"]
    assert links.tracking_params(ITUNES_STRIPPED + "&at=someoneelse", AFFILIATE_AT) == ["at"]
    assert links.tracking_params(own + f"&at={AFFILIATE_AT}", AFFILIATE_AT) == ["at", "at"]
    assert links.tracking_params(
        f"https://apps.apple.com/us/app/id1?at={AFFILIATE_AT}", AFFILIATE_AT
    ) == ["at"]
    assert links.tracking_params(own + "&ct=campaign", AFFILIATE_AT) == ["ct"]


@pytest.mark.parametrize("bad", ["a b", "1l3", "x" * 33, "tok&ct=1", "tok=1"])
def test_a_malformed_token_is_refused(bad):
    assert not links.is_valid_apple_token(bad)


def _apple_show() -> dict:
    show = copy.deepcopy(_load("lezwatch_show_imdb_only.json"))
    show["id"] = 990002
    show["slug"] = "apple-links"
    show["link"] = "https://lezwatchtv.com/show/apple-links/"
    show["title"] = {"rendered": "Apple Links"}
    show["meta"]["lezshows_tvmaze_id"] = [""]
    show["meta"]["lezshows_imdb"] = [""]
    show["acf"]["lezshows_imdb"] = ""
    show["acf"]["lezshows_waystowatch"] = [{"url": u} for u in (APPLE_TV, ITUNES_TAGGED, OTHERS[0])]
    return show


def _build(tmp_path, no_sleep, **kwargs):
    sleep, _ = no_sleep
    from qtv_pipeline.http import PacedClient

    transport = httpx.MockTransport(build_handler(extra_shows=[_apple_show()]))
    cache, out = tmp_path / "cache", tmp_path / "out"
    build_mod.run_fetch(
        cache,
        full=True,
        log=lambda _m: None,
        client_factory=lambda **kw: PacedClient(transport=transport, sleep=sleep, **kw),
    )
    doc = build_mod.run_build(
        cache, out, git_sha="deadbeef", workflow_run_id="123", log=lambda _m: None, **kwargs
    )
    return doc, out


def _apple_links(doc) -> list[str]:
    return [
        w["url"] for w in next(s for s in doc["shows"] if s["slug"] == "apple-links")["watch_links"]
    ]


def test_with_no_token_the_snapshot_is_byte_identical(tmp_path, no_sleep):
    before, out_a = _build(tmp_path / "a", no_sleep)
    empty, out_b = _build(tmp_path / "b", no_sleep, apple_affiliate_token="")
    assert empty["content_digest"] == before["content_digest"]
    # Byte for byte, apart from the two fields that name the run itself.
    a = json.loads((out_a / "snapshot.v1.json").read_text())
    b = json.loads((out_b / "snapshot.v1.json").read_text())
    for doc in (a, b):
        doc.pop("generated_at")
        for source in doc["sources"].values():
            source.pop("fetched_at")
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    assert _apple_links(empty) == [APPLE_TV, ITUNES_STRIPPED, OTHERS[0]]


def test_with_a_token_only_apple_links_carry_it(tmp_path, no_sleep):
    doc, out = _build(tmp_path, no_sleep, apple_affiliate_token=AFFILIATE_AT)
    assert _apple_links(doc) == [
        APPLE_TV + f"&at={AFFILIATE_AT}",
        ITUNES_STRIPPED + f"&at={AFFILIATE_AT}",
        OTHERS[0],
    ]
    published = (out / "snapshot.v1.json").read_text()
    assert published.count(f"at={AFFILIATE_AT}") == 2
    assert "1001l6hu" not in published


def test_negative_control_a_token_the_build_was_not_given_fails_the_gate(
    tmp_path, no_sleep, monkeypatch
):
    """A token added without being configured (here: a sabotaged adder) is refused at publish."""
    real = links.add_apple_token
    calls: list[str] = []

    def sabotaged(url: str, _token: str) -> str:
        calls.append(url)
        return real(url, "someoneelse1")

    monkeypatch.setattr(links, "add_apple_token", sabotaged)
    with pytest.raises(build_mod.BuildError, match="affiliate or tracking parameters"):
        _build(tmp_path, no_sleep, apple_affiliate_token=AFFILIATE_AT)
    assert calls, "the sabotaged adder was never called"
    assert not (tmp_path / "out" / "snapshot.v1.json").exists()


def test_a_malformed_configured_token_stops_the_build(tmp_path, no_sleep):
    malformed = "not a valid value"
    with pytest.raises(build_mod.BuildError, match="apple affiliate token"):
        _build(tmp_path, no_sleep, apple_affiliate_token=malformed)


def test_the_cli_reads_the_token_from_the_environment(tmp_path, monkeypatch):
    seen = {}
    monkeypatch.setattr(build_mod, "run_build", lambda *a, **kw: seen.update(kw))
    monkeypatch.delenv("QTV_APPLE_AFFILIATE_TOKEN", raising=False)
    assert cli.main(["build", "--cache", str(tmp_path), "--out", str(tmp_path / "o")]) == 0
    assert seen["apple_affiliate_token"] == ""
    monkeypatch.setenv("QTV_APPLE_AFFILIATE_TOKEN", f" {AFFILIATE_AT} ")
    assert cli.main(["build", "--cache", str(tmp_path), "--out", str(tmp_path / "o")]) == 0
    assert seen["apple_affiliate_token"] == AFFILIATE_AT
