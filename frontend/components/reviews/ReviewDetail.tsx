"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import useSWR, { useSWRConfig } from "swr"
import ActionPanel from "@/components/students/ActionPanel"
import DeleteStudentConfirm from "@/components/students/DeleteStudentConfirm"
import LatestResults from "@/components/students/LatestResults"
import { retentionNote } from "@/components/reviews/retention"
import { draftFileUrl, fetcher, promoteReview } from "@/lib/api.client"
import type { ActionType, AgentAction, Student, ThesisDraft } from "@/lib/api.types"

/** Matches `app`'s ONE_OFF_ACTIONS. */
const REVIEW_ACTIONS: ActionType[] = [
  "generate_review",
  "verify_bibliography",
  "defence_questions",
]

/**
 * One thesis, read once. The row is a hidden student, so everything here is
 * the student's own endpoints; a promoted one has moved to its student page.
 */
export default function ReviewDetail({ reviewId }: { reviewId: string }) {
  const studentKey = `/api/students/${reviewId}`
  const router = useRouter()
  const { mutate } = useSWRConfig()
  const { data: review, error } = useSWR<Student>(studentKey, fetcher)
  const { data: drafts } = useSWR<ThesisDraft[]>(`${studentKey}/drafts`, fetcher)
  const { data: actions } = useSWR<AgentAction[]>(`${studentKey}/actions`, fetcher)

  const [promoting, setPromoting] = useState(false)
  const [promoteError, setPromoteError] = useState<string | null>(null)
  const [confirmingPromotion, setConfirmingPromotion] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const isStudent = review?.is_one_off === false
  useEffect(() => {
    if (isStudent) router.replace(`/students/${reviewId}`)
  }, [isStudent, reviewId, router])

  if (error) {
    return (
      <main className="px-12 py-10">
        <p className="text-[13px] text-critical-text">Nie znaleziono recenzji.</p>
      </main>
    )
  }
  if (!review || isStudent) {
    return (
      <main className="px-12 py-10">
        <p className="text-[13px] text-muted">Wczytywanie…</p>
      </main>
    )
  }

  const thesis = drafts?.[0]

  async function promote(): Promise<void> {
    setPromoting(true)
    setPromoteError(null)
    try {
      const student = await promoteReview(reviewId)
      void mutate(studentKey, student, { revalidate: false })
      void mutate("/api/reviews")
      void mutate("/api/students")
      void mutate("/api/dashboard/summary")
    } catch (err) {
      setPromoteError(
        err instanceof Error ? err.message : "Nie udało się założyć profilu studenta",
      )
      setPromoting(false)
    }
  }

  return (
    <main className="px-12 py-10">
      <Link href="/reviews" className="text-[12.5px] text-muted hover:text-foreground">
        ← Recenzje
      </Link>
      <h1 className="mt-2 text-[26px] font-semibold text-foreground">{review.full_name}</h1>
      <p className="mt-1.5 text-[13.5px] text-muted-strong">
        {review.current_topic ?? thesis?.filename}
      </p>
      {thesis && (
        <p data-testid="review-thesis" className="mt-1 text-[12.5px] text-muted">
          {thesis.has_file ? (
            <a href={draftFileUrl(reviewId, thesis.id)} className="text-accent hover:underline">
              {thesis.filename}
            </a>
          ) : (
            thesis.filename
          )}
          {" · "}
          {retentionNote(thesis.purged_at, thesis.purge_due_at)}
        </p>
      )}

      <div className="mt-7 space-y-7">
        {thesis?.purged_at ? (
          <p className="text-[13.5px] text-muted-strong">
            Tekst pracy został usunięty, więc nowych akcji nie można już uruchomić. Wyniki zostają.
          </p>
        ) : (
          <ActionPanel student={review} only={REVIEW_ACTIONS} />
        )}

        <LatestResults actions={actions ?? []} />

        <section className="rounded-xl border border-line bg-surface p-5">
          <h2 className="text-[14px] font-semibold text-foreground">Profil studenta</h2>
          <p className="mt-1 text-[13px] text-muted-strong">
            Jeśli zostajesz promotorem tej pracy, załóż profil. Autor trafi na listę studentów
            razem z pracą i wynikami. Tego nie da się cofnąć.
          </p>
          {thesis?.purged_at && (
            <p data-testid="promote-purged" className="mt-2 text-[13px] text-major-text">
              Tekst tej pracy jest już usunięty. Profil przejmie wyniki, a dalsze akcje będą
              wymagały ponownego wgrania pracy.
            </p>
          )}
          {promoteError && (
            <p className="mt-2 text-[13px] text-critical-text">{promoteError}</p>
          )}
          <div className="mt-3 flex items-center gap-2">
            {confirmingPromotion ? (
              <>
                <button
                  type="button"
                  onClick={() => void promote()}
                  disabled={promoting}
                  data-testid="promote-confirm"
                  className="h-9 rounded-lg bg-accent px-4 text-[13px] font-semibold text-white hover:bg-accent-hover transition-colors disabled:opacity-50"
                >
                  {promoting ? "Zakładanie…" : `Dodaj: ${review.full_name}`}
                </button>
                <button
                  type="button"
                  onClick={() => setConfirmingPromotion(false)}
                  className="h-9 rounded-lg border border-line px-4 text-[13px] font-medium text-foreground hover:bg-surface-alt transition-colors"
                >
                  Anuluj
                </button>
              </>
            ) : (
              <button
                type="button"
                onClick={() => setConfirmingPromotion(true)}
                data-testid="promote-review"
                className="h-9 rounded-lg border border-accent px-4 text-[13px] font-semibold text-accent-hover hover:bg-accent-soft transition-colors"
              >
                Załóż profil studenta
              </button>
            )}
          </div>
        </section>

        {deleting ? (
          <DeleteStudentConfirm
            student={review}
            onDeleted={() => router.push("/reviews")}
            onCancel={() => setDeleting(false)}
          />
        ) : (
          <div className="text-right">
            <button
              type="button"
              onClick={() => setDeleting(true)}
              className="text-[12.5px] text-muted hover:text-critical-text"
            >
              Usuń recenzję
            </button>
          </div>
        )}
      </div>
    </main>
  )
}
