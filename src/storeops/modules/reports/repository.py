"""Reports persistence.

Reports owns only the store-to-region mapping; every other figure is read
through a port. STUB: in-memory mapping.
"""

from __future__ import annotations

__all__ = ["ReportRepository"]

_STORE_REGIONS: dict[str, str] = {
    "store_001": "region_north",
    "store_002": "region_north",
    "store_003": "region_south",
}


class ReportRepository:
    def __init__(self) -> None:
        self._store_regions: dict[str, str] = dict(_STORE_REGIONS)

    async def region_of(self, store_id: str) -> str | None:
        return self._store_regions.get(store_id)

    async def stores_in_region(self, region_id: str) -> list[str]:
        return sorted(
            store_id
            for store_id, region in self._store_regions.items()
            if region == region_id
        )

    async def store_exists(self, store_id: str) -> bool:
        return store_id in self._store_regions
