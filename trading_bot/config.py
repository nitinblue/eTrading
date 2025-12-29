# trading_bot/config.py
import os
import yaml
from pydantic import BaseModel, Field
from typing import Optional, Dict

class Config(BaseModel):
    """Central configuration model using Pydantic for validation."""
    broker: Dict[str, str] = Field(..., description="Broker credentials and settings")
    sheets: Dict[str, str] = Field(..., description="Google Sheets integration settings")
    risk: Dict[str, float] = Field(default_factory=dict, description="Risk management params")
    logging: Dict[str, str] = Field(default_factory=dict, description="Logging settings")
    database: Optional[Dict[str, str]] = None  # Optional for persistence

    @classmethod
    def load(cls, file_path: str = 'config.yaml') -> 'Config':
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Config file {file_path} not found.")
        with open(file_path, 'r') as f:
            data = yaml.safe_load(f)
        return cls(**data)