# trading_bot/config.py
import yaml
import os
from pydantic import BaseModel
from typing import Dict

# Load .env if exists
from dotenv import load_dotenv
load_dotenv()

class Config(BaseModel):
    general: Dict = {}
    broker: Dict = {}
    risk: Dict = {}
    strategies: Dict = {}
    sheets: Dict = {}

    @classmethod
    def load(cls, file_path: str = 'config.yaml'):
        with open(file_path, 'r') as f:
            raw = f.read()

        # Substitute environment variables
        data = yaml.safe_load(os.path.expandvars(raw)) or {}

        return cls(**data)