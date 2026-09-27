"""Staff HTTP surface — endpoint 6."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from storeops.core.pagination import Page, PageParams
from storeops.modules.staff.models import StaffFilter, StaffRead, StaffRole
from storeops.modules.staff.service import StaffServiceDep

__all__ = ["router"]

router = APIRouter(prefix="/staff", tags=["staff"])


@router.get("", response_model=Page[StaffRead], summary="List store staff")
async def list_staff(
    service: StaffServiceDep,
    params: Annotated[PageParams, Depends()],
    store_id: Annotated[str | None, Query()] = None,
    role: Annotated[StaffRole | None, Query()] = None,
    active_only: Annotated[bool, Query()] = True,
) -> Page[StaffRead]:
    criteria = StaffFilter(store_id=store_id, role=role, active_only=active_only)
    rows, total = await service.list(criteria, limit=params.limit, offset=params.offset)
    return Page.of([StaffRead.from_domain(row) for row in rows], total, params)
