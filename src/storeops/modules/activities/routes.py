"""Activity HTTP surface — endpoints 1-3."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Query, status

from storeops.core.deps import BusDep
from storeops.core.pagination import Page, PageParams
from storeops.modules.activities.models import (
    ActivityCreate,
    ActivityFilter,
    ActivityRead,
    ActivityStatus,
    BulkStatusResult,
    BulkStatusUpdate,
)
from storeops.modules.activities.service import ActivityServiceDep

__all__ = ["router"]

router = APIRouter(prefix="/activities", tags=["activities"])


@router.get("", response_model=Page[ActivityRead], summary="List operational activities")
async def list_activities(
    service: ActivityServiceDep,
    params: Annotated[PageParams, Depends()],
    store_id: Annotated[str | None, Query()] = None,
    programme_id: Annotated[str | None, Query()] = None,
    activity_status: Annotated[ActivityStatus | None, Query(alias="status")] = None,
) -> Page[ActivityRead]:
    criteria = ActivityFilter(
        store_id=store_id,
        programme_id=programme_id,
        status=activity_status,
    )
    rows, total = await service.list(criteria, limit=params.limit, offset=params.offset)
    return Page.of([ActivityRead.from_domain(row) for row in rows], total, params)


@router.post(
    "",
    response_model=ActivityRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create an operational activity",
)
async def create_activity(
    service: ActivityServiceDep,
    payload: ActivityCreate,
) -> ActivityRead:
    return ActivityRead.from_domain(await service.create(payload))


@router.post(
    "/{activity_id}/complete",
    response_model=ActivityRead,
    summary="Mark an activity complete and notify subscribers",
)
async def complete_activity(
    service: ActivityServiceDep,
    bus: BusDep,
    activity_id: str,
    completed_by: Annotated[str, Body(embed=True, min_length=1)],
) -> ActivityRead:
    activity = await service.complete(activity_id, completed_by=completed_by, bus=bus)
    return ActivityRead.from_domain(activity)


@router.patch(
    "/bulk-status",
    response_model=BulkStatusResult,
    status_code=status.HTTP_207_MULTI_STATUS,
    summary="Apply one status to many activities during a shift handover",
)
async def bulk_update_status(
    service: ActivityServiceDep,
    bus: BusDep,
    payload: BulkStatusUpdate,
) -> BulkStatusResult:
    """Always 207: the code describes the per-item envelope, not the outcome.

    A batch where every item succeeded still returns 207, so clients parse one
    response shape rather than branching on the status line.
    """
    return await service.bulk_update_status(payload, bus=bus)
