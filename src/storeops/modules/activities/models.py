"""Activity domain records and wire schemas."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "Activity",
    "ActivityCreate",
    "ActivityFilter",
    "ActivityRead",
    "ActivityStatus",
    "BulkItemError",
    "BulkItemOutcome",
    "BulkItemResult",
    "BulkStatusResult",
    "BulkStatusUpdate",
    "BulkTargetStatus",
]


class ActivityStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"


class Activity(BaseModel):
    """Internal domain record. Never returned directly from a route."""

    model_config = ConfigDict(frozen=True)

    id: str
    store_id: str
    programme_id: str | None = None
    title: str
    status: ActivityStatus = ActivityStatus.PENDING
    assigned_staff_id: str | None = None
    due_at: datetime | None = None
    completed_at: datetime | None = None
    completed_by: str | None = None


class ActivityCreate(BaseModel):
    store_id: str = Field(min_length=1, max_length=32)
    title: str = Field(min_length=1, max_length=200)
    programme_id: str | None = None
    assigned_staff_id: str | None = None
    due_at: datetime | None = None


class ActivityRead(BaseModel):
    id: str
    store_id: str
    programme_id: str | None
    title: str
    status: ActivityStatus
    assigned_staff_id: str | None
    due_at: datetime | None
    completed_at: datetime | None

    @classmethod
    def from_domain(cls, activity: Activity) -> ActivityRead:
        return cls(
            id=activity.id,
            store_id=activity.store_id,
            programme_id=activity.programme_id,
            title=activity.title,
            status=activity.status,
            assigned_staff_id=activity.assigned_staff_id,
            due_at=activity.due_at,
            completed_at=activity.completed_at,
        )


class ActivityFilter(BaseModel):
    store_id: str | None = None
    programme_id: str | None = None
    status: ActivityStatus | None = None


class BulkTargetStatus(StrEnum):
    """The subset of statuses a handover may set in bulk.

    Deliberately narrower than `ActivityStatus`: a bulk handover closes work out
    or flags it as blocked. Reopening or cancelling stays a single-activity
    operation, so those values are not offered here and pydantic rejects them.
    """

    COMPLETED = "completed"
    BLOCKED = "blocked"


class BulkItemOutcome(StrEnum):
    UPDATED = "updated"
    FAILED = "failed"


class BulkStatusUpdate(BaseModel):
    """Inbound payload for a shift handover.

    `activity_ids` carries no length constraint here on purpose. The batch-size
    rule is a business rule, so the service raises `ValidationError` with
    `details.field` rather than letting pydantic emit a `details.errors` array.
    """

    activity_ids: list[str]
    status: BulkTargetStatus
    updated_by: str = Field(min_length=1, max_length=64)


class BulkItemError(BaseModel):
    code: str
    message: str


class BulkItemResult(BaseModel):
    id: str
    result: BulkItemOutcome
    error: BulkItemError | None = None


class BulkStatusResult(BaseModel):
    results: list[BulkItemResult] = Field(default_factory=list)
    updated: int = 0
    failed: int = 0
