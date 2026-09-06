"use client"

import { useState } from "react"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { useRouter } from "next/navigation"

const schema = z.object({
  email: z.string().email("Enter a valid email address"),
  password: z.string().min(8, "Password must be at least 8 characters"),
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
      setServerError("Invalid email or password.")
      return
    }
    router.push("/students")
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
          className="block text-sm font-medium text-gray-700"
        >
          Email
        </label>
        <input
          id="email"
          type="email"
          autoComplete="email"
          data-testid="email-input"
          className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
          {...register("email")}
        />
        {errors.email && (
          <p
            id="email-error"
            role="alert"
            data-testid="email-error"
            className="mt-1 text-sm text-red-600"
          >
            {errors.email.message}
          </p>
        )}
      </div>

      <div>
        <label
          htmlFor="password"
          className="block text-sm font-medium text-gray-700"
        >
          Password
        </label>
        <input
          id="password"
          type="password"
          autoComplete="current-password"
          data-testid="password-input"
          className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
          {...register("password")}
        />
        {errors.password && (
          <p
            id="password-error"
            role="alert"
            data-testid="password-error"
            className="mt-1 text-sm text-red-600"
          >
            {errors.password.message}
          </p>
        )}
      </div>

      {serverError && (
        <p
          role="alert"
          data-testid="server-error"
          className="rounded bg-red-50 px-3 py-2 text-sm text-red-700"
        >
          {serverError}
        </p>
      )}

      <button
        type="submit"
        disabled={isSubmitting}
        data-testid="submit-button"
        className="w-full rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
      >
        {isSubmitting ? "Signing in…" : "Sign in"}
      </button>
    </form>
  )
}
