from __future__ import annotations

from backend.application.agents.base import BaseAgent
from backend.application.dto import (
    PipelineState,
    merge_state_updates,
    pipeline_request,
    pipeline_result,
    require_dataset_meta,
    update_pipeline_data,
    update_pipeline_request,
    update_pipeline_result,
)
from backend.application.ports import DatasetGatewayPort
from backend.domain.entities.models import ColumnProfile
from backend.domain.services.normalization import build_column_profile


class ReferenceLoaderAgent(BaseAgent):
    name = "reference_loader"

    def __init__(self, dataset_gateway: DatasetGatewayPort):
        self.dataset_gateway = dataset_gateway

    def run(self, state: PipelineState) -> PipelineState:
        request = pipeline_request(state)
        traces = list(pipeline_result(state).agent_traces)
        if request.uploaded_dataset_path:
            dataset_meta = self.dataset_gateway.load_uploaded_dataset_meta(
                request.uploaded_dataset_path,
                dataset_name=request.uploaded_dataset_name or request.dataset_name,
            )
        else:
            meta_csv_path = request.meta_csv_path
            if not meta_csv_path:
                raise ValueError("meta_csv_path is required when uploaded_dataset_path is not provided.")
            dataset_meta = self.dataset_gateway.load_dataset_meta(
                meta_csv_path,
                dataset_id=request.dataset_id or None,
                dataset_name=request.dataset_name or None,
            )
        traces.append(
            self.trace(
                action="load_reference_data",
                target=dataset_meta.dataset_id,
                detail=(
                    f"dataset={dataset_meta.dataset_name}, uploaded={bool(request.uploaded_dataset_path)}"
                ),
            )
        )
        return merge_state_updates(
            update_pipeline_request(
                state,
                dataset_id=dataset_meta.dataset_id,
                dataset_name=dataset_meta.dataset_name,
            ),
            update_pipeline_data(state, dataset_meta=dataset_meta),
            update_pipeline_result(state, findings=[], agent_traces=traces),
        )


class SchemaParsingAgent(BaseAgent):
    name = "schema_parser"

    def run(self, state: PipelineState) -> PipelineState:
        dataset_meta = require_dataset_meta(state)
        columns: list[ColumnProfile] = []

        for raw_name in dataset_meta.request_fields:
            columns.append(build_column_profile(raw_name, "request"))
        for raw_name in dataset_meta.response_fields:
            columns.append(build_column_profile(raw_name, "response"))

        traces = list(pipeline_result(state).agent_traces)
        traces.append(
            self.trace(
                action="parse_schema",
                target=dataset_meta.dataset_id,
                detail=f"columns={len(columns)}",
            )
        )
        return merge_state_updates(
            update_pipeline_data(state, columns=columns),
            update_pipeline_result(state, agent_traces=traces),
        )
