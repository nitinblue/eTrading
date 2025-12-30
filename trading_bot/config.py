# trading_bot/config.py
import yaml
from pydantic import BaseModel
from typing import Dict, Any, Optional

class Config(BaseModel):
    general: Dict[str, Any] = {}
    broker: Dict[str, Any] = {}
    risk: Dict[str, Any] = {}
    strategies: Dict[str, Any] = {}
    sheets: Dict[str, Any] = {}

    @classmethod
    def load(cls, file_path: str = 'config.yaml') -> 'Config':
        with open(file_path, 'r') as f:
            data = yaml.safe_load(f) or {}
        return cls(**data)