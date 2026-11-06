// Hand-maintained mirror of the `app` service's response schemas.

export type FindingSeverity = "critical" | "major" | "minor"

export type FindingSource = "structure" | "methodology" | "requirements" | "coherence"

export interface Finding {
  section: string
  description: string
  severity: FindingSeverity
  suggestion: string
  // Which analysis raised it; absent on results stored before 2026-09-24.
  source?: FindingSource | null
  // The passage of the thesis it rests on, verbatim and checked against the
  // text by the agent; "" for an absence, missing on older results.
  quote?: string
}

export interface Score {
  criteria: string
  points: number
  max_points: number
}

export type ThesisType = "bachelor" | "master" | "master_article"
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
  research_area: string | null
  research_aim: string | null
  status: StudentStatus
  created_at: string
  updated_at: string
  /** When supervision ended — the start of the thesis files' retention clock. */
  closed_at: string | null
  /** The guideline set the thesis is judged against; null = the agent's defaults. */
  guideline_set_id: string | null
  /** A thesis reviewed once, with nobody supervised: it lives under /reviews. */
  is_one_off: boolean
}

/** A one-off review as the history lists it. */
export interface Review {
  id: string
  full_name: string
  field_of_study: string
  thesis_type: ThesisType
  current_topic: string | null
  created_at: string
  filename: string
  /** Set once the thesis text and file are gone; the results stay. */
  purged_at: string | null
  /** When retention will remove the thesis text and file. */
  purge_due_at: string | null
}

/** Read off a title page for the promoter to check; null for what was not found. */
export interface TitlePageSuggestion {
  full_name: string | null
  field_of_study: string | null
  thesis_type: ThesisType | null
  current_topic: string | null
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
  | "draft_student_email"
  | "defence_questions"
  | "generate_review"
  | "trial_review"
  | "verify_bibliography"
  | "review_fragment"

export type ActionStatus =
  | "pending"
  | "running"
  // A review paused for the promoter to pick the findings it may use.
  | "awaiting_input"
  | "completed"
  | "failed"
  | "cancelled"

/** One proposed thesis topic. */
export interface ProposedTopic {
  title: string
  rationale?: string
  scope?: string
  risks?: string
}

/**
 * One question for the defence. Results saved before the questions became
 * general also carry `rationale`, `section` and `focus`.
 */
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
/** What the bibliography check established about one entry. */
export type ReferenceStatus =
  | "verified"
  | "mismatch"
  | "not_indexed"
  | "suspicious"
  | "website"
  | "unchecked"

export interface CheckedReference {
  entry: string
  status: ReferenceStatus
  note: string
  doi: string
}

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
  subject?: string
  body?: string
  recommendation?: string
  total_percentage?: number
  references?: CheckedReference[]
  counts?: Partial<Record<ReferenceStatus, number>>
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

/** An action still pending or running — really, or dead and waiting to be cancelled. */
export interface ActionInProgress {
  id: string
  student_id: string
  student_name: string
  action_type: ActionType
  status: ActionStatus
  created_at: string
  updated_at: string
}

/** A fragment the promoter still owes an answer. */
export interface FragmentAwaiting {
  fragment_id: string
  student_id: string
  student_name: string
  part_name: string
  round_number: number
  received_on: string
}

/** A part past its deadline, with nothing handed in for it since. */
export interface PartOverdue {
  part_id: string
  student_id: string
  student_name: string
  part_name: string
  due_on: string
}

export interface DashboardSummary {
  active_students: number
  without_topic: number
  actions_in_progress: number
  /** Of those, the ones paused until the promoter answers. */
  awaiting_input: ActionInProgress[]
  recent_activity: RecentActivity[]
  awaiting_feedback: FragmentAwaiting[]
  overdue_parts: PartOverdue[]
}

// The agent's graph steps for a running action, and those already finished.
export interface ActionProgress {
  steps: string[]
  done: string[]
}

export type ActionErrorCode =
  | "provider_no_credits"
  | "provider_key_rejected"
  | "provider_rate_limited"

export interface TokenCounts {
  input_tokens: number
  output_tokens: number
  total_tokens: number
}

/** What an action spent, as the provider reported it; totals and by model. */
export interface TokenUsage extends TokenCounts {
  by_model: Record<string, TokenCounts>
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
  // Set when the promoter can fix the failure themselves.
  error_code?: ActionErrorCode | null
  /** The provider whose account ran it; null for a local model. */
  provider?: string | null
  /** Null before the agent reports any, and for actions older than the count. */
  usage?: TokenUsage | null
  accepted: boolean
  accepted_at: string | null
  created_at: string
  updated_at: string
  // Unfinished actions only.
  progress?: ActionProgress | null
}

// ---------- parts and fragments ----------

export type FragmentVerdict = "on_track" | "needs_changes" | "needs_additions"

export type PartState = FragmentVerdict | "not_submitted" | "awaiting_feedback"

/** What `review_fragment` returns: a summary and a draft, never a grade. */
export interface FragmentReview {
  summary: string
  answer: string
  direction: FragmentVerdict
  strengths: string[]
  changes: { point: string; quote: string }[]
  additions: string[]
  addressed: string[]
  next_step: string
}

export interface ThesisPart {
  id: string
  student_id: string
  name: string
  position: number
  due_on: string | null
}

export interface PartEntry extends ThesisPart {
  rounds: number
  state: PartState
}

export interface Fragment {
  id: string
  student_id: string
  part_id: string
  round_number: number
  received_on: string
  question: string | null
  filename: string | null
  format: string
  pages: number
  char_count: number
  preview: string
  has_file: boolean
  purged_at: string | null
  review_action_id: string | null
  /** Null until the promoter has answered. */
  verdict: FragmentVerdict | null
  feedback: string | null
  feedback_at: string | null
  created_at: string
}

export interface FragmentEntry extends Fragment {
  part_name: string
  /** Lives in the AI run; null without one. */
  summary: string | null
  review: AgentAction | null
}

export interface TimelineEvent {
  kind: "fragment" | "note" | "draft"
  on: string
  fragment: FragmentEntry | null
  note: MeetingNote | null
  draft: ThesisDraft | null
}

export interface Timeline {
  parts: PartEntry[]
  events: TimelineEvent[]
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
  /** The model is drafting the rubric from the source (ADR 0024). */
  drafting?: boolean
  /** Why the last draft failed, until the next one. */
  drafting_error?: string | null
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

/** Provider → the model a stored key for it runs on. */
export interface ModelCatalog {
  byok: Record<string, string>
}

export interface ApiKeyStatus {
  configured: boolean
  /** Every provider the promoter has a key for — one key per provider. */
  providers: string[]
}

export interface ApiKeySaved extends ApiKeyStatus {
  // False when the provider could not be asked; the key is stored unchecked.
  verified: boolean
}
