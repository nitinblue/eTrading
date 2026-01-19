import os
import yaml
import re
from dotenv import load_dotenv

_ENV_PATTERN = re.compile(r"\$\{([^}]+)\}")


def load_yaml_with_env(path: str) -> dict:
    # Load .env ONCE, globally
    load_dotenv(override=True)

    with open(path, "r") as f:
        raw = f.read()

    def repl(match):
        key = match.group(1)
        val = os.getenv(key)
        if val is None:
            raise RuntimeError(f"Missing environment variable: {key}")
        return val

    resolved = _ENV_PATTERN.sub(repl, raw)
    return yaml.safe_load(resolved)
