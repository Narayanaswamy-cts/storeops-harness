from __future__ import annotations

from httpx import AsyncClient

from storeops.modules.reports.models import MetricsScope, ScopeMetrics

from tests.conftest import API


async def test_store_metrics_aggregate_across_modules(
    client: AsyncClient, activity_payload: dict[str, str]
) -> None:
    created = (await client.post(f"{API}/activities", json=activity_payload)).json()
    await client.post(
        f"{API}/activities/{created['id']}/complete",
        json={"completed_by": "stf_0001"},
    )
    await client.post(
        f"{API}/programmes",
        json={"name": "Live", "store_ids": ["store_001"], "activate_immediately": True},
    )

    response = await client.get(f"{API}/reports/metrics", params={"store_id": "store_001"})

    assert response.status_code == 200
    body = response.json()
    assert body["scope"] == "store"
    assert body["store_count"] == 1
    assert body["active_programmes"] == 1
    assert body["active_staff"] == 2
    assert body["activities_by_status"] == {"completed": 1}
    # One alert from completing the activity, one from launching the programme.
    assert body["open_alerts"] == 2


async def test_region_metrics_sum_their_stores(client: AsyncClient) -> None:
    await client.post(
        f"{API}/activities",
        json={"store_id": "store_001", "title": "A"},
    )
    await client.post(
        f"{API}/activities",
        json={"store_id": "store_002", "title": "B"},
    )

    response = await client.get(f"{API}/reports/metrics", params={"region_id": "region_north"})

    assert response.status_code == 200
    body = response.json()
    assert body["scope"] == "region"
    assert body["store_count"] == 2
    assert body["activities_by_status"] == {"pending": 2}


async def test_metrics_requires_exactly_one_scope(client: AsyncClient) -> None:
    neither = await client.get(f"{API}/reports/metrics")
    both = await client.get(
        f"{API}/reports/metrics",
        params={"store_id": "store_001", "region_id": "region_north"},
    )

    assert neither.status_code == 422
    assert both.status_code == 422
    assert neither.json()["error"]["code"] == "validation_failed"


async def test_unknown_store_is_404(client: AsyncClient) -> None:
    response = await client.get(f"{API}/reports/metrics", params={"store_id": "store_999"})

    assert response.status_code == 404
    assert response.json()["error"]["details"]["resource"] == "store"


async def test_unknown_region_is_404(client: AsyncClient) -> None:
    response = await client.get(f"{API}/reports/metrics", params={"region_id": "region_x"})

    assert response.status_code == 404


def test_completion_rate_ignores_cancelled_activities() -> None:
    metrics = ScopeMetrics(
        scope=MetricsScope.STORE,
        scope_id="store_001",
        generated_at="2026-01-01T00:00:00Z",  # type: ignore[arg-type]
        activities_by_status={"completed": 3, "pending": 1, "cancelled": 6},
    )

    assert metrics.completion_rate == 0.75


def test_completion_rate_of_empty_store_is_zero() -> None:
    metrics = ScopeMetrics(
        scope=MetricsScope.STORE,
        scope_id="store_001",
        generated_at="2026-01-01T00:00:00Z",  # type: ignore[arg-type]
    )

    assert metrics.completion_rate == 0.0
