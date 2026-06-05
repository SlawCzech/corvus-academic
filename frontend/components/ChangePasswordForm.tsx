"use client"

import { useState } from "react"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"

const schema = z
  .object({
    current_password: z.string().min(1, "Wymagane"),
    new_password: z.string().min(8, "Minimum 8 znaków"),
    confirm_password: z.string().min(1, "Wymagane"),
  })
  .refine((d) => d.new_password === d.confirm_password, {
    message: "Hasła nie są zgodne",
    path: ["confirm_password"],
  })

type FormData = z.infer<typeof schema>

export default function ChangePasswordForm() {
  const [success, setSuccess] = useState(false)
  const [serverError, setServerError] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({ resolver: zodResolver(schema) })

  async function onSubmit(data: FormData) {
    setServerError(null)
    const res = await fetch("/api/users/me/password", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        current_password: data.current_password,
        new_password: data.new_password,
      }),
    })
    if (!res.ok) {
      const body = (await res.json()) as { detail?: string }
      setServerError(body.detail ?? "Zmiana hasła nie powiodła się.")
      return
    }
    setSuccess(true)
    reset()
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4 max-w-sm">
      {success && (
        <p className="rounded bg-green-50 p-3 text-sm text-green-700 dark:bg-green-950 dark:text-green-300">
          Hasło zostało zmienione.
        </p>
      )}
      {serverError && (
        <p className="rounded bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
          {serverError}
        </p>
      )}

      <div>
        <label className="block mb-1 text-[13px] font-medium text-gray-700 dark:text-gray-300">
          Aktualne hasło
        </label>
        <input
          type="password"
          {...register("current_password")}
          className="w-full rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-gray-900 dark:focus:ring-gray-100"
        />
        {errors.current_password && (
          <p className="mt-1 text-[12px] text-red-600">{errors.current_password.message}</p>
        )}
      </div>

      <div>
        <label className="block mb-1 text-[13px] font-medium text-gray-700 dark:text-gray-300">
          Nowe hasło
        </label>
        <input
          type="password"
          {...register("new_password")}
          className="w-full rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-gray-900 dark:focus:ring-gray-100"
        />
        {errors.new_password && (
          <p className="mt-1 text-[12px] text-red-600">{errors.new_password.message}</p>
        )}
      </div>

      <div>
        <label className="block mb-1 text-[13px] font-medium text-gray-700 dark:text-gray-300">
          Potwierdź nowe hasło
        </label>
        <input
          type="password"
          {...register("confirm_password")}
          className="w-full rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-gray-900 dark:focus:ring-gray-100"
        />
        {errors.confirm_password && (
          <p className="mt-1 text-[12px] text-red-600">{errors.confirm_password.message}</p>
        )}
      </div>

      <button
        type="submit"
        disabled={isSubmitting}
        className="flex h-8 items-center px-4 text-[13px] font-medium rounded-md bg-gray-900 dark:bg-white text-white dark:text-gray-900 hover:bg-gray-700 dark:hover:bg-gray-100 transition-colors disabled:opacity-50"
      >
        {isSubmitting ? "Zapisywanie…" : "Zmień hasło"}
      </button>
    </form>
  )
}
