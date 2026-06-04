from __future__ import annotations

from .adapters import (
    ACTAdapter,
    FederalAdapter,
    NSWAdapter,
    NTAdapter,
    QLDAdapter,
    SAAdapter,
    TASAdapter,
    VICAdapter,
    WAAdapter,
    Adapter,
)
from .fetch import make_fetcher
from .models import Bill, Jurisdiction


ADAPTERS: dict[Jurisdiction, type[Adapter]] = {
    Jurisdiction.ACT: ACTAdapter,
    Jurisdiction.QLD: QLDAdapter,
    Jurisdiction.NT: NTAdapter,
    Jurisdiction.WA: WAAdapter,
    Jurisdiction.TAS: TASAdapter,
    Jurisdiction.VIC: VICAdapter,
    Jurisdiction.SA: SAAdapter,
    Jurisdiction.NSW: NSWAdapter,
    Jurisdiction.FEDERAL: FederalAdapter,
}


def normalize_jurisdiction(jurisdiction: Jurisdiction | str) -> Jurisdiction:
    if isinstance(jurisdiction, Jurisdiction):
        return jurisdiction
    try:
        return Jurisdiction[jurisdiction.upper()]
    except KeyError:
        return Jurisdiction(jurisdiction.upper())


def list_jurisdictions() -> list[Jurisdiction]:
    return list(ADAPTERS)


def get_adapter(jurisdiction: Jurisdiction | str, *, backend: str = "auto") -> Adapter:
    normalized = normalize_jurisdiction(jurisdiction)
    return ADAPTERS[normalized](make_fetcher(backend))


def get_bills(
    jurisdiction: Jurisdiction | str,
    *,
    include_details: bool = False,
    backend: str = "auto",
) -> list[Bill]:
    adapter = get_adapter(jurisdiction, backend=backend)
    bills = adapter.list_bills()
    if include_details:
        bills = [adapter.get_bill(bill.id) for bill in bills]
    return bills


def get_bill(
    jurisdiction: Jurisdiction | str,
    bill_id: str,
    *,
    backend: str = "auto",
) -> Bill:
    return get_adapter(jurisdiction, backend=backend).get_bill(bill_id)
