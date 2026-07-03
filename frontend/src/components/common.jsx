import { formatFindingType } from "../lib/formatters";

export function displayValue(value) {
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "number") return Number.isFinite(value) ? value.toLocaleString("ko-KR") : "-";
  if (typeof value === "string" || typeof value === "boolean") return String(value);
  if (Array.isArray(value)) return value.length ? value.map(displayValue).join(", ") : "-";
  if (typeof value === "object") {
    const entries = Object.entries(value);
    return entries.length ? entries.map(([key, nestedValue]) => `${key}: ${displayValue(nestedValue)}`).join(" / ") : "-";
  }
  return String(value);
}

export function SummaryCard({ label, value }) {
  const renderedValue = displayValue(value);
  return (
    <div className="summary-card">
      <div className="summary-label">{label}</div>
      <div className="summary-value" title={renderedValue}>
        {renderedValue}
      </div>
    </div>
  );
}

export function FindingTypeBadge({ finding }) {
  const kind = finding.finding_type === "manual_review" ? "manual-review" : "issue";
  return <span className={`finding-badge finding-badge-${kind}`}>{formatFindingType(finding)}</span>;
}
