const JOB_POLL_INTERVAL_MS = 1500;
const JOB_TERMINAL_STATUSES = new Set(["completed", "partial_failed", "failed"]);

function isAnalyzePayload(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return false;
  }
  return ["batch", "summary", "results", "result", "error"].some((key) => key in value);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export function shouldUseAnalyzeStream() {
  const runtimeFlag = String(import.meta.env.VITE_VERCEL || import.meta.env.VITE_DEPLOYMENT_TARGET || "")
    .trim()
    .toLowerCase();

  if (runtimeFlag === "1" || runtimeFlag === "true" || runtimeFlag === "vercel") {
    return true;
  }
  if (typeof window === "undefined") {
    return false;
  }
  return (window.location.hostname || "").toLowerCase().endsWith(".vercel.app");
}

async function parseJsonResponse(response) {
  const responseText = await response.text();
  if (!responseText.trim()) {
    return null;
  }
  try {
    return JSON.parse(responseText);
  } catch {
    throw new Error(responseText || "분석 응답 형식이 올바르지 않습니다.");
  }
}

function applyAnalyzeStreamEvent(event, state, onProgress) {
  if (event.type === "progress" || event.type === "file_done" || event.type === "file_error" || event.type === "final") {
    onProgress(event);
  }
  if (event.type === "file_error" && event.error) {
    state.streamError = event.error;
  }
  if (event.type === "final") {
    state.finalPayload = event.payload ?? null;
  }
}

function parseAnalyzeStreamText(text, state, onProgress) {
  for (const line of text.split("\n")) {
    if (!line.trim()) {
      continue;
    }
    applyAnalyzeStreamEvent(JSON.parse(line), state, onProgress);
  }
}

async function parseAnalyzeStream(response, onProgress) {
  const state = { finalPayload: null, streamError: "" };

  if (!response.body) {
    parseAnalyzeStreamText(await response.text(), state, onProgress);
  } else {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) {
        break;
      }

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";
      for (const line of lines) {
        if (!line.trim()) {
          continue;
        }
        applyAnalyzeStreamEvent(JSON.parse(line), state, onProgress);
      }
    }

    buffer += decoder.decode();
    if (buffer.trim()) {
      applyAnalyzeStreamEvent(JSON.parse(buffer), state, onProgress);
    }
  }

  if (state.finalPayload?.error) {
    throw new Error(state.finalPayload.error);
  }
  if (!state.finalPayload && state.streamError) {
    throw new Error(state.streamError);
  }
  return state.finalPayload;
}

function jobProgressEvent(job, expectedTotal, fallbackMessage = "분석 중") {
  const total = Number(job?.total_items || job?.items?.length || expectedTotal || 1);
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

async function pollAnalyzeJob(initialJob, { expectedSourceCount, onProgress }) {
  let job = initialJob;
  onProgress(jobProgressEvent(job, expectedSourceCount, "작업 등록됨"));

  while (true) {
    await sleep(JOB_POLL_INTERVAL_MS);
    const response = await fetch(`/api/jobs/${encodeURIComponent(job.job_id)}/result`);
    const payload = await parseJsonResponse(response);

    if (!response.ok && response.status !== 202) {
      throw new Error(payload?.error || "분석 상태 조회에 실패했습니다.");
    }
    if (response.status === 202) {
      job = payload?.job || job;
      onProgress(jobProgressEvent(job, expectedSourceCount));
      continue;
    }
    if (!payload || !isAnalyzePayload(payload)) {
      throw new Error("분석 응답 형식이 올바르지 않습니다.");
    }
    onProgress(jobProgressEvent({ ...job, status: "completed", processed_items: job.total_items || 1 }, expectedSourceCount));
    if (payload.error && !payload.batch) {
      throw new Error(payload.error);
    }
    return payload;
  }
}

async function fetchAnalyzeStreamPayload(body, onProgress) {
  const response = await fetch("/api/analyze-stream", {
    method: "POST",
    body,
  });

  if (!response.ok) {
    const responseText = await response.text();
    let payload = null;
    try {
      payload = responseText.trim() ? JSON.parse(responseText) : null;
    } catch {
      payload = null;
    }
    throw new Error(payload?.error || responseText || "분석 요청에 실패했습니다.");
  }

  const payload = await parseAnalyzeStream(response, onProgress);
  if (!payload || !isAnalyzePayload(payload)) {
    throw new Error("분석 응답 형식이 올바르지 않습니다.");
  }
  if (payload.error && !payload.batch) {
    throw new Error(payload.error);
  }
  return payload;
}

export async function fetchAnalyzePayload({ body, expectedSourceCount, onProgress }) {
  if (shouldUseAnalyzeStream()) {
    return fetchAnalyzeStreamPayload(body, onProgress);
  }

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
    return pollAnalyzeJob(payload.job, { expectedSourceCount, onProgress });
  }
  if (!payload || !isAnalyzePayload(payload)) {
    throw new Error("분석 응답 형식이 올바르지 않습니다.");
  }
  if (payload.error && !payload.batch) {
    throw new Error(payload.error);
  }
  return payload;
}
