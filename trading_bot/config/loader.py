# config/loader.py
import yaml
from pathlib import Path

def load_yaml(path: str) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)

def load_all_configs():
    return {
        "account": load_yaml("config/account.yaml"),
        "portfolio": load_yaml("config/portfolio.yaml"),
        "risk": load_yaml("config/risk.yaml"),
        "strategy_defined": load_yaml("config/strategy_defined.yaml"),
        "strategy_undefined": load_yaml("config/strategy_undefined.yaml"),
        "execution": load_yaml("config/execution.yaml"),
    }
