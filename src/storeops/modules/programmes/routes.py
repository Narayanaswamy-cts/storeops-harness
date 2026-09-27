"""Programme HTTP surface — endpoints 4-5."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from storeops.core.deps import BusDep
from storeops.core.pagination import Page, PageParams
from storeops.modules.programmes.models import (
    ProgrammeCreate,
    ProgrammeRead,
    ProgrammeStatus,
)
from storeops.modules.programmes.service import ProgrammeServiceDep

__all__ = ["router"]

router = APIRouter(prefix="/programmes", tags=["programmes"])


@router.get("", response_model=Page[ProgrammeRead], summary="List store programmes")
async def list_programmes(
    service: ProgrammeServiceDep,
    params: Annotated[PageParams, Depends()],
    programme_status: Annotated[ProgrammeStatus | None, Query(alias="status")] = None,
) -> Page[ProgrammeRead]:
    rows, total = await service.list(
        programme_status=programme_status, limit=params.limit, offset=params.offset
    )
    return Page.of([ProgrammeRead.from_domain(row) for row in rows], total, params)


@router.post(
    "",
    response_model=ProgrammeRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a store programme",
)
async def create_programme(
    service: ProgrammeServiceDep,
    bus: BusDep,
    payload: ProgrammeCreate,
) -> ProgrammeRead:
    return ProgrammeRead.from_domain(await service.create(payload, bus=bus))
