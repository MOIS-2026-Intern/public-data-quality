from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.adapters.web import api_routes
from backend.adapters.web.app import create_app
from backend.infrastructure.io.sources import PreparedDataset


def test_create_app_uses_repo_frontend_dist_directory() -> None:
    app = create_app()
    expected = Path(__file__).resolve().parents[1] / "frontend" / "dist"

    assert Path(app.static_folder) == expected


def test_analyze_route_returns_single_result_envelope(monkeypatch, tmp_path) -> None:
    app = create_app()
    client = app.test_client()
    dataset = PreparedDataset(
        display_name="sample.csv",
        path=tmp_path / "sample.csv",
        source_type="file",
        response_type="csv",
    )

    monkeypatch.setattr(api_routes, "_request_payload", lambda: {})
    monkeypatch.setattr(api_routes, "_request_options", lambda payload: {})
    monkeypatch.setattr(api_routes, "_prepare_request_datasets", lambda payload, tmp_dir: [dataset])
    monkeypatch.setattr(
        api_routes,
        "analyze_prepared_datasets",
        lambda **kwargs: (
            {
                "batch": False,
                "summary": {"dataset_name": "sample"},
                "results": [{"ok": True, "filename": "sample.csv", "result": {"summary": {"dataset_name": "sample"}}}],
                "result": {"summary": {"dataset_name": "sample"}},
            },
            200,
        ),
    )

    response = client.post("/api/analyze")

    assert response.status_code == 200
    assert response.get_json()["batch"] is False
    assert response.get_json()["result"]["summary"]["dataset_name"] == "sample"
