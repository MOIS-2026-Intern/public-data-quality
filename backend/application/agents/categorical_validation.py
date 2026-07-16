from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from backend.application.agents.base import BaseAgent
from backend.application.dto import (
    PipelineState,
    merge_state_updates,
    pipeline_data,
    pipeline_request,
    pipeline_result,
    pipeline_rows,
    require_dataset_meta,
    update_pipeline_result,
)
from backend.application.services.categorical_validation.address_detail import run_llm_address_detail_validation
from backend.application.services.categorical_validation.column_validation import (
    index_column_values,
    llm_skip_reason,
    validation_values,
)
from backend.application.services.categorical_validation.llm_findings import apply_llm_categorical_findings
from backend.application.services.categorical_validation.row_context import (
    context_columns,
    context_rows,
    looks_row_context_signal_column,
    row_context_signal_score,
    run_llm_row_context_validation,
)
from backend.application.services.categorical_validation.value_validator import LLMCategoricalValueValidator
from backend.config.categorical import CATEGORICAL_LLM_MAX_WORKERS, ROW_CONTEXT_DEFAULT_LIMIT
from backend.domain.policies.categorical import (
    LocalCategoricalFindingCounts,
    apply_local_categorical_findings,
    looks_free_text_column,
    value_rows,
)


class CategoricalSemanticValidationAgent(BaseAgent):
    name = "categorical_semantic_validator"

    def __init__(self, validator: LLMCategoricalValueValidator | None = None):
        self.validator = validator

    def _llm_debug_detail(self, use_llm: bool) -> tuple[str, str]:
        if not use_llm or self.validator is None:
            return "", ""
        return self.validator.last_error, self.validator.last_response_preview

    @staticmethod
    def _value_rows(rows: list[dict[str, str]], column_name: str, target_value: str) -> list[int]:
        return value_rows(rows, column_name, target_value)

    @staticmethod
    def _context_columns(columns) -> list[dict[str, Any]]:
        return context_columns(columns)

    @staticmethod
    def _looks_row_context_signal_column(header: str) -> bool:
        return looks_row_context_signal_column(header)

    @staticmethod
    def _row_context_signal_score(header: str, count: int) -> int:
        return row_context_signal_score(header, count)

    @staticmethod
    def _context_rows(
        rows: list[dict[str, str]],
        headers: list[str],
        limit: int = ROW_CONTEXT_DEFAULT_LIMIT,
    ) -> list[dict[str, Any]]:
        return context_rows(rows, headers, limit)

    def _run_llm_row_context_validation(self, *, state, findings, traces):
        return run_llm_row_context_validation(
            state=state,
            findings=findings,
            traces=traces,
            validator=self.validator,
            trace=self.trace,
            debug_detail=lambda: self._llm_debug_detail(True),
        )

    def _run_llm_address_detail_validation(self, *, state, findings, traces):
        return run_llm_address_detail_validation(
            state=state,
            findings=findings,
            traces=traces,
            validator=self.validator,
            trace=self.trace,
            debug_detail=lambda: self._llm_debug_detail(True),
        )

    def _run_llm_column_task(
        self,
        *,
        column,
        dataset_meta,
        values: list[dict[str, Any]],
    ) -> dict[str, Any]:
        result = self.validator.validate(
            dataset_name=dataset_meta.dataset_name,
            provider_name=dataset_meta.provider_name,
            column_name=column.raw_name,
            standard_candidate=None,
            semantic_tags=column.semantic_tags,
            format_kind=column.format_kind or ("free_format" if looks_free_text_column(column) else "fixed_format"),
            values=values,
        )
        llm_error, llm_preview = self._llm_debug_detail(True)
        return {
            "column": column,
            "values": values,
            "result": result,
            "llm_error": llm_error,
            "llm_preview": llm_preview,
        }

    def _run_llm_column_tasks(self, tasks: list[dict[str, Any]], dataset_meta) -> list[dict[str, Any]]:
        if not tasks:
            return []
        max_workers = max(1, min(CATEGORICAL_LLM_MAX_WORKERS, len(tasks)))
        if max_workers == 1:
            return [
                self._run_llm_column_task(
                    column=task["column"],
                    dataset_meta=dataset_meta,
                    values=task["values"],
                )
                for task in tasks
            ]

        results: list[dict[str, Any] | None] = [None] * len(tasks)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    self._run_llm_column_task,
                    column=task["column"],
                    dataset_meta=dataset_meta,
                    values=task["values"],
                ): index
                for index, task in enumerate(tasks)
            }
            for future in as_completed(futures):
                results[futures[future]] = future.result()
        return [result for result in results if result is not None]

    def run(self, state: PipelineState) -> PipelineState:
        request = pipeline_request(state)
        data = pipeline_data(state)
        result = pipeline_result(state)
        traces = list(result.agent_traces)
        findings = list(result.findings)
        rows = pipeline_rows(state)
        use_llm = (
            request.use_llm_agents
            and self.validator is not None
            and self.validator.enabled
        )

        if not use_llm:
            traces.append(
                self.trace(
                    action="categorical_semantic_validate",
                    detail="llm_disabled; running_local_text_detectors_only",
                )
            )

        dataset_meta = require_dataset_meta(state)
        llm_tasks: list[dict[str, Any]] = []
        for column in data.columns:
            indexed_values = index_column_values(rows, column.raw_name)
            counter = indexed_values.counter
            local_counts = apply_local_categorical_findings(
                column=column,
                rows=rows,
                counter=counter,
                findings=findings,
                value_row_indexes=indexed_values.row_indexes,
            )
            if not use_llm:
                self._trace_local_skip(traces, column, local_counts, "llm_disabled")
                continue

            skip_reason = llm_skip_reason(column, counter)
            if skip_reason == "empty_counter":
                continue
            if skip_reason is not None:
                self._trace_local_skip(traces, column, local_counts, skip_reason)
                continue
            llm_tasks.append({"column": column, "values": validation_values(counter)})

        for item in self._run_llm_column_tasks(llm_tasks, dataset_meta):
            column = item["column"]
            values = item["values"]
            result = item["result"]
            if not result:
                traces.append(
                    self.trace(
                        action="categorical_semantic_validate",
                        target=column.raw_name,
                        detail=(f"llm_no_result,error={item['llm_error']},preview={item['llm_preview']}"),
                    )
                )
                continue
            generated = apply_llm_categorical_findings(
                column=column,
                rows=rows,
                result=result,
                findings=findings,
            )
            traces.append(
                self.trace(
                    action="categorical_semantic_validate",
                    target=column.raw_name,
                    detail=(
                        f"values={len(values)}, findings={generated}, "
                        f"domain={result.get('domain_label', '')}, "
                        f"overall_confidence={float(result.get('overall_confidence') or 0.0):.2f}, "
                        f"model={result.get('_llm_model', '')}, "
                        f"stage={result.get('_llm_stage', '')}, "
                        f"escalated={bool(result.get('_llm_escalated'))}"
                    ),
                )
            )

        if use_llm:
            findings, traces = self._run_llm_address_detail_validation(state=state, findings=findings, traces=traces)
            findings, traces = self._run_llm_row_context_validation(state=state, findings=findings, traces=traces)

        return update_pipeline_result(state, findings=findings, agent_traces=traces)

    def _trace_local_skip(
        self,
        traces: list,
        column,
        local_counts: LocalCategoricalFindingCounts,
        skipped_reason: str,
    ) -> None:
        if not local_counts.has_findings:
            return
        traces.append(
            self.trace(
                action="categorical_semantic_validate",
                target=column.raw_name,
                detail=local_counts.trace_detail(skipped_reason),
            )
        )
