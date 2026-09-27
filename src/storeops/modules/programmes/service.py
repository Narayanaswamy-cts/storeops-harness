"""Programme business rules. STUB bodies, real error and event contracts."""

from __future__ import annotations

import uuid
from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from storeops.core.errors import ConflictError, NotFoundError, ValidationError
from storeops.core.events import EventBus, ProgrammeLaunched
from storeops.modules.programmes.models import Programme, ProgrammeCreate, ProgrammeStatus
from storeops.modules.programmes.repository import ProgrammeRepository

__all__ = ["ProgrammeService", "ProgrammeServiceDep", "get_programme_service"]


class ProgrammeService:
    def __init__(self, repository: ProgrammeRepository) -> None:
        self._repository = repository

    async def create(self, payload: ProgrammeCreate, *, bus: EventBus) -> Programme:
        if payload.ends_on and payload.starts_on and payload.ends_on < payload.starts_on:
            raise ValidationError(
                "ends_on must not precede starts_on.",
                details={"field": "ends_on"},
            )
        if await self._repository.name_exists(payload.name):
            raise ConflictError(f"A programme named {payload.name!r} already exists.")

        programme = Programme(
            id=f"prg_{uuid.uuid4().hex[:12]}",
            name=payload.name,
            store_ids=tuple(dict.fromkeys(payload.store_ids)),
            starts_on=payload.starts_on,
            ends_on=payload.ends_on,
            status=(
                ProgrammeStatus.ACTIVE
                if payload.activate_immediately
                else ProgrammeStatus.DRAFT
            ),
        )
        stored = await self._repository.add(programme)

        if stored.status is ProgrammeStatus.ACTIVE:
            await bus.publish(
                ProgrammeLaunched(programme_id=stored.id, store_ids=stored.store_ids)
            )
        return stored

    async def list(
        self,
        *,
        programme_status: ProgrammeStatus | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Programme], int]:
        return await self._repository.list(
            programme_status=programme_status, limit=limit, offset=offset
        )

    async def get(self, programme_id: str) -> Programme:
        programme = await self._repository.get(programme_id)
        if programme is None:
            raise NotFoundError.for_resource("programme", programme_id)
        return programme

    async def active_count(self, store_id: str | None = None) -> int:
        """Read-only projection consumed by the reports module via a port."""
        return await self._repository.count_active(store_id)


@lru_cache(maxsize=1)
def get_programme_service() -> ProgrammeService:
    return ProgrammeService(ProgrammeRepository())


ProgrammeServiceDep = Annotated[ProgrammeService, Depends(get_programme_service)]
