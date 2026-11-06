"use client"

import { useState } from "react"
import useSWR from "swr"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { fetcher as apiFetcher, request } from "@/lib/api.client"
import type { University } from "@/lib/api.types"
import { z } from "zod"

interface User {
  id: string
  email: string
  role: string
  created_at: string
  /** A temporary password from an admin is waiting to be replaced. */
  must_change_password?: boolean
}

// Matches identity's own `Role` StrEnum ("admin" / "promotor") — the create
// form used to send "USER"/"ADMIN", which the backend's role validator has
// never accepted, so every submission failed with a 422.
const createSchema = z.object({
  email: z.string().email("Nieprawidłowy email"),
  password: z.string().min(8, "Minimum 8 znaków"),
  role: z.enum(["promotor", "admin"]),
  home_university_id: z.string().optional(),
})

type CreateForm = z.infer<typeof createSchema>

const fetcher = (url: string) =>
  request(url).then((r) => {
    if (!r.ok) throw new Error("Fetch failed")
    return r.json() as Promise<User[]>
  })

interface UserManagementTableProps {
  /** Prefills and opens the create-user modal — set from an access request row. */
  prefillEmail?: string
  onPrefillConsumed?: () => void
}

export default function UserManagementTable({
  prefillEmail,
  onPrefillConsumed,
}: UserManagementTableProps) {
  const { data: users, error, mutate } = useSWR<User[]>("/api/users", fetcher)
  const [showModal, setShowModal] = useState(false)
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null)
  const [resetConfirm, setResetConfirm] = useState<string | null>(null)
  const [resetError, setResetError] = useState<string | null>(null)
  const [issued, setIssued] = useState<{ email: string; password: string } | null>(null)

  const modalOpen = showModal || prefillEmail !== undefined

  function closeModal(): void {
    setShowModal(false)
    onPrefillConsumed?.()
  }

  async function onDelete(id: string) {
    await request(`/api/users/${id}`, { method: "DELETE" })
    await mutate()
    setDeleteConfirm(null)
  }

  async function onReset(user: User) {
    setResetError(null)
    const res = await request(`/api/users/${user.id}/password-reset`, { method: "POST" })
    const body = (await res.json().catch(() => ({}))) as {
      temporary_password?: string
      detail?: string
    }
    setResetConfirm(null)
    if (!res.ok || !body.temporary_password) {
      setResetError(body.detail ?? "Nie udało się zresetować hasła.")
      return
    }
    setIssued({ email: user.email, password: body.temporary_password })
    await mutate()
  }

  if (error) {
    return <p className="text-[13px] text-critical-text">Błąd ładowania użytkowników.</p>
  }

  return (
    <div>
      <div className="mb-4 flex justify-end">
        <button
          onClick={() => setShowModal(true)}
          className="flex h-9 items-center rounded-lg bg-accent px-4 text-[13px] font-semibold text-white hover:bg-accent-hover transition-colors"
        >
          Dodaj użytkownika
        </button>
      </div>

      {resetError && (
        <p className="mb-3 rounded-lg bg-critical-bg p-3 text-[13px] text-critical-text">
          {resetError}
        </p>
      )}

      <table className="w-full text-left text-[13.5px]">
        <thead>
          <tr className="border-b border-line">
            <th className="pb-2 font-medium text-muted-strong">Email</th>
            <th className="pb-2 font-medium text-muted-strong">Rola</th>
            <th className="pb-2 font-medium text-muted-strong">Utworzony</th>
            <th className="pb-2 font-medium text-muted-strong"></th>
          </tr>
        </thead>
        <tbody>
          {!users && (
            <tr>
              <td colSpan={4} className="py-6 text-center text-muted">
                Ładowanie…
              </td>
            </tr>
          )}
          {users?.length === 0 && (
            <tr>
              <td colSpan={4} className="py-6 text-center text-muted">
                Brak użytkowników.
              </td>
            </tr>
          )}
          {users?.map((user) => (
            <tr key={user.id} className="border-b border-line/60">
              <td className="py-3 text-foreground">
                {user.email}
                {user.must_change_password && (
                  <span className="ml-2 rounded bg-surface-alt px-1.5 py-0.5 text-[11px] text-muted">
                    hasło tymczasowe
                  </span>
                )}
              </td>
              <td className="py-3 text-muted-strong">{user.role}</td>
              <td className="py-3 text-muted">
                {new Date(user.created_at).toLocaleDateString("pl-PL")}
              </td>
              <td className="py-3 text-right">
                {resetConfirm === user.id ? (
                  <span className="flex items-center justify-end gap-2">
                    <span className="text-[12px] text-muted">Zresetować hasło?</span>
                    <button
                      onClick={() => onReset(user)}
                      className="text-[12px] text-accent hover:underline"
                    >
                      Tak
                    </button>
                    <button
                      onClick={() => setResetConfirm(null)}
                      className="text-[12px] text-muted hover:underline"
                    >
                      Nie
                    </button>
                  </span>
                ) : deleteConfirm === user.id ? (
                  <span className="flex items-center justify-end gap-2">
                    <span className="text-[12px] text-muted">Potwierdź usunięcie?</span>
                    <button
                      onClick={() => onDelete(user.id)}
                      className="text-[12px] text-critical-text hover:underline"
                    >
                      Tak
                    </button>
                    <button
                      onClick={() => setDeleteConfirm(null)}
                      className="text-[12px] text-muted hover:underline"
                    >
                      Nie
                    </button>
                  </span>
                ) : (
                  <span className="flex items-center justify-end gap-3">
                    <button
                      onClick={() => {
                        setDeleteConfirm(null)
                        setResetConfirm(user.id)
                      }}
                      className="text-[12px] text-muted-strong hover:underline"
                    >
                      Resetuj hasło
                    </button>
                    <button
                      onClick={() => {
                        setResetConfirm(null)
                        setDeleteConfirm(user.id)
                      }}
                      className="text-[12px] text-critical-text hover:underline"
                    >
                      Usuń
                    </button>
                  </span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {issued && (
        <TemporaryPasswordModal
          email={issued.email}
          password={issued.password}
          onClose={() => setIssued(null)}
        />
      )}

      {modalOpen && (
        <CreateUserModal
          key={prefillEmail ?? "blank"}
          initialEmail={prefillEmail}
          onCreated={() => {
            void mutate()
            closeModal()
          }}
          onClose={closeModal}
        />
      )}
    </div>
  )
}

/**
 * The temporary password, shown once: only its hash is kept, so closing
 * this is the last chance to copy it. Corvus sends no mail; the admin
 * passes it on themselves.
 */
function TemporaryPasswordModal({
  email,
  password,
  onClose,
}: {
  email: string
  password: string
  onClose: () => void
}) {
  const [copied, setCopied] = useState(false)

  async function copy() {
    try {
      await navigator.clipboard.writeText(password)
      setCopied(true)
    } catch {
      // No clipboard (an insecure context): the password stays on screen.
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div
        role="dialog"
        aria-labelledby="temporary-password-title"
        className="w-full max-w-md rounded-xl border border-line bg-surface p-6 shadow-xl"
      >
        <h2
          id="temporary-password-title"
          className="mb-2 text-[16px] font-semibold text-foreground"
        >
          Hasło tymczasowe
        </h2>
        <p className="mb-4 text-[13px] text-muted">
          Dla {email}. Przekaż je tej osobie: po zalogowaniu ustawi własne, a
          do tego czasu nic innego się nie otworzy. Wszystkie jej sesje zostały
          zakończone. Po zamknięciu tego okna hasła nie da się już zobaczyć.
        </p>
        <div className="mb-4 flex items-center gap-2">
          <code
            data-testid="temporary-password"
            className="flex-1 select-all rounded-lg border border-line bg-surface-alt px-3 py-2 font-mono text-[14px] text-foreground"
          >
            {password}
          </code>
          <button
            type="button"
            onClick={() => void copy()}
            className="flex h-9 items-center rounded-lg border border-line px-3 text-[13px] font-medium hover:bg-surface-alt transition-colors"
          >
            {copied ? "Skopiowane" : "Kopiuj"}
          </button>
        </div>
        <div className="flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="flex h-9 items-center rounded-lg bg-accent px-4 text-[13px] font-semibold text-white hover:bg-accent-hover transition-colors"
          >
            Gotowe
          </button>
        </div>
      </div>
    </div>
  )
}

function CreateUserModal({
  initialEmail,
  onCreated,
  onClose,
}: {
  initialEmail?: string
  onCreated: () => void
  onClose: () => void
}) {
  const [serverError, setServerError] = useState<string | null>(null)
  const { data: universities } = useSWR<University[]>(
    "/api/guidelines/universities",
    apiFetcher,
  )
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<CreateForm>({
    resolver: zodResolver(createSchema),
    defaultValues: { email: initialEmail ?? "", role: "promotor" },
  })

  async function onCreate(data: CreateForm) {
    setServerError(null)
    const res = await request("/api/users", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ...data,
        home_university_id: data.home_university_id || null,
      }),
    })
    if (!res.ok) {
      const body = (await res.json()) as { detail?: string }
      setServerError(body.detail ?? "Nie udało się utworzyć użytkownika.")
      return
    }
    onCreated()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-md rounded-xl border border-line bg-surface p-6 shadow-xl">
        <h2 className="mb-4 text-[16px] font-semibold text-foreground">
          Nowy użytkownik
        </h2>

        <form onSubmit={handleSubmit(onCreate)} className="space-y-4">
          {serverError && (
            <p className="rounded-lg bg-critical-bg p-3 text-[13px] text-critical-text">
              {serverError}
            </p>
          )}

          <div>
            <label className="mb-1 block text-[13px] font-medium text-muted-strong">
              Email
            </label>
            <input
              type="email"
              {...register("email")}
              className="w-full rounded-lg border border-line bg-surface px-3 py-1.5 text-[14px] focus:border-accent focus:outline-none"
            />
            {errors.email && (
              <p className="mt-1 text-[12px] text-critical-text">{errors.email.message}</p>
            )}
          </div>

          <div>
            <label className="mb-1 block text-[13px] font-medium text-muted-strong">
              Hasło
            </label>
            <input
              type="password"
              {...register("password")}
              className="w-full rounded-lg border border-line bg-surface px-3 py-1.5 text-[14px] focus:border-accent focus:outline-none"
            />
            {errors.password && (
              <p className="mt-1 text-[12px] text-critical-text">{errors.password.message}</p>
            )}
          </div>

          <div>
            <label className="mb-1 block text-[13px] font-medium text-muted-strong">
              Rola
            </label>
            <select
              {...register("role")}
              className="w-full rounded-lg border border-line bg-surface px-3 py-1.5 text-[14px] focus:border-accent focus:outline-none"
            >
              <option value="promotor">Promotor</option>
              <option value="admin">Administrator</option>
            </select>
          </div>

          <div>
            <label
              htmlFor="new-user-university"
              className="mb-1 block text-[13px] font-medium text-muted-strong"
            >
              Uczelnia (opcjonalnie)
            </label>
            <select
              id="new-user-university"
              {...register("home_university_id")}
              className="w-full rounded-lg border border-line bg-surface px-3 py-1.5 text-[14px] focus:border-accent focus:outline-none"
            >
              <option value="">Promotor wybierze sam w profilu</option>
              {(universities ?? []).map((u) => (
                <option key={u.id} value={u.id}>
                  {u.name}
                </option>
              ))}
            </select>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex h-9 items-center rounded-lg border border-line px-3.5 text-[13px] font-medium hover:bg-surface-alt transition-colors"
            >
              Anuluj
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="flex h-9 items-center rounded-lg bg-accent px-4 text-[13px] font-semibold text-white hover:bg-accent-hover transition-colors disabled:opacity-50"
            >
              {isSubmitting ? "Tworzenie…" : "Utwórz"}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
