"""Load simple KEY=VALUE settings without evaluating shell expressions."""
import os
import re
from pathlib import Path

ALLOWED = {"DATAFORSEO_LOGIN", "DATAFORSEO_PASSWORD", "OPENAI_API_KEY", "OPENAI_MODEL"}

def load_env(path: str | Path = ".env") -> None:
    path = Path(path)
    if not path.exists(): return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"): continue
        match = re.fullmatch(r"([A-Z_]+)\s*=\s*(.*)", stripped)
        if not match or match.group(1) not in ALLOWED:
            raise ValueError("Invalid or unsupported .env setting")
        key, value = match.groups()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if key not in os.environ: os.environ[key] = value
