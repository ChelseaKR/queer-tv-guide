from __future__ import annotations

import pytest

from qtv_pipeline.http import PacedClient
from qtv_pipeline.terms import TermsChanged, check_lezwatch_terms


def test_grant_present_passes(mock_transport, no_sleep):
    sleep, _ = no_sleep
    with PacedClient(transport=mock_transport, sleep=sleep) as client:
        check = check_lezwatch_terms(client)
    assert check.grant_present is True


def test_grant_removed_is_a_hard_stop(mock_transport_no_grant, no_sleep):
    """Negative control: if LezWatch's ToS page no longer contains the reuse
    grant, the pipeline must refuse to run rather than mirror on stale trust."""
    sleep, _ = no_sleep
    with PacedClient(transport=mock_transport_no_grant, sleep=sleep) as client:
        with pytest.raises(TermsChanged, match="no longer contains"):
            check_lezwatch_terms(client)
