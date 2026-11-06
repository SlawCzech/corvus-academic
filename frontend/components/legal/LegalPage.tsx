import Link from "next/link"
import type { ReactNode } from "react"

import Logo from "@/components/Logo"

/** The frame of a public legal page: the logo home, the text, the two links. */
export default function LegalPage({ children }: { children: ReactNode }) {
  return (
    <div className="mx-auto w-full max-w-[720px] px-4 py-10 sm:px-8">
      <Link href="/" className="mb-10 flex items-center gap-2.5 text-foreground">
        <Logo size="sm" />
      </Link>
      {children}
      <LegalLinks className="mt-12 border-t border-line pt-6" />
    </div>
  )
}

export function LegalLinks({ className = "" }: { className?: string }) {
  return (
    <nav className={`flex gap-5 text-[12.5px] text-muted ${className}`}>
      <Link href="/terms" className="hover:text-foreground hover:underline">
        Regulamin
      </Link>
      <Link href="/privacy" className="hover:text-foreground hover:underline">
        Polityka prywatności
      </Link>
    </nav>
  )
}
