from __future__ import annotations

from .celery_app import celery_app

app = celery_app()

# Import task definitions so the worker registers them at startup.
from . import tasks as _tasks  # noqa: E402,F401

