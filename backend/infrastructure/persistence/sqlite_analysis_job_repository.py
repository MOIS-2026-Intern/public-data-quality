from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from threading import Lock

from backend.application.dto import AnalysisJob, AnalysisJobItem


class SQLiteAnalysisJobRepository:
    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._ensure_schema()

    def save_job(self, job: AnalysisJob) -> AnalysisJob:
        payload = job.model_dump(mode="json")
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO analysis_jobs (
                    job_id,
                    status,
                    queue_backend,
                    queue_task_id,
                    request_json,
                    total_items,
                    processed_items,
                    success_count,
                    failed_count,
                    row_count,
                    finding_count,
                    issue_finding_count,
                    manual_review_finding_count,
                    batch_result_artifact_json,
                    batch_report_artifact_json,
                    error_message,
                    created_at,
                    updated_at,
                    started_at,
                    completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    status = excluded.status,
                    queue_backend = excluded.queue_backend,
                    queue_task_id = excluded.queue_task_id,
                    request_json = excluded.request_json,
                    total_items = excluded.total_items,
                    processed_items = excluded.processed_items,
                    success_count = excluded.success_count,
                    failed_count = excluded.failed_count,
                    row_count = excluded.row_count,
                    finding_count = excluded.finding_count,
                    issue_finding_count = excluded.issue_finding_count,
                    manual_review_finding_count = excluded.manual_review_finding_count,
                    batch_result_artifact_json = excluded.batch_result_artifact_json,
                    batch_report_artifact_json = excluded.batch_report_artifact_json,
                    error_message = excluded.error_message,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at,
                    started_at = excluded.started_at,
                    completed_at = excluded.completed_at
                """,
                (
                    payload["job_id"],
                    payload["status"],
                    payload["queue_backend"],
                    payload.get("queue_task_id"),
                    json.dumps(payload["request"], ensure_ascii=False),
                    payload["total_items"],
                    payload["processed_items"],
                    payload["success_count"],
                    payload["failed_count"],
                    payload["row_count"],
                    payload["finding_count"],
                    payload["issue_finding_count"],
                    payload["manual_review_finding_count"],
                    _json_or_none(payload.get("batch_result_artifact")),
                    _json_or_none(payload.get("batch_report_artifact")),
                    payload.get("error_message"),
                    payload["created_at"],
                    payload["updated_at"],
                    payload.get("started_at"),
                    payload.get("completed_at"),
                ),
            )
        return job

    def save_job_item(self, item: AnalysisJobItem) -> AnalysisJobItem:
        payload = item.model_dump(mode="json")
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO analysis_job_items (
                    item_id,
                    job_id,
                    item_index,
                    display_name,
                    source_type,
                    response_type,
                    status,
                    dataset_name,
                    source_artifact_json,
                    result_artifact_json,
                    validation_result_artifact_json,
                    error_report_artifact_json,
                    error_message,
                    row_count,
                    column_count,
                    finding_count,
                    issue_finding_count,
                    manual_review_finding_count,
                    created_at,
                    updated_at,
                    started_at,
                    completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(item_id) DO UPDATE SET
                    job_id = excluded.job_id,
                    item_index = excluded.item_index,
                    display_name = excluded.display_name,
                    source_type = excluded.source_type,
                    response_type = excluded.response_type,
                    status = excluded.status,
                    dataset_name = excluded.dataset_name,
                    source_artifact_json = excluded.source_artifact_json,
                    result_artifact_json = excluded.result_artifact_json,
                    validation_result_artifact_json = excluded.validation_result_artifact_json,
                    error_report_artifact_json = excluded.error_report_artifact_json,
                    error_message = excluded.error_message,
                    row_count = excluded.row_count,
                    column_count = excluded.column_count,
                    finding_count = excluded.finding_count,
                    issue_finding_count = excluded.issue_finding_count,
                    manual_review_finding_count = excluded.manual_review_finding_count,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at,
                    started_at = excluded.started_at,
                    completed_at = excluded.completed_at
                """,
                (
                    payload["item_id"],
                    payload["job_id"],
                    payload["index"],
                    payload["display_name"],
                    payload["source_type"],
                    payload.get("response_type"),
                    payload["status"],
                    payload.get("dataset_name"),
                    _json_or_none(payload.get("source_artifact")),
                    _json_or_none(payload.get("result_artifact")),
                    _json_or_none(payload.get("validation_result_artifact")),
                    _json_or_none(payload.get("error_report_artifact")),
                    payload.get("error_message"),
                    payload["row_count"],
                    payload["column_count"],
                    payload["finding_count"],
                    payload["issue_finding_count"],
                    payload["manual_review_finding_count"],
                    payload["created_at"],
                    payload["updated_at"],
                    payload.get("started_at"),
                    payload.get("completed_at"),
                ),
            )
        return item

    def get_job(self, job_id: str, *, with_items: bool = True) -> AnalysisJob | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    job_id,
                    status,
                    queue_backend,
                    queue_task_id,
                    request_json,
                    total_items,
                    processed_items,
                    success_count,
                    failed_count,
                    row_count,
                    finding_count,
                    issue_finding_count,
                    manual_review_finding_count,
                    batch_result_artifact_json,
                    batch_report_artifact_json,
                    error_message,
                    created_at,
                    updated_at,
                    started_at,
                    completed_at
                FROM analysis_jobs
                WHERE job_id = ?
                """,
                (job_id,),
            ).fetchone()
        if row is None:
            return None

        items = self.list_job_items(job_id) if with_items else []
        return AnalysisJob(
            job_id=row["job_id"],
            status=row["status"],
            queue_backend=row["queue_backend"],
            queue_task_id=row["queue_task_id"],
            request=json.loads(row["request_json"] or "{}"),
            total_items=row["total_items"],
            processed_items=row["processed_items"],
            success_count=row["success_count"],
            failed_count=row["failed_count"],
            row_count=row["row_count"],
            finding_count=row["finding_count"],
            issue_finding_count=row["issue_finding_count"],
            manual_review_finding_count=row["manual_review_finding_count"],
            batch_result_artifact=_model_from_json(row["batch_result_artifact_json"]),
            batch_report_artifact=_model_from_json(row["batch_report_artifact_json"]),
            error_message=row["error_message"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            items=items,
        )

    def get_job_item(self, item_id: str) -> AnalysisJobItem | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    item_id,
                    job_id,
                    item_index,
                    display_name,
                    source_type,
                    response_type,
                    status,
                    dataset_name,
                    source_artifact_json,
                    result_artifact_json,
                    validation_result_artifact_json,
                    error_report_artifact_json,
                    error_message,
                    row_count,
                    column_count,
                    finding_count,
                    issue_finding_count,
                    manual_review_finding_count,
                    created_at,
                    updated_at,
                    started_at,
                    completed_at
                FROM analysis_job_items
                WHERE item_id = ?
                """,
                (item_id,),
            ).fetchone()
        return _item_from_row(row)

    def list_job_items(self, job_id: str) -> list[AnalysisJobItem]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    item_id,
                    job_id,
                    item_index,
                    display_name,
                    source_type,
                    response_type,
                    status,
                    dataset_name,
                    source_artifact_json,
                    result_artifact_json,
                    validation_result_artifact_json,
                    error_report_artifact_json,
                    error_message,
                    row_count,
                    column_count,
                    finding_count,
                    issue_finding_count,
                    manual_review_finding_count,
                    created_at,
                    updated_at,
                    started_at,
                    completed_at
                FROM analysis_job_items
                WHERE job_id = ?
                ORDER BY item_index
                """,
                (job_id,),
            ).fetchall()
        return [item for row in rows if (item := _item_from_row(row)) is not None]

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure_schema(self) -> None:
        with self._lock, self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS analysis_jobs (
                    job_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    queue_backend TEXT NOT NULL,
                    queue_task_id TEXT,
                    request_json TEXT NOT NULL,
                    total_items INTEGER NOT NULL,
                    processed_items INTEGER NOT NULL,
                    success_count INTEGER NOT NULL,
                    failed_count INTEGER NOT NULL,
                    row_count INTEGER NOT NULL,
                    finding_count INTEGER NOT NULL,
                    issue_finding_count INTEGER NOT NULL,
                    manual_review_finding_count INTEGER NOT NULL,
                    batch_result_artifact_json TEXT,
                    batch_report_artifact_json TEXT,
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT
                );

                CREATE TABLE IF NOT EXISTS analysis_job_items (
                    item_id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    item_index INTEGER NOT NULL,
                    display_name TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    response_type TEXT,
                    status TEXT NOT NULL,
                    dataset_name TEXT,
                    source_artifact_json TEXT,
                    result_artifact_json TEXT,
                    validation_result_artifact_json TEXT,
                    error_report_artifact_json TEXT,
                    error_message TEXT,
                    row_count INTEGER NOT NULL,
                    column_count INTEGER NOT NULL,
                    finding_count INTEGER NOT NULL,
                    issue_finding_count INTEGER NOT NULL,
                    manual_review_finding_count INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    FOREIGN KEY(job_id) REFERENCES analysis_jobs(job_id)
                );
                """
            )


def _json_or_none(value: object) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)


def _model_from_json(value: str | None):
    if not value:
        return None
    return json.loads(value)


def _item_from_row(row) -> AnalysisJobItem | None:
    if row is None:
        return None
    return AnalysisJobItem(
        item_id=row["item_id"],
        job_id=row["job_id"],
        index=row["item_index"],
        display_name=row["display_name"],
        source_type=row["source_type"],
        response_type=row["response_type"],
        status=row["status"],
        dataset_name=row["dataset_name"],
        source_artifact=_model_from_json(row["source_artifact_json"]),
        result_artifact=_model_from_json(row["result_artifact_json"]),
        validation_result_artifact=_model_from_json(row["validation_result_artifact_json"]),
        error_report_artifact=_model_from_json(row["error_report_artifact_json"]),
        error_message=row["error_message"],
        row_count=row["row_count"],
        column_count=row["column_count"],
        finding_count=row["finding_count"],
        issue_finding_count=row["issue_finding_count"],
        manual_review_finding_count=row["manual_review_finding_count"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        started_at=row["started_at"],
        completed_at=row["completed_at"],
    )

