"use client"

import { useState } from "react"
import { IconSparkles } from "@tabler/icons-react"
import { seedDemoStudents } from "@/lib/api.client"

interface DemoStudentsOfferProps {
  onLoaded: () => void
}

/**
 * An empty roster's way in: seven fictional students with meeting notes and
 * theses built to exercise the AI actions (docs/specs/demo-fixtures.md).
 * Once loaded they are ordinary students — deleted the ordinary way.
 */
export default function DemoStudentsOffer({ onLoaded }: DemoStudentsOfferProps) {
  const [busy, setBusy] = useState(false)
  const [failure, setFailure] = useState<string | null>(null)

  async function load(): Promise<void> {
    setBusy(true)
    setFailure(null)
    try {
      await seedDemoStudents()
      onLoaded()
    } catch (err) {
      setFailure(err instanceof Error ? err.message : "Nie udało się wczytać studentów")
    } finally {
      setBusy(false)
    }
  }

  return (
    <div
      data-testid="demo-students-offer"
      className="rounded-xl border border-line bg-surface px-6 py-5"
    >
      <p className="text-[14px] font-semibold text-foreground">
        Nie masz jeszcze żadnych studentów.
      </p>
      <p className="mt-1.5 max-w-2xl text-[13px] text-muted-strong">
        Możesz zacząć od przykładowych: siedmioro fikcyjnych studentów z notatkami ze spotkań i
        pracami o różnej jakości — z celowo zaszytymi błędami, żeby było widać, co znajdują akcje
        AI. Usuwasz ich jak każdego innego studenta, kiedy przejdziesz na własne prace.
      </p>
      <button
        type="button"
        onClick={() => void load()}
        disabled={busy}
        data-testid="load-demo-students"
        className="mt-4 flex h-9 items-center gap-1.5 rounded-lg bg-accent px-4 text-[13px] font-semibold text-white hover:bg-accent-hover transition-colors disabled:opacity-50"
      >
        <IconSparkles size={15} stroke={2} />
        {busy ? "Wczytuję…" : "Wczytaj przykładowych studentów"}
      </button>
      {failure && <p className="mt-2 text-[12.5px] text-critical-text">{failure}</p>}
    </div>
  )
}
