"""Shared fixtures.

Services are cached singletons, so every test clears the caches and builds a
fresh app. `create_app` wires the modules synchronously, which is what lets us
drive the app over `httpx.ASGITransport` without a lifespan manager.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

import pytest
from httpx import ASGITransport, AsyncClient

from storeops.core.config import Settings
from storeops.core.deps import get_event_bus
from storeops.main import create_app
from storeops.modules.activities.service import get_activity_service
from storeops.modules.alerts.service import get_alert_service
from storeops.modules.programmes.service import get_programme_service
from storeops.modules.reports.service import get_report_service
from storeops.modules.staff.service import get_staff_service

API = "/api/v1"

_PROVIDERS = (
    get_event_bus,
    get_activity_service,
    get_programme_service,
    get_staff_service,
    get_alert_service,
    get_report_service,
)


@pytest.fixture(autouse=True)
def reset_singletons() -> Iterator[None]:
    for provider in _PROVIDERS:
        provider.cache_clear()
    yield
    for provider in _PROVIDERS:
        provider.cache_clear()


@pytest.fixture
def settings() -> Settings:
    return Settings(environment="test", api_prefix=API)


@pytest.fixture
async def client(reset_singletons: None, settings: Settings) -> AsyncIterator[AsyncClient]:
    del reset_singletons  # ordering dependency only
    app = create_app(settings)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://storeops.test") as http:
        yield http


@pytest.fixture
def activity_payload() -> dict[str, str]:
    return {"store_id": "store_001", "title": "Reset the end-cap display"}
