from __future__ import annotations

import os
from dataclasses import dataclass

import constants


@dataclass(frozen=True)
class AppSettings:
    timeout_seconds: int = constants.DEFAULT_TIMEOUT_SECONDS
    retries: int = constants.DEFAULT_RETRIES
    backoff_seconds: float = constants.DEFAULT_BACKOFF_SECONDS
    default_max_pages: int = constants.DEFAULT_MAX_PAGES
    default_limit: int = constants.DEFAULT_LIMIT
    default_pool_size: int = constants.DEFAULT_POOL_SIZE
    default_mode: str = constants.DEFAULT_MODE
    default_output_dir: str = constants.DEFAULT_OUTPUT_DIR
    default_quality: int = constants.DEFAULT_QUALITY

    @classmethod
    def from_env(cls) -> "AppSettings":
        return cls(
            timeout_seconds=int(os.getenv("PHFETCH_TIMEOUT", constants.DEFAULT_TIMEOUT_SECONDS)),
            retries=int(os.getenv("PHFETCH_RETRIES", constants.DEFAULT_RETRIES)),
            backoff_seconds=float(os.getenv("PHFETCH_BACKOFF", constants.DEFAULT_BACKOFF_SECONDS)),
            default_max_pages=int(os.getenv("PHFETCH_MAX_PAGES", constants.DEFAULT_MAX_PAGES)),
            default_limit=int(os.getenv("PHFETCH_LIMIT", constants.DEFAULT_LIMIT)),
            default_pool_size=int(os.getenv("PHFETCH_POOL_SIZE", constants.DEFAULT_POOL_SIZE)),
            default_mode=os.getenv("PHFETCH_MODE", constants.DEFAULT_MODE),
            default_output_dir=os.getenv("PHFETCH_OUTPUT", constants.DEFAULT_OUTPUT_DIR),
            default_quality=int(os.getenv("PHFETCH_QUALITY", constants.DEFAULT_QUALITY)),
        )
