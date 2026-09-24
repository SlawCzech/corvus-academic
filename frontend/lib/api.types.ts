// Hand-maintained mirror of the `app` service's response schemas.

export type FindingSeverity = "critical" | "major" | "minor"

export type FindingSource = "structure" | "methodology" | "requirements"

export interface Finding {
  section: string
  description: string
  severity: FindingSeverity
  suggestion: string
  // Which analysis raised it; absent on results stored before 2026-09-24.
  source?: FindingSource | null
}

export interface Score {
  criteria: string
  points: number
  max_points: number
}

export type ThesisType = "bachelor" | "master_article"
export type StudentStatus = "active" | "graduated" | "archived"

export interface Student {
  id: string
  promotor_id: string
  full_name: string
  index_number: string | null
  field_of_study: string
  thesis_type: ThesisType
  current_topic: string | null
  current_topic_set_at: string | null
  status: StudentStatus
  created_at: string
  updated_at: string
  /** When supervision ended — the start of the thesis files' retention clock. */
  closed_at: string | null
  /** The guideline set the thesis is judged against; null = the agent's defaults. */
  guideline_set_id: string | null
}

export interface MeetingNote {
  id: string
  student_id: string
  promotor_id: string
  occurred_at: string
  content: string
  source_action_id: string | null
  created_at: string
}

export interface ThesisDraft {
  id: string
  student_id: string
  version_number: number
  filename: string
  pages: number
  format: string
  char_count: number
  preview: string
  uploaded_by: string
  created_at: string
  /** Whether the original upload can still be downloaded. */
  has_file: boolean
  file_size: number | null
  file_sha256: string | null
  /** The version the promoter accepted as final. */
  is_accepted: boolean
  /** Set once the text and file are gone; the row stays as a trace. */
  purged_at: string | null
  /** When retention will purge this version, if it is scheduled at all. */
  purge_due_at: string | null
}

export type ActionType =
  | "propose_topic"
  | "evaluate_methodology"
  | "check_progress"
  | "draft_meeting_note"
  | "defence_questions"
  | "generate_review"

export type ActionStatus = "pending" | "running" | "completed" | "failed"

/** One proposed thesis topic. */
export interface ProposedTopic {
  title: string
  rationale?: string
  scope?: string
  risks?: string
}

/** One question for the defence. */
export interface DefenceQuestion {
  question: string
  rationale?: string
  section?: string
  focus?: string
}

/** One difference between two draft versions. */
export interface ProgressChange {
  area: string
  change: string
  assessment?: string
}

/**
 * The action-specific part of a result. Which keys are present depends on the
 * action that produced it.
 */
export interface ActionOutput {
  topics?: ProposedTopic[]
  recommended?: number
  questions?: DefenceQuestion[]
  summary?: string
  changes?: ProgressChange[]
  concerns?: string[]
  next_steps?: string[]
  content?: string
  topics_discussed?: string[]
  agreed_actions?: string[]
  recommendation?: string
  total_percentage?: number
}

/** The agent's whole payload for one finished action. */
export interface ActionResult {
  findings?: Finding[]
  /** Analysis branches that failed; the review was written without them. */
  node_errors?: string[]
  scores?: Score[]
  output?: ActionOutput
  summary?: string | null
  recommendation?: string | null
  status?: string
  error?: string | null
}

export interface AccessRequest {
  id: string
  email: string
  created_at: string
}

export interface RecentActivity {
  student_id: string
  student_name: string
  action_type: ActionType
  status: ActionStatus
  updated_at: string
}

export interface DashboardSummary {
  active_students: number
  without_topic: number
  actions_in_progress: number
  recent_activity: RecentActivity[]
}

export interface AgentAction {
  id: string
  student_id: string
  promotor_id: string
  action_type: ActionType
  status: ActionStatus
  task_id: string | null
  detail: string | null
  output: ActionResult | null
  error: string | null
  accepted: boolean
  accepted_at: string | null
  created_at: string
  updated_at: string
}

// ---------- guideline catalog ----------

export type GuidelineVersionStatus = "draft" | "published" | "superseded"

export interface University {
  id: string
  name: string
  short_name: string
}

export interface Thresholds {
  min_sources: number | null
  min_foreign_sources: number | null
  min_body_chars: number | null
  max_body_chars: number | null
}

export interface GuidelineVersionSummary {
  id: string
  version_no: number
  status: GuidelineVersionStatus
  effective_from: string | null
  published_at: string | null
  created_at: string
}

export interface GuidelineSource {
  filename: string
  sha256: string
  size: number
  downloadable: boolean
}

export interface GuidelineVersion extends GuidelineVersionSummary {
  set_id: string
  set_name: string
  thesis_type: ThesisType
  university: University
  rubric_md: string
  thresholds: Thresholds
  source: GuidelineSource | null
  created_by: string
  published_by: string | null
}

export interface GuidelineSet {
  id: string
  name: string
  thesis_type: ThesisType
  university: University
  /** The version in force; null while a set has only a draft. */
  current: GuidelineVersionSummary | null
  has_draft: boolean
}

export interface GuidelineSetDetail {
  id: string
  name: string
  thesis_type: ThesisType
  university: University
  /** Newest first. */
  versions: GuidelineVersionSummary[]
}

export interface LocalModel {
  name: string
  parameter_size: string | null
}

/** What a promoter may pick: installed models the admin has enabled. */
export interface ModelCatalog {
  /** The model an action runs on when none is picked. */
  default: string
  available: LocalModel[]
  /** False when the agent could not reach Ollama — `available` is then empty. */
  local_available: boolean
  /** Provider → the model a stored key runs on. */
  byok: Record<string, string>
}

export interface AdminModel {
  name: string
  parameter_size: string | null
  /** False when the server no longer has it — a setting left behind. */
  installed: boolean
  enabled: boolean
  is_default: boolean
}

export interface AdminModelCatalog {
  models: AdminModel[]
  local_available: boolean
  server_default: string
}

export interface ApiKeyStatus {
  configured: boolean
  provider: string | null
}
