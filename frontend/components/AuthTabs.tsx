"use client";

import { useState } from "react";
import LoginForm from "@/components/LoginForm";
import AccessRequestForm from "@/components/AccessRequestForm";

type Tab = "login" | "request";

const SWITCH =
  "text-accent underline underline-offset-4 hover:text-accent-hover";

export default function AuthTabs({ initialTab }: { initialTab: Tab }) {
  const [tab, setTab] = useState<Tab>(initialTab);

  if (tab === "request") {
    return (
      <div>
        <AccessRequestForm />
        <p className="mt-8 text-[13.5px] text-muted">
          Masz już konto?{" "}
          <button
            type="button"
            onClick={() => setTab("login")}
            className={SWITCH}
          >
            Zaloguj się
          </button>
        </p>
      </div>
    );
  }

  return (
    <div>
      <h1 className="mb-7 text-[22px] font-semibold text-foreground">
        Zaloguj się
      </h1>
      <LoginForm />
      <p className="mt-8 text-[13.5px] text-muted">
        Nie masz konta? Zakłada je administrator —{" "}
        <button
          type="button"
          onClick={() => setTab("request")}
          className={SWITCH}
        >
          zostaw adres email
        </button>
        .
      </p>
    </div>
  );
}
