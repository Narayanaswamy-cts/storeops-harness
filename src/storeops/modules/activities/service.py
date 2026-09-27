"""Activity business rules.

STUB: rule bodies are intentionally minimal. What is *not* a stub is the shape —
every failure leaves as an `AppError`, and completion notifies the rest of the
system by publishing to the event bus rather than calling the alerts module.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from functools import lru_cache
from typing import Annotated, Any

from fastapi import Depends

from storeops.core.errors import ConflictError, NotFoundError, ValidationError
from storeops.core.events import ActivityCompleted, ActivityStatusChanged, EventBus
from storeops.modules.activities.models import (
    Activity,
    ActivityCreate,
    ActivityFilter,
    ActivityStatus,
    BulkItemError,
    BulkItemOutcome,
    BulkItemResult,
    BulkStatusResult,
    BulkStatusUpdate,
)
from storeops.modules.activities.repository import ActivityRepository

__all__ = [
    "MAX_BULK_ACTIVITIES",
    "ActivityService",
    "ActivityServiceDep",
    "get_activity_service",
]

MAX_BULK_ACTIVITIES = 100
"""Upper bound on one handover batch. A larger batch is a client error, not a
page -- the caller is expected to split the shift's work, and an unbounded list
would let one request rewrite an entire store."""

_ItemResults = list[BulkItemResult]
"""Alias declared at module scope on purpose.

`ActivityService` defines a method named `list`, which shadows `builtins.list`
inside the class body -- a bare `list[...]` annotation in any method defined
after it resolves to the method object and fails `mypy --strict`. Do not inline
this alias back into the class.
"""


def _validated_ids(activity_ids: list[str]) -> list[str]:
    """Enforce the batch-size rule and collapse duplicates, keeping order.

    De-duplicating here is what makes a repeated id appear once in the response
    and be written once.
    """
    if not activity_ids:
        message = "activity_ids must contain at least one id."
        raise ValidationError(message, details={"field": "activity_ids"})
    if len(activity_ids) > MAX_BULK_ACTIVITIES:
        message = f"activity_ids may not exceed {MAX_BULK_ACTIVITIES} entries."
        raise ValidationError(
            message,
            details={"field": "activity_ids", "max": MAX_BULK_ACTIVITIES},
        )
    return list(dict.fromkeys(activity_ids))


_LEGAL_SOURCES: dict[ActivityStatus, frozenset[ActivityStatus]] = {
    ActivityStatus.COMPLETED: frozenset(
        {ActivityStatus.PENDING, ActivityStatus.IN_PROGRESS, ActivityStatus.BLOCKED}
    ),
    ActivityStatus.BLOCKED: frozenset(
        {ActivityStatus.PENDING, ActivityStatus.IN_PROGRESS}
    ),
}
"""The only statement of handover transition legality.

Read as: to reach the key, an activity must currently be in one of the values.

Everything the sprint requires falls out of this one mapping rather than a
branch per rule -- an activity already in the target status is absent from its
own source set, `CANCELLED` appears in no set so it is terminal, and `COMPLETED`
is absent from `BLOCKED`'s sources so completion cannot be walked back here.
Reopening or cancelling remains a single-activity operation.
"""


def _transition(target: ActivityStatus, updated_by: str) -> dict[str, Any]:
    """The fields a legal transition writes.

    Completion stamps who closed the work and when, matching what the
    single-activity `complete` route records. Blocking only moves the status --
    an activity that is later completed gets its timestamp then.
    """
    if target is ActivityStatus.COMPLETED:
        return {
            "status": target,
            "completed_at": datetime.now(UTC),
            "completed_by": updated_by,
        }
    return {"status": target}


def _conflict(
    activity_id: str,
    current: ActivityStatus,
    target: ActivityStatus,
) -> BulkItemResult:
    """Report an illegal transition per item, without raising it."""
    message = f"Activity {activity_id!r} is {current.value} and may not become {target.value}."
    error = ConflictError(message, details={"status": current.value})
    return BulkItemResult(
        id=activity_id,
        result=BulkItemOutcome.FAILED,
        error=BulkItemError(code=error.code, message=error.message),
    )


def _failed(activity_id: str) -> BulkItemResult:
    """Build a per-item failure from the typed hierarchy without raising it.

    The error contract still owns the code and the message; this endpoint merely
    reports them inside a successful envelope.
    """
    error = NotFoundError.for_resource("activity", activity_id)
    return BulkItemResult(
        id=activity_id,
        result=BulkItemOutcome.FAILED,
        error=BulkItemError(code=error.code, message=error.message),
    )


class ActivityService:
    def __init__(self, repository: ActivityRepository) -> None:
        self._repository = repository

    async def create(self, payload: ActivityCreate) -> Activity:
        if payload.due_at is not None and payload.due_at < datetime.now(UTC):
            raise ValidationError(
                "due_at must be in the future.",
                details={"field": "due_at"},
            )
        activity = Activity(
            id=f"act_{uuid.uuid4().hex[:12]}",
            store_id=payload.store_id,
            programme_id=payload.programme_id,
            title=payload.title,
            assigned_staff_id=payload.assigned_staff_id,
            due_at=payload.due_at,
        )
        return await self._repository.add(activity)

    async def list(
        self,
        criteria: ActivityFilter,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[Activity], int]:
        return await self._repository.list(criteria, limit=limit, offset=offset)

    async def get(self, activity_id: str) -> Activity:
        activity = await self._repository.get(activity_id)
        if activity is None:
            raise NotFoundError.for_resource("activity", activity_id)
        return activity

    async def complete(self, activity_id: str, *, completed_by: str, bus: EventBus) -> Activity:
        activity = await self.get(activity_id)
        if activity.status is ActivityStatus.COMPLETED:
            raise ConflictError(
                f"Activity {activity_id!r} is already completed.",
                details={"status": activity.status.value},
            )
        if activity.status is ActivityStatus.CANCELLED:
            raise ConflictError(f"Activity {activity_id!r} was cancelled.")

        completed = activity.model_copy(
            update={
                "status": ActivityStatus.COMPLETED,
                "completed_at": datetime.now(UTC),
                "completed_by": completed_by,
            }
        )
        stored = await self._repository.replace(completed)

        # Boundary rule: notify via the bus, never by importing alerts.
        await bus.publish(
            ActivityCompleted(
                activity_id=stored.id,
                store_id=stored.store_id,
                completed_by=completed_by,
            )
        )
        return stored

    async def bulk_update_status(
        self,
        payload: BulkStatusUpdate,
        *,
        bus: EventBus,
    ) -> BulkStatusResult:
        """Apply one target status to many activities, reporting per item.

        Partial application is the contract: an id that cannot be applied is
        reported and the rest still change. Nothing is raised for a single bad
        item -- the request as a whole succeeded in doing what it could.

        All of the decision-making lives here rather than in the route, so the
        HTTP layer only maps this result onto a response body.
        """
        requested = _validated_ids(payload.activity_ids)
        target = ActivityStatus(payload.status.value)
        found = await self._repository.get_many(requested)

        results: _ItemResults = []
        for activity_id in requested:
            activity = found.get(activity_id)
            if activity is None:
                results.append(_failed(activity_id))
                continue
            if activity.status not in _LEGAL_SOURCES[target]:
                results.append(_conflict(activity_id, activity.status, target))
                continue
            stored = await self._repository.replace(
                activity.model_copy(update=_transition(target, payload.updated_by))
            )
            results.append(BulkItemResult(id=activity_id, result=BulkItemOutcome.UPDATED))

            # Boundary rule: audit by publishing. `activities` never imports
            # `alerts`. Publishing happens after the write so a subscriber can
            # never observe a state that was not persisted.
            await bus.publish(
                ActivityStatusChanged(
                    activity_id=stored.id,
                    store_id=stored.store_id,
                    from_status=activity.status.value,
                    to_status=stored.status.value,
                    changed_by=payload.updated_by,
                )
            )
            if target is ActivityStatus.COMPLETED:
                # Keeps bulk completion indistinguishable from the single-activity
                # route for anything already subscribed to ActivityCompleted.
                await bus.publish(
                    ActivityCompleted(
                        activity_id=stored.id,
                        store_id=stored.store_id,
                        completed_by=payload.updated_by,
                    )
                )

        updated = sum(1 for item in results if item.result is BulkItemOutcome.UPDATED)
        return BulkStatusResult(
            results=results,
            updated=updated,
            failed=len(results) - updated,
        )

    async def status_breakdown(self, store_id: str | None = None) -> dict[str, int]:
        """Read-only projection consumed by the reports module via a port."""
        return await self._repository.count_by_status(store_id)


@lru_cache(maxsize=1)
def get_activity_service() -> ActivityService:
    return ActivityService(ActivityRepository())


ActivityServiceDep = Annotated[ActivityService, Depends(get_activity_service)]
