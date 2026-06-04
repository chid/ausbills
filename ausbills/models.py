from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import json


class Jurisdiction(str, Enum):
    FEDERAL = "FEDERAL"
    NSW = "NSW"
    WA = "WA"
    NT = "NT"
    QLD = "QLD"
    VIC = "VIC"
    SA = "SA"
    TAS = "TAS"
    ACT = "ACT"


@dataclass(frozen=True)
class DocumentLink:
    url: str
    kind: str
    house: str | None = None
    date: str | None = None
    mime_type: str | None = None


@dataclass(frozen=True)
class Progress:
    current_stage: str | None = None
    passed_lower: bool = False
    passed_upper: bool = False
    assented: bool = False


@dataclass
class Bill:
    id: str
    jurisdiction: Jurisdiction
    title: str
    source_url: str
    status: str | None = None
    house: str | None = None
    introduced_date: str | None = None
    assent_date: str | None = None
    sponsor: str | None = None
    portfolio: str | None = None
    summary: str | None = None
    progress: Progress = field(default_factory=Progress)
    documents: list[DocumentLink] = field(default_factory=list)

    def as_dict(self) -> dict:
        return asdict(self)

    def as_json(self) -> str:
        return json.dumps(self.as_dict(), indent=2)

    # Backward-compatible spellings for callers that only need serialization.
    def asDict(self) -> dict:
        return self.as_dict()

    def asJson(self) -> str:
        return self.as_json()
