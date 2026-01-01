# trading_bot/config.py
import yaml
import os
<<<<<<< HEAD
from pydantic import BaseModel
from typing import Dict

# Load .env if exists
=======
import os.path  # ADD THIS LINE
>>>>>>> a2d3074eaa89e65f81eea4d1269dac9b85efdf4e
from dotenv import load_dotenv
load_dotenv()

class Config(BaseModel):
    general: Dict = {}
    broker: Dict = {}
    risk: Dict = {}
    strategies: Dict = {}
    sheets: Dict = {}

    @classmethod
<<<<<<< HEAD
    def load(cls, file_path: str = 'config.yaml'):
        with open(file_path, 'r') as f:
            raw = f.read()

        # Substitute environment variables
        data = yaml.safe_load(os.path.expandvars(raw)) or {}

=======
    def load(cls, file_path: str = 'config.yaml') -> 'Config':       
        with open(file_path, 'r') as f:
            yaml_str = f.read()  # Read as STRING first
        
        # EXPAND ${VAR_NAME} → env values
        yaml_str = os.path.expandvars(yaml_str)
        # print(f"DEBUG YAML after expand: {yaml_str[:200]}...")  # Debug
        data = yaml.safe_load(yaml_str) or {}
        # print(f"🔍 Final config broker: {data.get('broker', {})}")
        # print(f"🔍 Final config sheets: {data.get('sheets', {})}")
>>>>>>> a2d3074eaa89e65f81eea4d1269dac9b85efdf4e
        return cls(**data)