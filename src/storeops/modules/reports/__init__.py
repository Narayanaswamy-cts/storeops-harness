"""Store and region metrics."""

from storeops.modules.reports.routes import router
from storeops.modules.reports.service import configure_sources

__all__ = ["configure_sources", "router"]
