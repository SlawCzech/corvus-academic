// Auto-generated from gateway OpenAPI schema via `npm run gen-types`.
// Manually maintained until the gateway is running locally.

export type FindingSeverity = "critical" | "major" | "minor"

export interface Finding {
  section: string
  description: string
  severity: FindingSeverity
  suggestion: string
}

export interface Score {
  criteria: string
  points: number
  max_points: number
}

export interface AnalysisResult {
  evaluation_id: string
  findings: Finding[]
  scores: Score[]
  summary: string | null
  recommendation: string | null
  status: string
  error: string | null
}

export interface TaskStatusResponse {
  status: string
  result: AnalysisResult | null
}
