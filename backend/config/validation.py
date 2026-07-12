from __future__ import annotations

from backend.domain.policies.shared.settings import (
    BOOLEAN_ALLOWED_VALUES,
    DATE_PATTERNS,
    FREE_TEXT_COLUMN_NAME_TOKENS,
    MANUAL_REVIEW_RULE_IDS,
    RULE_SEVERITY_BY_RULE_ID,
    SEVERITY_VALUES,
    VALIDATION_CRITERIA,
)

TAG_RULE_MAP = {
    "date": ["date_domain", "time_sequence_consistency", "precedence_accuracy"],
    "phone": ["number_domain"],
    "geo_lat": ["number_domain", "logical_consistency"],
    "geo_lon": ["number_domain", "logical_consistency"],
    "coordinate_pair": ["logical_consistency", "reference_relation"],
    "address": ["required_value", "whitespace_special_characters"],
    "boolean": ["boolean_domain", "logical_consistency"],
    "numeric": ["number_domain"],
    "count": ["quantity_domain", "logical_consistency", "calculation_formula"],
    "enum": ["code_domain", "reference_relation"],
    "identifier": ["number_domain", "duplicate_data", "reference_relation"],
    "name": ["required_value", "garbled_text", "whitespace_special_characters"],
    "width": ["number_domain"],
    "amount": ["amount_domain", "calculation_formula"],
    "quantity": ["quantity_domain", "calculation_formula"],
    "rate": ["rate_domain", "calculation_formula"],
    "code": ["code_domain", "reference_relation"],
    "free_text": [],
}
