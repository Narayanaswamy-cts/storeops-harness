"""Staff business rules.

`StaffService` structurally satisfies `StaffDirectory`, so other modules can be
handed this instance while only ever seeing the read-only protocol.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from storeops.core.errors import NotFoundError
from storeops.modules.staff.models import StaffFilter, StaffMember
from storeops.modules.staff.port import StaffSummary
from storeops.modules.staff.repository import StaffRepository

__all__ = ["StaffService", "StaffServiceDep", "get_staff_service"]


class StaffService:
    def __init__(self, repository: StaffRepository) -> None:
        self._repository = repository

    # -- module-internal (full domain record) ------------------------------

    async def get(self, staff_id: str) -> StaffMember:
        member = await self._repository.get(staff_id)
        if member is None:
            raise NotFoundError.for_resource("staff member", staff_id)
        return member

    async def list(
        self,
        criteria: StaffFilter,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[StaffMember], int]:
        return await self._repository.list(criteria, limit=limit, offset=offset)

    # -- StaffDirectory implementation (what other modules may call) -------

    async def find(self, staff_id: str) -> StaffSummary | None:
        member = await self._repository.get(staff_id)
        return member.to_summary() if member else None

    async def headcount(self, store_id: str) -> int:
        return await self._repository.headcount(store_id)

    async def is_active(self, staff_id: str) -> bool:
        member = await self._repository.get(staff_id)
        return bool(member and member.is_active)


@lru_cache(maxsize=1)
def get_staff_service() -> StaffService:
    return StaffService(StaffRepository())


StaffServiceDep = Annotated[StaffService, Depends(get_staff_service)]
