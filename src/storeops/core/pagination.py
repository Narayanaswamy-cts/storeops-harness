"""Shared pagination contract used by every list endpoint."""

from __future__ import annotations

from typing import Annotated, Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel, Field

__all__ = ["Page", "PageParams"]

ItemT = TypeVar("ItemT")


class PageParams(BaseModel):
    limit: Annotated[int, Query(ge=1, le=100)] = 25
    offset: Annotated[int, Query(ge=0)] = 0


class Page(BaseModel, Generic[ItemT]):
    items: list[ItemT] = Field(default_factory=list)
    total: int = 0
    limit: int = 25
    offset: int = 0

    @classmethod
    def of(cls, items: list[ItemT], total: int, params: PageParams) -> "Page[ItemT]":
        return cls(items=items, total=total, limit=params.limit, offset=params.offset)
