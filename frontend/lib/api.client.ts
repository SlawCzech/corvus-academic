import type {
  AdminModelCatalog,
  AgentAction,
  ActionType,
  Fragment,
  FragmentVerdict,
  GuidelineSetDetail,
  GuidelineVersion,
  MeetingNote,
  Student,
  StudentStatus,
  ThesisDraft,
  ThesisPart,
  Thresholds,
  ThesisType,
  University,
} from "./api.types"

/**
 * Renew the session, at most once at a time.
 *
 * Every call on this page goes through `request`, and a page that has been
 * open for a while fires several at once — polling an action, reloading the
 * roster. Without this, one expired token would send five refreshes, four of
 * them racing to replace the cookie the other four are using.
 */
let renewal: Promise<boolean> | null = null

async function renewSession(): Promise<boolean> {
  renewal ??= fetch("/api/auth/refresh", { method: "POST" })
    .then((res) => res.ok)
    .catch(() => false)
  const renewed = await renewal
  renewal = null
  return renewed
}

/**
 * Fetch, and if the session has expired, renew it and try once more.
 *
 * The access token is short next to the work: one review is four sequential
 * model calls. A token that expires while the page waits used to surface as
 * "Nie znaleziono studenta" — a 401 that the UI could only read as "gone".
 */
async function request(url: string, init?: RequestInit): Promise<Response> {
  const res = await fetch(url, init)
  if (res.status !== 401) return res
  if (!(await renewSession())) {
    // The refresh token is gone or rejected too: there is no session left to
    // save, and every other call would fail the same way. A full load on
    // purpose: this is a plain module, not a component with a router.
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    if (typeof window !== "undefined") window.location.assign("/login")
    return res
  }
  return fetch(url, init)
}

/** Turn a failed response into an Error carrying the API's own explanation. */
async function fail(res: Response, fallback: string): Promise<never> {
  let detail = fallback
  try {
    const body = (await res.json()) as { detail?: string; error?: string }
    detail = body.detail ?? body.error ?? fallback
  } catch {
    // Body was empty or not JSON — the fallback says enough.
  }
  throw new Error(detail)
}

async function getJson<T>(url: string, notFound: string): Promise<T> {
  const res = await request(url)
  if (!res.ok) return fail(res, notFound)
  return res.json() as Promise<T>
}

export const fetcher = <T>(url: string): Promise<T> =>
  getJson<T>(url, "Nie udało się pobrać danych")

// ---------- students ----------

export interface NewStudent {
  full_name: string
  field_of_study: string
  thesis_type: string
  index_number?: string | null
  research_area?: string | null
  research_aim?: string | null
}

export async function createStudent(student: NewStudent): Promise<Student> {
  const res = await request("/api/students", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(student),
  })
  if (!res.ok) return fail(res, "Nie udało się dodać studenta")
  return res.json() as Promise<Student>
}

/**
 * A partial edit of a student. A key left out is kept; `null` clears the
 * three fields that may be empty. A new `thesis_type` drops the guideline set
 * unless one for the new type is sent alongside.
 */
export interface StudentChanges {
  full_name?: string
  field_of_study?: string
  thesis_type?: ThesisType
  index_number?: string | null
  research_area?: string | null
  research_aim?: string | null
  current_topic?: string | null
  status?: StudentStatus
  guideline_set_id?: string | null
}

export async function updateStudent(
  studentId: string,
  changes: StudentChanges,
): Promise<Student> {
  const res = await request(`/api/students/${studentId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(changes),
  })
  if (!res.ok) return fail(res, "Nie udało się zapisać zmiany")
  return res.json() as Promise<Student>
}

/** Which demo students were added, and which were already on the roster. */
export interface DemoSeedResult {
  created: string[]
  skipped: string[]
}

/** Put the demo students on the caller's roster — those not there yet. */
export async function seedDemoStudents(): Promise<DemoSeedResult> {
  const res = await request("/api/students/demo", { method: "POST" })
  if (!res.ok) return fail(res, "Nie udało się wczytać przykładowych studentów")
  return res.json() as Promise<DemoSeedResult>
}

const AGENT_DOWN =
  "Serwis AI nie odpowiada, więc nic nie zostało usunięte — wyniki AI są też po jego stronie. Spróbuj za chwilę."

/**
 * Delete a student for good: notes, versions, files and AI results.
 * Nothing is deleted when the AI service cannot be reached (503).
 */
export async function deleteStudent(studentId: string): Promise<void> {
  const res = await request(`/api/students/${studentId}`, { method: "DELETE" })
  if (res.status === 503) throw new Error(AGENT_DOWN)
  if (!res.ok) await fail(res, "Nie udało się usunąć studenta")
}

// ---------- meeting notes ----------

export async function createMeetingNote(
  studentId: string,
  content: string,
  occurredAt?: string,
): Promise<MeetingNote> {
  const res = await request(`/api/students/${studentId}/meeting-notes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content, occurred_at: occurredAt ?? null }),
  })
  if (!res.ok) return fail(res, "Nie udało się zapisać notatki")
  return res.json() as Promise<MeetingNote>
}

// ---------- thesis drafts ----------

export async function uploadDraft(
  studentId: string,
  file: File,
): Promise<ThesisDraft> {
  const form = new FormData()
  form.append("file", file)
  const res = await request(`/api/students/${studentId}/drafts`, {
    method: "POST",
    body: form,
  })
  if (!res.ok) return fail(res, "Nie udało się wczytać pliku")
  return res.json() as Promise<ThesisDraft>
}

/** The list comes back whole: accepting one version changes the others' fate. */
async function changeDrafts(url: string, method: string, failure: string): Promise<ThesisDraft[]> {
  const res = await request(url, { method })
  if (!res.ok) return fail(res, failure)
  return res.json() as Promise<ThesisDraft[]>
}

export function acceptDraft(studentId: string, draftId: string): Promise<ThesisDraft[]> {
  return changeDrafts(
    `/api/students/${studentId}/drafts/${draftId}/accept`,
    "POST",
    "Nie udało się zaakceptować wersji",
  )
}

export function clearDraftAcceptance(
  studentId: string,
  draftId: string,
): Promise<ThesisDraft[]> {
  return changeDrafts(
    `/api/students/${studentId}/drafts/${draftId}/accept`,
    "DELETE",
    "Nie udało się cofnąć akceptacji",
  )
}

export function deleteDraft(studentId: string, draftId: string): Promise<ThesisDraft[]> {
  return changeDrafts(
    `/api/students/${studentId}/drafts/${draftId}`,
    "DELETE",
    "Nie udało się usunąć wersji",
  )
}

export function draftFileUrl(studentId: string, draftId: string): string {
  return `/api/students/${studentId}/drafts/${draftId}/file`
}

// ---------- parts and fragments ----------

export async function addPart(
  studentId: string,
  name: string,
  dueOn: string | null,
): Promise<ThesisPart> {
  const res = await request(`/api/students/${studentId}/parts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, due_on: dueOn }),
  })
  if (!res.ok) return fail(res, "Nie udało się dodać części")
  return res.json() as Promise<ThesisPart>
}

export async function updatePart(
  studentId: string,
  partId: string,
  changes: { name?: string; position?: number; due_on?: string | null },
): Promise<ThesisPart[]> {
  const res = await request(`/api/students/${studentId}/parts/${partId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(changes),
  })
  if (!res.ok) return fail(res, "Nie udało się zmienić części")
  return res.json() as Promise<ThesisPart[]>
}

export async function deletePart(studentId: string, partId: string): Promise<void> {
  const res = await request(`/api/students/${studentId}/parts/${partId}`, {
    method: "DELETE",
  })
  if (!res.ok) return fail(res, "Nie udało się usunąć części")
}

export interface NewFragment {
  partName: string
  file: File | null
  text: string | null
  receivedOn: string
  question: string | null
}

export async function uploadFragment(
  studentId: string,
  fragment: NewFragment,
): Promise<Fragment> {
  const form = new FormData()
  form.append("part_name", fragment.partName)
  form.append("received_on", fragment.receivedOn)
  if (fragment.file) form.append("file", fragment.file)
  if (fragment.text) form.append("text", fragment.text)
  if (fragment.question) form.append("question", fragment.question)
  const res = await request(`/api/students/${studentId}/fragments`, {
    method: "POST",
    body: form,
  })
  if (!res.ok) return fail(res, "Nie udało się zapisać fragmentu")
  return res.json() as Promise<Fragment>
}

export interface FragmentFeedback {
  verdict: FragmentVerdict
  feedback: string | null
  /** The run the text started from, when the promoter worked from its draft. */
  sourceActionId: string | null
  nextDueOn: string | null
}

export async function saveFragmentFeedback(
  studentId: string,
  fragmentId: string,
  feedback: FragmentFeedback,
): Promise<Fragment> {
  const res = await request(
    `/api/students/${studentId}/fragments/${fragmentId}/feedback`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        verdict: feedback.verdict,
        feedback: feedback.feedback,
        source_action_id: feedback.sourceActionId,
        next_due_on: feedback.nextDueOn,
      }),
    },
  )
  if (!res.ok) return fail(res, "Nie udało się zapisać feedbacku")
  return res.json() as Promise<Fragment>
}

export async function deleteFragment(
  studentId: string,
  fragmentId: string,
): Promise<void> {
  const res = await request(`/api/students/${studentId}/fragments/${fragmentId}`, {
    method: "DELETE",
  })
  if (!res.ok) return fail(res, "Nie udało się usunąć fragmentu")
}

export function fragmentFileUrl(studentId: string, fragmentId: string): string {
  return `/api/students/${studentId}/fragments/${fragmentId}/file`
}

// ---------- AI actions ----------

export interface ActionOptions {
  /**
   * Run on the promoter's own key for this provider. Left out, the action
   * runs on a local model — a stored key is never used unless asked for.
   */
  provider?: string
  /** Ollama model tag override; empty/undefined lets the server pick its default. */
  model?: string
  language?: string
  /** Only read by generate_review; ignored by every other action type. */
  reviewTone?: string
  /** generate_review only: pause after the analyses to pick the findings. */
  reviewFindingsFirst?: boolean
  /** review_fragment only: the fragment it reads. */
  fragmentId?: string
}

export async function triggerAction(
  studentId: string,
  actionType: ActionType,
  detail?: string,
  options?: ActionOptions,
): Promise<AgentAction> {
  const res = await request(`/api/students/${studentId}/actions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      action_type: actionType,
      detail: detail || null,
      provider: options?.provider || null,
      model: options?.model || null,
      language: options?.language || "pl",
      review_tone: options?.reviewTone || "auto",
      review_findings_first: options?.reviewFindingsFirst ?? false,
      fragment_id: options?.fragmentId ?? null,
    }),
  })
  if (!res.ok) return fail(res, "Nie udało się uruchomić akcji")
  return res.json() as Promise<AgentAction>
}

export function fetchAction(
  studentId: string,
  actionId: string,
): Promise<AgentAction> {
  return getJson<AgentAction>(
    `/api/students/${studentId}/actions/${actionId}`,
    "Nie udało się sprawdzić statusu akcji",
  )
}

/** Stop an action that has not finished. 409 when it already has. */
/** Write a paused review from the findings the promoter kept (their indices). */
export async function resumeAction(
  studentId: string,
  actionId: string,
  acceptedFindings: number[],
): Promise<AgentAction> {
  const res = await request(`/api/students/${studentId}/actions/${actionId}/resume`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ accepted_findings: acceptedFindings }),
  })
  if (!res.ok) return fail(res, "Nie udało się wznowić recenzji")
  return res.json() as Promise<AgentAction>
}

export async function cancelAction(studentId: string, actionId: string): Promise<AgentAction> {
  const res = await request(`/api/students/${studentId}/actions/${actionId}/cancel`, {
    method: "POST",
  })
  if (!res.ok) return fail(res, "Nie udało się przerwać akcji")
  return res.json() as Promise<AgentAction>
}

/** Delete an action from the history, result and all; a running one is stopped. */
export async function deleteAction(studentId: string, actionId: string): Promise<void> {
  const res = await request(`/api/students/${studentId}/actions/${actionId}`, {
    method: "DELETE",
  })
  if (res.status === 503) throw new Error(AGENT_DOWN)
  if (!res.ok) await fail(res, "Nie udało się usunąć akcji")
}

export async function acceptAction(
  studentId: string,
  actionId: string,
  topicIndex = 0,
): Promise<AgentAction> {
  const res = await request(
    `/api/students/${studentId}/actions/${actionId}/accept`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ topic_index: topicIndex }),
    },
  )
  if (!res.ok) return fail(res, "Nie udało się zaakceptować wyniku")
  return res.json() as Promise<AgentAction>
}

// ---------- guideline catalog ----------

async function sendJson<T>(url: string, method: string, body: unknown, failure: string): Promise<T> {
  const res = await request(url, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  if (!res.ok) return fail(res, failure)
  return res.json() as Promise<T>
}

export function guidelineSourceUrl(versionId: string): string {
  return `/api/guidelines/versions/${versionId}/source`
}

export function createUniversity(name: string, shortName: string): Promise<University> {
  return sendJson(
    "/api/admin/guidelines/universities",
    "POST",
    { name, short_name: shortName },
    "Nie udało się dodać uczelni",
  )
}

export function createGuidelineSet(
  universityId: string,
  thesisType: string,
  name: string,
): Promise<GuidelineSetDetail> {
  return sendJson(
    "/api/admin/guidelines/sets",
    "POST",
    { university_id: universityId, thesis_type: thesisType, name },
    "Nie udało się dodać zestawu",
  )
}

/** Open the next version as a draft; it starts from the version in force. */
export function createGuidelineDraft(setId: string): Promise<GuidelineVersion> {
  return sendJson(
    `/api/admin/guidelines/sets/${setId}/versions`,
    "POST",
    {},
    "Nie udało się utworzyć szkicu",
  )
}

export interface GuidelineDraftChanges {
  rubric_md?: string
  thresholds?: Thresholds
  effective_from?: string | null
}

export function updateGuidelineDraft(
  versionId: string,
  changes: GuidelineDraftChanges,
): Promise<GuidelineVersion> {
  return sendJson(
    `/api/admin/guidelines/versions/${versionId}`,
    "PATCH",
    changes,
    "Nie udało się zapisać szkicu",
  )
}

export async function uploadGuidelineSource(
  versionId: string,
  file: File,
): Promise<GuidelineVersion> {
  const form = new FormData()
  form.append("file", file)
  const res = await request(`/api/admin/guidelines/versions/${versionId}/source`, {
    method: "PUT",
    body: form,
  })
  if (!res.ok) return fail(res, "Nie udało się wczytać pliku")
  return res.json() as Promise<GuidelineVersion>
}

export async function publishGuidelineVersion(versionId: string): Promise<GuidelineVersion> {
  const res = await request(`/api/admin/guidelines/versions/${versionId}/publish`, {
    method: "POST",
  })
  if (!res.ok) return fail(res, "Nie udało się opublikować wersji")
  return res.json() as Promise<GuidelineVersion>
}

// ---------- access requests ----------

export async function dismissAccessRequest(id: string): Promise<void> {
  const res = await request(`/api/admin/access-requests/${id}`, {
    method: "DELETE",
  })
  if (!res.ok) await fail(res, "Nie udało się odrzucić prośby")
}

// ---------- local models (admin) ----------

export function setModelEnabled(name: string, enabled: boolean): Promise<AdminModelCatalog> {
  return sendJson(
    "/api/admin/models",
    "PATCH",
    { name, enabled },
    enabled ? "Nie udało się udostępnić modelu" : "Nie udało się wyłączyć modelu",
  )
}

export function setDefaultModel(name: string): Promise<AdminModelCatalog> {
  return sendJson(
    "/api/admin/models/default",
    "PUT",
    { name },
    "Nie udało się ustawić modelu domyślnego",
  )
}
