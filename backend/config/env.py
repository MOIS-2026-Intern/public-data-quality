from __future__ import annotations

from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

_ENV_LOADED = False


def ensure_runtime_environment() -> None:
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    if load_dotenv is None:
        _ENV_LOADED = True
        return

    project_root = Path(__file__).resolve().parents[2]
    load_dotenv(project_root / ".env")
    load_dotenv()
    _ENV_LOADED = True
