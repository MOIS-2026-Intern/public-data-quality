import { useState } from "react";
import { ControlPanel } from "./components/ControlPanel";
import { ResultsPanel } from "./components/ResultsPanel";
import { useAnalyzeForm } from "./hooks/useAnalyzeForm";
import { fetchAnalyzePayload } from "./lib/analyzeClient";
import { buildAnalyzeRequestBody, expectedSourceCount } from "./lib/analyzeRequest";
import { createInitialProgress, mergeProgressEvent } from "./lib/progress";

function App() {
  const form = useAnalyzeForm();
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState(() => ({
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
    jobId: "",
    jobStatus: "",
  }));

  async function handleAnalyze(event) {
    event.preventDefault();
    const request = form.values;
    const totalSources = expectedSourceCount(request);
    const updateProgress = (progressEvent) => {
      setProgress((currentProgress) => mergeProgressEvent(currentProgress, progressEvent, totalSources));
    };

    setLoading(true);
    setError("");
    setResult(null);
    setProgress(createInitialProgress(totalSources));

    try {
      const body = buildAnalyzeRequestBody(request);
      const payload = await fetchAnalyzePayload({
        body,
        expectedSourceCount: totalSources,
        onProgress: updateProgress,
      });
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
        <ControlPanel form={form} loading={loading} error={error} onSubmit={handleAnalyze} />
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
