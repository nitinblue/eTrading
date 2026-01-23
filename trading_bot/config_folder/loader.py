import yaml
from decimal import Decimal
from pathlib import Path

CONFIG_DIR = Path(__file__).parent


def _load_yaml(file_name: str) -> dict:
    path = CONFIG_DIR / file_name
    if not path.exists():
        raise FileNotFoundError(f"Missing config: {path}")
    with open(path, "r") as f:
        return yaml.safe_load(f) or {}


def _decimalize(obj):
    """
    Recursively convert floats → Decimal
    """
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: _decimalize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_decimalize(v) for v in obj]
    return obj


def load_all_configs() -> dict:
    config = {
        "risk": _load_yaml("risk.yaml"),
        "tastytrade_broker": _load_yaml("tastytrade_broker.yaml"),
        "strategies": _load_yaml("strategies.yaml"),
        "system": _load_yaml("system.yaml"),
    }

    return _decimalize(config)

'''
def load_all_configs():
    return {
        "account": load_yaml("trading_bot/config_folder/account.yaml"),
        "portfolio": load_yaml("trading_bot/config_folder/portfolio.yaml"),
        "risk": load_yaml("trading_bot/config_folder/risk.yaml"),
        "strategy_defined": load_yaml("trading_bot/config_folder/strategy_defined.yaml"),
        "strategy_undefined": load_yaml("trading_bot/config_folder/strategy_undefined.yaml"),
        "broker": load_yaml("trading_bot/config_folder/broker.yaml"),
    }
'''