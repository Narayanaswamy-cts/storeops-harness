from __future__ import annotations

import pytest
from httpx import AsyncClient

from storeops.core.errors import (
    AppError,
    ConflictError,
    DependencyError,
    ForbiddenError,
    NotFoundError,
    ReadOnlyModuleError,
    ValidationError,
)

from tests.conftest import API


@pytest.mark.parametrize(
    ("error_type", "code", "status_code"),
    [
        (ValidationError, "validation_failed", 422),
        (NotFoundError, "not_found", 404),
        (ConflictError, "conflict", 409),
        (ForbiddenError, "forbidden", 403),
        (ReadOnlyModuleError, "read_only_module", 403),
        (DependencyError, "dependency_unavailable", 503),
    ],
)
def test_hierarchy_carries_code_and_status(
    error_type: type[AppError], code: str, status_code: int
) -> None:
    error = error_type()

    assert isinstance(error, AppError)
    assert error.code == code
    assert error.status_code == status_code
    assert error.message == error_type.default_message


def test_payload_shape_is_stable() -> None:
    error = NotFoundError.for_resource("activity", "act_1")

    assert error.to_payload() == {
        "error": {
            "code": "not_found",
            "message": "activity 'act_1' was not found.",
            "details": {"resource": "activity", "id": "act_1"},
        }
    }


def test_details_are_omitted_when_empty() -> None:
    assert "details" not in ValidationError().to_payload()["error"]


def test_read_only_module_error_is_a_forbidden_error() -> None:
    assert issubclass(ReadOnlyModuleError, ForbiddenError)


async def test_pydantic_validation_is_normalised_to_the_envelope(
    client: AsyncClient,
) -> None:
    response = await client.post(f"{API}/activities", json={"title": "no store id"})

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_failed"
    assert body["error"]["details"]["errors"]


async def test_unknown_path_is_not_wrapped(client: AsyncClient) -> None:
    """Starlette's own 404 for an unrouted path stays as-is."""
    response = await client.get(f"{API}/nope")

    assert response.status_code == 404


async def test_health_endpoint(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
