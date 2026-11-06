import type { Metadata } from "next"

import AcceptTermsForm from "@/components/legal/AcceptTermsForm"
import LegalPage from "@/components/legal/LegalPage"
import { operator } from "@/content/legal/operator"
import Terms from "@/content/legal/Terms"
import { TERMS_VERSION } from "@/content/legal/version"

export const metadata: Metadata = { title: "Akceptacja regulaminu — Corvus" }

interface AcceptPageProps {
  searchParams: Promise<{ next?: string }>
}

/** Only a path on this site: `next` comes from the address bar. */
function safeNext(next: string | undefined): string {
  return next && next.startsWith("/") && !next.startsWith("//") ? next : "/dashboard"
}

export default async function AcceptTermsPage({ searchParams }: AcceptPageProps) {
  const { next } = await searchParams
  return (
    <LegalPage>
      <div className="mb-8 rounded-xl border border-line bg-surface-alt p-5 text-[14px] leading-relaxed text-muted-strong">
        Zanim zaczniesz pracę ze studentami, przeczytaj i zaakceptuj regulamin. Zawiera umowę
        powierzenia przetwarzania danych studentów (§ 5): Corvus przechowuje je w Twoim imieniu.
      </div>
      <Terms operator={operator()} />
      <AcceptTermsForm version={TERMS_VERSION} next={safeNext(next)} />
    </LegalPage>
  )
}
