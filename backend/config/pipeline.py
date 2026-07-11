from __future__ import annotations

PIPELINE_PROGRESS_STEPS = (
    ("load_reference_data", "입력 형식 확인"),
    ("normalize_columns", "컬럼 구조 정리"),
    ("profile_values", "데이터 프로파일링"),
    ("route_rules", "검증 기준 라우팅"),
    ("semantic_profile", "컬럼 의미 분석"),
    ("validate", "규칙 기반 검증"),
    ("categorical_semantic_validate", "정밀/문맥 검증"),
    ("propose_repairs", "수정 제안 구성"),
    ("final_finding_verify", "오류 재검증"),
    ("verify_results", "최종 결과 정리"),
)
REPORT_PROGRESS_STEP = ("write_reports", "리포트 생성")
PIPELINE_PROGRESS_STEP_LABELS = dict(PIPELINE_PROGRESS_STEPS + (REPORT_PROGRESS_STEP,))
PIPELINE_PROGRESS_ACTIVE_MESSAGE_SUFFIX = " 중"
PIPELINE_PROGRESS_DONE_MESSAGE_SUFFIX = " 완료"
PIPELINE_REQUEST_SOURCE_REQUIRED_ERROR = "uploaded_dataset_csv, dataset_id, or dataset_name 중 하나는 필요합니다."
PIPELINE_REQUEST_META_CSV_REQUIRED_ERROR = "dataset_id 또는 dataset_name으로 분석하려면 meta_csv가 필요합니다."
PIPELINE_REQUEST_BOOL_TYPE_ERROR = "{field_name} must be a bool."
PIPELINE_REQUEST_TEXT_TYPE_ERROR = "{field_name} must be a string."
PIPELINE_DATASET_META_REQUIRED_ERROR = "dataset_meta is required."
PIPELINE_STRING_LIST_TYPE_ERROR = "{field_name} must be a list[str]."
PIPELINE_STRING_LIST_ITEM_TYPE_ERROR = "{field_name} must contain only strings."
PIPELINE_ROW_LIST_TYPE_ERROR = "{field_name} must be a list[dict[str, str]]."
PIPELINE_ROW_LIST_ITEM_TYPE_ERROR = "{field_name} must contain only dict rows."
PIPELINE_DICT_LIST_TYPE_ERROR = "{field_name} must be a list[dict[str, Any]]."
PIPELINE_DICT_LIST_ITEM_TYPE_ERROR = "{field_name} must contain only dictionaries."
PIPELINE_DICT_TYPE_ERROR = "{field_name} must be a dict[str, Any]."
PIPELINE_COLUMNS_TYPE_ERROR = "columns must be a list[ColumnProfile]."
PIPELINE_COLUMNS_ITEM_TYPE_ERROR = "columns must contain only ColumnProfile instances."
PIPELINE_FINDINGS_TYPE_ERROR = "findings must be a list[ValidationFinding]."
PIPELINE_FINDINGS_ITEM_TYPE_ERROR = "findings must contain only ValidationFinding instances."
PIPELINE_AGENT_TRACES_TYPE_ERROR = "agent_traces must be a list[AgentTrace]."
PIPELINE_AGENT_TRACES_ITEM_TYPE_ERROR = "agent_traces must contain only AgentTrace instances."
PIPELINE_DATASET_META_TYPE_ERROR = "dataset_meta must be a DatasetMeta instance."
PIPELINE_UNKNOWN_FIELD_ERROR = "{section} has no field '{field_name}'."

PROFILE_STEP_NAME = "profiler"
VALIDATION_STEP_NAME = "validator"
REPAIR_STEP_NAME = "repair_planner"
VERIFICATION_STEP_NAME = "verifier"
