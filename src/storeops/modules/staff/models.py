"""Staff domain records and wire schemas (module-private)."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from storeops.modules.staff.port import StaffSummary

__all__ = ["StaffFilter", "StaffMember", "StaffRead", "StaffRole"]


class StaffRole(StrEnum):
    ASSOCIATE = "associate"
    SUPERVISOR = "supervisor"
    MANAGER = "manager"
    REGIONAL = "regional"


class StaffMember(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    store_id: str
    first_name: str
    last_name: str
    role: StaffRole = StaffRole.ASSOCIATE
    is_active: bool = True

    @property
    def display_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def to_summary(self) -> StaffSummary:
        return StaffSummary(
            id=self.id,
            store_id=self.store_id,
            display_name=self.display_name,
            role=self.role.value,
            is_active=self.is_active,
        )


class StaffRead(BaseModel):
    id: str
    store_id: str
    display_name: str
    role: StaffRole
    is_active: bool

    @classmethod
    def from_domain(cls, member: StaffMember) -> StaffRead:
        return cls(
            id=member.id,
            store_id=member.store_id,
            display_name=member.display_name,
            role=member.role,
            is_active=member.is_active,
        )


class StaffFilter(BaseModel):
    store_id: str | None = None
    role: StaffRole | None = None
    active_only: bool = True
