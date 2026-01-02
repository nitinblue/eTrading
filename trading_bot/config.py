# trading_bot/config.py
import yaml
import os
from pydantic import BaseModel
from typing import Dict

# Load .env if exists
import os.path  # ADD THIS LINE
from dotenv import load_dotenv
load_dotenv()

class Config(BaseModel):
    general: Dict = {}
    broker: Dict = {}
    risk: Dict = {}
    strategies: Dict = {}
    sheets: Dict = {}

    @classmethod
    def load(cls, file_path: str = 'config.yaml') -> 'Config':       
        with open(file_path, 'r') as f:
            yaml_str = f.read()  # Read as STRING first
        
        # EXPAND ${VAR_NAME} → env values
        yaml_str = os.path.expandvars(yaml_str)
        # print(f"DEBUG YAML after expand: {yaml_str[:200]}...")  # Debug
        data = yaml.safe_load(yaml_str) or {}
        # print(f"🔍 Final config broker: {data.get('broker', {})}")
        # print(f"🔍 Final config sheets: {data.get('sheets', {})}")
        return cls(**data)