"""Alert HTTP surface — endpoints 7-8."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Query

from storeops.core.pagination import Page, PageParams
from storeops.modules.alerts.models import (
    AlertFilter,
    AlertRead,
    AlertSeverity,
    AlertState,
)
from storeops.modules.alerts.service import AlertServiceDep

__all__ = ["router"]

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=Page[AlertRead], summary="List operational alerts")
async def list_alerts(
    service: AlertServiceDep,
    params: Annotated[PageParams, Depends()],
    store_id: Annotated[str | None, Query()] = None,
    severity: Annotated[AlertSeverity | None, Query()] = None,
    alert_state: Annotated[AlertState | None, Query(alias="state")] = None,
) -> Page[AlertRead]:
    criteria = AlertFilter(store_id=store_id, severity=severity, state=alert_state)
    rows, total = await service.list(criteria, limit=params.limit, offset=params.offset)
    return Page.of([AlertRead.from_domain(row) for row in rows], total, params)


@router.post(
    "/{alert_id}/acknowledge",
    response_model=AlertRead,
    summary="Acknowledge an open alert",
)
async def acknowledge_alert(
    service: AlertServiceDep,
    alert_id: str,
    acknowledged_by: Annotated[str, Body(embed=True, min_length=1)],
) -> AlertRead:
    alert = await service.acknowledge(alert_id, acknowledged_by=acknowledged_by)
    return AlertRead.from_domain(alert)
