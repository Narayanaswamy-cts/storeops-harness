"""Application composition root.

This is the only module permitted to import more than one feature module. It
wires services together, registers event-bus subscribers and installs the
exception handlers that translate the typed error hierarchy into HTTP responses.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from storeops import __version__
from storeops.core.config import Settings, get_settings
from storeops.core.deps import get_event_bus
from storeops.core.errors import AppError, InternalError, ValidationError
from storeops.modules.activities.routes import router as activities_router
from storeops.modules.activities.service import get_activity_service
from storeops.modules.alerts.routes import router as alerts_router
from storeops.modules.alerts.service import get_alert_service
from storeops.modules.alerts.subscribers import register as register_alert_subscribers
from storeops.modules.programmes.routes import router as programmes_router
from storeops.modules.programmes.service import get_programme_service
from storeops.modules.reports.ports import MetricsSources
from storeops.modules.reports.routes import router as reports_router
from storeops.modules.reports.service import configure_sources
from storeops.modules.staff.routes import router as staff_router
from storeops.modules.staff.service import get_staff_service

__all__ = ["app", "create_app"]

logger = logging.getLogger(__name__)


def wire_modules() -> None:
    """Connect modules to one another — only via the bus and read-only ports.

    Called synchronously from `create_app` rather than from a lifespan hook, so
    that tests driving the app through `httpx.ASGITransport` (which does not run
    lifespan events) get a fully wired app.
    """
    bus = get_event_bus()
    bus.clear()

    # Notifications: alerts subscribes; publishers stay ignorant of it.
    register_alert_subscribers(bus, get_alert_service())

    # Reports reads other modules through narrow, read-only protocols.
    configure_sources(
        MetricsSources(
            activities=get_activity_service(),
            programmes=get_programme_service(),
            alerts=get_alert_service(),
            staff=get_staff_service(),
        )
    )


def _install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: Exception) -> JSONResponse:
        error = exc if isinstance(exc, AppError) else InternalError()
        if error.status_code >= 500:
            logger.error("app error: %r", error)
        return JSONResponse(status_code=error.status_code, content=error.to_payload())

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation(_: Request, exc: Exception) -> JSONResponse:
        raw = exc.errors() if isinstance(exc, RequestValidationError) else []
        error = ValidationError(details={"errors": jsonable_encoder(raw)})
        return JSONResponse(status_code=error.status_code, content=error.to_payload())

    @app.exception_handler(Exception)
    async def handle_unexpected(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled exception", exc_info=exc)
        error = InternalError()
        return JSONResponse(status_code=error.status_code, content=error.to_payload())


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()

    app = FastAPI(title=resolved.app_name, version=__version__)

    _install_error_handlers(app)
    wire_modules()

    for router in (
        activities_router,
        programmes_router,
        staff_router,
        alerts_router,
        reports_router,
    ):
        app.include_router(router, prefix=resolved.api_prefix)

    @app.get("/health", tags=["meta"], summary="Liveness probe")
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    return app


app = create_app()
