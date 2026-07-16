from __future__ import annotations

FINAL_VERIFICATION_CONFIDENCE_THRESHOLD = 0.90
MAX_FINAL_VERIFICATION_CANDIDATES = 30
MAX_FINAL_VERIFICATION_ROWS_PER_FINDING = 5
MAX_FINAL_VERIFICATION_VALUE_LENGTH = 80
VERIFICATION_STRONG_LLM_CONFIDENCE_THRESHOLD = 0.90
DETERMINISTIC_ISSUE_RULE_IDS = {
    "garbled_text",
    "whitespace_issue",
    "special_character_issue",
    "required_value",
    "duplicate_data",
    "date_domain",
    "number_domain",
    "boolean_domain",
    "amount_domain",
    "quantity_domain",
    "rate_domain",
    "time_sequence_consistency",
    "precedence_accuracy",
    "logical_consistency",
    "calculation_formula",
    "reference_relation",
    "address_region_prefix_mismatch",
}
STRONG_LLM_ISSUE_RULE_IDS = {
    "boolean_domain",
    "categorical_value_out_of_domain",
    "categorical_value_truncated",
    "date_domain",
    "logical_consistency",
}
DETERMINISTIC_TRUNCATION_DETECTORS = {
    "detector:truncated_address",
}
