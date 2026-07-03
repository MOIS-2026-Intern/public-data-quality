import { useEffect, useState } from "react";
import {
  buildColumnSummary,
  formatConfidence,
  formatCriterionName,
  formatFindingType,
  formatPercent,
} from "../lib/formatters";

function buildCellIssueMap(findings) {
  const issueMap = new Map();

  for (const finding of findings || []) {
    if (finding.finding_type !== "issue") continue;
    if (!finding.row_indexes?.length) continue;
    if (!finding.column_name) continue;

    for (const rowIndex of finding.row_indexes) {
      const key = `${rowIndex}::${finding.column_name}`;
      const bucket = issueMap.get(key) || [];
      bucket.push(finding);
      issueMap.set(key, bucket);
    }
  }

  return issueMap;
}

function displayValue(value) {
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "number") return Number.isFinite(value) ? value.toLocaleString("ko-KR") : "-";
  if (typeof value === "string" || typeof value === "boolean") return String(value);
  if (Array.isArray(value)) return value.length ? value.map(displayValue).join(", ") : "-";
  if (typeof value === "object") {
    const entries = Object.entries(value);
    return entries.length ? entries.map(([key, nestedValue]) => `${key}: ${displayValue(nestedValue)}`).join(" / ") : "-";
  }
  return String(value);
}

function formatCellIssues(issues) {
  return (issues || []).map((finding) => ({
    key: `${finding.rule_id}-${finding.message}`,
    label: `${formatFindingType(finding)} · ${formatCriterionName(finding.criterion_name)}`,
    message: finding.message,
  }));
}

function formatCount(value) {
  if (value === null || value === undefined) return "-";
  return Number(value).toLocaleString("ko-KR");
}

function totalCount(column) {
  if (column.total_count !== null && column.total_count !== undefined) {
    return column.total_count;
  }
  if (column.non_empty_count !== null && column.non_empty_count !== undefined) {
    return Number(column.non_empty_count || 0) + Number(column.null_count || 0);
  }
  return null;
}

function buildValueDistributionRows(column) {
  if (!column?.top_values?.length) return [];
  const denominator = column.non_empty_count || column.top_values.reduce((sum, [, count]) => sum + count, 0);
  const rows = column.top_values.slice(0, 5).map(([value, count]) => ({
    label: value || "(빈 값)",
    count: Number(count) || 0,
    ratio: denominator ? (Number(count) || 0) / denominator : 0,
  }));
  const shownCount = rows.reduce((sum, row) => sum + row.count, 0);
  const otherCount = Math.max((column.non_empty_count || shownCount) - shownCount, 0);
  if (otherCount > 0) {
    rows.push({
      label: "기타",
      count: otherCount,
      ratio: denominator ? otherCount / denominator : 0,
    });
  }
  return rows;
}

function ColumnValueDonut({ column }) {
  const rows = buildValueDistributionRows(column).filter((row) => row.count > 0);
  if (!rows.length) return "-";
  const colors = ["#1f6f5b", "#11284d", "#b16c08", "#8b5cf6", "#0f766e", "#64748b"];
  let cursor = 0;
  const gradient = rows
    .map((row, index) => {
      const start = cursor;
      const end = cursor + row.ratio * 100;
      cursor = end;
      return `${colors[index % colors.length]} ${start}% ${end}%`;
    })
    .join(", ");

  return (
    <div className="column-donut-panel">
      <div className="column-donut-chart" style={{ background: `conic-gradient(${gradient})` }}>
        <div className="column-donut-center">
          <strong>{formatCount(column.non_empty_count)}</strong>
          <span>유효값</span>
        </div>
      </div>
      <div className="column-donut-legend">
        {rows.map((row, index) => (
          <div className="column-donut-legend-row" key={`${row.label}-${row.count}`}>
            <span className="column-donut-swatch" style={{ background: colors[index % colors.length] }} />
            <span className="column-donut-label" title={row.label}>{row.label}</span>
            <span>{formatCount(row.count)}건</span>
            <span>{Math.round(row.ratio * 100)}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function standardMappingText(column) {
  if (!column) return "표준용어 정보 없음";
  const candidate = column.standard_candidates?.[0];
  if (!candidate) return "표준용어 미매핑";
  return candidate;
}

function normalizedColumnName(value) {
  return String(value || "").replace(/\s+/g, "").trim();
}

function hasDifferentStandardTerm(column) {
  const candidate = column?.standard_candidates?.[0];
  if (!candidate) return false;
  return normalizedColumnName(candidate) !== normalizedColumnName(column.raw_name);
}

function StandardMappingBadge({ column }) {
  if (!hasDifferentStandardTerm(column)) return null;
  const candidate = column?.standard_candidates?.[0];

  return (
    <span
      className="standard-mapping-badge is-mapped"
      title={standardMappingText(column)}
    >
      <span className="standard-mapping-prefix">표준</span>
      <span className="standard-mapping-term">{candidate}</span>
    </span>
  );
}

export function PreviewPanel({
  headers,
  rows,
  columns,
  findings,
}) {
  const safeHeaders = headers || [];
  const safeRows = rows || [];
  const safeColumns = columns || [];
  const safeFindings = findings || [];
  const [hoveredColumnName, setHoveredColumnName] = useState(safeHeaders[0] || "");
  const hoveredColumn = safeColumns.find((column) => column.raw_name === hoveredColumnName) || null;
  const columnByName = new Map(safeColumns.map((column) => [column.raw_name, column]));
  const cellIssueMap = buildCellIssueMap(safeFindings);

  useEffect(() => {
    setHoveredColumnName(safeHeaders[0] || "");
  }, [safeHeaders.join("|")]);

  if (!safeRows.length) {
    return <div className="empty-state">업로드된 데이터 미리보기를 생성하지 못했습니다.</div>;
  }

  return (
    <div className="preview-layout">
      <div className="preview-table-wrap">
        <table className="preview-table">
          <thead>
            <tr>
              <th>행</th>
              {safeHeaders.map((header) => (
                <th
                  key={header}
                  className={hoveredColumnName === header ? "is-column-hovered" : ""}
                  onMouseEnter={() => setHoveredColumnName(header)}
                  title={standardMappingText(columnByName.get(header))}
                >
                  <span className="preview-column-header">
                    <span className="preview-column-name">{header}</span>
                    <StandardMappingBadge column={columnByName.get(header)} />
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {safeRows.map((row, index) => (
              <tr key={`preview-row-${index}`}>
                <td>{index + 1}</td>
                {safeHeaders.map((header) => {
                  const issueKey = `${index + 1}::${header}`;
                  const cellIssues = cellIssueMap.get(issueKey) || [];
                  const formattedIssues = formatCellIssues(cellIssues);
                  const hasIssues = formattedIssues.length > 0;
                  return (
                    <td
                      key={`${index}-${header}`}
                      className={[
                        hoveredColumnName === header ? "is-column-hovered" : "",
                        hasIssues ? "is-fix-needed" : "",
                      ]
                        .filter(Boolean)
                        .join(" ")}
                      onMouseEnter={() => setHoveredColumnName(header)}
                      tabIndex={hasIssues ? 0 : undefined}
                    >
                      <span className="preview-cell-value">{displayValue(row[header])}</span>
                      {hasIssues ? (
                        <span className="cell-issue-tooltip" role="tooltip">
                          {formattedIssues.map((issue) => (
                            <span className="cell-issue-tooltip-item" key={issue.key}>
                              <strong>{issue.label}</strong>
                              <span>{issue.message}</span>
                            </span>
                          ))}
                        </span>
                      ) : null}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <aside className="hover-panel">
        <div className="hover-panel-title">컬럼 상세 정보</div>
        <div className="hover-panel-subtitle">{hoveredColumnName || "-"}</div>
        {!hoveredColumn ? (
          <div className="empty-state">컬럼 프로파일 정보가 없습니다.</div>
        ) : (
          <div className="hover-detail-list">
            <div className="hover-detail-item hover-detail-item-primary">
              <div className="hover-detail-key">컬럼 요약</div>
              <div className="hover-detail-value">
                {buildColumnSummary(hoveredColumn)}
              </div>
            </div>
            <div className="hover-detail-item hover-detail-item-primary">
              <div className="hover-detail-key">값 분포</div>
              <div className="hover-detail-value">
                <ColumnValueDonut column={hoveredColumn} />
              </div>
            </div>
            <div className="hover-detail-item">
              <div className="hover-detail-key">전체 / 유효값</div>
              <div className="hover-detail-value">
                {formatCount(totalCount(hoveredColumn))}건 / {formatCount(hoveredColumn.non_empty_count)}건
              </div>
            </div>
            <div className="hover-detail-item">
              <div className="hover-detail-key">결측 비율</div>
              <div className="hover-detail-value">{formatPercent(hoveredColumn.null_ratio)}</div>
            </div>
            <div className="hover-detail-item">
              <div className="hover-detail-key">고유값 수</div>
              <div className="hover-detail-value">{hoveredColumn.distinct_count ?? "200+"}</div>
            </div>
            <div className="hover-detail-item">
              <div className="hover-detail-key">숫자 파싱 비율</div>
              <div className="hover-detail-value">{formatPercent(hoveredColumn.numeric_parse_ratio)}</div>
            </div>
            <div className="hover-detail-item">
              <div className="hover-detail-key">날짜 파싱 비율</div>
              <div className="hover-detail-value">{formatPercent(hoveredColumn.date_parse_ratio)}</div>
            </div>
            <div className="hover-detail-item">
              <div className="hover-detail-key">의미 프로파일</div>
              <div className="hover-detail-value">{hoveredColumn.semantic_profile_label || "-"}</div>
            </div>
            <div className="hover-detail-item">
              <div className="hover-detail-key">설명</div>
              <div className="hover-detail-value">
                {hoveredColumn.semantic_profile_description || "의미 설명이 없습니다."}
              </div>
            </div>
            <div className="hover-detail-item">
              <div className="hover-detail-key">의미 신뢰도</div>
              <div className="hover-detail-value">{formatConfidence(hoveredColumn.semantic_profile_confidence)}</div>
            </div>
            <div className="hover-detail-item">
              <div className="hover-detail-key">LLM 의미 프로파일링</div>
              <div className="hover-detail-value">{hoveredColumn.semantic_profile_llm_needed ? "필요" : "불필요"}</div>
            </div>
            <div className="hover-detail-item">
              <div className="hover-detail-key">LLM 필요 사유</div>
              <div className="hover-detail-value">
                {hoveredColumn.semantic_profile_llm_reasons?.join(", ") || "-"}
              </div>
            </div>
            <div className="hover-detail-item">
              <div className="hover-detail-key">표준용어 후보</div>
              <div className="hover-detail-value">{hoveredColumn.standard_candidates?.[0] || "-"}</div>
            </div>
            <div className="hover-detail-item">
              <div className="hover-detail-key">샘플값</div>
              <div className="hover-detail-value">{hoveredColumn.sample_values?.join(", ") || "-"}</div>
            </div>
            <div className="hover-detail-item">
              <div className="hover-detail-key">적용 규칙</div>
              <div className="hover-detail-value">{hoveredColumn.assigned_rules?.join(", ") || "-"}</div>
            </div>
            <div className="hover-detail-item">
              <div className="hover-detail-key">수정 제안</div>
              <div className="hover-detail-value">{hoveredColumn.repair_suggestion || "-"}</div>
            </div>
          </div>
        )}
      </aside>

    </div>
  );
}
