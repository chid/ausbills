import os

import pytest

import ausbills
from ausbills.errors import SourceBlockedError


pytestmark = pytest.mark.live


@pytest.mark.skipif(not os.getenv("AUSBILLS_LIVE"), reason="set AUSBILLS_LIVE=1 to run live smoke tests")
@pytest.mark.parametrize("jurisdiction", ausbills.list_jurisdictions())
def test_live_get_bills_returns_sample(jurisdiction):
    try:
        bills = ausbills.get_bills(jurisdiction)
    except SourceBlockedError as exc:
        pytest.skip(str(exc))
    assert bills
    assert bills[0].title
