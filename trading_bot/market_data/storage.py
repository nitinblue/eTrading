# trading_bot/market_data/storage.py
import json
import os
from typing import Any, Dict
import logging

logger = logging.getLogger(__name__)

class DataStorage:
    def __init__(self, file_path: str = "market_data.json"):
        self.file_path = file_path
        self.data: Dict[str, Any] = self._load()

    def _load(self) -> Dict[str, Any]:
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                logger.warning(f"Corrupted {self.file_path} — starting fresh.")
        return {}

    def save(self, key: str, value: Any):
        self.data[key] = value
        with open(self.file_path, 'w') as f:
            json.dump(self.data, f, indent=4, default=str)
        logger.info(f"Saved {key} to storage")

    def load(self, key: str) -> Any:
        return self.data.get(key)