"use client"

import useSWR from "swr"
import { dismissAccessRequest, fetcher } from "@/lib/api.client"
import type { AccessRequest } from "@/lib/api.types"

interface AccessRequestsPanelProps {
  onAdd: (email: string) => void
}

export default function AccessRequestsPanel({ onAdd }: AccessRequestsPanelProps) {
  const { data: requests, mutate } = useSWR<AccessRequest[]>(
    "/api/admin/access-requests",
    fetcher,
  )

  async function dismiss(id: string) {
    await dismissAccessRequest(id)
    void mutate()
  }

  if (!requests || requests.length === 0) return null

  return (
    <div className="mb-8 rounded-xl border border-line bg-surface p-5">
      <h2 className="mb-3 text-[13px] font-semibold text-foreground">
        Oczekujące prośby o dostęp ({requests.length})
      </h2>
      <div className="flex flex-col gap-1">
        {requests.map((r) => (
          <div
            key={r.id}
            className="flex items-center justify-between rounded-lg px-2 py-2 hover:bg-surface-alt"
          >
            <div>
              <span className="text-[13.5px] text-foreground">{r.email}</span>
              <span className="ml-2 text-[12px] text-muted">
                {new Date(r.created_at).toLocaleDateString("pl-PL")}
              </span>
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => onAdd(r.email)}
                className="text-[12.5px] font-medium text-accent hover:text-accent-hover"
              >
                Dodaj konto
              </button>
              <button
                onClick={() => void dismiss(r.id)}
                className="text-[12.5px] text-muted hover:text-critical-text"
              >
                Odrzuć
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
