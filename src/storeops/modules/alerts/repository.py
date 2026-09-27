"""Alert persistence. STUB: in-memory dict, real signatures."""

from __future__ import annotations

from storeops.modules.alerts.models import Alert, AlertFilter, AlertState

__all__ = ["AlertRepository"]


class AlertRepository:
    def __init__(self) -> None:
        self._rows: dict[str, Alert] = {}

    async def add(self, alert: Alert) -> Alert:
        self._rows[alert.id] = alert
        return alert

    async def get(self, alert_id: str) -> Alert | None:
        return self._rows.get(alert_id)

    async def replace(self, alert: Alert) -> Alert:
        self._rows[alert.id] = alert
        return alert

    async def list(
        self,
        criteria: AlertFilter,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[Alert], int]:
        matches = [row for row in self._rows.values() if self._matches(row, criteria)]
        matches.sort(key=lambda row: row.raised_at, reverse=True)
        return matches[offset : offset + limit], len(matches)

    async def count_open(self, store_id: str | None = None) -> int:
        return sum(
            1
            for row in self._rows.values()
            if row.state is AlertState.OPEN and (store_id is None or row.store_id == store_id)
        )

    @staticmethod
    def _matches(row: Alert, criteria: AlertFilter) -> bool:
        if criteria.store_id is not None and row.store_id != criteria.store_id:
            return False
        if criteria.severity is not None and row.severity is not criteria.severity:
            return False
        return not (criteria.state is not None and row.state is not criteria.state)
