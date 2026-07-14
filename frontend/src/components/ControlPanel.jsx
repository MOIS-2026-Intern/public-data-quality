const SOURCE_TYPES = [
  { id: "file", label: "파일 업로드" },
  { id: "url", label: "URL 입력" },
  { id: "api", label: "API 호출" },
];

export function ControlPanel({ form, loading, error, onSubmit }) {
  const { values, actions } = form;
  const fileCount = values.datasetFiles.length;
  const selectedFileLabel =
    fileCount === 0 ? "선택된 파일 없음" : fileCount === 1 ? values.datasetFiles[0].name : `${fileCount}개 파일 선택됨`;
  const selectedFileTitle = values.datasetFiles.map((file) => file.name).join("\n");
  const urlListFileCount = values.urlListFiles.length;
  const selectedUrlListLabel =
    urlListFileCount === 0
      ? "선택된 파일 없음"
      : urlListFileCount === 1
        ? values.urlListFiles[0].name
        : `${urlListFileCount}개 파일 선택됨`;
  const selectedUrlListTitle = values.urlListFiles.map((file) => file.name).join("\n");

  return (
    <section className="control-panel">
      <form onSubmit={onSubmit}>
        <div className="control-section">
          <div className="source-tabs" role="tablist" aria-label="데이터 입력 방식">
            {SOURCE_TYPES.map((source) => (
              <button
                className={`source-tab ${values.sourceType === source.id ? "is-active" : ""}`}
                type="button"
                role="tab"
                aria-selected={values.sourceType === source.id}
                key={source.id}
                onClick={() => actions.setSourceType(source.id)}
              >
                {source.label}
              </button>
            ))}
          </div>
        </div>

        <div className="control-section control-section-input">
          {values.sourceType === "file" ? (
            <div className="file-field">
              <span className="file-field-label">파일 업로드</span>
              <label className="file-picker">
                <input
                  className="file-picker-input"
                  type="file"
                  multiple
                  accept=".csv,.tsv,.txt,.xlsx,.xls,.json,.jsonl,.xml,.zip,text/csv,text/tab-separated-values,application/json,application/xml,text/xml,application/zip,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                  onChange={(event) => actions.setDatasetFiles(Array.from(event.target.files || []))}
                />
                <span className="file-picker-action">파일 선택</span>
                <span className="file-picker-name" title={selectedFileTitle}>
                  {selectedFileLabel}
                </span>
              </label>
              {fileCount > 1 ? (
                <div className="selected-files" aria-label="선택된 파일">
                  {values.datasetFiles.map((file) => (
                    <span className="selected-file" key={`${file.name}-${file.size}-${file.lastModified}`} title={file.name}>
                      {file.name}
                    </span>
                  ))}
                </div>
              ) : null}
            </div>
          ) : null}

          {values.sourceType === "url" ? (
            <>
              <label>
                <span className="control-label-title is-primary">입력 URL 목록</span>
                <textarea
                  rows={5}
                  value={values.dataUrl}
                  onChange={(event) => actions.setDataUrl(event.target.value)}
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
                    onChange={(event) => actions.setUrlListFiles(Array.from(event.target.files || []))}
                  />
                  <span className="file-picker-action">파일 선택</span>
                  <span className="file-picker-name" title={selectedUrlListTitle}>
                    {selectedUrlListLabel}
                  </span>
                </label>
                {urlListFileCount > 1 ? (
                  <div className="selected-files" aria-label="선택된 URL 목록 파일">
                    {values.urlListFiles.map((file) => (
                      <span className="selected-file" key={`${file.name}-${file.size}-${file.lastModified}`} title={file.name}>
                        {file.name}
                      </span>
                    ))}
                  </div>
                ) : null}
              </div>
            </>
          ) : null}

          {values.sourceType === "api" ? (
            <>
              <div className="api-field-stack">
                <label>
                  <span className="control-label-title is-primary">공공데이터 API URL</span>
                  <input
                    type="url"
                    value={values.apiUrl}
                    onChange={(event) => actions.setApiUrl(event.target.value)}
                    placeholder="https://..."
                    spellCheck={false}
                  />
                </label>
                <label>
                  <span className="control-label-title is-secondary">Service Key</span>
                  <input
                    type="password"
                    value={values.apiServiceKey}
                    onChange={(event) => actions.setApiServiceKey(event.target.value)}
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
                    value={values.apiPageNo}
                    onChange={(event) => actions.setApiPageNo(event.target.value)}
                    inputMode="numeric"
                    placeholder="1"
                  />
                </label>
                <label>
                  <span className="control-label-title is-secondary">numOfRows</span>
                  <input
                    value={values.apiNumOfRows}
                    onChange={(event) => actions.setApiNumOfRows(event.target.value)}
                    inputMode="numeric"
                    placeholder="100"
                  />
                </label>
              </div>
              <div className="api-grid-row">
                <label>
                  <span className="control-label-title is-secondary">응답 형식</span>
                  <select value={values.apiResponseType} onChange={(event) => actions.setApiResponseType(event.target.value)}>
                    <option value="json">JSON</option>
                    <option value="xml">XML</option>
                  </select>
                </label>
                <label>
                  <span className="control-label-title is-secondary">형식 파라미터</span>
                  <select
                    value={values.apiResponseTypeParam}
                    onChange={(event) => actions.setApiResponseTypeParam(event.target.value)}
                  >
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
                  value={values.apiParams}
                  onChange={(event) => actions.setApiParams(event.target.value)}
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
              value={values.openAiApiKey}
              onChange={(event) => actions.setOpenAiApiKey(event.target.value)}
              placeholder="sk-..."
              autoComplete="off"
              spellCheck={false}
            />
          </label>
          <label>
            빠른 라우팅 모델
            <input
              value={values.llmFastModel}
              onChange={(event) => actions.setLlmFastModel(event.target.value)}
              placeholder="예: gpt-4o-mini"
            />
          </label>
          <label>
            정밀 검증 모델
            <input
              value={values.llmStrongModel}
              onChange={(event) => actions.setLlmStrongModel(event.target.value)}
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
