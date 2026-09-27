"""The staff module's public, read-only contract.

This is the *only* module in `staff` that other modules may import. It exposes
queries and a flat DTO — no create/update/delete, and no access to the
repository or the mutable domain record. That is how "staff is read-only to
other modules" is expressed in types rather than in a comment.

Writes happen exclusively through `staff`'s own routes and service.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

__all__ = ["StaffDirectory", "StaffSummary"]


class StaffSummary(BaseModel):
    """Immutable projection safe to hand to any module."""

    model_config = ConfigDict(frozen=True)

    id: str
    store_id: str
    display_name: str
    role: str
    is_active: bool


@runtime_checkable
class StaffDirectory(Protocol):
    """Read-only queries other modules may perform against staff."""

    async def find(self, staff_id: str) -> StaffSummary | None: ...

    async def headcount(self, store_id: str) -> int: ...

    async def is_active(self, staff_id: str) -> bool: ...
