export function createInitialProgress(total) {
  return {
    visible: true,
    percent: 0,
    message: "업로드 중",
    current: 0,
    total,
    filename: "",
    stageLabel: "",
    stageIndex: 0,
    stageTotal: 0,
    stages: [],
    history: [{ message: "업로드 중" }],
    jobId: "",
    jobStatus: "",
  };
}

export function mergeProgressEvent(currentProgress, event, fallbackTotal) {
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
    total: Number(event.total) || fallbackTotal,
    filename: event.filename || currentProgress.filename || "",
    stageLabel: event.stage_label || event.stageLabel || currentProgress.stageLabel || "",
    stageIndex: Number(event.stage_index ?? currentProgress.stageIndex ?? 0),
    stageTotal: Number(event.stage_total ?? currentProgress.stageTotal ?? 0),
    stages: Array.isArray(event.stages) ? event.stages : currentProgress.stages || [],
    jobId: event.job_id || event.jobId || currentProgress.jobId || "",
    jobStatus: event.job_status || event.jobStatus || currentProgress.jobStatus || "",
    history,
  };
}
