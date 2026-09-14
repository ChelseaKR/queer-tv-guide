"""The licence gate.

Before any mirror runs, re-check that LezWatch.TV's terms of use still grant
reuse. The grant is a sentence on a page they can edit at any time, not a
versioned licence file, so the pipeline reads it fresh on every run rather than
trusting docs/LICENSES-AND-ATTRIBUTION.md to still be true.

TVmaze's grant is a stable, versioned licence (CC BY-SA 4.0) referenced by a
permanent URL; it is not re-fetched every run, only documented.
"""

from __future__ import annotations

from dataclasses import dataclass

from .http import PacedClient

LEZWATCH_TOS_URL = "https://lezwatchtv.com/tos/"
GRANT_SENTENCE = "use, reuse, and extend the data here for no fees"


class TermsChanged(RuntimeError):
    """The LezWatch ToS no longer contains the sentence the licence review relied on.

    This is a hard stop: docs/LICENSES-AND-ATTRIBUTION.md's verdict for LezWatch
    is only as good as that sentence. Nobody is contacted; the mirror does not run
    until a human re-reads the ToS and updates the licence doc.
    """


@dataclass(frozen=True)
class TermsCheck:
    url: str
    grant_present: bool

    def raise_if_changed(self) -> None:
        if not self.grant_present:
            raise TermsChanged(
                f"{self.url} no longer contains {GRANT_SENTENCE!r}. "
                "Re-read the terms, update docs/LICENSES-AND-ATTRIBUTION.md, "
                "and do not run the mirror until then. Do not contact LezWatch."
            )


def check_lezwatch_terms(client: PacedClient) -> TermsCheck:
    fetched = client.get(LEZWATCH_TOS_URL)
    assert fetched is not None
    present = GRANT_SENTENCE in fetched.text()
    check = TermsCheck(url=LEZWATCH_TOS_URL, grant_present=present)
    check.raise_if_changed()
    return check
