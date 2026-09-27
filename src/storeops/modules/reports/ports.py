"""Read-only ports the reports module needs from elsewhere.

Reports aggregates data owned by other modules. Rather than importing those
modules (which would create a cycle the moment any of them ever needed a
report), it declares the narrow read contracts it requires here and has them
injected by the composition root in `storeops.main`.

The staff figure comes from `staff.port.StaffDirectory` — the one cross-module
import the boundary rules allow, and read-only by construction.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from storeops.modules.staff.port import StaffDirectory

__all__ = ["ActivityMetrics", "AlertMetrics", "MetricsSources", "ProgrammeMetrics"]


class ActivityMetrics(Protocol):
    async def status_breakdown(self, store_id: str | None = None) -> dict[str, int]: ...


class ProgrammeMetrics(Protocol):
    async def active_count(self, store_id: str | None = None) -> int: ...


class AlertMetrics(Protocol):
    async def open_count(self, store_id: str | None = None) -> int: ...


@dataclass(frozen=True)
class MetricsSources:
    activities: ActivityMetrics
    programmes: ProgrammeMetrics
    alerts: AlertMetrics
    staff: StaffDirectory
