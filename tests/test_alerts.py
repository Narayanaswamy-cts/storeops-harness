from __future__ import annotations

from httpx import AsyncClient

from storeops.core.deps import get_event_bus
from storeops.core.events import ActivityCompleted, ActivityOverdue, ProgrammeLaunched

from tests.conftest import API


async def test_alerts_start_empty(client: AsyncClient) -> None:
    response = await client.get(f"{API}/alerts")

    assert response.status_code == 200
    assert response.json()["total"] == 0


async def test_completing_an_activity_raises_an_alert_over_the_bus(
    client: AsyncClient, activity_payload: dict[str, str]
) -> None:
    created = (await client.post(f"{API}/activities", json=activity_payload)).json()
    await client.post(
        f"{API}/activities/{created['id']}/complete",
        json={"completed_by": "stf_0001"},
    )

    alerts = (await client.get(f"{API}/alerts")).json()

    assert alerts["total"] == 1
    assert alerts["items"][0]["kind"] == "activity.completed"
    assert alerts["items"][0]["state"] == "open"
    assert created["id"] in alerts["items"][0]["message"]


async def test_launching_a_programme_alerts_every_store(client: AsyncClient) -> None:
    await client.post(
        f"{API}/programmes",
        json={
            "name": "Rollout",
            "store_ids": ["store_001", "store_002"],
            "activate_immediately": True,
        },
    )

    alerts = (await client.get(f"{API}/alerts")).json()

    assert alerts["total"] == 2
    assert {item["store_id"] for item in alerts["items"]} == {"store_001", "store_002"}


async def test_draft_programme_raises_no_alert(client: AsyncClient) -> None:
    await client.post(f"{API}/programmes", json={"name": "Quiet draft"})

    assert (await client.get(f"{API}/alerts")).json()["total"] == 0


async def test_acknowledge_alert_moves_it_out_of_open(
    client: AsyncClient, activity_payload: dict[str, str]
) -> None:
    created = (await client.post(f"{API}/activities", json=activity_payload)).json()
    await client.post(
        f"{API}/activities/{created['id']}/complete",
        json={"completed_by": "stf_0001"},
    )
    alert_id = (await client.get(f"{API}/alerts")).json()["items"][0]["id"]

    response = await client.post(
        f"{API}/alerts/{alert_id}/acknowledge",
        json={"acknowledged_by": "stf_0001"},
    )

    assert response.status_code == 200
    assert response.json()["state"] == "acknowledged"
    assert response.json()["acknowledged_at"] is not None


async def test_acknowledging_twice_conflicts(
    client: AsyncClient, activity_payload: dict[str, str]
) -> None:
    created = (await client.post(f"{API}/activities", json=activity_payload)).json()
    await client.post(
        f"{API}/activities/{created['id']}/complete",
        json={"completed_by": "stf_0001"},
    )
    alert_id = (await client.get(f"{API}/alerts")).json()["items"][0]["id"]
    body = {"acknowledged_by": "stf_0001"}
    await client.post(f"{API}/alerts/{alert_id}/acknowledge", json=body)

    response = await client.post(f"{API}/alerts/{alert_id}/acknowledge", json=body)

    assert response.status_code == 409


async def test_acknowledge_unknown_alert_is_404(client: AsyncClient) -> None:
    response = await client.post(
        f"{API}/alerts/alr_missing/acknowledge",
        json={"acknowledged_by": "stf_0001"},
    )

    assert response.status_code == 404


async def test_subscribers_are_registered_for_every_published_event(
    client: AsyncClient,
) -> None:
    del client  # the fixture is what wires the bus
    bus = get_event_bus()

    assert bus.subscriber_count(ActivityCompleted) == 1
    assert bus.subscriber_count(ActivityOverdue) == 1
    assert bus.subscriber_count(ProgrammeLaunched) == 1


# ---------------------------------------- handover audit trail (sprint 3) ---


async def test_bulk_handover_writes_one_audit_alert_per_updated_activity(
    client: AsyncClient,
) -> None:
    """AC-3.4 / AC-3.5 -- alerts records the audit entry, reacting to the bus.

    `activities` never imports `alerts`. The entries below exist only because
    `alerts` subscribed to ActivityStatusChanged in `main.wire_modules`.
    """
    ids = []
    for title in ("Shelf reset", "Stock count"):
        created = await client.post(
            f"{API}/activities",
            json={"store_id": "store_001", "title": title},
        )
        ids.append(created.json()["id"])

    response = await client.patch(
        f"{API}/activities/bulk-status",
        json={
            "activity_ids": [*ids, "act_ghost"],
            "status": "blocked",
            "updated_by": "staff_555",
        },
    )
    assert response.status_code == 207

    alerts = (await client.get(f"{API}/alerts")).json()["items"]
    audit = [a for a in alerts if a["kind"] == "activity.status_changed"]

    # exactly two updated activities -> exactly two audit entries
    assert len(audit) == 2
    assert {a["severity"] for a in audit} == {"info"}
    for entry in audit:
        assert "from pending to blocked" in entry["message"]
        assert "staff_555" in entry["message"]


async def test_bulk_completion_writes_both_audit_and_completion_alerts(
    client: AsyncClient,
) -> None:
    """AC-3.3 / AC-3.4 -- the two entries are deliberate, not a duplicate.

    One is the audit record of the transition; the other is the pre-existing
    completion notification. A change that collapses them into one is a
    regression.
    """
    created = await client.post(
        f"{API}/activities",
        json={"store_id": "store_001", "title": "Close out"},
    )
    activity_id = created.json()["id"]

    await client.patch(
        f"{API}/activities/bulk-status",
        json={
            "activity_ids": [activity_id],
            "status": "completed",
            "updated_by": "staff_555",
        },
    )

    kinds = sorted(a["kind"] for a in (await client.get(f"{API}/alerts")).json()["items"])

    assert kinds == ["activity.completed", "activity.status_changed"]
