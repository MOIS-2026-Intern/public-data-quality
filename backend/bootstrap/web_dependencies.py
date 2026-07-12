from __future__ import annotations

import os
import tempfile
from functools import lru_cache
from pathlib import Path

from backend.adapters.web.dependencies import WebAdapterDependencies
from backend.application.use_cases import PipelineAnalysisUseCase
from backend.config.reporting import (
    VALIDATION_OUTPUT_BASE_DIR_NAME,
    VALIDATION_OUTPUT_DIR_ENV_VAR,
    VALIDATION_OUTPUT_DIR_NAME,
)
from backend.infrastructure.io.sources import prepare_api_datasets, prepare_saved_dataset, prepare_url_datasets
from backend.infrastructure.io.url_lists import load_url_list
from backend.infrastructure.orchestration.factory import LangGraphPipelineExecutorFactory
from backend.infrastructure.reporting.artifacts import public_download_name
from backend.infrastructure.reporting.pipeline_outputs import attach_report_paths
from backend.infrastructure.reporting.workbooks import write_batch_error_report


@lru_cache(maxsize=1)
def pipeline_analysis_use_case() -> PipelineAnalysisUseCase:
    return PipelineAnalysisUseCase(executor_factory=LangGraphPipelineExecutorFactory())


def validation_output_dir(base_dir: Path | None = None) -> Path:
    if base_dir is not None:
        base = Path(base_dir)
    else:
        configured_dir = os.getenv(VALIDATION_OUTPUT_DIR_ENV_VAR)
        if configured_dir:
            return Path(configured_dir)
        if os.getenv("VERCEL"):
            base = Path("/tmp") / VALIDATION_OUTPUT_BASE_DIR_NAME
        else:
            base = Path(tempfile.gettempdir()) / VALIDATION_OUTPUT_BASE_DIR_NAME
    return base / VALIDATION_OUTPUT_DIR_NAME


def build_web_dependencies() -> WebAdapterDependencies:
    return WebAdapterDependencies(
        pipeline_analysis_use_case=pipeline_analysis_use_case,
        validation_output_dir=validation_output_dir,
        attach_report_paths=attach_report_paths,
        write_batch_error_report=write_batch_error_report,
        public_download_name=public_download_name,
        prepare_saved_dataset=prepare_saved_dataset,
        prepare_url_datasets=prepare_url_datasets,
        prepare_api_datasets=prepare_api_datasets,
        load_url_list=load_url_list,
    )
