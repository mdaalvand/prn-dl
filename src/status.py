from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any


@dataclass
class PipelineReporter:
    enabled: bool = True
    json_output: bool = False

    def __post_init__(self) -> None:
        self._logger = logging.getLogger("phfetch")

    def event(self, message: str, **fields: Any) -> None:
        if not self.enabled:
            return
        if self.json_output:
            payload = {"message": message, **fields}
            self._logger.info(json.dumps(payload, ensure_ascii=False))
            return
        if fields:
            self._logger.info("%s | %s", message, fields)
            return
        self._logger.info(message)
