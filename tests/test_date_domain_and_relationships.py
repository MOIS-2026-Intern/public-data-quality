from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.domain.entities.models import ColumnProfile, DatasetMeta
from backend.domain.policies.columns.rules import validate_column
from backend.domain.policies.relationships import validate_dataset_relationships
from backend.domain.policies.relationships.calculation_rules import validate_calculation_relationships


def _dataset_meta() -> DatasetMeta:
    return DatasetMeta(dataset_id="dataset", dataset_name="dataset")


def test_date_domain_allows_day_of_month_distribution() -> None:
    values = ["27", "26", "21", "17", "18", "27", "3", "10", "23", "5"]
    column = ColumnProfile(
        raw_name="종료일",
        normalized_name="종료일",
        source="response",
        semantic_tags=["date"],
        assigned_rules=["date_domain"],
        inferred_primitive_type="text",
        non_empty_count=len(values),
        distinct_count=len(set(values)),
        sample_values=values,
        top_values=[(value, 1) for value in values],
        date_parse_ratio=0.0,
    )
    rows = [{"종료일": value} for value in values]

    findings = validate_column(column, _dataset_meta(), rows)

    assert [finding.rule_id for finding in findings] == []


def test_required_value_allows_blank_sigungu_for_sejong() -> None:
    rows = [
        {"시도명": "세종특별자치시", "시군구명": ""},
        {"시도명": "서울특별시", "시군구명": "강남구"},
    ]
    column = ColumnProfile(
        raw_name="시군구명",
        normalized_name="시군구명",
        source="response",
        semantic_tags=[],
        assigned_rules=["required_value"],
        inferred_primitive_type="text",
        non_empty_count=1,
        null_count=1,
        null_ratio=0.5,
        distinct_count=1,
        sample_values=["강남구"],
        top_values=[("강남구", 1)],
    )

    findings = validate_column(column, _dataset_meta(), rows)

    assert [finding.rule_id for finding in findings] == []


def test_required_value_allows_blank_sigun_for_sejong() -> None:
    rows = [
        {"시도": "세종특별자치시", "시군": ""},
        {"시도": "서울특별시", "시군": "강남구"},
    ]
    column = ColumnProfile(
        raw_name="시군",
        normalized_name="시군",
        source="response",
        semantic_tags=[],
        assigned_rules=["required_value"],
        inferred_primitive_type="text",
        non_empty_count=1,
        null_count=1,
        null_ratio=0.5,
        distinct_count=1,
        sample_values=["강남구"],
        top_values=[("강남구", 1)],
    )

    findings = validate_column(column, _dataset_meta(), rows)

    assert [finding.rule_id for finding in findings] == []


def test_required_value_skips_non_sejong_blank_sigungu_when_null_ratio_is_high() -> None:
    rows = [{"시도명": "세종특별자치시", "시군구명": ""}]
    rows.extend(
        {"시도명": "서울특별시", "시군구명": f"행정구역{i}"}
        for i in range(1, 20)
    )
    rows.append({"시도명": "부산광역시", "시군구명": ""})

    column = ColumnProfile(
        raw_name="시군구명",
        normalized_name="시군구명",
        source="response",
        semantic_tags=[],
        assigned_rules=["required_value"],
        inferred_primitive_type="text",
        non_empty_count=19,
        null_count=2,
        null_ratio=round(2 / 21, 4),
        distinct_count=19,
        sample_values=["행정구역1", "행정구역2", "행정구역3"],
        top_values=[("행정구역1", 1), ("행정구역2", 1), ("행정구역3", 1)],
    )

    findings = validate_column(column, _dataset_meta(), rows)

    assert findings == []


def test_required_value_skips_when_null_ratio_is_high() -> None:
    rows = [{"기관명": ""} for _ in range(6)]
    rows.extend({"기관명": f"기관{i}"} for i in range(1, 15))

    column = ColumnProfile(
        raw_name="기관명",
        normalized_name="기관명",
        source="response",
        semantic_tags=["name"],
        assigned_rules=["required_value"],
        inferred_primitive_type="text",
        non_empty_count=14,
        null_count=6,
        null_ratio=0.3,
        distinct_count=14,
        sample_values=["기관1", "기관2", "기관3"],
        top_values=[("기관1", 1), ("기관2", 1), ("기관3", 1)],
    )

    findings = validate_column(column, _dataset_meta(), rows)

    assert findings == []


def test_required_value_reports_when_null_ratio_is_below_two_percent() -> None:
    rows = [{"연락처": ""}]
    rows.extend({"연락처": f"02-0000-{i:04d}"} for i in range(1, 100))

    column = ColumnProfile(
        raw_name="연락처",
        normalized_name="연락처",
        source="response",
        semantic_tags=["name"],
        assigned_rules=["required_value"],
        inferred_primitive_type="text",
        non_empty_count=99,
        null_count=1,
        null_ratio=0.01,
        distinct_count=99,
        sample_values=["02-0000-0001", "02-0000-0002", "02-0000-0003"],
        top_values=[("02-0000-0001", 1), ("02-0000-0002", 1), ("02-0000-0003", 1)],
    )

    findings = validate_column(column, _dataset_meta(), rows)

    assert len(findings) == 1
    assert findings[0].rule_id == "required_value"
    assert findings[0].row_indexes == [1]
    assert findings[0].message == "필수성이 높은 컬럼으로 추정되나 결측값 1건이 존재합니다."
    assert "null_ratio:0.01" in findings[0].evidence


def test_required_value_skips_when_null_ratio_is_exactly_two_percent() -> None:
    rows = [{"연락처": ""}]
    rows.extend({"연락처": f"02-0000-{i:04d}"} for i in range(1, 50))

    column = ColumnProfile(
        raw_name="연락처",
        normalized_name="연락처",
        source="response",
        semantic_tags=["name"],
        assigned_rules=["required_value"],
        inferred_primitive_type="text",
        non_empty_count=49,
        null_count=1,
        null_ratio=0.02,
        distinct_count=49,
        sample_values=["02-0000-0001", "02-0000-0002", "02-0000-0003"],
        top_values=[("02-0000-0001", 1), ("02-0000-0002", 1), ("02-0000-0003", 1)],
    )

    findings = validate_column(column, _dataset_meta(), rows)

    assert findings == []


def test_calculation_formula_relationships_are_disabled() -> None:
    columns = [
        ColumnProfile(
            raw_name="계획인원",
            normalized_name="계획인원",
            source="response",
            semantic_tags=["count"],
            assigned_rules=["calculation_formula"],
            inferred_primitive_type="numeric",
            non_empty_count=2,
            distinct_count=2,
            sample_values=["10", "20"],
        ),
        ColumnProfile(
            raw_name="수료인원",
            normalized_name="수료인원",
            source="response",
            semantic_tags=["count"],
            assigned_rules=["calculation_formula"],
            inferred_primitive_type="numeric",
            non_empty_count=2,
            distinct_count=2,
            sample_values=["5", "10"],
        ),
        ColumnProfile(
            raw_name="기수",
            normalized_name="기수",
            source="response",
            semantic_tags=["count"],
            assigned_rules=["calculation_formula"],
            inferred_primitive_type="numeric",
            non_empty_count=2,
            distinct_count=2,
            sample_values=["1", "2"],
        ),
    ]
    rows = [
        {"계획인원": "10", "수료인원": "5", "기수": "1"},
        {"계획인원": "20", "수료인원": "10", "기수": "2"},
    ]
    candidates = [
        {
            "rule_id": "calculation_formula",
            "columns": ["계획인원", "수료인원", "기수"],
            "confidence": 0.99,
        }
    ]

    findings = validate_dataset_relationships(columns, rows, candidates)

    assert [finding.rule_id for finding in findings] == []


def test_calculation_formula_supports_sum_of_multiple_component_columns() -> None:
    columns = [
        ColumnProfile(
            raw_name="지급건수합계(건)",
            normalized_name="지급건수합계(건)",
            source="response",
            semantic_tags=["count"],
            assigned_rules=["calculation_formula"],
            inferred_primitive_type="numeric",
            non_empty_count=2,
            distinct_count=2,
            sample_values=["19", "20"],
        ),
        ColumnProfile(
            raw_name="주택지급건수(건)",
            normalized_name="주택지급건수(건)",
            source="response",
            semantic_tags=["count"],
            assigned_rules=["calculation_formula"],
            inferred_primitive_type="numeric",
            non_empty_count=2,
            distinct_count=1,
            sample_values=["6"],
        ),
        ColumnProfile(
            raw_name="온실지급건수(건)",
            normalized_name="온실지급건수(건)",
            source="response",
            semantic_tags=["count"],
            assigned_rules=["calculation_formula"],
            inferred_primitive_type="numeric",
            non_empty_count=2,
            distinct_count=1,
            sample_values=["8"],
        ),
        ColumnProfile(
            raw_name="소상공인 지급건수(건)",
            normalized_name="소상공인 지급건수(건)",
            source="response",
            semantic_tags=["count"],
            assigned_rules=["calculation_formula"],
            inferred_primitive_type="numeric",
            non_empty_count=2,
            distinct_count=1,
            sample_values=["5"],
        ),
    ]
    rows = [
        {
            "지급건수합계(건)": "19",
            "주택지급건수(건)": "6",
            "온실지급건수(건)": "8",
            "소상공인 지급건수(건)": "5",
        },
        {
            "지급건수합계(건)": "20",
            "주택지급건수(건)": "6",
            "온실지급건수(건)": "8",
            "소상공인 지급건수(건)": "5",
        },
        {
            "지급건수합계(건)": "20",
            "주택지급건수(건)": "6",
            "온실지급건수(건)": "8",
            "소상공인 지급건수(건)": "5",
        },
    ]
    candidates = [
        {
            "rule_id": "calculation_formula",
            "columns": [
                "지급건수합계(건)",
                "주택지급건수(건)",
                "온실지급건수(건)",
                "소상공인 지급건수(건)",
            ],
            "confidence": 0.99,
        }
    ]

    findings = validate_calculation_relationships(columns, rows, candidates)

    assert len(findings) == 1
    assert findings[0].row_indexes == [2, 3]
    assert "주택지급건수(건) + 온실지급건수(건) + 소상공인 지급건수(건)" in findings[0].message


def test_reference_relationship_skips_plain_sigungu_to_sigungu_name_mapping() -> None:
    columns = [
        ColumnProfile(
            raw_name="시군구",
            normalized_name="시군구",
            source="response",
            semantic_tags=["code"],
            assigned_rules=["reference_relation"],
            inferred_primitive_type="text",
            non_empty_count=2,
            distinct_count=1,
            sample_values=["380"],
            top_values=[("380", 2)],
        ),
        ColumnProfile(
            raw_name="시군구명",
            normalized_name="시군구명",
            source="response",
            semantic_tags=["name"],
            assigned_rules=["reference_relation"],
            inferred_primitive_type="text",
            non_empty_count=2,
            distinct_count=2,
            sample_values=["사하구", "은평구"],
            top_values=[("사하구", 1), ("은평구", 1)],
        ),
    ]
    rows = [
        {"시군구": "380", "시군구명": "사하구"},
        {"시군구": "380", "시군구명": "은평구"},
    ]
    candidates = [
        {
            "rule_id": "reference_relation",
            "columns": ["시군구", "시군구명"],
            "confidence": 0.99,
        }
    ]

    findings = validate_dataset_relationships(columns, rows, candidates)

    assert [finding.rule_id for finding in findings] == []


def test_reference_relationship_skips_plain_eupmyeondong_to_name_mapping() -> None:
    columns = [
        ColumnProfile(
            raw_name="읍면동",
            normalized_name="읍면동",
            source="response",
            semantic_tags=["code"],
            assigned_rules=["reference_relation"],
            inferred_primitive_type="text",
            non_empty_count=2,
            distinct_count=1,
            sample_values=["602"],
            top_values=[("602", 2)],
        ),
        ColumnProfile(
            raw_name="읍면동명",
            normalized_name="읍면동명",
            source="response",
            semantic_tags=["name"],
            assigned_rules=["reference_relation"],
            inferred_primitive_type="text",
            non_empty_count=2,
            distinct_count=2,
            sample_values=["상계동", "중계동"],
            top_values=[("상계동", 1), ("중계동", 1)],
        ),
    ]
    rows = [
        {"읍면동": "602", "읍면동명": "상계동"},
        {"읍면동": "602", "읍면동명": "중계동"},
    ]
    candidates = [
        {
            "rule_id": "reference_relation",
            "columns": ["읍면동", "읍면동명"],
            "confidence": 0.99,
        }
    ]

    findings = validate_dataset_relationships(columns, rows, candidates)

    assert [finding.rule_id for finding in findings] == []


def test_reference_relationship_skips_plain_beopjeongdong_to_name_mapping() -> None:
    columns = [
        ColumnProfile(
            raw_name="법정동",
            normalized_name="법정동",
            source="response",
            semantic_tags=["code"],
            assigned_rules=["reference_relation"],
            inferred_primitive_type="text",
            non_empty_count=2,
            distinct_count=1,
            sample_values=["110"],
            top_values=[("110", 2)],
        ),
        ColumnProfile(
            raw_name="법정동명",
            normalized_name="법정동명",
            source="response",
            semantic_tags=["name"],
            assigned_rules=["reference_relation"],
            inferred_primitive_type="text",
            non_empty_count=2,
            distinct_count=2,
            sample_values=["청운동", "효자동"],
            top_values=[("청운동", 1), ("효자동", 1)],
        ),
    ]
    rows = [
        {"법정동": "110", "법정동명": "청운동"},
        {"법정동": "110", "법정동명": "효자동"},
    ]
    candidates = [
        {
            "rule_id": "reference_relation",
            "columns": ["법정동", "법정동명"],
            "confidence": 0.99,
        }
    ]

    findings = validate_dataset_relationships(columns, rows, candidates)

    assert [finding.rule_id for finding in findings] == []


def test_reference_relationship_skips_local_admin_code_name_variants() -> None:
    columns = [
        ColumnProfile(
            raw_name="시군구코드",
            normalized_name="시군구코드",
            source="response",
            semantic_tags=["code"],
            assigned_rules=["reference_relation"],
            inferred_primitive_type="text",
            non_empty_count=2,
            distinct_count=1,
            sample_values=["380"],
            top_values=[("380", 2)],
        ),
        ColumnProfile(
            raw_name="시군구명칭",
            normalized_name="시군구명칭",
            source="response",
            semantic_tags=["name"],
            assigned_rules=["reference_relation"],
            inferred_primitive_type="text",
            non_empty_count=2,
            distinct_count=2,
            sample_values=["사하구", "은평구"],
            top_values=[("사하구", 1), ("은평구", 1)],
        ),
    ]
    rows = [
        {"시군구코드": "380", "시군구명칭": "사하구"},
        {"시군구코드": "380", "시군구명칭": "은평구"},
    ]
    candidates = [
        {
            "rule_id": "reference_relation",
            "columns": ["시군구코드", "시군구명칭"],
            "confidence": 0.99,
        }
    ]

    findings = validate_dataset_relationships(columns, rows, candidates)

    assert [finding.rule_id for finding in findings] == []


def test_reference_relationship_keeps_long_official_local_admin_code() -> None:
    columns = [
        ColumnProfile(
            raw_name="법정동코드",
            normalized_name="법정동코드",
            source="response",
            semantic_tags=["code"],
            assigned_rules=["reference_relation"],
            inferred_primitive_type="text",
            non_empty_count=2,
            distinct_count=1,
            sample_values=["1111010100"],
            top_values=[("1111010100", 2)],
        ),
        ColumnProfile(
            raw_name="법정동명",
            normalized_name="법정동명",
            source="response",
            semantic_tags=["name"],
            assigned_rules=["reference_relation"],
            inferred_primitive_type="text",
            non_empty_count=2,
            distinct_count=2,
            sample_values=["청운동", "효자동"],
            top_values=[("청운동", 1), ("효자동", 1)],
        ),
    ]
    rows = [
        {"법정동코드": "1111010100", "법정동명": "청운동"},
        {"법정동코드": "1111010100", "법정동명": "효자동"},
    ]
    candidates = [
        {
            "rule_id": "reference_relation",
            "columns": ["법정동코드", "법정동명"],
            "confidence": 0.99,
        }
    ]

    findings = validate_dataset_relationships(columns, rows, candidates)

    assert [finding.rule_id for finding in findings] == ["reference_relation"]


def test_reference_relationship_ignores_whitespace_only_name_differences() -> None:
    columns = [
        ColumnProfile(
            raw_name="기관코드",
            normalized_name="기관코드",
            source="response",
            semantic_tags=["code"],
            assigned_rules=["reference_relation"],
            inferred_primitive_type="text",
            non_empty_count=2,
            distinct_count=1,
            sample_values=["A-01"],
            top_values=[("A-01", 2)],
        ),
        ColumnProfile(
            raw_name="기관명",
            normalized_name="기관명",
            source="response",
            semantic_tags=["name"],
            assigned_rules=["reference_relation"],
            inferred_primitive_type="text",
            non_empty_count=2,
            distinct_count=2,
            sample_values=["서울 센터", "서울센터"],
            top_values=[("서울 센터", 1), ("서울센터", 1)],
        ),
    ]
    rows = [
        {"기관코드": "A-01", "기관명": "서울 센터"},
        {"기관코드": "A-01", "기관명": "서울센터"},
    ]
    candidates = [
        {
            "rule_id": "reference_relation",
            "columns": ["기관코드", "기관명"],
            "confidence": 0.99,
        }
    ]

    findings = validate_dataset_relationships(columns, rows, candidates)

    assert [finding.rule_id for finding in findings] == []


def test_reference_relationship_ignores_three_column_candidates() -> None:
    columns = [
        ColumnProfile(
            raw_name="기관코드",
            normalized_name="기관코드",
            source="response",
            semantic_tags=["code"],
            assigned_rules=["reference_relation"],
            inferred_primitive_type="text",
            non_empty_count=2,
            distinct_count=1,
            sample_values=["A-01"],
            top_values=[("A-01", 2)],
        ),
        ColumnProfile(
            raw_name="기관명",
            normalized_name="기관명",
            source="response",
            semantic_tags=["name"],
            assigned_rules=["reference_relation"],
            inferred_primitive_type="text",
            non_empty_count=2,
            distinct_count=2,
            sample_values=["기관A", "기관B"],
            top_values=[("기관A", 1), ("기관B", 1)],
        ),
        ColumnProfile(
            raw_name="기관유형",
            normalized_name="기관유형",
            source="response",
            semantic_tags=["enum"],
            assigned_rules=[],
            inferred_primitive_type="text",
            non_empty_count=2,
            distinct_count=1,
            sample_values=["공공"],
            top_values=[("공공", 2)],
        ),
    ]
    rows = [
        {"기관코드": "A-01", "기관명": "기관A", "기관유형": "공공"},
        {"기관코드": "A-01", "기관명": "기관B", "기관유형": "공공"},
    ]
    candidates = [
        {
            "rule_id": "reference_relation",
            "columns": ["기관코드", "기관명", "기관유형"],
            "confidence": 0.99,
        }
    ]

    findings = validate_dataset_relationships(columns, rows, candidates)

    assert [finding.rule_id for finding in findings] == []
