# trading_bot/config.py
import os
import os.path  # ADD THIS LINE
from dotenv import load_dotenv
load_dotenv()
print("✅ .env loaded:")
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
            yaml_str = f.read()  # Read as STRING first
        
        # EXPAND ${VAR_NAME} → env values
        yaml_str = os.path.expandvars(yaml_str)
        print(f"DEBUG YAML after expand: {yaml_str[:200]}...")  # Debug
        data = yaml.safe_load(yaml_str) or {}
        return cls(**data)