import { useState } from "react";
import type { AnalysisResult as AnalysisResultType } from "../types";
import NormReference from "./NormReference";
import SeverityBadge from "./SeverityBadge";
import "./AnalysisResult.css";

interface Props {
  result: AnalysisResultType;
}

export default function AnalysisResult({ result }: Props) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(result.report_template);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <section className="analysis">
      <div className="analysis__card">
        <div className="analysis__row">
          <div>
            <h3 className="analysis__label">Defect type</h3>
            <p className="analysis__value">{result.defect_type}</p>
          </div>
          <div>
            <h3 className="analysis__label">Affected component</h3>
            <p className="analysis__value">{result.affected_component}</p>
          </div>
        </div>

        <div>
          <h3 className="analysis__label">Likely cause</h3>
          <p className="analysis__text">{result.likely_cause}</p>
        </div>

        <div>
          <h3 className="analysis__label">Severity</h3>
          <SeverityBadge
            severity={result.severity}
            justification={result.severity_justification}
          />
        </div>
      </div>

      {result.norm_references.length > 0 && (
        <div className="analysis__section">
          <h3 className="analysis__section-title">Applicable Standards</h3>
          <div className="analysis__norms">
            {result.norm_references.slice(0, 3).map((ref, i) => (
              <NormReference key={i} reference={ref} />
            ))}
          </div>
        </div>
      )}

      <div className="analysis__section">
        <div className="analysis__section-header">
          <h3 className="analysis__section-title">Report Template</h3>
          <button className="analysis__copy-btn" onClick={handleCopy}>
            {copied ? "Copied!" : "Copy to clipboard"}
          </button>
        </div>
        <pre className="analysis__template">{result.report_template}</pre>
      </div>

      <p className="analysis__disclaimer">{result.disclaimer}</p>
    </section>
  );
}
