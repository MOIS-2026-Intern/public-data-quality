import { useEffect, useState } from "react";
import { SummaryCard, displayValue } from "./components/common";
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
const JOB_POLL_INTERVAL_MS = 1500;
const JOB_TERMINAL_STATUSES = new Set(["completed", "partial_failed", "failed"]);

function splitLineValues(value) {
  return value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function isAnalyzePayload(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return false;
  }
  return ["batch", "summary", "results", "result", "error"].some((key) => key in value);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function ControlPanel({
  sourceType,
  setSourceType,
  datasetFiles,
  setDatasetFiles,
  urlListFiles,
  setUrlListFiles,
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
  const urlListFileCount = urlListFiles.length;
  const selectedUrlListLabel =
    urlListFileCount === 0
      ? "선택된 파일 없음"
      : urlListFileCount === 1
        ? urlListFiles[0].name
        : `${urlListFileCount}개 파일 선택됨`;
  const selectedUrlListTitle = urlListFiles.map((file) => file.name).join("\n");

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
            <>
              <label>
                <span className="control-label-title is-primary">입력 URL 목록</span>
                <textarea
                  rows={5}
                  value={dataUrl}
                  onChange={(event) => setDataUrl(event.target.value)}
                  placeholder={"https://...\nhttps://..."}
                  spellCheck={false}
                />
              </label>
              <div className="file-field">
                <span className="file-field-label">URL 목록 파일 업로드</span>
                <label className="file-picker">
                  <input
                    className="file-picker-input"
                    type="file"
                    multiple
                    accept=".txt,.csv,.tsv,.xlsx,.xls,text/plain,text/csv,text/tab-separated-values,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    onChange={(event) => setUrlListFiles(Array.from(event.target.files || []))}
                  />
                  <span className="file-picker-action">파일 선택</span>
                  <span className="file-picker-name" title={selectedUrlListTitle}>
                    {selectedUrlListLabel}
                  </span>
                </label>
                {urlListFileCount > 1 ? (
                  <div className="selected-files" aria-label="선택된 URL 목록 파일">
                    {urlListFiles.map((file) => (
                      <span className="selected-file" key={`${file.name}-${file.size}-${file.lastModified}`} title={file.name}>
                        {file.name}
                      </span>
                    ))}
                  </div>
                ) : null}
              </div>
            </>
          ) : null}

          {sourceType === "api" ? (
            <>
              <div className="api-field-stack">
                <label>
                  <span className="control-label-title is-primary">공공데이터 API URL</span>
                  <input
                    type="url"
                    value={apiUrl}
                    onChange={(event) => setApiUrl(event.target.value)}
                    placeholder="https://..."
                    spellCheck={false}
                  />
                </label>
                <label>
                  <span className="control-label-title is-secondary">Service Key</span>
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
                  <span className="control-label-title is-secondary">pageNo</span>
                  <input
                    value={apiPageNo}
                    onChange={(event) => setApiPageNo(event.target.value)}
                    inputMode="numeric"
                    placeholder="1"
                  />
                </label>
                <label>
                  <span className="control-label-title is-secondary">numOfRows</span>
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
                  <span className="control-label-title is-secondary">응답 형식</span>
                  <select value={apiResponseType} onChange={(event) => setApiResponseType(event.target.value)}>
                    <option value="json">JSON</option>
                    <option value="xml">XML</option>
                  </select>
                </label>
                <label>
                  <span className="control-label-title is-secondary">형식 파라미터</span>
                  <select value={apiResponseTypeParam} onChange={(event) => setApiResponseTypeParam(event.target.value)}>
                    <option value="_type">_type</option>
                    <option value="type">type</option>
                    <option value="returnType">returnType</option>
                    <option value="none">사용 안함</option>
                  </select>
                </label>
              </div>
              <label>
                <span className="control-label-title is-secondary">추가 파라미터</span>
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
      <SummaryCard label="오류/이상 탐지" value={summary.issue_finding_count ?? 0} />
      <SummaryCard label="수동 검토 필요" value={summary.manual_review_finding_count ?? 0} />
    </div>
  );
}

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

function FindingRowsTable({ rows, emptyText }) {
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
            <th className="finding-cell-nowrap">LLM 최종 검증</th>
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
                <td>{displayValue(finding.llm_final_verification)}</td>
                <td className="finding-cell-nowrap">{displayValue(formatRelatedColumns(finding))}</td>
              </tr>
            ))
          ) : (
            <tr>
              <td colSpan={10} className="finding-empty-cell">
                {emptyText}
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function FindingsTable({ findings, previewRows }) {
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
      <FindingRowsTable rows={activeSection.rows} emptyText={activeSection.emptyText} />
    </div>
  );
}

function reportDownloadUrl(result) {
  if (result?.summary?.error_report_download_path) return result.summary.error_report_download_path;
  const reportPath = result?.summary?.error_report_xlsx;
  if (!reportPath) return "";
  return `/api/reports/download?path=${encodeURIComponent(reportPath)}`;
}

function ResultContent({ result }) {
  if (!result) {
    return null;
  }

  return (
    <>
      <SummarySection summary={result.summary || {}} />
      {reportDownloadUrl(result) ? (
        <div className="report-actions">
          <a className="download-report-button" href={reportDownloadUrl(result)}>
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

function BatchReportActions({ result }) {
  const downloadUrl = reportDownloadUrl(result);
  if (!downloadUrl) return null;

  return (
    <div className="report-actions">
      <a className="download-report-button" href={downloadUrl}>
        전체 오류 리포트 다운로드
      </a>
    </div>
  );
}

function batchItemName(item, index) {
  return item?.filename || item?.result?.summary?.dataset_name || `데이터 ${index + 1}`;
}

function filteredBatchEntries(items, searchQuery) {
  const query = searchQuery.trim().toLowerCase();
  return items
    .map((item, index) => ({ item, index, name: batchItemName(item, index) }))
    .filter(({ item, name }) => {
      if (!query) return true;
      const datasetName = item?.result?.summary?.dataset_name || "";
      return `${name} ${datasetName}`.toLowerCase().includes(query);
    });
}

function BatchDatasetSelector({ items, activeIndex, searchQuery, setSearchQuery, onSelect }) {
  const entries = filteredBatchEntries(items, searchQuery);

  return (
    <aside className="batch-dataset-panel" aria-label="데이터셋 목록">
      <div className="batch-dataset-header">
        <div>
          <span>데이터셋 목록</span>
          <strong>{items.length.toLocaleString("ko-KR")}개</strong>
        </div>
      </div>
      <input
        className="batch-dataset-search"
        type="search"
        value={searchQuery}
        onChange={(event) => setSearchQuery(event.target.value)}
        placeholder="파일명 검색"
        aria-label="데이터셋 파일명 검색"
      />
      <div className="batch-dataset-list" role="listbox" aria-label="분석 결과 데이터셋">
        {entries.length ? (
          entries.map(({ item, index, name }) => {
            const summary = item.result?.summary || {};
            return (
              <button
                className={`batch-dataset-row ${index === activeIndex ? "is-active" : ""} ${item.ok ? "" : "is-error"}`}
                type="button"
                role="option"
                aria-selected={index === activeIndex}
                title={name}
                key={`${name}-${index}`}
                onClick={() => onSelect(index)}
              >
                <span className="batch-dataset-name">{name}</span>
                {item.ok ? (
                  <span className="batch-dataset-metrics">
                    <span>오류 {displayValue(summary.issue_finding_count ?? 0)}</span>
                    <span>검토 {displayValue(summary.manual_review_finding_count ?? 0)}</span>
                    <span>행 {displayValue(summary.row_count ?? "-")}</span>
                  </span>
                ) : (
                  <span className="batch-dataset-status">실패</span>
                )}
              </button>
            );
          })
        ) : (
          <div className="batch-dataset-empty">검색 결과가 없습니다.</div>
        )}
      </div>
    </aside>
  );
}

function ResultsPanel({ result, loading, progress }) {
  const isBatch = Boolean(result?.batch);
  const batchItems = isBatch ? result.results || [] : [];
  const singleResult = !isBatch ? result?.result || result?.results?.[0]?.result || null : null;
  const [activeBatchIndex, setActiveBatchIndex] = useState(0);
  const [batchSearchQuery, setBatchSearchQuery] = useState("");
  const activeBatchItem = batchItems[activeBatchIndex] || batchItems[0] || null;

  useEffect(() => {
    setActiveBatchIndex(0);
    setBatchSearchQuery("");
  }, [result]);

  useEffect(() => {
    if (!isBatch || !batchItems.length) return;
    if (activeBatchIndex >= batchItems.length) {
      setActiveBatchIndex(0);
      return;
    }
    const entries = filteredBatchEntries(batchItems, batchSearchQuery);
    if (entries.length && !entries.some((entry) => entry.index === activeBatchIndex)) {
      setActiveBatchIndex(entries[0].index);
    }
  }, [activeBatchIndex, batchItems, batchItems.length, batchSearchQuery, isBatch]);

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
          {batchItems.length ? (
            <div className="batch-result-shell">
              <BatchReportActions result={result} />
              <BatchDatasetSelector
                items={batchItems}
                activeIndex={activeBatchIndex}
                searchQuery={batchSearchQuery}
                setSearchQuery={setBatchSearchQuery}
                onSelect={setActiveBatchIndex}
              />
              <div className="batch-active-detail">
                {activeBatchItem?.ok && activeBatchItem.result ? (
                  <ResultContent result={activeBatchItem.result} />
                ) : (
                  <div className="failed-file">
                    <strong>{batchItemName(activeBatchItem, activeBatchIndex)}</strong>
                    <span>{activeBatchItem?.error || "분석 실패"}</span>
                  </div>
                )}
              </div>
            </div>
          ) : null}
        </>
      ) : (
        <ResultContent result={singleResult} />
      )}
    </section>
  );
}

function App() {
  const [sourceType, setSourceType] = useState("file");
  const [datasetFiles, setDatasetFiles] = useState([]);
  const [urlListFiles, setUrlListFiles] = useState([]);
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
    if (sourceType === "url") return splitLineValues(dataUrl).length + urlListFiles.length || 1;
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
        jobId: event.job_id || event.jobId || currentProgress.jobId || "",
        jobStatus: event.job_status || event.jobStatus || currentProgress.jobStatus || "",
        history,
      };
    });
  }

  function appendCommonAnalyzeFields(body, useLlmForRequest) {
    body.append("use_llm_agents", String(useLlmForRequest));
    if (useLlmForRequest && openAiApiKey.trim()) body.append("openai_api_key", openAiApiKey.trim());
    if (useLlmForRequest && llmFastModel) body.append("llm_fast_model", llmFastModel);
    if (useLlmForRequest && llmStrongModel) body.append("llm_strong_model", llmStrongModel);
  }

  async function parseJsonResponse(response) {
    const responseText = await response.text();
    if (!responseText.trim()) return null;
    try {
      return JSON.parse(responseText);
    } catch {
      throw new Error(responseText || "분석 응답 형식이 올바르지 않습니다.");
    }
  }

  function jobProgressEvent(job, fallbackMessage = "분석 중") {
    const total = Number(job?.total_items || job?.items?.length || expectedSourceCount() || 1);
    const processed = Number(job?.processed_items || 0);
    const runningItem = (job?.items || []).find((item) => item.status === "running");
    const latestItem = runningItem || (job?.items || []).find((item) => item.status === "queued") || (job?.items || [])[0];
    const terminal = JOB_TERMINAL_STATUSES.has(job?.status);
    const percent = terminal
      ? 100
      : total > 0 && processed > 0
        ? Math.min(99, Math.round((processed / total) * 100))
        : job?.status === "running"
          ? 10
          : 3;
    const statusLabel =
      job?.status === "queued"
        ? "업로드 중"
        : job?.status === "running"
          ? "분석 중"
          : job?.status === "completed"
            ? "분석 완료"
            : job?.status === "partial_failed"
              ? "일부 분석 실패"
              : job?.status === "failed"
                ? "분석 실패"
                : fallbackMessage;

    return {
      type: "progress",
      progress: percent,
      current: processed,
      total,
      filename: latestItem?.display_name || latestItem?.dataset_name || "",
      job_id: job?.job_id || "",
      job_status: job?.status || "",
      message: statusLabel,
    };
  }

  async function pollAnalyzeJob(initialJob) {
    let job = initialJob;
    updateProgress(jobProgressEvent(job, "작업 등록됨"));

    while (true) {
      await sleep(JOB_POLL_INTERVAL_MS);
      const response = await fetch(`/api/jobs/${encodeURIComponent(job.job_id)}/result`);
      const payload = await parseJsonResponse(response);

      if (!response.ok && response.status !== 202) {
        throw new Error(payload?.error || "분석 상태 조회에 실패했습니다.");
      }
      if (response.status === 202) {
        job = payload?.job || job;
        updateProgress(jobProgressEvent(job));
        continue;
      }
      if (!payload || !isAnalyzePayload(payload)) {
        throw new Error("분석 응답 형식이 올바르지 않습니다.");
      }
      updateProgress(jobProgressEvent({ ...job, status: "completed", processed_items: job.total_items || 1 }));
      if (payload.error && !payload.batch) {
        throw new Error(payload.error);
      }
      return payload;
    }
  }

  async function fetchAnalyzePayload(body) {
    const response = await fetch("/api/analyze", {
      method: "POST",
      body,
    });
    const payload = await parseJsonResponse(response);

    if (!response.ok && response.status !== 202) {
      throw new Error(payload?.error || "분석 요청에 실패했습니다.");
    }
    if (response.status === 202 || payload?.job) {
      if (!payload?.job?.job_id) {
        throw new Error("분석 작업 ID를 받지 못했습니다.");
      }
      return pollAnalyzeJob(payload.job);
    }
    if (!payload || !isAnalyzePayload(payload)) {
      throw new Error("분석 응답 형식이 올바르지 않습니다.");
    }
    if (payload.error && !payload.batch) {
      throw new Error(payload.error);
    }
    return payload;
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
      if (sourceType === "url" && dataUrls.length === 0 && urlListFiles.length === 0) {
        throw new Error("입력 URL 또는 URL 목록 파일을 한 개 이상 추가하세요.");
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
        urlListFiles.forEach((urlListFile) => body.append("url_list_file", urlListFile));
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
      appendCommonAnalyzeFields(body, useLlmForRequest);

      const payload = await fetchAnalyzePayload(body);
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
          urlListFiles={urlListFiles}
          setUrlListFiles={setUrlListFiles}
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
