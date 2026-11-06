"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { request } from "@/lib/api.client"
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

interface ChangePasswordFormProps {
  /**
   * Where to go once a temporary password from an admin is replaced. Set,
   * the form asks for that password instead of "the current one".
   */
  temporaryThen?: string
}

export default function ChangePasswordForm({ temporaryThen }: ChangePasswordFormProps = {}) {
  const router = useRouter()
  const temporary = temporaryThen !== undefined
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
    const res = await request("/api/users/me/password", {
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
    if (temporary) {
      // The new session cookie no longer carries the mark, so the proxy
      // lets the rest of the app open again.
      router.replace(temporaryThen)
      router.refresh()
      return
    }
    setSuccess(true)
    reset()
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4 max-w-sm">
      {success && (
        <p className="rounded-lg bg-success-bg p-3 text-[13.5px] text-success-text">
          Hasło zostało zmienione.
        </p>
      )}
      {serverError && (
        <p className="rounded-lg bg-critical-bg p-3 text-[13.5px] text-critical-text">
          {serverError}
        </p>
      )}

      <div>
        <label className="block mb-1 text-[13px] font-medium text-muted-strong">
          {temporary ? "Hasło tymczasowe" : "Aktualne hasło"}
        </label>
        <input
          type="password"
          {...register("current_password")}
          className="w-full rounded-lg border border-line bg-surface px-3 py-1.5 text-[14px] text-foreground focus:border-accent focus:outline-none"
        />
        {errors.current_password && (
          <p className="mt-1 text-[12px] text-critical-text">{errors.current_password.message}</p>
        )}
      </div>

      <div>
        <label className="block mb-1 text-[13px] font-medium text-muted-strong">
          Nowe hasło
        </label>
        <input
          type="password"
          {...register("new_password")}
          className="w-full rounded-lg border border-line bg-surface px-3 py-1.5 text-[14px] text-foreground focus:border-accent focus:outline-none"
        />
        {errors.new_password && (
          <p className="mt-1 text-[12px] text-critical-text">{errors.new_password.message}</p>
        )}
      </div>

      <div>
        <label className="block mb-1 text-[13px] font-medium text-muted-strong">
          Potwierdź nowe hasło
        </label>
        <input
          type="password"
          {...register("confirm_password")}
          className="w-full rounded-lg border border-line bg-surface px-3 py-1.5 text-[14px] text-foreground focus:border-accent focus:outline-none"
        />
        {errors.confirm_password && (
          <p className="mt-1 text-[12px] text-critical-text">{errors.confirm_password.message}</p>
        )}
      </div>

      <button
        type="submit"
        disabled={isSubmitting}
        className="flex h-9 items-center px-4 text-[13px] font-semibold rounded-lg bg-accent text-white hover:bg-accent-hover transition-colors disabled:opacity-50"
      >
        {isSubmitting ? "Zapisywanie…" : temporary ? "Ustaw hasło" : "Zmień hasło"}
      </button>
    </form>
  )
}
