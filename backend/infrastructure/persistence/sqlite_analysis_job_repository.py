from __future__ import annotations

import sqlite3
from pathlib import Path
from threading import Lock

from backend.application.dto import AnalysisJob, AnalysisJobItem

from .sqlite_analysis_job_store import (
    ITEM_LIST_SQL,
    ITEM_SELECT_SQL,
    ITEM_UPSERT_SQL,
    JOB_SELECT_SQL,
    JOB_UPSERT_SQL,
    SCHEMA_SQL,
    item_from_row,
    item_params,
    job_from_row,
    job_params,
)


class SQLiteAnalysisJobRepository:
    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._ensure_schema()

    def save_job(self, job: AnalysisJob) -> AnalysisJob:
        with self._lock, self._connect() as connection:
            connection.execute(JOB_UPSERT_SQL, job_params(job))
        return job

    def save_job_item(self, item: AnalysisJobItem) -> AnalysisJobItem:
        with self._lock, self._connect() as connection:
            connection.execute(ITEM_UPSERT_SQL, item_params(item))
        return item

    def get_job(self, job_id: str, *, with_items: bool = True) -> AnalysisJob | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(JOB_SELECT_SQL, (job_id,)).fetchone()
        return job_from_row(row, items=self.list_job_items(job_id) if with_items else [])

    def get_job_item(self, item_id: str) -> AnalysisJobItem | None:
        with self._lock, self._connect() as connection:
            return item_from_row(connection.execute(ITEM_SELECT_SQL, (item_id,)).fetchone())

    def list_job_items(self, job_id: str) -> list[AnalysisJobItem]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(ITEM_LIST_SQL, (job_id,)).fetchall()
        return [item for row in rows if (item := item_from_row(row)) is not None]

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure_schema(self) -> None:
        with self._lock, self._connect() as connection:
            connection.executescript(SCHEMA_SQL)
