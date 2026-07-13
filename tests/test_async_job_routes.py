from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.adapters.web import api_routes
from backend.adapters.web.app import create_app
from backend.application.dto import AnalysisJob, PipelineExecutionRequest


def _job() -> AnalysisJob:
    return AnalysisJob(
        job_id="job-1",
        status="queued",
        request=PipelineExecutionRequest(openai_api_key="sk-secret"),
        total_items=1,
    )


def test_create_analysis_job_route_returns_sanitized_job(monkeypatch) -> None:
    monkeypatch.delenv("VERCEL", raising=False)
    app = create_app()
    client = app.test_client()

    monkeypatch.setattr(api_routes, "_request_payload", lambda: {})
    monkeypatch.setattr(api_routes, "_request_options", lambda payload: PipelineExecutionRequest(openai_api_key="sk-secret"))
    monkeypatch.setattr(api_routes, "_prepare_request_datasets", lambda payload, tmp_dir, *, dependencies=None: [])
    monkeypatch.setattr(api_routes, "submit_analysis_job", lambda **kwargs: _job())

    response = client.post("/api/jobs")

    assert response.status_code == 202
    payload = response.get_json()
    assert payload["job"]["job_id"] == "job-1"
    assert "openai_api_key" not in payload["job"]["request"]


def test_analyze_route_can_submit_async_job(monkeypatch) -> None:
    monkeypatch.delenv("VERCEL", raising=False)
    app = create_app()
    client = app.test_client()

    monkeypatch.setattr(api_routes, "_request_payload", lambda: {})
    monkeypatch.setattr(api_routes, "_request_options", lambda payload: PipelineExecutionRequest())
    monkeypatch.setattr(api_routes, "_prepare_request_datasets", lambda payload, tmp_dir, *, dependencies=None: [])
    monkeypatch.setattr(api_routes, "submit_analysis_job", lambda **kwargs: _job())

    response = client.post("/api/analyze")

    assert response.status_code == 202
    assert response.get_json()["job"]["job_id"] == "job-1"


def test_analyze_route_runs_sync_on_vercel_even_when_async_requested(monkeypatch) -> None:
    monkeypatch.setenv("VERCEL", "1")
    app = create_app()
    client = app.test_client()

    monkeypatch.setattr(api_routes, "_request_payload", lambda: {"execution_mode": "async"})
    monkeypatch.setattr(api_routes, "_request_options", lambda payload: PipelineExecutionRequest())
    monkeypatch.setattr(api_routes, "_prepare_request_datasets", lambda payload, tmp_dir, *, dependencies=None: [])
    monkeypatch.setattr(
        api_routes,
        "analyze_prepared_datasets",
        lambda **kwargs: ({"batch": False, "result": {"summary": {"dataset_name": "sample"}}}, 200),
    )

    response = client.post("/api/analyze")

    assert response.status_code == 200
    assert response.get_json()["result"]["summary"]["dataset_name"] == "sample"


def test_create_analysis_job_route_is_disabled_on_vercel(monkeypatch) -> None:
    monkeypatch.setenv("VERCEL", "1")
    app = create_app()
    client = app.test_client()

    response = client.post("/api/jobs")

    assert response.status_code == 400
    assert response.get_json()["error"] == "비동기 분석은 로컬 Celery 실행 환경에서만 지원됩니다."


def test_analysis_job_result_route_returns_accepted_until_complete(monkeypatch) -> None:
    app = create_app()
    client = app.test_client()

    monkeypatch.setattr(api_routes, "get_analysis_job_result", lambda job_id, *, dependencies=None: (None, _job()))

    response = client.get("/api/jobs/job-1/result")

    assert response.status_code == 202
    assert response.get_json()["job"]["status"] == "queued"
