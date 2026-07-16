import { useEffect, useState } from "react";
import { displayValue } from "./common";
import { getColumnErrorReportDownloadUrl, getReportDownloadUrl, ResultContent } from "./ResultContent";

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

function batchItemName(item, index) {
  return item?.filename || item?.result?.summary?.dataset_name || `데이터 ${index + 1}`;
}

function filteredBatchEntries(items, searchQuery) {
  const query = searchQuery.trim().toLowerCase();
  return items
    .map((item, index) => ({ item, index, name: batchItemName(item, index) }))
    .filter(({ item, name }) => {
      if (!query) {
        return true;
      }
      const datasetName = item?.result?.summary?.dataset_name || "";
      return `${name} ${datasetName}`.toLowerCase().includes(query);
    });
}

function BatchReportActions({ result }) {
  const downloadUrl = getReportDownloadUrl(result);
  const columnErrorDownloadUrl = getColumnErrorReportDownloadUrl(result);
  if (!downloadUrl && !columnErrorDownloadUrl) {
    return null;
  }

  return (
    <div className="report-actions">
      {downloadUrl ? (
        <a className="download-report-button" href={downloadUrl}>
          전체 오류 리포트 다운로드
        </a>
      ) : null}
      {columnErrorDownloadUrl ? (
        <a className="download-report-button" href={columnErrorDownloadUrl}>
          컬럼별 데이터 오류 다운로드
        </a>
      ) : null}
    </div>
  );
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

export function ResultsPanel({ result, loading, progress }) {
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
    if (!isBatch || !batchItems.length) {
      return;
    }
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
