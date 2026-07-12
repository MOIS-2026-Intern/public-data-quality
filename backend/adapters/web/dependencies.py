from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

from backend.application.dto import PreparedDataset
from backend.application.use_cases import PipelineAnalysisUseCase


@dataclass(frozen=True)
class WebAdapterDependencies:
    pipeline_analysis_use_case: Callable[[], PipelineAnalysisUseCase]
    validation_output_dir: Callable[[Path | None], Path]
    attach_report_paths: Callable[..., dict[str, Any]]
    write_batch_error_report: Callable[..., Path]
    public_download_name: Callable[..., str]
    prepare_saved_dataset: Callable[..., list[PreparedDataset]]
    prepare_url_datasets: Callable[..., list[PreparedDataset]]
    prepare_api_datasets: Callable[..., list[PreparedDataset]]
    load_url_list: Callable[..., list[str]]


@lru_cache(maxsize=1)
def default_web_dependencies() -> WebAdapterDependencies:
    from backend.bootstrap.web_dependencies import build_web_dependencies

    return build_web_dependencies()
