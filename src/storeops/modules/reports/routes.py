"""Report HTTP surface — endpoint 9."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from storeops.core.errors import ValidationError
from storeops.modules.reports.models import ScopeMetrics
from storeops.modules.reports.service import ReportServiceDep

__all__ = ["router"]

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get(
    "/metrics",
    response_model=ScopeMetrics,
    summary="Operational metrics for one store or one region",
)
async def get_metrics(
    service: ReportServiceDep,
    store_id: Annotated[str | None, Query()] = None,
    region_id: Annotated[str | None, Query()] = None,
) -> ScopeMetrics:
    if (store_id is None) == (region_id is None):
        raise ValidationError(
            "Supply exactly one of store_id or region_id.",
            details={"params": ["store_id", "region_id"]},
        )
    if store_id is not None:
        return await service.store_metrics(store_id)
    assert region_id is not None  # noqa: S101 -- narrowed by the guard above
    return await service.region_metrics(region_id)
