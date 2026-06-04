from pathlib import Path

import pytest

import ausbills
from ausbills.adapters import (
    ACTAdapter,
    FederalAdapter,
    NSWAdapter,
    NTAdapter,
    QLDAdapter,
    SAAdapter,
    TASAdapter,
    VICAdapter,
    WAAdapter,
)
from ausbills.errors import SourceBlockedError
from ausbills.fetch import is_blocked_response
from ausbills.models import Bill, DocumentLink, Jurisdiction


FIXTURES = Path(__file__).parent / "fixtures"


class FixtureFetcher:
    def __init__(self, jurisdiction: str):
        self.jurisdiction = jurisdiction.lower()

    def get_text(self, url: str, **kwargs) -> str:
        if url.endswith("/lh"):
            return self._read("detail.html")
        if "view/html" in url or "detail" in url or "bills.nsf" in url and "Current" not in url:
            return self._read("detail.html")
        if self.jurisdiction in {"act", "nt", "wa", "tas", "vic", "sa", "nsw", "federal"}:
            return self._read("list.html")
        return self._read("list.html")

    def get_json(self, url: str, **kwargs):
        return __import__("json").loads(self._read("list.json"))

    def _read(self, name: str) -> str:
        return (FIXTURES / self.jurisdiction / name).read_text()


ADAPTER_CASES = [
    (Jurisdiction.ACT, ACTAdapter),
    (Jurisdiction.QLD, QLDAdapter),
    (Jurisdiction.NT, NTAdapter),
    (Jurisdiction.WA, WAAdapter),
    (Jurisdiction.TAS, TASAdapter),
    (Jurisdiction.VIC, VICAdapter),
    (Jurisdiction.SA, SAAdapter),
    (Jurisdiction.NSW, NSWAdapter),
    (Jurisdiction.FEDERAL, FederalAdapter),
]


@pytest.mark.parametrize(("jurisdiction", "adapter_cls"), ADAPTER_CASES)
def test_adapter_lists_and_hydrates_fixture_bill(jurisdiction, adapter_cls):
    adapter = adapter_cls(FixtureFetcher(jurisdiction.value))

    bills = adapter.list_bills()
    assert bills
    assert all(isinstance(bill, Bill) for bill in bills)
    assert bills[0].jurisdiction == jurisdiction
    assert bills[0].id
    assert bills[0].title
    assert bills[0].source_url.startswith("https://")

    detailed = adapter.get_bill(bills[0].id)
    assert isinstance(detailed, Bill)
    assert detailed.documents
    assert all(isinstance(doc, DocumentLink) for doc in detailed.documents)


def test_public_api_exports_new_surface():
    assert Jurisdiction.ACT in ausbills.list_jurisdictions()
    assert ausbills.Bill is Bill
    assert ausbills.SourceBlockedError is SourceBlockedError


def test_blocked_source_detection():
    challenge = (FIXTURES / "blocked" / "cloudflare.html").read_text()
    assert is_blocked_response(challenge, 503)
