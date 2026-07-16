from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import backend.adapters.web.pipeline_service as pipeline_service
from backend.adapters.web.dependencies import WebAdapterDependencies
from backend.application.dto import PipelineExecutionRequest


class _FakeUseCase:
    def __init__(self) -> None:
        self.run_request = None
        self.stream_request = None

    def run(self, request):
        self.run_request = request
        return {"sentinel": "run"}

    def stream(self, request):
        self.stream_request = request
        yield {"kind": "result", "result": {"sentinel": "stream"}}


def _dependencies(use_case: _FakeUseCase) -> WebAdapterDependencies:
    return WebAdapterDependencies(
        pipeline_analysis_use_case=lambda: use_case,
        validation_output_dir=lambda base_dir=None: Path("/tmp"),
        attach_report_paths=lambda **kwargs: kwargs["response"],
        write_batch_error_report=lambda **kwargs: Path("/tmp/report.xlsx"),
        write_batch_column_error_report=lambda **kwargs: Path("/tmp/column_report.xlsx"),
        public_download_name=lambda filename, default_suffix=".xlsx": filename,
        prepare_saved_dataset=lambda *args, **kwargs: [],
        prepare_url_datasets=lambda *args, **kwargs: [],
        prepare_api_datasets=lambda *args, **kwargs: [],
        load_url_list=lambda *args, **kwargs: [],
    )


def test_run_pipeline_forwards_openai_api_key(monkeypatch) -> None:
    use_case = _FakeUseCase()
    monkeypatch.setattr(pipeline_service, "_pipeline_run_result", lambda result: result)

    result = pipeline_service.run_pipeline(
        request=PipelineExecutionRequest(
            uploaded_dataset_csv="uploaded.csv",
            use_llm_agents=True,
            openai_api_key="sk-test",
        ),
        dependencies=_dependencies(use_case),
    )

    assert result == {"sentinel": "run"}
    assert use_case.run_request.openai_api_key == "sk-test"


def test_stream_pipeline_forwards_openai_api_key(monkeypatch) -> None:
    use_case = _FakeUseCase()
    monkeypatch.setattr(pipeline_service, "_pipeline_run_result", lambda result: result)

    events = list(
        pipeline_service.stream_pipeline(
            request=PipelineExecutionRequest(
                uploaded_dataset_csv="uploaded.csv",
                use_llm_agents=True,
                openai_api_key="sk-test",
            ),
            dependencies=_dependencies(use_case),
        )
    )

    assert use_case.stream_request.openai_api_key == "sk-test"
    assert events == [{"kind": "result", "result": {"sentinel": "stream"}}]
