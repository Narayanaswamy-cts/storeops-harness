"""Providers for cross-cutting singletons.

Lives in `core` so that every module can depend on it without any module having
to depend on another module.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from storeops.core.events import EventBus

__all__ = ["BusDep", "get_event_bus"]


@lru_cache(maxsize=1)
def get_event_bus() -> EventBus:
    return EventBus()


BusDep = Annotated[EventBus, Depends(get_event_bus)]
