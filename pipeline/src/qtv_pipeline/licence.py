"""The licence and attribution text the snapshot carries and the app must
display. Kept as one source of truth, matching docs/LICENSES-AND-ATTRIBUTION.md
word for word; a diff between this file and that doc is a bug."""

from __future__ import annotations

from typing import Any

TERMS_READ_ON = "2026-09-13"

SNAPSHOT_LICENCE = {
    "spdx": "CC-BY-SA-4.0",
    "name": "Creative Commons Attribution-ShareAlike 4.0 International",
    "url": "https://creativecommons.org/licenses/by-sa/4.0/",
}

LICENCE_NOTICE = (
    "This dataset is published under the Creative Commons Attribution-ShareAlike "
    "4.0 International licence. Show and character data: LezWatch.TV. Episode "
    "and schedule data: TVmaze (CC BY-SA 4.0). If you redistribute this file, "
    "keep this notice and these credits."
)

ATTRIBUTION = [
    {
        "source": "lezwatch",
        "name": "LezWatch.TV",
        "url": "https://lezwatchtv.com/",
        "text": (
            "Show and character data from LezWatch.TV (https://lezwatchtv.com), "
            "the volunteer-run database of queer female, non-binary and "
            "transgender characters on TV. Used with thanks under its terms of "
            "use; LezWatch.TV does not endorse this app."
        ),
        "licence_name": "LezWatch.TV Terms of Use (free reuse, no formal open licence)",
        "licence_url": "https://lezwatchtv.com/tos/",
        "terms_url": "https://lezwatchtv.com/tos/",
        "terms_read_on": TERMS_READ_ON,
    },
    {
        "source": "tvmaze",
        "name": "TVmaze",
        "url": "https://www.tvmaze.com/",
        "text": (
            "Episode and schedule data from TVmaze (https://www.tvmaze.com), "
            "licensed under CC BY-SA 4.0 "
            "(https://creativecommons.org/licenses/by-sa/4.0/). Reformatted for "
            "this app; TVmaze provides the data as-is without warranty and does "
            "not endorse this app."
        ),
        "licence_name": "CC BY-SA 4.0",
        "licence_url": "https://creativecommons.org/licenses/by-sa/4.0/",
        "terms_url": "https://www.tvmaze.com/api",
        "terms_read_on": TERMS_READ_ON,
    },
]


def attribution_problems(doc: dict[str, Any]) -> list[str]:
    """Every way a built snapshot falls short of the attribution each source
    requires (docs/LICENSES-AND-ATTRIBUTION.md). Empty means complete.

    - LezWatch.TV ToS: "link back to us, or note us by name". Every show and
      character carries its LezWatch page (`source_url`) for the app to link.
    - TVmaze API licensing: CC BY-SA 4.0, attribution "by linking back to
      TVmaze ... using the URLs available in the API". Every joined schedule
      carries its TVmaze URL.
    - CC BY-SA 4.0 s.3(a)/(b): licence notice and URI, source credits, a
      modification notice, the warranty disclaimer.
    """
    by_source = {a.get("source"): a for a in doc.get("attribution") or []}
    return (
        _licence_problems(doc.get("licence") or {})
        + _lezwatch_problems(by_source.get("lezwatch"))
        + _tvmaze_problems(by_source.get("tvmaze"))
        + _record_problems(doc)
    )


def _licence_problems(lic: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    snap = lic.get("snapshot") or {}
    if snap.get("spdx") != "CC-BY-SA-4.0":
        problems.append(f"licence.snapshot.spdx is {snap.get('spdx')!r}, not CC-BY-SA-4.0")
    if snap.get("url") != SNAPSHOT_LICENCE["url"]:
        problems.append("licence.snapshot.url is not the CC BY-SA 4.0 URI")
    notice = lic.get("notice") or ""
    for needle in ("LezWatch.TV", "TVmaze", "CC BY-SA 4.0", "keep this notice"):
        if needle not in notice:
            problems.append(f"licence.notice does not mention {needle!r}")
    return problems


def _lezwatch_problems(entry: dict[str, Any] | None) -> list[str]:
    if not entry:
        return ["no LezWatch.TV attribution entry"]
    problems: list[str] = []
    if not str(entry.get("url", "")).startswith("https://lezwatchtv.com/"):
        problems.append("LezWatch.TV attribution does not link lezwatchtv.com")
    if "LezWatch.TV does not endorse this app" not in entry.get("text", ""):
        problems.append("LezWatch.TV attribution lacks the non-endorsement statement")
    return problems


def _tvmaze_problems(entry: dict[str, Any] | None) -> list[str]:
    if not entry:
        return ["no TVmaze attribution entry"]
    problems: list[str] = []
    if not str(entry.get("url", "")).startswith("https://www.tvmaze.com/"):
        problems.append("TVmaze attribution does not link tvmaze.com")
    if entry.get("licence_url") != SNAPSHOT_LICENCE["url"]:
        problems.append("TVmaze attribution does not link the CC BY-SA 4.0 licence")
    required = ("CC BY-SA 4.0", "Reformatted", "without warranty", "does not endorse this app")
    problems += [
        f"TVmaze attribution text lacks {needle!r}"
        for needle in required
        if needle not in entry.get("text", "")
    ]
    return problems


def _record_problems(doc: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    for record in [*(doc.get("shows") or []), *(doc.get("characters") or [])]:
        if not str(record.get("source_url", "")).startswith("https://lezwatchtv.com/"):
            problems.append(f"{record.get('id')}: no LezWatch.TV page to link")
    for show in doc.get("shows") or []:
        sched = show.get("schedule") or {}
        tvmaze_url = str(sched.get("tvmaze_url") or "")
        if sched.get("schedule_known") and not tvmaze_url.startswith("https://www.tvmaze.com/"):
            problems.append(f"{show.get('id')}: schedule shown without a TVmaze URL to credit")
    return problems
