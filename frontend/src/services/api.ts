import type { AnalysisResult } from "../types";

const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export async function analyzeDefect(description: string): Promise<AnalysisResult> {
  const response = await fetch(`${API_BASE}/api/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ description }),
  });

  if (response.status === 422) {
    const body = await response.json().catch(() => ({}));
    const detail = body?.detail?.[0]?.msg ?? "Description is too short or too long.";
    throw new Error(detail);
  }

  if (response.status === 503) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body?.detail ?? "AI analysis service is temporarily unavailable.");
  }

  if (!response.ok) {
    throw new Error(`Unexpected error (HTTP ${response.status}). Please retry.`);
  }

  return response.json() as Promise<AnalysisResult>;
}
