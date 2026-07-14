export function splitLineValues(value) {
  return value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export function expectedSourceCount(request) {
  if (request.sourceType === "file") {
    return request.datasetFiles.length;
  }
  if (request.sourceType === "url") {
    return splitLineValues(request.dataUrl).length + request.urlListFiles.length || 1;
  }
  return 1;
}

function validateAnalyzeRequest(request, dataUrls) {
  if (request.sourceType === "file" && request.datasetFiles.length === 0) {
    throw new Error("분석할 파일을 먼저 업로드하세요.");
  }
  if (request.sourceType === "url" && dataUrls.length === 0 && request.urlListFiles.length === 0) {
    throw new Error("입력 URL 또는 URL 목록 파일을 한 개 이상 추가하세요.");
  }
  if (request.sourceType === "api" && !request.apiUrl.trim()) {
    throw new Error("호출 URL을 입력하세요.");
  }
  if (request.useLlm && !request.openAiApiKey.trim()) {
    throw new Error("OpenAI API Key를 입력하세요.");
  }
}

function appendCommonAnalyzeFields(body, request) {
  body.append("use_llm_agents", String(request.useLlm));
  if (request.useLlm && request.openAiApiKey.trim()) {
    body.append("openai_api_key", request.openAiApiKey.trim());
  }
  if (request.useLlm && request.llmFastModel) {
    body.append("llm_fast_model", request.llmFastModel);
  }
  if (request.useLlm && request.llmStrongModel) {
    body.append("llm_strong_model", request.llmStrongModel);
  }
}

export function buildAnalyzeRequestBody(request) {
  const dataUrls = splitLineValues(request.dataUrl);
  validateAnalyzeRequest(request, dataUrls);

  const body = new FormData();
  body.append("source_type", request.sourceType);

  if (request.sourceType === "file") {
    request.datasetFiles.forEach((datasetFile) => body.append("dataset_file", datasetFile));
  }

  if (request.sourceType === "url") {
    dataUrls.forEach((url) => body.append("data_url", url));
    request.urlListFiles.forEach((urlListFile) => body.append("url_list_file", urlListFile));
  }

  if (request.sourceType === "api") {
    body.append("api_url", request.apiUrl.trim());
    body.append("api_method", "GET");
    if (request.apiServiceKey.trim()) {
      body.append("service_key", request.apiServiceKey.trim());
    }
    if (request.apiPageNo.trim()) {
      body.append("page_no", request.apiPageNo.trim());
    }
    if (request.apiNumOfRows.trim()) {
      body.append("num_of_rows", request.apiNumOfRows.trim());
    }
    if (request.apiResponseType) {
      body.append("api_response_type", request.apiResponseType);
    }
    if (request.apiResponseTypeParam) {
      body.append("api_response_type_param", request.apiResponseTypeParam);
    }
    if (request.apiParams.trim()) {
      body.append("api_params", request.apiParams.trim());
    }
  }

  appendCommonAnalyzeFields(body, request);
  return body;
}
