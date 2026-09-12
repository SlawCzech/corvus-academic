import type {
  AgentAction,
  ActionType,
  MeetingNote,
  Student,
  ThesisDraft,
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
    // save, and every other call would fail the same way.
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

export async function updateStudent(
  studentId: string,
  changes: { current_topic?: string; status?: string },
): Promise<Student> {
  const res = await request(`/api/students/${studentId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(changes),
  })
  if (!res.ok) return fail(res, "Nie udało się zapisać zmiany")
  return res.json() as Promise<Student>
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

// ---------- AI actions ----------

export async function triggerAction(
  studentId: string,
  actionType: ActionType,
  detail?: string,
): Promise<AgentAction> {
  const res = await request(`/api/students/${studentId}/actions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action_type: actionType, detail: detail || null }),
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
