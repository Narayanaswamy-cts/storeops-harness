"""Operational alerts.

No other module may import this package — that is the point of the event bus.
Alerts are raised by *subscribing* to domain events during app wiring; see
`storeops.modules.alerts.subscribers.register`.
"""

from storeops.modules.alerts.routes import router
from storeops.modules.alerts.subscribers import register

__all__ = ["register", "router"]
