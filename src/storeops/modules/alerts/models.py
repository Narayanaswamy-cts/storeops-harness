"""Alert domain records and wire schemas."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

__all__ = [
    "Alert",
    "AlertCreate",
    "AlertFilter",
    "AlertRead",
    "AlertSeverity",
    "AlertState",
]


class AlertSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertState(StrEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class Alert(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    store_id: str
    kind: str
    severity: AlertSeverity = AlertSeverity.INFO
    state: AlertState = AlertState.OPEN
    message: str
    source_event: str | None = None
    raised_at: datetime
    acknowledged_at: datetime | None = None
    acknowledged_by: str | None = None


class AlertCreate(BaseModel):
    store_id: str
    kind: str
    message: str
    severity: AlertSeverity = AlertSeverity.INFO
    source_event: str | None = None


class AlertRead(BaseModel):
    id: str
    store_id: str
    kind: str
    severity: AlertSeverity
    state: AlertState
    message: str
    raised_at: datetime
    acknowledged_at: datetime | None

    @classmethod
    def from_domain(cls, alert: Alert) -> AlertRead:
        return cls(
            id=alert.id,
            store_id=alert.store_id,
            kind=alert.kind,
            severity=alert.severity,
            state=alert.state,
            message=alert.message,
            raised_at=alert.raised_at,
            acknowledged_at=alert.acknowledged_at,
        )


class AlertFilter(BaseModel):
    store_id: str | None = None
    severity: AlertSeverity | None = None
    state: AlertState | None = None
