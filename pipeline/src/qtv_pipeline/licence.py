"""The licence and attribution text the snapshot carries and the app must
display. Kept as one source of truth, matching docs/LICENSES-AND-ATTRIBUTION.md
word for word; a diff between this file and that doc is a bug."""

from __future__ import annotations

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
