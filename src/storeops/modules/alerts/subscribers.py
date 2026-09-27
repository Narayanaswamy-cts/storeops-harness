"""Event-bus subscriptions that turn domain events into alerts.

This file is the inbound edge of the alerts module. Activities and programmes
publish; alerts reacts here. Neither publisher knows this module exists.
"""

from __future__ import annotations

from storeops.core.events import (
    ActivityCompleted,
    ActivityOverdue,
    ActivityStatusChanged,
    EventBus,
    ProgrammeLaunched,
)
from storeops.modules.alerts.models import AlertCreate, AlertSeverity
from storeops.modules.alerts.service import AlertService

__all__ = ["register"]


def register(bus: EventBus, service: AlertService) -> None:
    """Wire alert handlers onto the bus. Called once from `storeops.main`."""

    async def on_activity_completed(event: ActivityCompleted) -> None:
        # STUB: real logic would resolve any open "overdue" alert for this activity.
        await service.raise_alert(
            AlertCreate(
                store_id=event.store_id,
                kind="activity.completed",
                severity=AlertSeverity.INFO,
                message=f"Activity {event.activity_id} completed by {event.completed_by}.",
                source_event=event.name,
            )
        )

    async def on_activity_status_changed(event: ActivityStatusChanged) -> None:
        """The handover audit trail.

        One entry per activity that actually changed, naming the transition and
        who made it. `activities` does not know this handler exists.
        """
        await service.raise_alert(
            AlertCreate(
                store_id=event.store_id,
                kind="activity.status_changed",
                severity=AlertSeverity.INFO,
                message=(
                    f"Activity {event.activity_id} moved from {event.from_status} "
                    f"to {event.to_status} by {event.changed_by}."
                ),
                source_event=event.name,
            )
        )

    async def on_activity_overdue(event: ActivityOverdue) -> None:
        await service.raise_alert(
            AlertCreate(
                store_id=event.store_id,
                kind="activity.overdue",
                severity=AlertSeverity.WARNING,
                message=f"Activity {event.activity_id} was due at {event.due_at.isoformat()}.",
                source_event=event.name,
            )
        )

    async def on_programme_launched(event: ProgrammeLaunched) -> None:
        for store_id in event.store_ids:
            await service.raise_alert(
                AlertCreate(
                    store_id=store_id,
                    kind="programme.launched",
                    severity=AlertSeverity.INFO,
                    message=f"Programme {event.programme_id} is now active.",
                    source_event=event.name,
                )
            )

    bus.subscribe(ActivityCompleted, on_activity_completed)
    bus.subscribe(ActivityStatusChanged, on_activity_status_changed)
    bus.subscribe(ActivityOverdue, on_activity_overdue)
    bus.subscribe(ProgrammeLaunched, on_programme_launched)
