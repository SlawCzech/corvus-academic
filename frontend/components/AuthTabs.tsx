"use client"

import { useState } from "react"
import LoginForm from "@/components/LoginForm"
import AccessRequestForm from "@/components/AccessRequestForm"

type Tab = "login" | "request"

export default function AuthTabs({ initialTab }: { initialTab: Tab }) {
  const [tab, setTab] = useState<Tab>(initialTab)

  return (
    <div className="w-full max-w-[380px]">
      <div className="mb-8 flex border-b border-line">
        <button
          type="button"
          onClick={() => setTab("login")}
          className={`flex-1 pb-3 text-[14px] font-semibold transition-colors ${
            tab === "login"
              ? "border-b-2 border-accent text-foreground"
              : "border-b-2 border-transparent text-muted"
          }`}
        >
          Zaloguj się
        </button>
        <button
          type="button"
          onClick={() => setTab("request")}
          className={`flex-1 pb-3 text-[14px] font-semibold transition-colors ${
            tab === "request"
              ? "border-b-2 border-accent text-foreground"
              : "border-b-2 border-transparent text-muted"
          }`}
        >
          Poproś o dostęp
        </button>
      </div>

      {tab === "login" ? (
        <div>
          <h1 className="mb-1.5 text-[24px] font-semibold text-foreground">
            Zaloguj się
          </h1>
          <p className="mb-7 text-[13.5px] text-muted">
            Wprowadź dane swojego konta promotora.
          </p>
          <LoginForm />
        </div>
      ) : (
        <AccessRequestForm />
      )}
    </div>
  )
}
