from __future__ import annotations

from httpx import AsyncClient

from tests.conftest import API


async def test_create_programme_defaults_to_draft(client: AsyncClient) -> None:
    response = await client.post(
        f"{API}/programmes",
        json={"name": "Spring Reset", "store_ids": ["store_001"]},
    )

    assert response.status_code == 201
    assert response.json()["status"] == "draft"
    assert response.json()["store_ids"] == ["store_001"]


async def test_create_programme_deduplicates_store_ids(client: AsyncClient) -> None:
    response = await client.post(
        f"{API}/programmes",
        json={"name": "Dedupe", "store_ids": ["store_001", "store_001", "store_002"]},
    )

    assert response.json()["store_ids"] == ["store_001", "store_002"]


async def test_duplicate_programme_name_conflicts(client: AsyncClient) -> None:
    await client.post(f"{API}/programmes", json={"name": "Spring Reset"})

    response = await client.post(f"{API}/programmes", json={"name": "spring reset"})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


async def test_end_before_start_is_rejected(client: AsyncClient) -> None:
    response = await client.post(
        f"{API}/programmes",
        json={"name": "Bad dates", "starts_on": "2026-05-01", "ends_on": "2026-04-01"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["details"]["field"] == "ends_on"


async def test_list_programmes_filters_by_status(client: AsyncClient) -> None:
    await client.post(f"{API}/programmes", json={"name": "Draft one"})
    await client.post(
        f"{API}/programmes",
        json={"name": "Live one", "activate_immediately": True},
    )

    response = await client.get(f"{API}/programmes", params={"status": "active"})

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["name"] == "Live one"
