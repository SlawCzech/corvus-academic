"use client"

import { useState } from "react"
import useSWR from "swr"
import { IconFileCheck, IconMessage2, IconUpload } from "@tabler/icons-react"
import FragmentCard from "@/components/students/FragmentCard"
import FragmentUploadForm from "@/components/students/FragmentUploadForm"
import PartMap from "@/components/students/PartMap"
import { isUnfinished } from "@/hooks/useAction"
import { fetcher } from "@/lib/api.client"
import type { Timeline } from "@/lib/api.types"

// As often as `useAction` polls a running action.
const POLL_MS = 3000

function formatDay(day: string): string {
  return new Date(`${day}T12:00:00`).toLocaleDateString("pl-PL", {
    day: "numeric",
    month: "long",
    year: "numeric",
  })
}

/**
 * "Przebieg pracy": where the thesis stands, part by part, and how it got
 * there. Fragments, meeting notes and whole versions on one line of time.
 */
export default function WorkTimeline({ studentId }: { studentId: string }) {
  const [adding, setAdding] = useState(false)
  const { data, error, mutate } = useSWR<Timeline>(
    `/api/students/${studentId}/timeline`,
    fetcher,
    {
      refreshInterval: (current) =>
        current?.events.some(
          (e) => e.fragment?.review && isUnfinished(e.fragment.review),
        )
          ? POLL_MS
          : 0,
    },
  )
  const refresh = (): void => void mutate()

  return (
    <div className="max-w-3xl">
      <div className="mb-5 flex items-center justify-between gap-3">
        <h1 className="text-[24px] font-semibold text-foreground">Przebieg pracy</h1>
        {!adding && (
          <button
            type="button"
            onClick={() => setAdding(true)}
            className="flex h-9 items-center gap-2 rounded-lg bg-accent px-4 text-[13px] font-semibold text-white hover:bg-accent-hover"
          >
            <IconUpload size={15} stroke={2} />
            Dodaj fragment
          </button>
        )}
      </div>

      {error && (
        <p role="alert" className="mb-4 text-[13px] text-critical-text">
          Nie udało się wczytać przebiegu pracy.
        </p>
      )}

      {adding && (
        <FragmentUploadForm
          studentId={studentId}
          parts={data?.parts ?? []}
          onSaved={refresh}
          onClose={() => setAdding(false)}
        />
      )}

      {data && (
        <>
          <PartMap studentId={studentId} parts={data.parts} onChange={refresh} />
          {data.events.length === 0 ? (
            <p className="text-[13.5px] text-muted">
              Tu pojawią się fragmenty pracy, notatki ze spotkań i kolejne wersje.
            </p>
          ) : (
            <ol className="border-l border-line pl-5">
              {data.events.map((event) => {
                const id =
                  event.fragment?.id ?? event.note?.id ?? event.draft?.id ?? event.on
                return (
                  <li key={id} data-testid="timeline-event" className="mb-4">
                    <p className="mb-1 text-[12.5px] text-muted">{formatDay(event.on)}</p>
                    {event.fragment && (
                      <FragmentCard
                        studentId={studentId}
                        entry={event.fragment}
                        onChange={refresh}
                      />
                    )}
                    {event.note && (
                      <div className="flex gap-2 text-[13.5px] text-foreground">
                        <IconMessage2
                          size={16}
                          stroke={1.75}
                          className="mt-0.5 shrink-0 text-muted"
                        />
                        <p className="whitespace-pre-wrap">{event.note.content}</p>
                      </div>
                    )}
                    {event.draft && (
                      <div className="flex gap-2 text-[13.5px] text-foreground">
                        <IconFileCheck
                          size={16}
                          stroke={1.75}
                          className="mt-0.5 shrink-0 text-muted"
                        />
                        <span>
                          Wersja {event.draft.version_number} całej pracy
                          {event.draft.is_accepted ? " (zaakceptowana)" : ""}
                        </span>
                      </div>
                    )}
                  </li>
                )
              })}
            </ol>
          )}
        </>
      )}
    </div>
  )
}
