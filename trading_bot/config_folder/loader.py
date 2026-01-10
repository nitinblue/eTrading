# config/loader.py
import yaml
from pathlib import Path

def load_yaml(path: str) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)

def load_all_configs():
    return {
        "account": load_yaml("trading_bot/config_folder/account.yaml"),
        "portfolio": load_yaml("trading_bot/config_folder/portfolio.yaml"),
        "risk": load_yaml("trading_bot/config_folder/risk.yaml"),
        "strategy_defined": load_yaml("trading_bot/config_folder/strategy_defined.yaml"),
        "strategy_undefined": load_yaml("trading_bot/config_folder/strategy_undefined.yaml"),
        "broker": load_yaml("trading_bot/config_folder/broker.yaml"),
    }
