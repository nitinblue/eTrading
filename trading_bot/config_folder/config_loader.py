import os
import yaml
from dotenv import load_dotenv
from pathlib import Path


def get_project_root() -> Path:
    """
    Assumes:
    project_root/
      ├── trading_bot/
      │     └── config_folder/
      │           └── config_loader.py  <-- this file
    """
    return Path(__file__).resolve().parents[2]


def load_yaml_with_env(relative_path: str) -> dict:
    project_root = get_project_root()

    # 1️⃣ Load .env from root
    load_dotenv(project_root / ".env")

    # 2️⃣ Build absolute config path
    config_path = project_root / relative_path
    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")

    # 3️⃣ Load YAML
    with open(config_path, "r") as f:
        raw = yaml.safe_load(f)

    # 4️⃣ Resolve ${ENV_VAR}
    def resolve(value):
        if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
            env_key = value[2:-1]
            resolved = os.getenv(env_key)
            if resolved is None:
                raise ValueError(f"Missing env var: {env_key}")
            return resolved
        elif isinstance(value, dict):
            return {k: resolve(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [resolve(v) for v in value]
        return value

    return resolve(raw)
