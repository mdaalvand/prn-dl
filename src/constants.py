from __future__ import annotations

DEFAULT_TIMEOUT_SECONDS = 15
DEFAULT_MAX_PAGES = 3
DEFAULT_LIMIT = 10
DEFAULT_POOL_SIZE = 100
DEFAULT_MODE = "top"
DEFAULT_OUTPUT_DIR = "downloads"
DEFAULT_QUALITY = 480
DEFAULT_RETRIES = 3
DEFAULT_BACKOFF_SECONDS = 0.8
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

ORDER_TO_QUERY = {
    "most_relevant": None,
    "most_viewed": "mv",
    "top_rated": "tr",
    "newest": "mr",
    "hottest": "ht",
}

PERIOD_TO_QUERY = {
    "daily": "d",
    "weekly": "w",
    "monthly": "m",
    "alltime": "a",
}

ORIENTATION_ALIASES = {
    "straight": "straight",
    "hetero": "straight",
    "gay": "gay",
    "lesbian": "lesbian",
    "lesbo": "lesbian",
    "trans": "transgender",
    "transgender": "transgender",
    "bi": "bi",
    "bisexual": "bi",
    "any": "any",
    "all": "any",
    "دوجنسه": "bi",
    "گی": "gay",
    "لز": "lesbian",
    "لزبین": "lesbian",
    "ترنس": "transgender",
}
