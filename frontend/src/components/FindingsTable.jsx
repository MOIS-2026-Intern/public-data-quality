import { useEffect, useState } from "react";
import { displayValue } from "./common";
import { formatCriterionName, formatRelatedColumns, formatRuleId, formatSeverity } from "../lib/formatters";

function expandedFindingRows(findings, previewRows) {
  return (findings || []).flatMap((finding, findingIndex) => {
    const rowIndexes = Array.isArray(finding.row_indexes) && finding.row_indexes.length ? finding.row_indexes : [null];
    return rowIndexes.map((rowIndex, occurrenceIndex) => {
      const sourceRow = rowIndex ? previewRows?.[Number(rowIndex) - 1] : null;
      const rowValue = rowIndex ? finding.row_values?.[String(rowIndex)] : undefined;
      return {
        finding,
        rowIndex,
        occurrenceIndex,
        findingIndex,
        currentValue: rowValue ?? (sourceRow ? sourceRow[finding.column_name] : ""),
      };
    });
  });
}

function FindingRowsTable({ rows, emptyText, showLlmFinalVerification = true }) {
  const columnCount = showLlmFinalVerification ? 10 : 9;

  return (
    <div className="table-wrap finding-section-table-wrap">
      <table>
        <thead>
          <tr>
            <th className="finding-cell-nowrap">컬럼</th>
            <th>행</th>
            <th className="finding-cell-nowrap">검증영역</th>
            <th className="finding-cell-nowrap">기준명</th>
            <th>현재 값</th>
            <th>심각도</th>
            <th className="finding-cell-nowrap">규칙</th>
            <th className="finding-cell-nowrap">메시지</th>
            {showLlmFinalVerification ? <th className="finding-cell-nowrap">LLM 최종 검증</th> : null}
            <th className="finding-cell-nowrap">관련 컬럼</th>
          </tr>
        </thead>
        <tbody>
          {rows.length ? (
            rows.map(({ finding, rowIndex, occurrenceIndex, findingIndex, currentValue }) => (
              <tr
                key={`${finding.column_name}-${findingIndex}-${rowIndex || "none"}-${occurrenceIndex}`}
                className={finding.finding_type === "manual_review" ? "finding-row-manual-review" : "finding-row-issue"}
              >
                <td className="finding-cell-nowrap">{displayValue(finding.column_name)}</td>
                <td>{displayValue(rowIndex)}</td>
                <td className="finding-cell-nowrap">{displayValue(finding.category_label)}</td>
                <td className="finding-cell-nowrap">{displayValue(formatCriterionName(finding.criterion_name))}</td>
                <td>{displayValue(currentValue)}</td>
                <td>{displayValue(formatSeverity(finding.severity))}</td>
                <td className="finding-cell-nowrap">{displayValue(formatRuleId(finding.rule_id))}</td>
                <td>{displayValue(finding.message)}</td>
                {showLlmFinalVerification ? <td>{displayValue(finding.llm_final_verification)}</td> : null}
                <td className="finding-cell-nowrap">{displayValue(formatRelatedColumns(finding))}</td>
              </tr>
            ))
          ) : (
            <tr>
              <td colSpan={columnCount} className="finding-empty-cell">
                {emptyText}
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

export function FindingsTable({ findings, previewRows }) {
  const [activeFindingType, setActiveFindingType] = useState("issue");
  const rows = expandedFindingRows(findings, previewRows);
  const issueRows = rows.filter(({ finding }) => finding.finding_type !== "manual_review");
  const manualReviewRows = rows.filter(({ finding }) => finding.finding_type === "manual_review");
  const sections = [
    {
      id: "issue",
      title: "오류/이상 탐지",
      rows: issueRows,
      emptyText: "탐지된 오류/이상이 없습니다.",
    },
    {
      id: "manual-review",
      title: "수동 검토 필요",
      rows: manualReviewRows,
      emptyText: "수동 검토 항목이 없습니다.",
    },
  ];
  const activeSection = sections.find((section) => section.id === activeFindingType) || sections[0];

  useEffect(() => {
    setActiveFindingType("issue");
  }, [findings]);

  return (
    <div className="findings-tabbed">
      <div className="finding-tabs" role="tablist" aria-label="검증 결과 유형">
        {sections.map((section) => (
          <button
            className={`finding-tab ${section.id === activeSection.id ? "is-active" : ""}`}
            type="button"
            role="tab"
            aria-selected={section.id === activeSection.id}
            key={section.id}
            onClick={() => setActiveFindingType(section.id)}
          >
            <span>{section.title}</span>
            <strong>{section.rows.length.toLocaleString("ko-KR")}건</strong>
          </button>
        ))}
      </div>
      <FindingRowsTable
        rows={activeSection.rows}
        emptyText={activeSection.emptyText}
        showLlmFinalVerification={activeSection.id !== "manual-review"}
      />
    </div>
  );
}
