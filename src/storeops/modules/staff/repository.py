"""Staff persistence. STUB: in-memory dict seeded with a couple of rows."""

from __future__ import annotations

from storeops.modules.staff.models import StaffFilter, StaffMember, StaffRole

__all__ = ["StaffRepository"]

_SEED: tuple[StaffMember, ...] = (
    StaffMember(
        id="stf_0001",
        store_id="store_001",
        first_name="Ada",
        last_name="Okonjo",
        role=StaffRole.MANAGER,
    ),
    StaffMember(
        id="stf_0002",
        store_id="store_001",
        first_name="Ravi",
        last_name="Menon",
        role=StaffRole.ASSOCIATE,
    ),
)


class StaffRepository:
    def __init__(self) -> None:
        self._rows: dict[str, StaffMember] = {member.id: member for member in _SEED}

    async def get(self, staff_id: str) -> StaffMember | None:
        return self._rows.get(staff_id)

    async def list(
        self,
        criteria: StaffFilter,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[StaffMember], int]:
        matches = [row for row in self._rows.values() if self._matches(row, criteria)]
        matches.sort(key=lambda row: row.id)
        return matches[offset : offset + limit], len(matches)

    async def headcount(self, store_id: str) -> int:
        return sum(1 for row in self._rows.values() if row.store_id == store_id and row.is_active)

    @staticmethod
    def _matches(row: StaffMember, criteria: StaffFilter) -> bool:
        if criteria.store_id is not None and row.store_id != criteria.store_id:
            return False
        if criteria.role is not None and row.role is not criteria.role:
            return False
        return not (criteria.active_only and not row.is_active)
