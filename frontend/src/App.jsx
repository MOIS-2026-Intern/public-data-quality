import { useEffect, useState } from "react";
import { FindingTypeBadge, SummaryCard, displayValue } from "./components/common";
import { PreviewPanel } from "./components/PreviewPanel";
import {
  formatCriterionName,
  formatRelatedColumns,
  formatRuleId,
  formatSeverity,
} from "./lib/formatters";

function ControlPanel({
  datasetFiles,
  setDatasetFiles,
  openAiApiKey,
  setOpenAiApiKey,
  llmFastModel,
  setLlmFastModel,
  llmStrongModel,
  setLlmStrongModel,
  loading,
  progress,
  error,
  onSubmit,
}) {
  const fileCount = datasetFiles.length;
  const selectedFileLabel =
    fileCount === 0 ? "선택된 파일 없음" : fileCount === 1 ? datasetFiles[0].name : `${fileCount}개 파일 선택됨`;
  const selectedFileTitle = datasetFiles.map((file) => file.name).join("\n");

  return (
    <section className="control-panel">
      <form onSubmit={onSubmit}>
        <div className="file-field">
          <span className="file-field-label">CSV / Excel 업로드</span>
          <label className="file-picker">
            <input
              className="file-picker-input"
              type="file"
              multiple
              accept=".csv,.xlsx,.xls,text/csv,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
              onChange={(event) => setDatasetFiles(Array.from(event.target.files || []))}
            />
            <span className="file-picker-action">파일 선택</span>
            <span className="file-picker-name" title={selectedFileTitle}>
              {selectedFileLabel}
            </span>
          </label>
          {fileCount > 1 ? (
            <div className="selected-files" aria-label="선택된 파일">
              {datasetFiles.map((file) => (
                <span className="selected-file" key={`${file.name}-${file.size}-${file.lastModified}`} title={file.name}>
                  {file.name}
                </span>
              ))}
            </div>
          ) : null}
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
        <button className="primary-button" type="submit" disabled={loading || fileCount === 0}>
          {loading ? "분석 중..." : "분석 실행"}
        </button>
      </form>
      <LoadingProgress progress={progress} />
      {error ? <div className="error-box">{error}</div> : null}
    </section>
  );
}

function LoadingProgress({ progress }) {
  if (!progress?.visible) {
    return null;
  }

  const percent = Math.max(0, Math.min(100, Number(progress.percent) || 0));
  const statusText = progress.message || "분석 중";
  const countText =
    progress.total > 0 ? `${Math.min(progress.current || 0, progress.total)} / ${progress.total}` : "";

  return (
    <div className="progress-panel" aria-live="polite">
      <div className="progress-meta">
        <span>{statusText}</span>
        <strong>{countText || `${percent}%`}</strong>
      </div>
      <div className="progress-track" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow={percent}>
        <div className="progress-fill" style={{ width: `${percent}%` }} />
      </div>
    </div>
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

function BatchSummarySection({ summary }) {
  return (
    <div className="summary-grid">
      <SummaryCard label="파일 수" value={summary.dataset_count ?? 0} />
      <SummaryCard label="성공" value={summary.success_count ?? 0} />
      <SummaryCard label="실패" value={summary.failed_count ?? 0} />
      <SummaryCard label="총 행 수" value={summary.row_count ?? 0} />
      <SummaryCard label="검증 결과" value={summary.finding_count ?? 0} />
      <SummaryCard label="오류/이상" value={summary.issue_finding_count ?? 0} />
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
  const [activeResultIndex, setActiveResultIndex] = useState(0);
  const isBatch = Boolean(result?.batch);
  const successfulItems = isBatch ? (result.results || []).filter((item) => item.ok && item.result) : [];
  const failedItems = isBatch ? (result.results || []).filter((item) => !item.ok) : [];
  const activeItem = successfulItems[activeResultIndex] || successfulItems[0] || null;
  const activeResult = isBatch ? activeItem?.result : result;

  useEffect(() => {
    setActiveResultIndex(0);
  }, [result]);

  if (!result) {
    return (
      <section className="results-panel">
        <div className="empty-state">분석을 실행하면 요약, 검증 결과, 컬럼 상세가 여기에 표시됩니다.</div>
      </section>
    );
  }

  return (
    <section className="results-panel">
      {isBatch ? (
        <>
          <BatchSummarySection summary={result.summary || {}} />
          {successfulItems.length ? (
            <div className="result-tabs" role="tablist" aria-label="분석 결과 파일">
              {successfulItems.map((item, index) => (
                <button
                  className={`result-tab ${index === activeResultIndex ? "is-active" : ""}`}
                  type="button"
                  role="tab"
                  aria-selected={index === activeResultIndex}
                  key={`${item.filename}-${index}`}
                  onClick={() => setActiveResultIndex(index)}
                  title={item.filename}
                >
                  {item.filename}
                </button>
              ))}
            </div>
          ) : null}
          {failedItems.length ? (
            <div className="failed-files">
              {failedItems.map((item, index) => (
                <div className="failed-file" key={`${item.filename}-${index}`}>
                  <strong>{item.filename}</strong>
                  <span>{item.error || "분석 실패"}</span>
                </div>
              ))}
            </div>
          ) : null}
        </>
      ) : null}

      {activeResult ? <SummarySection summary={activeResult.summary || {}} /> : null}

      {activeResult ? (
        <>
          <div className="result-section">
            <h2>검증 결과</h2>
            <FindingsTable findings={activeResult.findings} />
          </div>

          <div className="result-section">
            <h2>데이터 미리보기</h2>
            <PreviewPanel
              headers={activeResult.preview_headers || []}
              rows={activeResult.preview_rows || []}
              columns={activeResult.columns || []}
              findings={activeResult.findings || []}
            />
          </div>
        </>
      ) : null}
    </section>
  );
}

function App() {
  const [datasetFiles, setDatasetFiles] = useState([]);
  const [useLlm] = useState(true);
  const [openAiApiKey, setOpenAiApiKey] = useState("");
  const [llmFastModel, setLlmFastModel] = useState("gpt-4o-mini");
  const [llmStrongModel, setLlmStrongModel] = useState("gpt-4o");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState({ visible: false, percent: 0, message: "", current: 0, total: 0 });

  function updateProgress(event) {
    setProgress({
      visible: true,
      percent: Number(event.progress) || 0,
      message: event.message || "분석 중",
      current: Number(event.current) || 0,
      total: Number(event.total) || datasetFiles.length,
    });
  }

  async function parseAnalyzeStream(response) {
    if (!response.body) {
      const responseText = await response.text();
      return responseText ? JSON.parse(responseText) : null;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let finalPayload = null;
    let streamError = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (!line.trim()) continue;
        const event = JSON.parse(line);
        if (event.type === "progress" || event.type === "file_done" || event.type === "file_error") {
          updateProgress(event);
        }
        if (event.type === "file_error" && event.error) {
          streamError = event.error;
        }
        if (event.type === "final") {
          updateProgress(event);
          finalPayload = event.payload;
        }
      }
    }

    if (buffer.trim()) {
      const event = JSON.parse(buffer);
      if (event.type === "final") {
        updateProgress(event);
        finalPayload = event.payload;
      }
    }

    if (finalPayload?.error) {
      throw new Error(finalPayload.error);
    }
    if (!finalPayload && streamError) {
      throw new Error(streamError);
    }
    return finalPayload;
  }

  async function handleAnalyze(event) {
    event.preventDefault();
    setLoading(true);
    setError("");
    setResult(null);
    setProgress({
      visible: true,
      percent: 0,
      message: "업로드 중",
      current: 0,
      total: datasetFiles.length,
    });

    try {
      if (datasetFiles.length === 0) {
        throw new Error("분석할 CSV 파일을 먼저 업로드하세요.");
      }
      if (useLlm && !openAiApiKey.trim()) {
        throw new Error("OpenAI API Key를 입력하세요.");
      }

      const body = new FormData();
      datasetFiles.forEach((datasetFile) => body.append("dataset_file", datasetFile));
      body.append("use_llm_agents", String(useLlm));
      if (openAiApiKey.trim()) body.append("openai_api_key", openAiApiKey.trim());
      if (llmFastModel) body.append("llm_fast_model", llmFastModel);
      if (llmStrongModel) body.append("llm_strong_model", llmStrongModel);

      const response = await fetch("/api/analyze-stream", {
        method: "POST",
        body,
      });

      if (!response.ok) {
        const responseText = await response.text();
        let payload = null;
        try {
          payload = responseText ? JSON.parse(responseText) : null;
        } catch {
          payload = null;
        }
        throw new Error(payload?.error || responseText || "분석 요청에 실패했습니다.");
      }

      const payload = await parseAnalyzeStream(response);
      if (!payload) {
        throw new Error("분석 응답 형식이 올바르지 않습니다.");
      }
      setResult(payload);
    } catch (err) {
      setError(err.message);
      setResult(null);
      setProgress((currentProgress) => ({
        ...currentProgress,
        visible: true,
        message: err.message || "분석 실패",
      }));
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
          datasetFiles={datasetFiles}
          setDatasetFiles={setDatasetFiles}
          openAiApiKey={openAiApiKey}
          setOpenAiApiKey={setOpenAiApiKey}
          llmFastModel={llmFastModel}
          setLlmFastModel={setLlmFastModel}
          llmStrongModel={llmStrongModel}
          setLlmStrongModel={setLlmStrongModel}
          loading={loading}
          progress={progress}
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
