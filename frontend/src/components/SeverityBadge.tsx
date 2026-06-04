import type { Severity } from "../types";
import "./SeverityBadge.css";

interface Props {
  severity: Severity;
  justification: string;
}

const COLORS: Record<Severity, string> = {
  Critical: "#dc2626",
  High: "#ea580c",
  Medium: "#ca8a04",
  Low: "#16a34a",
};

export default function SeverityBadge({ severity, justification }: Props) {
  return (
    <div className="severity-badge">
      <span
        className="severity-badge__label"
        style={{ backgroundColor: COLORS[severity] }}
      >
        {severity}
      </span>
      <p className="severity-badge__justification">{justification}</p>
    </div>
  );
}
