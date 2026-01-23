import os
import re
import yaml
from decimal import Decimal
from typing import Any

# Regex to find ${VAR_NAME} in your YAML files
ENV_VAR_PATTERN = re.compile(r".*?\${(\w+)}.*?")

class ConfigManager:
    def __init__(self, config_dir: str = "config_folder"):
        self.config_dir = config_dir
        self.configs = {}
        self._load_all_configs()

    def _env_var_constructor(self, loader, node):
        """Replaces ${VAR_NAME} with the actual environment variable value."""
        value = loader.construct_scalar(node)
        for var in ENV_VAR_PATTERN.findall(value):
            # os.getenv(var, "") returns empty string if variable is not set
            value = value.replace(f"${{{var}}}", os.getenv(var, ""))
        return value

    def _load_all_configs(self):
        """Loads every .yaml file in the folder into a dictionary."""
        # Register the environment variable handler
        yaml.SafeLoader.add_implicit_resolver("!env", ENV_VAR_PATTERN, None)
        yaml.SafeLoader.add_constructor("!env", self._env_var_constructor)

        if not os.path.exists(self.config_dir):
            return

        for filename in os.listdir(self.config_dir):
            if filename.endswith((".yaml", ".yml")):
                path = os.path.join(self.config_dir, filename)
                with open(path, "r") as f:
                    # Each file's data is stored under its filename
                    self.configs[filename] = yaml.load(f, Loader=yaml.SafeLoader)

    def get(self, file_name: str, key_path: str, default: Any = None) -> Any:
        """
        Safely gets a value using dot-notation (e.g., 'broker.tastytrade.live.client_secret').
        """
        data = self.configs.get(file_name)
        if not data: return default

        keys = key_path.split('.')
        for key in keys:
            if isinstance(data, dict) and key in data:
                data = data[key]
            else:
                return default
        return data

    def get_decimal(self, file_name: str, key_path: str, default: str = "0") -> Decimal:
        """Forces a value to Decimal (crucial for money calculations)."""
        val = self.get(file_name, key_path)
        try:
            return Decimal(str(val)) if val is not None else Decimal(default)
        except:
            return Decimal(default)

# Global Instance
cfg = ConfigManager()