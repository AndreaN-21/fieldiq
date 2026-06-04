import { useState } from "react";
import type { AnalysisResult } from "../types";
import { analyzeDefect } from "../services/api";
import "./DefectForm.css";

const MAX_CHARS = 2000;

const EXAMPLES = [
  "Large diagonal crack on the south facade, approximately 5mm wide, running from the window lintel to the corner. Appeared after last winter. The wall is load-bearing masonry.",
  "Moisture stains and white efflorescence on the basement wall, spreading over roughly 2 square metres. The wall feels damp to the touch. No visible cracks but paint is peeling.",
  "Spalling concrete on the underside of a first-floor slab — exposed rebar visible in two spots, each about 10cm diameter. Rust streaks running down the soffit. Building is from 1975.",
  "Hairline cracks forming a map pattern (crazing) across the exterior render of the east facade. Cracks are superficial but widespread. Noticed after a dry summer.",
];

interface Props {
  onResult: (result: AnalysisResult) => void;
}

export default function DefectForm({ onResult }: Props) {
  const [description, setDescription] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const remaining = MAX_CHARS - description.length;
  const canSubmit = description.length >= 20 && !loading;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const result = await analyzeDefect(description);
      onResult(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "An unexpected error occurred.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <form className="defect-form" onSubmit={handleSubmit}>
      <label className="defect-form__label" htmlFor="description">
        Defect description
      </label>

      <div className="defect-form__examples">
        <span className="defect-form__examples-label">Examples:</span>
        {EXAMPLES.map((ex, i) => (
          <button
            key={i}
            type="button"
            className="defect-form__example-btn"
            onClick={() => setDescription(ex)}
            disabled={loading}
          >
            {ex.slice(0, 48)}…
          </button>
        ))}
      </div>

      <div className="defect-form__textarea-wrap">
        <textarea
          id="description"
          className="defect-form__textarea"
          placeholder="Describe the observed defect: location, dimensions, appearance, when it was noticed..."
          value={description}
          onChange={(e) => setDescription(e.target.value.slice(0, MAX_CHARS))}
          rows={6}
          disabled={loading}
        />
        <span className={`defect-form__counter${remaining < 100 ? " defect-form__counter--warn" : ""}`}>
          {remaining} characters remaining
        </span>
      </div>

      {error && <p className="defect-form__error">{error}</p>}

      <button
        type="submit"
        className="defect-form__submit"
        disabled={!canSubmit}
      >
        {loading ? (
          <>
            <span className="defect-form__spinner" aria-hidden="true" />
            Analysing…
          </>
        ) : (
          "Analyse defect"
        )}
      </button>
    </form>
  );
}
