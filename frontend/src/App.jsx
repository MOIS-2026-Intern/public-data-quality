import { useEffect, useState } from "react";
import { FindingTypeBadge, SummaryCard, displayValue } from "./components/common";
import { PreviewPanel } from "./components/PreviewPanel";
import {
  formatCriterionName,
  formatRelatedColumns,
  formatRuleId,
  formatSeverity,
} from "./lib/formatters";

const SOURCE_TYPES = [
  { id: "file", label: "파일 업로드" },
  { id: "url", label: "URL 입력" },
  { id: "api", label: "API 호출" },
];

function splitLineValues(value) {
  return value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function ControlPanel({
  sourceType,
  setSourceType,
  datasetFiles,
  setDatasetFiles,
  dataUrl,
  setDataUrl,
  apiUrl,
  setApiUrl,
  apiServiceKey,
  setApiServiceKey,
  apiPageNo,
  setApiPageNo,
  apiNumOfRows,
  setApiNumOfRows,
  apiResponseType,
  setApiResponseType,
  apiResponseTypeParam,
  setApiResponseTypeParam,
  apiParams,
  setApiParams,
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
  const fileCount = datasetFiles.length;
  const selectedFileLabel =
    fileCount === 0 ? "선택된 파일 없음" : fileCount === 1 ? datasetFiles[0].name : `${fileCount}개 파일 선택됨`;
  const selectedFileTitle = datasetFiles.map((file) => file.name).join("\n");

  return (
    <section className="control-panel">
      <form onSubmit={onSubmit}>
        <div className="control-section">
          <div className="source-tabs" role="tablist" aria-label="데이터 입력 방식">
            {SOURCE_TYPES.map((source) => (
              <button
                className={`source-tab ${sourceType === source.id ? "is-active" : ""}`}
                type="button"
                role="tab"
                aria-selected={sourceType === source.id}
                key={source.id}
                onClick={() => setSourceType(source.id)}
              >
                {source.label}
              </button>
            ))}
          </div>
        </div>

        <div className="control-section control-section-input">
          {sourceType === "file" ? (
            <div className="file-field">
              <span className="file-field-label">파일 업로드</span>
              <label className="file-picker">
                <input
                  className="file-picker-input"
                  type="file"
                  multiple
                  accept=".csv,.tsv,.txt,.xlsx,.xls,.json,.jsonl,.xml,.zip,text/csv,text/tab-separated-values,application/json,application/xml,text/xml,application/zip,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
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
          ) : null}

          {sourceType === "url" ? (
            <label>
              입력 URL 목록
              <textarea
                rows={5}
                value={dataUrl}
                onChange={(event) => setDataUrl(event.target.value)}
                placeholder={"https://...\nhttps://..."}
                spellCheck={false}
              />
            </label>
          ) : null}

          {sourceType === "api" ? (
            <>
              <div className="api-field-stack">
                <label>
                  공공데이터 API URL
                  <input
                    type="url"
                    value={apiUrl}
                    onChange={(event) => setApiUrl(event.target.value)}
                    placeholder="https://..."
                    spellCheck={false}
                  />
                </label>
                <label>
                  Service Key
                  <input
                    type="password"
                    value={apiServiceKey}
                    onChange={(event) => setApiServiceKey(event.target.value)}
                    placeholder="공공데이터포털 인증키"
                    autoComplete="off"
                    spellCheck={false}
                  />
                </label>
              </div>
              <div className="api-grid-row">
                <label>
                  pageNo
                  <input
                    value={apiPageNo}
                    onChange={(event) => setApiPageNo(event.target.value)}
                    inputMode="numeric"
                    placeholder="1"
                  />
                </label>
                <label>
                  numOfRows
                  <input
                    value={apiNumOfRows}
                    onChange={(event) => setApiNumOfRows(event.target.value)}
                    inputMode="numeric"
                    placeholder="100"
                  />
                </label>
              </div>
              <div className="api-grid-row">
                <label>
                  응답 형식
                  <select value={apiResponseType} onChange={(event) => setApiResponseType(event.target.value)}>
                    <option value="json">JSON</option>
                    <option value="xml">XML</option>
                  </select>
                </label>
                <label>
                  형식 파라미터
                  <select value={apiResponseTypeParam} onChange={(event) => setApiResponseTypeParam(event.target.value)}>
                    <option value="_type">_type</option>
                    <option value="type">type</option>
                    <option value="returnType">returnType</option>
                    <option value="none">사용 안함</option>
                  </select>
                </label>
              </div>
              <label>
                추가 파라미터
                <textarea
                  rows={4}
                  value={apiParams}
                  onChange={(event) => setApiParams(event.target.value)}
                  placeholder={"시도명=서울특별시\n분류=일반"}
                  spellCheck={false}
                />
              </label>
            </>
          ) : null}
        </div>

        <div className="control-section model-section">
          <div className="control-section-title">LLM 설정</div>
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
        </div>

        <div className="control-actions">
          <button className={`primary-button ${loading ? "is-loading" : ""}`} type="submit" disabled={loading}>
            {loading ? "분석 중" : "분석 실행"}
          </button>
        </div>
      </form>
      {error ? <div className="error-box">{error}</div> : null}
    </section>
  );
}

function LoadingProgress({ progress }) {
  if (!progress?.visible) {
    return null;
  }

  const percent = Math.max(0, Math.min(100, Number(progress.percent) || 0));

  return (
    <div className="progress-panel" aria-live="polite">
      <div className="progress-meta">
        <strong>{percent}%</strong>
      </div>
      <div className="progress-track" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow={percent}>
        <div className="progress-fill" style={{ width: `${percent}%` }} />
      </div>
    </div>
  );
}

function LoadingResults({ progress }) {
  const currentStage = progress?.stageLabel || progress?.message || "분석 중";

  return (
    <div className="loading-state">
      <div className="loading-heading">
        <strong>{currentStage}</strong>
      </div>
      <LoadingProgress progress={progress} />
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

function expandedFindingRows(findings, previewRows) {
  return (findings || []).flatMap((finding, findingIndex) => {
    const rowIndexes = Array.isArray(finding.row_indexes) && finding.row_indexes.length ? finding.row_indexes : [null];
    return rowIndexes.map((rowIndex, occurrenceIndex) => {
      const sourceRow = rowIndex ? previewRows?.[Number(rowIndex) - 1] : null;
      return {
        finding,
        rowIndex,
        occurrenceIndex,
        findingIndex,
        currentValue: sourceRow ? sourceRow[finding.column_name] : "",
      };
    });
  });
}

function FindingsTable({ findings, previewRows }) {
  const rows = expandedFindingRows(findings, previewRows);

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>행</th>
            <th>판정</th>
            <th>검증영역</th>
            <th>기준명</th>
            <th>컬럼</th>
            <th>현재 값</th>
            <th>심각도</th>
            <th>규칙</th>
            <th>메시지</th>
            <th>관련 컬럼</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(({ finding, rowIndex, occurrenceIndex, findingIndex, currentValue }) => (
            <tr
              key={`${finding.column_name}-${findingIndex}-${rowIndex || "none"}-${occurrenceIndex}`}
              className={finding.finding_type === "manual_review" ? "finding-row-manual-review" : "finding-row-issue"}
            >
              <td>{displayValue(rowIndex)}</td>
              <td>
                <FindingTypeBadge finding={finding} />
              </td>
              <td>{displayValue(finding.category_label)}</td>
              <td>{displayValue(formatCriterionName(finding.criterion_name))}</td>
              <td>{displayValue(finding.column_name)}</td>
              <td>{displayValue(currentValue)}</td>
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

function reportDownloadUrl(result) {
  const reportPath = result?.summary?.error_report_xlsx;
  if (!reportPath) return "";
  return `/api/reports/download?path=${encodeURIComponent(reportPath)}`;
}

function ResultsPanel({ result, loading, progress }) {
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
        {loading ? (
          <div className="empty-state empty-state-loading">
            <LoadingResults progress={progress} />
          </div>
        ) : (
          <div className="empty-state">분석을 실행하면 요약, 검증 결과, 컬럼 상세가 여기에 표시됩니다.</div>
        )}
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

      {activeResult ? (
        <>
          <SummarySection summary={activeResult.summary || {}} />
          {reportDownloadUrl(activeResult) ? (
            <div className="report-actions">
              <a className="download-report-button" href={reportDownloadUrl(activeResult)}>
                오류 리포트 다운로드
              </a>
            </div>
          ) : null}
        </>
      ) : null}

      {activeResult ? (
        <>
          <div className="result-section">
            <h2>검증 결과</h2>
            <FindingsTable findings={activeResult.findings} previewRows={activeResult.preview_rows || []} />
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
  const [sourceType, setSourceType] = useState("file");
  const [datasetFiles, setDatasetFiles] = useState([]);
  const [dataUrl, setDataUrl] = useState("");
  const [apiUrl, setApiUrl] = useState("");
  const [apiServiceKey, setApiServiceKey] = useState("");
  const [apiPageNo, setApiPageNo] = useState("1");
  const [apiNumOfRows, setApiNumOfRows] = useState("100");
  const [apiResponseType, setApiResponseType] = useState("json");
  const [apiResponseTypeParam, setApiResponseTypeParam] = useState("_type");
  const [apiParams, setApiParams] = useState("");
  const [useLlm] = useState(true);
  const [openAiApiKey, setOpenAiApiKey] = useState("");
  const [llmFastModel, setLlmFastModel] = useState("gpt-4o-mini");
  const [llmStrongModel, setLlmStrongModel] = useState("gpt-4o");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState({
    visible: false,
    percent: 0,
    message: "",
    current: 0,
    total: 0,
    filename: "",
    stageLabel: "",
    stageIndex: 0,
    stageTotal: 0,
    stages: [],
    history: [],
  });

  function expectedSourceCount() {
    if (sourceType === "file") return datasetFiles.length;
    if (sourceType === "url") return splitLineValues(dataUrl).length || 1;
    return 1;
  }

  function updateProgress(event) {
    setProgress((currentProgress) => {
      const message = event.message || "분석 중";
      const lastMessage = currentProgress.history?.[currentProgress.history.length - 1]?.message || "";
      const history =
        message && message !== lastMessage
          ? [...(currentProgress.history || []), { message }].slice(-8)
          : currentProgress.history || [];
      return {
        ...currentProgress,
        visible: true,
        percent: Number(event.progress) || 0,
        message,
        current: Number(event.current) || 0,
        total: Number(event.total) || expectedSourceCount(),
        filename: event.filename || currentProgress.filename || "",
        stageLabel: event.stage_label || event.stageLabel || currentProgress.stageLabel || "",
        stageIndex: Number(event.stage_index ?? currentProgress.stageIndex ?? 0),
        stageTotal: Number(event.stage_total ?? currentProgress.stageTotal ?? 0),
        stages: Array.isArray(event.stages) ? event.stages : currentProgress.stages || [],
        history,
      };
    });
  }

  function handleStreamEvent(event) {
    if (event.type === "progress" || event.type === "file_done" || event.type === "file_error" || event.type === "final") {
      updateProgress(event);
    }
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
        handleStreamEvent(event);
        if (event.type === "file_error" && event.error) {
          streamError = event.error;
        }
        if (event.type === "final") {
          finalPayload = event.payload;
        }
      }
    }

    if (buffer.trim()) {
      const event = JSON.parse(buffer);
      handleStreamEvent(event);
      if (event.type === "final") {
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
      total: expectedSourceCount(),
      filename: "",
      stageLabel: "",
      stageIndex: 0,
      stageTotal: 0,
      stages: [],
      history: [{ message: "업로드 중" }],
    });

    try {
      const useLlmForRequest = useLlm;
      const dataUrls = splitLineValues(dataUrl);
      if (sourceType === "file" && datasetFiles.length === 0) {
        throw new Error("분석할 파일을 먼저 업로드하세요.");
      }
      if (sourceType === "url" && dataUrls.length === 0) {
        throw new Error("입력 URL을 한 개 이상 입력하세요.");
      }
      if (sourceType === "api" && !apiUrl.trim()) {
        throw new Error("호출 URL을 입력하세요.");
      }
      if (useLlmForRequest && !openAiApiKey.trim()) {
        throw new Error("OpenAI API Key를 입력하세요.");
      }

      const body = new FormData();
      body.append("source_type", sourceType);
      if (sourceType === "file") {
        datasetFiles.forEach((datasetFile) => body.append("dataset_file", datasetFile));
      }
      if (sourceType === "url") {
        dataUrls.forEach((url) => body.append("data_url", url));
      }
      if (sourceType === "api") {
        body.append("api_url", apiUrl.trim());
        body.append("api_method", "GET");
        if (apiServiceKey.trim()) body.append("service_key", apiServiceKey.trim());
        if (apiPageNo.trim()) body.append("page_no", apiPageNo.trim());
        if (apiNumOfRows.trim()) body.append("num_of_rows", apiNumOfRows.trim());
        if (apiResponseType) body.append("api_response_type", apiResponseType);
        if (apiResponseTypeParam) body.append("api_response_type_param", apiResponseTypeParam);
        if (apiParams.trim()) body.append("api_params", apiParams.trim());
      }
      body.append("use_llm_agents", String(useLlmForRequest));
      if (useLlmForRequest && openAiApiKey.trim()) body.append("openai_api_key", openAiApiKey.trim());
      if (useLlmForRequest && llmFastModel) body.append("llm_fast_model", llmFastModel);
      if (useLlmForRequest && llmStrongModel) body.append("llm_strong_model", llmStrongModel);

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
          sourceType={sourceType}
          setSourceType={setSourceType}
          datasetFiles={datasetFiles}
          setDatasetFiles={setDatasetFiles}
          dataUrl={dataUrl}
          setDataUrl={setDataUrl}
          apiUrl={apiUrl}
          setApiUrl={setApiUrl}
          apiServiceKey={apiServiceKey}
          setApiServiceKey={setApiServiceKey}
          apiPageNo={apiPageNo}
          setApiPageNo={setApiPageNo}
          apiNumOfRows={apiNumOfRows}
          setApiNumOfRows={setApiNumOfRows}
          apiResponseType={apiResponseType}
          setApiResponseType={setApiResponseType}
          apiResponseTypeParam={apiResponseTypeParam}
          setApiResponseTypeParam={setApiResponseTypeParam}
          apiParams={apiParams}
          setApiParams={setApiParams}
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
        <ResultsPanel result={result} loading={loading} progress={progress} />
      </main>

      <footer className="app-footer">
        <img className="footer-logo" src="/image/mois_logo.png" alt="행정안전부 로고" />
        <span className="footer-text">행정안전부 데이터정보화담당관</span>
      </footer>
    </div>
  );
}

export default App;
