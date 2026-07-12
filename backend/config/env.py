from __future__ import annotations

from importlib.util import find_spec
from pathlib import Path

if find_spec("dotenv") is not None:  # pragma: no branch
    from dotenv import load_dotenv
else:  # pragma: no cover
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
