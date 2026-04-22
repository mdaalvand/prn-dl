from __future__ import annotations

import random

from models import Video


def select_videos(
    videos: list[Video],
    limit: int,
    pool_size: int,
    mode: str,
    seed: int | None = None,
) -> list[Video]:
    if limit <= 0 or pool_size <= 0 or not videos:
        return []
    pool = videos[: max(1, pool_size)]
    if mode == "random":
        rng = random.Random(seed)
        take = min(limit, len(pool))
        return rng.sample(pool, take)
    return pool[:limit]
