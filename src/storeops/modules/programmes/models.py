"""Programme domain records and wire schemas."""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "Programme",
    "ProgrammeCreate",
    "ProgrammeRead",
    "ProgrammeStatus",
]


class ProgrammeStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    CLOSED = "closed"


class Programme(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    status: ProgrammeStatus = ProgrammeStatus.DRAFT
    store_ids: tuple[str, ...] = ()
    starts_on: date | None = None
    ends_on: date | None = None


class ProgrammeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    store_ids: list[str] = Field(default_factory=list, max_length=5000)
    starts_on: date | None = None
    ends_on: date | None = None
    activate_immediately: bool = False


class ProgrammeRead(BaseModel):
    id: str
    name: str
    status: ProgrammeStatus
    store_ids: list[str]
    starts_on: date | None
    ends_on: date | None

    @classmethod
    def from_domain(cls, programme: Programme) -> ProgrammeRead:
        return cls(
            id=programme.id,
            name=programme.name,
            status=programme.status,
            store_ids=list(programme.store_ids),
            starts_on=programme.starts_on,
            ends_on=programme.ends_on,
        )
