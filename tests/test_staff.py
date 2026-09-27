from __future__ import annotations

from httpx import AsyncClient

from storeops.modules.staff.port import StaffDirectory
from storeops.modules.staff.service import StaffService, get_staff_service

from tests.conftest import API


async def test_list_staff_returns_seeded_members(client: AsyncClient) -> None:
    response = await client.get(f"{API}/staff")

    assert response.status_code == 200
    assert response.json()["total"] == 2
    assert response.json()["items"][0]["display_name"] == "Ada Okonjo"


async def test_list_staff_filters_by_role(client: AsyncClient) -> None:
    response = await client.get(f"{API}/staff", params={"role": "manager"})

    assert response.json()["total"] == 1
    assert response.json()["items"][0]["role"] == "manager"


async def test_staff_service_satisfies_the_read_only_port() -> None:
    service = get_staff_service()

    assert isinstance(service, StaffDirectory)


async def test_port_exposes_no_mutating_operations() -> None:
    exposed = {name for name in dir(StaffDirectory) if not name.startswith("_")}

    assert exposed == {"find", "headcount", "is_active"}


async def test_summary_projection_hides_internal_fields() -> None:
    service = get_staff_service()

    summary = await service.find("stf_0001")

    assert summary is not None
    assert summary.display_name == "Ada Okonjo"
    assert not hasattr(summary, "first_name")


async def test_service_mutators_are_module_private() -> None:
    """Staff writes must not be reachable through the shared surface."""
    public = {name for name in vars(StaffService) if not name.startswith("_")}

    assert public == {"get", "list", "find", "headcount", "is_active"}
