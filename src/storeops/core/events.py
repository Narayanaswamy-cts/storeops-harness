"""In-process event bus.

This is the *only* sanctioned channel for cross-module notification. A module
publishes a `DomainEvent`; interested modules subscribe during app wiring. No
module imports a sibling module in order to notify it.

Event payloads are frozen dataclasses of primitives — never ORM rows or another
module's domain objects — so subscribers gain no coupling to the publisher.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, TypeVar, cast

__all__ = [
    "ActivityCompleted",
    "ActivityOverdue",
    "ActivityStatusChanged",
    "DomainEvent",
    "EventBus",
    "ProgrammeLaunched",
    "StaffRosterChanged",
]

logger = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class DomainEvent:
    """Base class for everything that travels over the bus."""

    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def name(self) -> str:
        return type(self).__name__


@dataclass(frozen=True, kw_only=True)
class ActivityCompleted(DomainEvent):
    activity_id: str
    store_id: str
    completed_by: str


@dataclass(frozen=True, kw_only=True)
class ActivityStatusChanged(DomainEvent):
    """Raised once per activity whose status actually changed.

    `from_status` and `to_status` are plain strings rather than the
    `ActivityStatus` enum on purpose: `core` is a leaf and may not depend on a
    feature module. A subscriber that needs the enum can re-parse it.
    """

    activity_id: str
    store_id: str
    from_status: str
    to_status: str
    changed_by: str


@dataclass(frozen=True, kw_only=True)
class ActivityOverdue(DomainEvent):
    activity_id: str
    store_id: str
    due_at: datetime


@dataclass(frozen=True, kw_only=True)
class ProgrammeLaunched(DomainEvent):
    programme_id: str
    store_ids: tuple[str, ...]


@dataclass(frozen=True, kw_only=True)
class StaffRosterChanged(DomainEvent):
    store_id: str
    headcount: int


EventT = TypeVar("EventT", bound=DomainEvent)
Handler = Callable[[Any], Awaitable[None]]


class EventBus:
    """Synchronous-dispatch, async-handler event bus.

    Handler failures are logged and swallowed: a notification subscriber must not
    be able to fail the publisher's request. Swap in a broker-backed
    implementation later without touching any module.
    """

    def __init__(self) -> None:
        self._handlers: dict[type[DomainEvent], list[Handler]] = defaultdict(list)

    def subscribe(
        self,
        event_type: type[EventT],
        handler: Callable[[EventT], Awaitable[None]],
    ) -> None:
        self._handlers[event_type].append(cast(Handler, handler))

    async def publish(self, event: DomainEvent) -> None:
        for handler in self._handlers.get(type(event), []):
            try:
                await handler(event)
            except Exception:  # noqa: BLE001 -- isolate subscribers from publishers
                logger.exception("event handler failed for %s", event.name)

    def subscriber_count(self, event_type: type[DomainEvent]) -> int:
        return len(self._handlers.get(event_type, []))

    def clear(self) -> None:
        """Reset all subscriptions. Test-support only."""
        self._handlers.clear()
