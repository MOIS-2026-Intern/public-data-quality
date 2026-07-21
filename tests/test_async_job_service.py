from pathlib import Path
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import backend.adapters.web.job_service as job_service
from backend.adapters.web.dependencies import WebAdapterDependencies
from backend.adapters.web.pipeline_service import PipelineRunResult
from backend.application.dto import AnalysisJob, PipelineExecutionRequest
from backend.infrastructure.io.sources import PreparedDataset
from backend.infrastructure.io.loaders.loading import iter_uploaded_rows
from backend.infrastructure.persistence import SQLiteAnalysisJobRepository
from backend.infrastructure.reporting.pipeline_outputs import attach_report_paths
from backend.infrastructure.reporting.workbooks import (
    write_batch_column_error_report,
    write_batch_error_report,
)
from backend.infrastructure.storage import FilesystemArtifactStore


class _FakeQueue:
    def __init__(self) -> None:
        self.job_ids: list[str] = []

    def enqueue_job(self, job_id: str) -> str:
        self.job_ids.append(job_id)
        return "task-1"


def _dependencies(
    tmp_path: Path,
    queue: _FakeQueue,
    write_column_report=write_batch_column_error_report,
) -> WebAdapterDependencies:
    repository = SQLiteAnalysisJobRepository(tmp_path / "jobs.sqlite3")
    artifact_store = FilesystemArtifactStore(tmp_path / "artifacts")
    return WebAdapterDependencies(
        pipeline_analysis_use_case=lambda: None,
        validation_output_dir=lambda base_dir=None: Path(base_dir or tmp_path / "validation") / "validation",
        attach_report_paths=attach_report_paths,
        write_batch_error_report=write_batch_error_report,
        write_batch_column_error_report=write_column_report,
        public_download_name=lambda filename, default_suffix=".xlsx": filename,
        prepare_saved_dataset=lambda *args, **kwargs: [],
        prepare_url_datasets=lambda *args, **kwargs: [],
        prepare_api_datasets=lambda *args, **kwargs: [],
        load_url_list=lambda *args, **kwargs: [],
        analysis_job_repository=lambda: repository,
        artifact_store=lambda: artifact_store,
        analysis_queue=lambda: queue,
        analysis_queue_backend="celery",
    )


def test_async_job_service_submits_processes_and_finalizes(monkeypatch, tmp_path) -> None:
    queue = _FakeQueue()
    dependencies = _dependencies(tmp_path, queue)
    dataset_path = tmp_path / "sample.csv"
    dataset_path.write_text("value\n1\n", encoding="utf-8")
    dataset = PreparedDataset(
        display_name="sample.csv",
        path=dataset_path,
        source_type="file",
        response_type="csv",
    )

    monkeypatch.setattr(
        job_service,
        "run_pipeline",
        lambda *, request, dependencies=None: PipelineRunResult(
            response={
                "summary": {
                    "dataset_name": request.uploaded_dataset_name or "sample.csv",
                    "column_count": 1,
                    "row_count": 1,
                    "finding_count": 0,
                    "issue_finding_count": 0,
                    "manual_review_finding_count": 0,
                },
                "preview_headers": ["value"],
                "preview_rows": [{"value": "1"}],
                "columns": [{"raw_name": "value"}],
                "findings": [],
            },
            validation_rows=[{"value": "1"}],
        ),
    )

    job = job_service.submit_analysis_job(
        prepared_datasets=[dataset],
        request=PipelineExecutionRequest(),
        dependencies=dependencies,
    )

    assert queue.job_ids == [job.job_id]
    assert job.queue_task_id == "task-1"
    assert job.request.openai_api_key is None

    item = job.items[0]
    item_result = job_service.process_analysis_job_item(
        job_id=job.job_id,
        item_id=item.item_id,
        dependencies=dependencies,
    )
    assert item_result["ok"] is True

    payload = job_service.finalize_analysis_job(
        job_id=job.job_id,
        item_results=[item_result],
        dependencies=dependencies,
    )

    stored_job = job_service.get_analysis_job(job.job_id, dependencies=dependencies)
    assert isinstance(stored_job, AnalysisJob)
    assert stored_job.status == "completed"
    assert stored_job.batch_result_artifact is not None
    assert stored_job.items[0].result_artifact is not None
    assert stored_job.items[0].validation_result_artifact is not None
    assert stored_job.items[0].error_report_artifact is not None
    assert payload["batch"] is False
    assert payload["result"]["summary"]["error_report_xlsx"].startswith(f"jobs/{job.job_id}/")


def test_async_job_service_finalizes_batch_column_error_report(monkeypatch, tmp_path) -> None:
    queue = _FakeQueue()
    dependencies = _dependencies(tmp_path, queue)
    first_path = tmp_path / "first.csv"
    second_path = tmp_path / "second.csv"
    first_path.write_text("name,price\nA,1\n", encoding="utf-8")
    second_path.write_text("name,price\nB,2\n", encoding="utf-8")
    datasets = [
        PreparedDataset(display_name="first.csv", path=first_path, source_type="file", response_type="csv"),
        PreparedDataset(display_name="second.csv", path=second_path, source_type="file", response_type="csv"),
    ]

    monkeypatch.setattr(
        job_service,
        "run_pipeline",
        lambda *, request, dependencies=None: PipelineRunResult(
            response={
                "summary": {
                    "dataset_name": request.uploaded_dataset_name or "sample.csv",
                    "column_count": 2,
                    "row_count": 1,
                    "finding_count": 1,
                    "issue_finding_count": 1,
                    "manual_review_finding_count": 0,
                },
                "preview_headers": ["name", "price"],
                "preview_rows": [{"name": "A", "price": "1"}],
                "columns": [{"raw_name": "name"}, {"raw_name": "price"}],
                "findings": [
                    {
                        "column_name": "price",
                        "finding_type": "issue",
                        "category_label": "컬럼 완결성 검증",
                        "row_indexes": [1],
                        "message": "가격 오류",
                        "llm_final_verification": "LLM 확인 결과 오류입니다.",
                        "row_values": {"1": "1"},
                    }
                ],
            },
            validation_rows=list(iter_uploaded_rows(request.uploaded_dataset_csv)),
        ),
    )

    job = job_service.submit_analysis_job(
        prepared_datasets=datasets,
        request=PipelineExecutionRequest(),
        dependencies=dependencies,
    )

    item_results = [
        job_service.process_analysis_job_item(
            job_id=job.job_id,
            item_id=item.item_id,
            dependencies=dependencies,
        )
        for item in job.items
    ]
    payload = job_service.finalize_analysis_job(
        job_id=job.job_id,
        item_results=item_results,
        dependencies=dependencies,
    )

    assert payload["batch"] is True
    assert payload["summary"]["error_report_xlsx"].startswith(f"jobs/{job.job_id}/")
    assert payload["summary"]["column_error_report_xlsx"].startswith(f"jobs/{job.job_id}/")
    assert payload["summary"]["column_error_report_download_path"].startswith("/api/jobs/artifacts/download?key=")
    assert payload["summary"]["column_error_report_xlsx_files"] == [
        payload["summary"]["column_error_report_xlsx"]
    ]
    assert payload["summary"]["column_error_report_download_paths"] == [
        payload["summary"]["column_error_report_download_path"]
    ]


def test_async_job_service_zips_split_batch_column_error_reports(monkeypatch, tmp_path) -> None:
    queue = _FakeQueue()

    def write_split_column_reports(*, entries, output_dir):
        reports_dir = output_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        first_report = reports_dir / "전체_컬럼별_데이터_오류_01.xlsx"
        second_report = reports_dir / "archive_컬럼별_데이터_오류.xlsx"
        first_report.write_bytes(b"first")
        second_report.write_bytes(b"second")
        return [first_report, second_report]

    dependencies = _dependencies(tmp_path, queue, write_column_report=write_split_column_reports)
    first_path = tmp_path / "first.csv"
    second_path = tmp_path / "second.csv"
    first_path.write_text("value\n1\n", encoding="utf-8")
    second_path.write_text("value\n2\n", encoding="utf-8")
    datasets = [
        PreparedDataset(display_name="first.csv", path=first_path, source_type="file", response_type="csv"),
        PreparedDataset(display_name="second.csv", path=second_path, source_type="file", response_type="csv"),
    ]

    monkeypatch.setattr(
        job_service,
        "run_pipeline",
        lambda *, request, dependencies=None: PipelineRunResult(
            response={
                "summary": {
                    "dataset_name": request.uploaded_dataset_name or "sample.csv",
                    "column_count": 1,
                    "row_count": 1,
                    "finding_count": 0,
                    "issue_finding_count": 0,
                    "manual_review_finding_count": 0,
                },
                "preview_headers": ["value"],
                "preview_rows": [{"value": "1"}],
                "columns": [{"raw_name": "value"}],
                "findings": [],
            },
            validation_rows=list(iter_uploaded_rows(request.uploaded_dataset_csv)),
        ),
    )

    job = job_service.submit_analysis_job(
        prepared_datasets=datasets,
        request=PipelineExecutionRequest(),
        dependencies=dependencies,
    )
    item_results = [
        job_service.process_analysis_job_item(
            job_id=job.job_id,
            item_id=item.item_id,
            dependencies=dependencies,
        )
        for item in job.items
    ]
    payload = job_service.finalize_analysis_job(
        job_id=job.job_id,
        item_results=item_results,
        dependencies=dependencies,
    )

    column_report_key = payload["summary"]["column_error_report_xlsx"]
    assert column_report_key.endswith("/전체_컬럼별_데이터_오류.zip")
    assert payload["summary"]["column_error_report_xlsx_files"] == [column_report_key]
    assert payload["summary"]["column_error_report_download_paths"] == [
        payload["summary"]["column_error_report_download_path"]
    ]
    artifact = dependencies.artifact_store().resolve_download(column_report_key)
    assert artifact.content_type == "application/zip"
    with zipfile.ZipFile(artifact.path) as archive:
        assert archive.namelist() == [
            "전체_컬럼별_데이터_오류_01.xlsx",
            "archive_컬럼별_데이터_오류.xlsx",
        ]


def test_public_job_payload_hides_api_key_and_source_artifact(tmp_path) -> None:
    queue = _FakeQueue()
    dependencies = _dependencies(tmp_path, queue)
    dataset_path = tmp_path / "sample.csv"
    dataset_path.write_text("value\n1\n", encoding="utf-8")

    job = job_service.submit_analysis_job(
        prepared_datasets=[
            PreparedDataset(
                display_name="sample.csv",
                path=dataset_path,
                source_type="file",
                response_type="csv",
            )
        ],
        request=PipelineExecutionRequest(openai_api_key="sk-secret"),
        dependencies=dependencies,
    )

    payload = job.public_payload()
    assert "openai_api_key" not in payload["request"]
    assert "source_artifact" not in payload["items"][0]


def test_async_job_service_processes_nested_display_name(monkeypatch, tmp_path) -> None:
    queue = _FakeQueue()
    dependencies = _dependencies(tmp_path, queue)
    dataset_path = tmp_path / "inner.csv"
    dataset_path.write_text("value\n1\n", encoding="utf-8")
    display_name = "archive.zip/inner.csv"

    def fake_run_pipeline(*, request, dependencies=None):
        assert request.uploaded_dataset_name == display_name
        assert request.uploaded_dataset_csv is not None
        materialized_path = Path(request.uploaded_dataset_csv)
        assert materialized_path.exists()
        assert materialized_path.parts[-2:] == ("archive.zip", "inner.csv")
        return PipelineRunResult(
            response={
                "summary": {
                    "dataset_name": display_name,
                    "column_count": 1,
                    "row_count": 1,
                    "finding_count": 0,
                    "issue_finding_count": 0,
                    "manual_review_finding_count": 0,
                },
                "preview_headers": ["value"],
                "preview_rows": [{"value": "1"}],
                "columns": [{"raw_name": "value"}],
                "findings": [],
            },
            validation_rows=[{"value": "1"}],
        )

    monkeypatch.setattr(job_service, "run_pipeline", fake_run_pipeline)

    job = job_service.submit_analysis_job(
        prepared_datasets=[
            PreparedDataset(
                display_name=display_name,
                path=dataset_path,
                source_type="file",
                response_type="csv",
            )
        ],
        request=PipelineExecutionRequest(),
        dependencies=dependencies,
    )

    item_result = job_service.process_analysis_job_item(
        job_id=job.job_id,
        item_id=job.items[0].item_id,
        dependencies=dependencies,
    )

    assert item_result["ok"] is True
