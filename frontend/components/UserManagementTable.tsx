"use client"

import { useState } from "react"
import useSWR from "swr"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"

interface User {
  id: string
  email: string
  role: string
  created_at: string
}

const createSchema = z.object({
  email: z.string().email("Nieprawidłowy email"),
  password: z.string().min(8, "Minimum 8 znaków"),
  role: z.enum(["USER", "ADMIN"]),
})

type CreateForm = z.infer<typeof createSchema>

const fetcher = (url: string) =>
  fetch(url).then((r) => {
    if (!r.ok) throw new Error("Fetch failed")
    return r.json() as Promise<User[]>
  })

export default function UserManagementTable() {
  const { data: users, error, mutate } = useSWR<User[]>("/api/users", fetcher)
  const [showModal, setShowModal] = useState(false)
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null)
  const [serverError, setServerError] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<CreateForm>({
    resolver: zodResolver(createSchema),
    defaultValues: { role: "USER" },
  })

  async function onCreate(data: CreateForm) {
    setServerError(null)
    const res = await fetch("/api/users", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    })
    if (!res.ok) {
      const body = (await res.json()) as { detail?: string }
      setServerError(body.detail ?? "Nie udało się utworzyć użytkownika.")
      return
    }
    await mutate()
    setShowModal(false)
    reset()
  }

  async function onDelete(id: string) {
    await fetch(`/api/users/${id}`, { method: "DELETE" })
    await mutate()
    setDeleteConfirm(null)
  }

  if (error) {
    return <p className="text-sm text-red-600">Błąd ładowania użytkowników.</p>
  }

  return (
    <div>
      <div className="mb-4 flex justify-end">
        <button
          onClick={() => setShowModal(true)}
          className="flex h-8 items-center px-4 text-[13px] font-medium rounded-md bg-gray-900 dark:bg-white text-white dark:text-gray-900 hover:bg-gray-700 dark:hover:bg-gray-100 transition-colors"
        >
          Dodaj użytkownika
        </button>
      </div>

      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-gray-200 dark:border-gray-800">
            <th className="pb-2 font-medium text-gray-700 dark:text-gray-300">Email</th>
            <th className="pb-2 font-medium text-gray-700 dark:text-gray-300">Rola</th>
            <th className="pb-2 font-medium text-gray-700 dark:text-gray-300">Utworzony</th>
            <th className="pb-2 font-medium text-gray-700 dark:text-gray-300"></th>
          </tr>
        </thead>
        <tbody>
          {!users && (
            <tr>
              <td colSpan={4} className="py-6 text-center text-gray-400">
                Ładowanie…
              </td>
            </tr>
          )}
          {users?.length === 0 && (
            <tr>
              <td colSpan={4} className="py-6 text-center text-gray-400">
                Brak użytkowników.
              </td>
            </tr>
          )}
          {users?.map((user) => (
            <tr key={user.id} className="border-b border-gray-100 dark:border-gray-900">
              <td className="py-3 text-gray-900 dark:text-gray-100">{user.email}</td>
              <td className="py-3 text-gray-600 dark:text-gray-400">{user.role}</td>
              <td className="py-3 text-gray-500">
                {new Date(user.created_at).toLocaleDateString("pl-PL")}
              </td>
              <td className="py-3 text-right">
                {deleteConfirm === user.id ? (
                  <span className="flex items-center justify-end gap-2">
                    <span className="text-[12px] text-gray-500">Potwierdź usunięcie?</span>
                    <button
                      onClick={() => onDelete(user.id)}
                      className="text-[12px] text-red-600 hover:underline"
                    >
                      Tak
                    </button>
                    <button
                      onClick={() => setDeleteConfirm(null)}
                      className="text-[12px] text-gray-500 hover:underline"
                    >
                      Nie
                    </button>
                  </span>
                ) : (
                  <button
                    onClick={() => setDeleteConfirm(user.id)}
                    className="text-[12px] text-red-500 hover:underline"
                  >
                    Usuń
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="w-full max-w-md rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950 p-6 shadow-xl">
            <h2 className="mb-4 text-base font-semibold text-gray-900 dark:text-gray-100">
              Nowy użytkownik
            </h2>

            <form onSubmit={handleSubmit(onCreate)} className="space-y-4">
              {serverError && (
                <p className="rounded bg-red-50 p-3 text-sm text-red-700">{serverError}</p>
              )}

              <div>
                <label className="block mb-1 text-[13px] font-medium text-gray-700 dark:text-gray-300">
                  Email
                </label>
                <input
                  type="email"
                  {...register("email")}
                  className="w-full rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-gray-900"
                />
                {errors.email && (
                  <p className="mt-1 text-[12px] text-red-600">{errors.email.message}</p>
                )}
              </div>

              <div>
                <label className="block mb-1 text-[13px] font-medium text-gray-700 dark:text-gray-300">
                  Hasło
                </label>
                <input
                  type="password"
                  {...register("password")}
                  className="w-full rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-gray-900"
                />
                {errors.password && (
                  <p className="mt-1 text-[12px] text-red-600">{errors.password.message}</p>
                )}
              </div>

              <div>
                <label className="block mb-1 text-[13px] font-medium text-gray-700 dark:text-gray-300">
                  Rola
                </label>
                <select
                  {...register("role")}
                  className="w-full rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-gray-900"
                >
                  <option value="USER">USER</option>
                  <option value="ADMIN">ADMIN</option>
                </select>
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => {
                    setShowModal(false)
                    setServerError(null)
                    reset()
                  }}
                  className="flex h-8 items-center px-3.5 text-[13px] font-medium border border-gray-200 dark:border-gray-700 rounded-md hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
                >
                  Anuluj
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="flex h-8 items-center px-4 text-[13px] font-medium rounded-md bg-gray-900 dark:bg-white text-white dark:text-gray-900 hover:bg-gray-700 dark:hover:bg-gray-100 transition-colors disabled:opacity-50"
                >
                  {isSubmitting ? "Tworzenie…" : "Utwórz"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
