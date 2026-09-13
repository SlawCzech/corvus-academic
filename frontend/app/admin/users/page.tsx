"use client"

import { useState } from "react"
import AccessRequestsPanel from "@/components/AccessRequestsPanel"
import UserManagementTable from "@/components/UserManagementTable"

export default function AdminUsersPage() {
  const [prefillEmail, setPrefillEmail] = useState<string | undefined>(undefined)

  return (
    <main className="mx-auto max-w-4xl px-8 py-10">
      <h1 className="mb-8 font-serif text-[26px] font-semibold text-foreground">
        Zarządzanie użytkownikami
      </h1>
      <AccessRequestsPanel onAdd={setPrefillEmail} />
      <UserManagementTable
        prefillEmail={prefillEmail}
        onPrefillConsumed={() => setPrefillEmail(undefined)}
      />
    </main>
  )
}
