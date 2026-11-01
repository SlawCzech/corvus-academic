"use client"

import { useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import useSWR from "swr"
import { IconPlus } from "@tabler/icons-react"
import ReviewForm from "@/components/reviews/ReviewForm"
import { retentionNote } from "@/components/reviews/retention"
import { fetcher } from "@/lib/api.client"
import type { Review } from "@/lib/api.types"

/** The promoter's one-off reviews: theses read once, with nobody supervised. */
export default function ReviewList() {
  const router = useRouter()
  const { data: reviews, error } = useSWR<Review[]>("/api/reviews", fetcher)
  const [showForm, setShowForm] = useState(false)

  return (
    <main className="px-12 py-10">
      <div className="mb-6 flex items-start justify-between gap-6">
        <div>
          <h1 className="text-[26px] font-semibold text-foreground">Recenzje</h1>
          <p className="mt-1.5 text-[13.5px] text-muted-strong">
            Jednorazowe recenzje prac, bez profilu studenta.
          </p>
        </div>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="flex h-10 items-center gap-1.5 rounded-lg bg-accent px-4 text-[13px] font-semibold text-white hover:bg-accent-hover transition-colors"
        >
          <IconPlus size={15} stroke={2.25} />
          Nowa recenzja
        </button>
      </div>

      {showForm && (
        <ReviewForm
          onCreated={(review) => router.push(`/reviews/${review.id}`)}
          onCancel={() => setShowForm(false)}
        />
      )}

      {error ? (
        <p className="text-[13px] text-critical-text">Nie udało się wczytać recenzji.</p>
      ) : !reviews ? (
        <p className="text-[13px] text-muted">Wczytywanie…</p>
      ) : reviews.length === 0 ? (
        <p data-testid="reviews-empty" className="text-[13.5px] text-muted">
          Nie ma jeszcze żadnej recenzji.
        </p>
      ) : (
        <ul className="divide-y divide-line/60 rounded-xl border border-line bg-surface">
          {reviews.map((review) => (
            <li key={review.id}>
              <Link
                href={`/reviews/${review.id}`}
                className="flex items-center justify-between gap-6 px-5 py-3.5 hover:bg-surface-alt transition-colors"
              >
                <span className="min-w-0">
                  <span className="block truncate text-[14px] font-semibold text-foreground">
                    {review.full_name}
                  </span>
                  <span className="block truncate text-[12.5px] text-muted-strong">
                    {review.current_topic ?? review.filename}
                  </span>
                </span>
                <span className="shrink-0 text-right text-[12.5px] text-muted">
                  {retentionNote(review.purged_at, review.purge_due_at)}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </main>
  )
}
