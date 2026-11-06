import type { Metadata } from "next"

import LegalPage from "@/components/legal/LegalPage"
import { operator } from "@/content/legal/operator"
import Privacy from "@/content/legal/Privacy"

export const metadata: Metadata = { title: "Polityka prywatności — Corvus" }

export default function PrivacyPage() {
  return (
    <LegalPage>
      <Privacy operator={operator()} />
    </LegalPage>
  )
}
