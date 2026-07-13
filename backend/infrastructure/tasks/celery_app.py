from __future__ import annotations

import os
from functools import lru_cache

from backend.config.celery import (
    CELERY_BROKER_URL_ENV_VAR,
    CELERY_RESULT_BACKEND_ENV_VAR,
    CELERY_TASK_ALWAYS_EAGER_ENV_VAR,
    DEFAULT_CELERY_BROKER_URL,
    DEFAULT_CELERY_RESULT_BACKEND,
)


def _env_flag(name: str, *, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _broker_url() -> str:
    configured = os.getenv(CELERY_BROKER_URL_ENV_VAR) or os.getenv("REDIS_URL")
    return (configured or DEFAULT_CELERY_BROKER_URL).strip()


def _result_backend() -> str:
    configured = os.getenv(CELERY_RESULT_BACKEND_ENV_VAR) or os.getenv("REDIS_URL")
    return (configured or DEFAULT_CELERY_RESULT_BACKEND).strip()


@lru_cache(maxsize=1)
def celery_app():
    from celery import Celery

    app = Celery("ldq_gpt")
    app.conf.update(
        broker_url=_broker_url(),
        result_backend=_result_backend(),
        task_always_eager=_env_flag(CELERY_TASK_ALWAYS_EAGER_ENV_VAR, default=False),
        task_store_eager_result=True,
        task_ignore_result=False,
        task_track_started=True,
        worker_prefetch_multiplier=1,
        accept_content=["json"],
        task_serializer="json",
        result_serializer="json",
        timezone="Asia/Seoul",
        enable_utc=True,
        imports=("backend.infrastructure.tasks.tasks",),
    )
    return app
