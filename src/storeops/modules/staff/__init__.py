"""Store staff.

Read-only to the rest of the system. Other modules may import
`storeops.modules.staff.port` — and nothing else from this package.
"""

from storeops.modules.staff.routes import router

__all__ = ["router"]
