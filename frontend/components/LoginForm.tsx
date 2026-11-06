"use client"

import { useState } from "react"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { useRouter } from "next/navigation"

const schema = z.object({
  email: z.string().email("Podaj poprawny adres email"),
  password: z.string().min(8, "Hasło ma co najmniej 8 znaków"),
})

type FormData = z.infer<typeof schema>

export default function LoginForm() {
  const router = useRouter()
  const [serverError, setServerError] = useState<string | null>(null)
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({
    resolver: zodResolver(schema),
  })

  const onSubmit = async (data: FormData): Promise<void> => {
    setServerError(null)
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    })
    if (!res.ok) {
      setServerError("Nieprawidłowy email lub hasło.")
      return
    }
    const { home } = (await res.json()) as { home?: string }
    router.push(home ?? "/dashboard")
  }

  return (
    <form
      onSubmit={handleSubmit(onSubmit)}
      data-testid="login-form"
      className="space-y-5"
      noValidate
    >
      <div>
        <label
          htmlFor="email"
          className="block text-[13px] font-medium text-muted-strong"
        >
          Email
        </label>
        <input
          id="email"
          type="email"
          autoComplete="email"
          data-testid="email-input"
          className="mt-1.5 block h-[42px] w-full rounded-lg border border-line bg-surface px-3.5 text-[14px] text-foreground focus:border-accent focus:outline-none"
          {...register("email")}
        />
        {errors.email && (
          <p
            id="email-error"
            role="alert"
            data-testid="email-error"
            className="mt-1.5 text-[12.5px] text-critical-text"
          >
            {errors.email.message}
          </p>
        )}
      </div>

      <div>
        <label
          htmlFor="password"
          className="block text-[13px] font-medium text-muted-strong"
        >
          Hasło
        </label>
        <input
          id="password"
          type="password"
          autoComplete="current-password"
          data-testid="password-input"
          className="mt-1.5 block h-[42px] w-full rounded-lg border border-line bg-surface px-3.5 text-[14px] text-foreground focus:border-accent focus:outline-none"
          {...register("password")}
        />
        {errors.password && (
          <p
            id="password-error"
            role="alert"
            data-testid="password-error"
            className="mt-1.5 text-[12.5px] text-critical-text"
          >
            {errors.password.message}
          </p>
        )}
      </div>

      {serverError && (
        <p
          role="alert"
          data-testid="server-error"
          className="rounded-lg bg-critical-bg px-3.5 py-2.5 text-[13px] text-critical-text"
        >
          {serverError}
        </p>
      )}

      <button
        type="submit"
        disabled={isSubmitting}
        data-testid="submit-button"
        className="h-11 w-full rounded-lg bg-accent text-[14px] font-semibold text-white hover:bg-accent-hover transition-colors disabled:opacity-50"
      >
        {isSubmitting ? "Logowanie…" : "Zaloguj się"}
      </button>
    </form>
  )
}
