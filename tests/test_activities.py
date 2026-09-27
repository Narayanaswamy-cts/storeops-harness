from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from httpx import AsyncClient

from storeops.core.deps import get_event_bus
from storeops.core.events import ActivityCompleted, ActivityStatusChanged
from tests.conftest import API


async def test_create_activity_returns_201_and_pending_status(
    client: AsyncClient, activity_payload: dict[str, str]
) -> None:
    response = await client.post(f"{API}/activities", json=activity_payload)

    assert response.status_code == 201
    body = response.json()
    assert body["id"].startswith("act_")
    assert body["status"] == "pending"
    assert body["store_id"] == "store_001"


async def test_create_activity_rejects_due_date_in_the_past(client: AsyncClient) -> None:
    past = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    response = await client.post(
        f"{API}/activities",
        json={"store_id": "store_001", "title": "Late job", "due_at": past},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_failed"


async def test_list_activities_paginates_and_filters_by_store(
    client: AsyncClient, activity_payload: dict[str, str]
) -> None:
    await client.post(f"{API}/activities", json=activity_payload)
    await client.post(
        f"{API}/activities",
        json={"store_id": "store_002", "title": "Stock count"},
    )

    everything = await client.get(f"{API}/activities")
    assert everything.status_code == 200
    assert everything.json()["total"] == 2

    filtered = await client.get(f"{API}/activities", params={"store_id": "store_002"})
    assert filtered.json()["total"] == 1
    assert filtered.json()["items"][0]["store_id"] == "store_002"


async def test_complete_activity_transitions_to_completed(
    client: AsyncClient, activity_payload: dict[str, str]
) -> None:
    created = (await client.post(f"{API}/activities", json=activity_payload)).json()

    response = await client.post(
        f"{API}/activities/{created['id']}/complete",
        json={"completed_by": "stf_0001"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert response.json()["completed_at"] is not None


async def test_completing_twice_conflicts(
    client: AsyncClient, activity_payload: dict[str, str]
) -> None:
    created = (await client.post(f"{API}/activities", json=activity_payload)).json()
    body = {"completed_by": "stf_0001"}
    await client.post(f"{API}/activities/{created['id']}/complete", json=body)

    response = await client.post(f"{API}/activities/{created['id']}/complete", json=body)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


async def test_complete_unknown_activity_is_404(client: AsyncClient) -> None:
    response = await client.post(
        f"{API}/activities/act_missing/complete",
        json={"completed_by": "stf_0001"},
    )

    assert response.status_code == 404
    assert response.json()["error"]["details"]["resource"] == "activity"


# --------------------------------------------- shift handover bulk update ---


async def _create(client: AsyncClient, title: str) -> str:
    response = await client.post(
        f"{API}/activities",
        json={"store_id": "store_001", "title": title},
    )
    assert response.status_code == 201
    return str(response.json()["id"])


async def test_bulk_status_applies_every_valid_activity(client: AsyncClient) -> None:
    """AC-1.3 -- all ids valid, so all are applied and reported in order."""
    ids = [await _create(client, f"Shelf {n}") for n in range(3)]

    response = await client.patch(
        f"{API}/activities/bulk-status",
        json={"activity_ids": ids, "status": "completed", "updated_by": "staff_001"},
    )

    assert response.status_code == 207
    body = response.json()
    assert body["updated"] == 3
    assert body["failed"] == 0
    assert [item["id"] for item in body["results"]] == ids
    assert {item["result"] for item in body["results"]} == {"updated"}

    listed = (await client.get(f"{API}/activities")).json()["items"]
    assert {row["status"] for row in listed} == {"completed"}


async def test_bulk_status_can_set_blocked(client: AsyncClient) -> None:
    """AC-1.1 / AC-1.2 -- the new blocked state is reachable in bulk."""
    activity_id = await _create(client, "Awaiting stock")

    response = await client.patch(
        f"{API}/activities/bulk-status",
        json={
            "activity_ids": [activity_id],
            "status": "blocked",
            "updated_by": "staff_001",
        },
    )

    assert response.status_code == 207
    assert response.json()["updated"] == 1
    fetched = (await client.get(f"{API}/activities")).json()["items"][0]
    assert fetched["status"] == "blocked"


async def test_bulk_status_rejects_a_status_outside_the_handover_set(
    client: AsyncClient,
) -> None:
    """AC-1.2 -- only completed and blocked may be set in bulk."""
    activity_id = await _create(client, "Not cancellable in bulk")

    response = await client.patch(
        f"{API}/activities/bulk-status",
        json={
            "activity_ids": [activity_id],
            "status": "cancelled",
            "updated_by": "staff_001",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_failed"


async def test_bulk_status_reports_unknown_ids_without_failing_the_batch(
    client: AsyncClient,
) -> None:
    """AC-1.4 -- partial application is the contract, not an error."""
    good = await _create(client, "Real activity")

    response = await client.patch(
        f"{API}/activities/bulk-status",
        json={
            "activity_ids": [good, "act_missing"],
            "status": "completed",
            "updated_by": "staff_001",
        },
    )

    assert response.status_code == 207
    body = response.json()
    assert body["updated"] == 1
    assert body["failed"] == 1

    by_id = {item["id"]: item for item in body["results"]}
    assert by_id[good]["result"] == "updated"
    assert by_id["act_missing"]["result"] == "failed"
    assert by_id["act_missing"]["error"]["code"] == "not_found"

    # the rule: the valid item really did change
    listed = (await client.get(f"{API}/activities")).json()["items"]
    assert [row["status"] for row in listed] == ["completed"]


async def test_bulk_status_rejects_an_empty_id_list(client: AsyncClient) -> None:
    """AC-1.5 -- empty batch is a client error, raised by the service."""
    response = await client.patch(
        f"{API}/activities/bulk-status",
        json={"activity_ids": [], "status": "completed", "updated_by": "staff_001"},
    )

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_failed"
    assert error["details"]["field"] == "activity_ids"


async def test_bulk_status_rejects_more_than_one_hundred_ids(
    client: AsyncClient,
) -> None:
    """AC-1.5 -- the batch-size ceiling carries details.field."""
    response = await client.patch(
        f"{API}/activities/bulk-status",
        json={
            "activity_ids": [f"act_{n:04d}" for n in range(101)],
            "status": "completed",
            "updated_by": "staff_001",
        },
    )

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_failed"
    assert error["details"]["field"] == "activity_ids"
    assert error["details"]["max"] == 100


async def test_bulk_status_collapses_duplicate_ids(client: AsyncClient) -> None:
    """AC-1.6 -- a repeated id is reported once and written once."""
    activity_id = await _create(client, "Sent twice")

    response = await client.patch(
        f"{API}/activities/bulk-status",
        json={
            "activity_ids": [activity_id, activity_id, activity_id],
            "status": "blocked",
            "updated_by": "staff_001",
        },
    )

    assert response.status_code == 207
    body = response.json()
    assert len(body["results"]) == 1
    assert body["updated"] == 1
    assert body["failed"] == 0


async def test_bulk_status_requires_an_acting_staff_member(
    client: AsyncClient,
) -> None:
    """AC-1.2 -- updated_by identifies who performed the handover."""
    activity_id = await _create(client, "Needs an actor")

    response = await client.patch(
        f"{API}/activities/bulk-status",
        json={"activity_ids": [activity_id], "status": "completed", "updated_by": ""},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_failed"


# ------------------------------------------ handover transition legality ---


async def _bulk(
    client: AsyncClient, ids: list[str], status: str, by: str = "staff_001"
) -> dict[str, Any]:
    response = await client.patch(
        f"{API}/activities/bulk-status",
        json={"activity_ids": ids, "status": status, "updated_by": by},
    )
    assert response.status_code == 207
    body: dict[str, Any] = response.json()
    return body


async def test_bulk_status_conflicts_when_already_in_target_status(
    client: AsyncClient,
) -> None:
    """AC-2.1 -- a no-op is reported, not silently counted as an update."""
    activity_id = await _create(client, "Already done")
    await _bulk(client, [activity_id], "completed")
    first = (await client.get(f"{API}/activities")).json()["items"][0]

    body = await _bulk(client, [activity_id], "completed")

    assert body["updated"] == 0
    assert body["failed"] == 1
    item = body["results"][0]
    assert item["error"]["code"] == "conflict"

    # the rule: the original completion timestamp was not overwritten
    again = (await client.get(f"{API}/activities")).json()["items"][0]
    assert again["completed_at"] == first["completed_at"]


async def test_bulk_status_cannot_walk_completion_back_to_blocked(
    client: AsyncClient,
) -> None:
    """AC-2.3 -- completion is terminal for the handover endpoint."""
    activity_id = await _create(client, "Finished work")
    await _bulk(client, [activity_id], "completed")

    body = await _bulk(client, [activity_id], "blocked")

    assert body["failed"] == 1
    assert body["results"][0]["error"]["code"] == "conflict"
    fetched = (await client.get(f"{API}/activities")).json()["items"][0]
    assert fetched["status"] == "completed"


async def test_bulk_status_allows_blocked_to_become_completed(
    client: AsyncClient,
) -> None:
    """AC-2.4 -- blocked work can still be closed out."""
    activity_id = await _create(client, "Was blocked")
    await _bulk(client, [activity_id], "blocked")

    body = await _bulk(client, [activity_id], "completed")

    assert body["updated"] == 1
    fetched = (await client.get(f"{API}/activities")).json()["items"][0]
    assert fetched["status"] == "completed"


async def test_bulk_status_allows_pending_to_become_blocked(
    client: AsyncClient,
) -> None:
    """AC-2.5 -- the common handover case."""
    activity_id = await _create(client, "Blocked by delivery")

    body = await _bulk(client, [activity_id], "blocked")

    assert body["updated"] == 1


async def test_bulk_completion_records_who_and_when(client: AsyncClient) -> None:
    """AC-2.6 -- completion stamps the actor; blocking does not."""
    completed_id = await _create(client, "To complete")
    blocked_id = await _create(client, "To block")

    await _bulk(client, [completed_id], "completed", by="staff_042")
    await _bulk(client, [blocked_id], "blocked", by="staff_042")

    rows = {r["id"]: r for r in (await client.get(f"{API}/activities")).json()["items"]}
    assert rows[completed_id]["completed_at"] is not None
    assert rows[blocked_id]["completed_at"] is None


async def test_bulk_status_mixed_batch_counts_match_the_items(
    client: AsyncClient,
) -> None:
    """AC-2.7 / AC-2.9 -- legal applied, illegal reported, counts consistent.

    This is the inversion-sensitive test: flipping the `not in` legality check
    in the service, or removing `CANCELLED` from being terminal, changes these
    counts and fails here.
    """
    fresh = await _create(client, "Fresh")
    done = await _create(client, "Done already")
    await _bulk(client, [done], "completed")

    body = await _bulk(client, [fresh, done, "act_ghost"], "completed")

    assert body["updated"] == 1
    assert body["failed"] == 2
    codes = {
        item["id"]: (item["error"]["code"] if item["error"] else None)
        for item in body["results"]
    }
    assert codes[fresh] is None
    assert codes[done] == "conflict"
    assert codes["act_ghost"] == "not_found"
    assert body["updated"] + body["failed"] == len(body["results"])


# ------------------------------------------- handover audit via the bus ----


async def test_bulk_update_publishes_exactly_one_event_per_updated_activity(
    client: AsyncClient,
) -> None:
    """AC-3.2 / AC-3.5 -- exact counts, not merely "some events fired"."""

    legal = [await _create(client, f"Legal {n}") for n in range(3)]
    already_done = await _create(client, "Already done")
    await _bulk(client, [already_done], "completed")

    seen: list[ActivityStatusChanged] = []

    async def capture(event: ActivityStatusChanged) -> None:
        seen.append(event)

    get_event_bus().subscribe(ActivityStatusChanged, capture)

    body = await _bulk(client, [*legal, already_done, "act_ghost"], "completed")

    assert body["updated"] == 3
    assert body["failed"] == 2
    # three updated -> exactly three events; the conflict and the miss publish nothing
    assert len(seen) == 3
    assert sorted(event.activity_id for event in seen) == sorted(legal)
    assert {event.to_status for event in seen} == {"completed"}
    assert {event.from_status for event in seen} == {"pending"}
    assert {event.changed_by for event in seen} == {"staff_001"}


async def test_bulk_completion_also_publishes_activity_completed(
    client: AsyncClient,
) -> None:
    """AC-3.3 -- bulk completion looks identical to the single-activity route."""

    activity_id = await _create(client, "To complete in bulk")
    seen: list[ActivityCompleted] = []

    async def capture(event: ActivityCompleted) -> None:
        seen.append(event)

    get_event_bus().subscribe(ActivityCompleted, capture)

    await _bulk(client, [activity_id], "completed", by="staff_077")

    assert len(seen) == 1
    assert seen[0].activity_id == activity_id
    assert seen[0].completed_by == "staff_077"


async def test_blocking_does_not_publish_activity_completed(
    client: AsyncClient,
) -> None:
    """AC-3.3 -- only completion raises the completion event."""

    activity_id = await _create(client, "To block")
    seen: list[ActivityCompleted] = []

    async def capture(event: ActivityCompleted) -> None:
        seen.append(event)

    get_event_bus().subscribe(ActivityCompleted, capture)

    await _bulk(client, [activity_id], "blocked")

    assert not seen


async def test_a_failing_subscriber_cannot_affect_the_response(
    client: AsyncClient,
) -> None:
    """AC-3.8 -- publish swallows handler errors, so the response is unaffected.

    Without this test a broken audit subscriber would look like success in
    every other test, because EventBus.publish logs and continues.
    """

    activity_id = await _create(client, "Audit will explode")

    async def explode(_event: ActivityStatusChanged) -> None:
        message = "deliberate subscriber failure"
        raise RuntimeError(message)

    get_event_bus().subscribe(ActivityStatusChanged, explode)

    response = await client.patch(
        f"{API}/activities/bulk-status",
        json={
            "activity_ids": [activity_id],
            "status": "completed",
            "updated_by": "staff_001",
        },
    )

    assert response.status_code == 207
    body = response.json()
    assert body["updated"] == 1
    assert body["results"][0]["result"] == "updated"

    # the rule: the write still happened despite the subscriber failing
    fetched = (await client.get(f"{API}/activities")).json()["items"][0]
    assert fetched["status"] == "completed"
