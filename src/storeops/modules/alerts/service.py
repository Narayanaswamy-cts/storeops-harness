"""Alert business rules. STUB bodies, real error contract."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from storeops.core.errors import ConflictError, NotFoundError
from storeops.modules.alerts.models import Alert, AlertCreate, AlertFilter, AlertState
from storeops.modules.alerts.repository import AlertRepository

__all__ = ["AlertService", "AlertServiceDep", "get_alert_service"]


class AlertService:
    def __init__(self, repository: AlertRepository) -> None:
        self._repository = repository

    async def raise_alert(self, payload: AlertCreate) -> Alert:
        alert = Alert(
            id=f"alr_{uuid.uuid4().hex[:12]}",
            store_id=payload.store_id,
            kind=payload.kind,
            severity=payload.severity,
            message=payload.message,
            source_event=payload.source_event,
            raised_at=datetime.now(UTC),
        )
        return await self._repository.add(alert)

    async def list(
        self,
        criteria: AlertFilter,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[Alert], int]:
        return await self._repository.list(criteria, limit=limit, offset=offset)

    async def get(self, alert_id: str) -> Alert:
        alert = await self._repository.get(alert_id)
        if alert is None:
            raise NotFoundError.for_resource("alert", alert_id)
        return alert

    async def acknowledge(self, alert_id: str, *, acknowledged_by: str) -> Alert:
        alert = await self.get(alert_id)
        if alert.state is not AlertState.OPEN:
            raise ConflictError(
                f"Alert {alert_id!r} is {alert.state.value}, not open.",
                details={"state": alert.state.value},
            )
        acknowledged = alert.model_copy(
            update={
                "state": AlertState.ACKNOWLEDGED,
                "acknowledged_at": datetime.now(UTC),
                "acknowledged_by": acknowledged_by,
            }
        )
        return await self._repository.replace(acknowledged)

    async def open_count(self, store_id: str | None = None) -> int:
        """Read-only projection consumed by the reports module via a port."""
        return await self._repository.count_open(store_id)


@lru_cache(maxsize=1)
def get_alert_service() -> AlertService:
    return AlertService(AlertRepository())


AlertServiceDep = Annotated[AlertService, Depends(get_alert_service)]
