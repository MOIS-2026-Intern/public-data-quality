import { PreviewPanel } from "./PreviewPanel";
import { FindingsTable } from "./FindingsTable";
import { SummaryCard } from "./common";

export function getReportDownloadUrl(result) {
  if (result?.summary?.error_report_download_path) {
    return result.summary.error_report_download_path;
  }
  const reportPath = result?.summary?.error_report_xlsx;
  if (!reportPath) {
    return "";
  }
  return `/api/reports/download?path=${encodeURIComponent(reportPath)}`;
}

function SummarySection({ summary }) {
  return (
    <div className="summary-grid">
      <SummaryCard label="데이터셋" value={summary.dataset_name} />
      <SummaryCard label="행 수" value={summary.row_count ?? "-"} />
      <SummaryCard label="컬럼 수" value={summary.column_count} />
      <SummaryCard label="검증 결과" value={summary.finding_count ?? 0} />
      <SummaryCard label="오류/이상 탐지" value={summary.issue_finding_count ?? 0} />
      <SummaryCard label="수동 검토 필요" value={summary.manual_review_finding_count ?? 0} />
    </div>
  );
}

export function ResultContent({ result }) {
  if (!result) {
    return null;
  }

  const reportDownloadUrl = getReportDownloadUrl(result);

  return (
    <>
      <SummarySection summary={result.summary || {}} />
      {reportDownloadUrl ? (
        <div className="report-actions">
          <a className="download-report-button" href={reportDownloadUrl}>
            오류 리포트 다운로드
          </a>
        </div>
      ) : null}

      <div className="result-section">
        <h2>검증 결과</h2>
        <FindingsTable findings={result.findings} previewRows={result.preview_rows || []} />
      </div>

      <div className="result-section">
        <h2>데이터 미리보기</h2>
        <PreviewPanel
          headers={result.preview_headers || []}
          rows={result.preview_rows || []}
          columns={result.columns || []}
          findings={result.findings || []}
          totalRows={result.summary?.row_count}
        />
      </div>
    </>
  );
}
