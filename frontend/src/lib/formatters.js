export function formatPercent(value) {
  if (value === null || value === undefined) return "-";
  return `${Math.round(value * 100)}%`;
}

export function formatConfidence(value) {
  if (value === null || value === undefined) return "-";
  return `${Math.round(value * 100)}%`;
}

export function formatTopValues(topValues) {
  if (!topValues?.length) return "-";
  return topValues.map(([value, count]) => `${value} (${count})`).join(", ");
}

export function formatCriterionName(value) {
  const labels = {
    required_value: "필수값 존재 여부",
    garbled_text: "깨진 글자 검증",
    whitespace_special_characters: "공백/특수문자 검증",
    whitespace_issue: "공백 이상 검증",
    special_character_issue: "불필요 특수문자 검증",
    duplicate_data: "중복 데이터 검증",
    date_domain: "날짜 형식 유효성",
    number_domain: "번호/수치 형식 유효성",
    boolean_domain: "여부값 유효성",
    code_domain: "코드값 유효성",
    amount_domain: "금액값 유효성",
    quantity_domain: "수량값 유효성",
    rate_domain: "비율값 유효성",
    time_sequence_consistency: "시간 순서 정합성",
    precedence_accuracy: "선후 관계 정확성",
    logical_consistency: "논리 일관성",
    calculation_formula: "계산식 정합성",
    reference_relation: "참조 관계 정합성",
    categorical_semantic_domain: "범주 의미 일관성",
  };
  return labels[value] || value || "-";
}

export function formatRuleId(value) {
  const labels = {
    manual_review_required: "수동 검토 필요",
    required_value: "필수값 누락 검증",
    garbled_text: "깨진 글자 검증",
    whitespace_special_characters: "공백/특수문자 검증",
    whitespace_issue: "공백 이상 검증",
    special_character_issue: "불필요 특수문자 검증",
    duplicate_data: "중복 데이터 검증",
    date_domain: "날짜 도메인 검증",
    date_format_inconsistent: "날짜 형식 혼용",
    number_domain: "번호/수치 도메인 검증",
    boolean_domain: "여부 도메인 검증",
    code_domain: "코드 도메인 검증",
    amount_domain: "금액 도메인 검증",
    quantity_domain: "수량 도메인 검증",
    rate_domain: "비율 도메인 검증",
    time_sequence_consistency: "시간 순서 검증",
    precedence_accuracy: "선후 관계 검증",
    logical_consistency: "논리 일관성 검증",
    calculation_formula: "계산식 검증",
    reference_relation: "참조 관계 검증",
    categorical_value_normalization: "범주값 표준화 필요",
    categorical_value_truncated: "범주값 잘림 의심",
    categorical_value_out_of_domain: "도메인 외 값 의심",
    categorical_value_manual_review: "범주값 수동 검토",
  };
  return labels[value] || value || "-";
}

export function formatSeverity(value) {
  const labels = {
    error: "오류",
    warning: "경고",
    info: "안내",
  };
  return labels[value] || value || "-";
}

export function formatFindingType(finding) {
  return finding.display_label || (finding.finding_type === "manual_review" ? "수동 검토 필요" : "오류/이상 탐지");
}

export function formatRelatedColumns(finding) {
  if (finding.related_columns?.length) {
    return finding.related_columns.join(", ");
  }
  return finding.column_name || "-";
}

export function buildColumnSummary(column) {
  return column.semantic_profile_description || `${column.raw_name} 컬럼의 의미 설명이 아직 생성되지 않았습니다.`;
}
