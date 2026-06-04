export type Severity = "Critical" | "High" | "Medium" | "Low";

export interface NormReference {
  title: string;
  article: string;
  excerpt: string;
  source_url: string;
}

export interface AnalysisResult {
  defect_type: string;
  affected_component: string;
  likely_cause: string;
  severity: Severity;
  severity_justification: string;
  norm_references: NormReference[];
  report_template: string;
  disclaimer: string;
}

export interface AnalyzeRequest {
  description: string;
}
