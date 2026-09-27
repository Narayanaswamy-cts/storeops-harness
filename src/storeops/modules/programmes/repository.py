"""Programme persistence. STUB: in-memory dict, real signatures."""

from __future__ import annotations

from storeops.modules.programmes.models import Programme, ProgrammeStatus

__all__ = ["ProgrammeRepository"]


class ProgrammeRepository:
    def __init__(self) -> None:
        self._rows: dict[str, Programme] = {}

    async def add(self, programme: Programme) -> Programme:
        self._rows[programme.id] = programme
        return programme

    async def get(self, programme_id: str) -> Programme | None:
        return self._rows.get(programme_id)

    async def name_exists(self, name: str) -> bool:
        return any(row.name.casefold() == name.casefold() for row in self._rows.values())

    async def list(
        self,
        *,
        programme_status: ProgrammeStatus | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Programme], int]:
        matches = [
            row
            for row in self._rows.values()
            if programme_status is None or row.status is programme_status
        ]
        matches.sort(key=lambda row: row.id)
        return matches[offset : offset + limit], len(matches)

    async def count_active(self, store_id: str | None = None) -> int:
        return sum(
            1
            for row in self._rows.values()
            if row.status is ProgrammeStatus.ACTIVE
            and (store_id is None or store_id in row.store_ids)
        )
