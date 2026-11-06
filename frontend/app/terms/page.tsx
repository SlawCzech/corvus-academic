import type { Metadata } from "next"

import LegalPage from "@/components/legal/LegalPage"
import { operator } from "@/content/legal/operator"
import Terms from "@/content/legal/Terms"

export const metadata: Metadata = { title: "Regulamin — Corvus" }

export default function TermsPage() {
  return (
    <LegalPage>
      <Terms operator={operator()} />
    </LegalPage>
  )
}
