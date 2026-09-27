"""Report wire schemas."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

__all__ = ["MetricsScope", "ScopeMetrics", "StoreRegion"]


class MetricsScope(StrEnum):
    STORE = "store"
    REGION = "region"


class StoreRegion(BaseModel):
    store_id: str
    region_id: str


class ScopeMetrics(BaseModel):
    scope: MetricsScope
    scope_id: str
    generated_at: datetime
    store_count: int = 0
    active_programmes: int = 0
    open_alerts: int = 0
    active_staff: int = 0
    activities_by_status: dict[str, int] = Field(default_factory=dict)

    @property
    def completion_rate(self) -> float:
        """Share of non-cancelled activities that are complete."""
        counted = {
            key: value for key, value in self.activities_by_status.items() if key != "cancelled"
        }
        total = sum(counted.values())
        return round(counted.get("completed", 0) / total, 4) if total else 0.0
