"""Activity persistence.

STUB: an in-memory dict stands in for the real store. Swap the body of each
method for SQL; the signatures are the contract the service is written against.
"""

from __future__ import annotations

from collections.abc import Sequence

from storeops.modules.activities.models import Activity, ActivityFilter

__all__ = ["ActivityRepository"]


class ActivityRepository:
    def __init__(self) -> None:
        self._rows: dict[str, Activity] = {}

    async def add(self, activity: Activity) -> Activity:
        self._rows[activity.id] = activity
        return activity

    async def get(self, activity_id: str) -> Activity | None:
        return self._rows.get(activity_id)

    async def replace(self, activity: Activity) -> Activity:
        self._rows[activity.id] = activity
        return activity

    async def get_many(self, activity_ids: Sequence[str]) -> dict[str, Activity]:
        """Fetch several rows in one call. Missing ids are simply absent.

        Returning a mapping rather than a list lets the service pair each
        requested id with its row -- or with nothing -- without a second scan.
        """
        return {
            activity_id: row
            for activity_id in activity_ids
            if (row := self._rows.get(activity_id)) is not None
        }

    async def list(
        self,
        criteria: ActivityFilter,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[Activity], int]:
        matches = [row for row in self._rows.values() if self._matches(row, criteria)]
        matches.sort(key=lambda row: row.id)
        return matches[offset : offset + limit], len(matches)

    async def count_by_status(self, store_id: str | None = None) -> dict[str, int]:
        counts: dict[str, int] = {}
        for row in self._rows.values():
            if store_id is not None and row.store_id != store_id:
                continue
            counts[row.status.value] = counts.get(row.status.value, 0) + 1
        return counts

    @staticmethod
    def _matches(row: Activity, criteria: ActivityFilter) -> bool:
        if criteria.store_id is not None and row.store_id != criteria.store_id:
            return False
        if criteria.programme_id is not None and row.programme_id != criteria.programme_id:
            return False
        return not (criteria.status is not None and row.status != criteria.status)
