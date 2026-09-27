"""Application settings."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

__all__ = ["Settings", "get_settings"]


@dataclass(frozen=True)
class Settings:
    app_name: str = "StoreOps API"
    api_prefix: str = "/api/v1"
    environment: str = "local"
    default_page_size: int = 25
    max_page_size: int = 100

    @property
    def debug(self) -> bool:
        return self.environment == "local"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        environment=os.getenv("STOREOPS_ENV", "local"),
        api_prefix=os.getenv("STOREOPS_API_PREFIX", "/api/v1"),
    )
