"""Report aggregation. STUB arithmetic, real boundary contract.

`configure_sources` is the seam the composition root uses to inject the read
ports. Until it is called the service raises `DependencyError` rather than
silently reporting zeroes.
"""

from __future__ import annotations

from datetime import UTC, datetime
from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from storeops.core.errors import DependencyError, NotFoundError
from storeops.modules.reports.models import MetricsScope, ScopeMetrics
from storeops.modules.reports.ports import MetricsSources
from storeops.modules.reports.repository import ReportRepository

__all__ = [
    "ReportService",
    "ReportServiceDep",
    "configure_sources",
    "get_report_service",
]

_sources: MetricsSources | None = None


def configure_sources(sources: MetricsSources) -> None:
    """Called once from `storeops.main` during app construction."""
    global _sources  # noqa: PLW0603 -- single wiring seam, set once at startup
    _sources = sources


class ReportService:
    def __init__(self, repository: ReportRepository) -> None:
        self._repository = repository

    @staticmethod
    def _require_sources() -> MetricsSources:
        if _sources is None:
            raise DependencyError("Reports metrics sources have not been configured.")
        return _sources

    async def store_metrics(self, store_id: str) -> ScopeMetrics:
        if not await self._repository.store_exists(store_id):
            raise NotFoundError.for_resource("store", store_id)
        sources = self._require_sources()
        return ScopeMetrics(
            scope=MetricsScope.STORE,
            scope_id=store_id,
            generated_at=datetime.now(UTC),
            store_count=1,
            active_programmes=await sources.programmes.active_count(store_id),
            open_alerts=await sources.alerts.open_count(store_id),
            active_staff=await sources.staff.headcount(store_id),
            activities_by_status=await sources.activities.status_breakdown(store_id),
        )

    async def region_metrics(self, region_id: str) -> ScopeMetrics:
        store_ids = await self._repository.stores_in_region(region_id)
        if not store_ids:
            raise NotFoundError.for_resource("region", region_id)
        sources = self._require_sources()

        # STUB: fan out per store and sum. Replace with one aggregate query.
        by_status: dict[str, int] = {}
        active_staff = 0
        open_alerts = 0
        for store_id in store_ids:
            for key, value in (await sources.activities.status_breakdown(store_id)).items():
                by_status[key] = by_status.get(key, 0) + value
            active_staff += await sources.staff.headcount(store_id)
            open_alerts += await sources.alerts.open_count(store_id)

        return ScopeMetrics(
            scope=MetricsScope.REGION,
            scope_id=region_id,
            generated_at=datetime.now(UTC),
            store_count=len(store_ids),
            active_programmes=await sources.programmes.active_count(),
            open_alerts=open_alerts,
            active_staff=active_staff,
            activities_by_status=by_status,
        )


@lru_cache(maxsize=1)
def get_report_service() -> ReportService:
    return ReportService(ReportRepository())


ReportServiceDep = Annotated[ReportService, Depends(get_report_service)]
