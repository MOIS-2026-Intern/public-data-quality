import { useState } from "react";
import { FindingTypeBadge, SummaryCard, displayValue } from "./components/common";
import { PreviewPanel } from "./components/PreviewPanel";
import {
  formatCriterionName,
  formatRelatedColumns,
  formatRuleId,
  formatSeverity,
} from "./lib/formatters";

function ControlPanel({
  datasetFile,
  setDatasetFile,
  openAiApiKey,
  setOpenAiApiKey,
  llmFastModel,
  setLlmFastModel,
  llmStrongModel,
  setLlmStrongModel,
  loading,
  error,
  onSubmit,
}) {
  return (
    <section className="control-panel">
      <form onSubmit={onSubmit}>
        <div className="file-field">
          <span className="file-field-label">CSV / Excel 업로드</span>
          <label className="file-picker">
            <input
              className="file-picker-input"
              type="file"
              accept=".csv,.xlsx,.xls,text/csv,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
              onChange={(event) => setDatasetFile(event.target.files?.[0] ?? null)}
            />
            <span className="file-picker-action">파일 선택</span>
            <span className="file-picker-name" title={datasetFile?.name || ""}>
              {datasetFile?.name || "선택된 파일 없음"}
            </span>
          </label>
        </div>
        <label>
          OpenAI API Key
          <input
            type="password"
            value={openAiApiKey}
            onChange={(event) => setOpenAiApiKey(event.target.value)}
            placeholder="sk-..."
            autoComplete="off"
            spellCheck={false}
          />
        </label>
        <label>
          빠른 라우팅 모델
          <input
            value={llmFastModel}
            onChange={(event) => setLlmFastModel(event.target.value)}
            placeholder="예: gpt-4o-mini"
          />
        </label>
        <label>
          정밀 검증 모델
          <input
            value={llmStrongModel}
            onChange={(event) => setLlmStrongModel(event.target.value)}
            placeholder="예: gpt-4o"
          />
        </label>
        <button className="primary-button" type="submit" disabled={loading || !datasetFile}>
          {loading ? "분석 중..." : "분석 실행"}
        </button>
      </form>
      {error ? <div className="error-box">{error}</div> : null}
    </section>
  );
}

function SummarySection({ summary }) {
  return (
    <div className="summary-grid">
      <SummaryCard label="데이터셋" value={summary.dataset_name} />
      <SummaryCard label="행 수" value={summary.row_count ?? "-"} />
      <SummaryCard label="컬럼 수" value={summary.column_count} />
      <SummaryCard label="검증 결과" value={summary.finding_count ?? 0} />
      <SummaryCard label="오류/이상" value={summary.issue_finding_count ?? 0} />
      <SummaryCard label="수동 검토" value={summary.manual_review_finding_count ?? 0} />
    </div>
  );
}

function FindingsTable({ findings }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>판정</th>
            <th>검증영역</th>
            <th>기준명</th>
            <th>컬럼</th>
            <th>심각도</th>
            <th>규칙</th>
            <th>메시지</th>
            <th>관련 컬럼</th>
          </tr>
        </thead>
        <tbody>
          {(findings || []).map((finding, index) => (
            <tr
              key={`${finding.column_name}-${index}`}
              className={finding.finding_type === "manual_review" ? "finding-row-manual-review" : "finding-row-issue"}
            >
              <td>
                <FindingTypeBadge finding={finding} />
              </td>
              <td>{displayValue(finding.category_label)}</td>
              <td>{displayValue(formatCriterionName(finding.criterion_name))}</td>
              <td>{displayValue(finding.column_name)}</td>
              <td>{displayValue(formatSeverity(finding.severity))}</td>
              <td>{displayValue(formatRuleId(finding.rule_id))}</td>
              <td>{displayValue(finding.message)}</td>
              <td>{displayValue(formatRelatedColumns(finding))}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ResultsPanel({ result }) {
  if (!result) {
    return (
      <section className="results-panel">
        <div className="empty-state">분석을 실행하면 요약, 검증 결과, 컬럼 상세가 여기에 표시됩니다.</div>
      </section>
    );
  }

  return (
    <section className="results-panel">
      <SummarySection summary={result.summary || {}} />

      <div className="result-section">
        <h2>검증 결과</h2>
        <FindingsTable findings={result.findings} />
      </div>

      <div className="result-section">
        <h2>데이터 미리보기</h2>
        <PreviewPanel
          headers={result.preview_headers || []}
          rows={result.preview_rows || []}
          columns={result.columns || []}
          findings={result.findings || []}
        />
      </div>
    </section>
  );
}

function App() {
  const [datasetFile, setDatasetFile] = useState(null);
  const [useLlm] = useState(true);
  const [openAiApiKey, setOpenAiApiKey] = useState("");
  const [llmFastModel, setLlmFastModel] = useState("gpt-4o-mini");
  const [llmStrongModel, setLlmStrongModel] = useState("gpt-4o");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleAnalyze(event) {
    event.preventDefault();
    setLoading(true);
    setError("");

    try {
      if (!datasetFile) {
        throw new Error("분석할 CSV 파일을 먼저 업로드하세요.");
      }
      if (useLlm && !openAiApiKey.trim()) {
        throw new Error("OpenAI API Key를 입력하세요.");
      }

      const body = new FormData();
      if (datasetFile) body.append("dataset_file", datasetFile);
      body.append("use_llm_agents", String(useLlm));
      if (openAiApiKey.trim()) body.append("openai_api_key", openAiApiKey.trim());
      if (llmFastModel) body.append("llm_fast_model", llmFastModel);
      if (llmStrongModel) body.append("llm_strong_model", llmStrongModel);

      const response = await fetch("/api/analyze", {
        method: "POST",
        body,
      });

      const responseText = await response.text();
      let payload = null;
      try {
        payload = responseText ? JSON.parse(responseText) : null;
      } catch {
        payload = null;
      }
      if (!response.ok) {
        throw new Error(payload?.error || responseText || "분석 요청에 실패했습니다.");
      }
      if (!payload) {
        throw new Error("분석 응답 형식이 올바르지 않습니다.");
      }
      setResult(payload);
    } catch (err) {
      setError(err.message);
      setResult(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app-shell">
      <header className="hero">
        <div className="hero-copy">
          <div className="hero-brand">
            <img className="hero-logo" src="/image/ldq_logo.png" alt="LDQ" />
            <h1>LLM 기반 공공데이터 품질 관리 시스템</h1>
          </div>
        </div>
      </header>

      <main className="content-grid">
        <ControlPanel
          datasetFile={datasetFile}
          setDatasetFile={setDatasetFile}
          openAiApiKey={openAiApiKey}
          setOpenAiApiKey={setOpenAiApiKey}
          llmFastModel={llmFastModel}
          setLlmFastModel={setLlmFastModel}
          llmStrongModel={llmStrongModel}
          setLlmStrongModel={setLlmStrongModel}
          loading={loading}
          error={error}
          onSubmit={handleAnalyze}
        />
        <ResultsPanel result={result} />
      </main>

      <footer className="app-footer">
        <img className="footer-logo" src="/image/mois_logo.png" alt="행정안전부 로고" />
        <span className="footer-text">행정안전부 데이터정보화담당관</span>
      </footer>
    </div>
  );
}

export default App;
