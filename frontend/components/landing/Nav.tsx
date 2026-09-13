"use client"

import Link from "next/link"

interface NavProps {
  role?: string | null
  isLoggedIn?: boolean
}

export default function Nav({ isLoggedIn }: NavProps) {
  return (
    <nav className="flex h-[76px] items-center justify-between border-b border-line px-16">
      <Link href="/" className="flex items-center gap-2.5">
        <div className="flex h-9 w-9 items-center justify-center rounded-full bg-navy font-serif text-[17px] font-semibold text-[#e8b876]">
          C
        </div>
        <span className="font-serif text-[19px] font-semibold text-foreground">
          Corvus
        </span>
      </Link>

      <div className="hidden items-center gap-9 md:flex">
        <a href="#mozliwosci" className="text-[14px] font-medium text-muted-strong hover:text-accent">
          Możliwości
        </a>
        <a href="#prywatnosc" className="text-[14px] font-medium text-muted-strong hover:text-accent">
          Prywatność i model
        </a>
      </div>

      <div className="flex items-center gap-3">
        {isLoggedIn ? (
          <Link
            href="/students"
            className="flex h-10 items-center rounded-lg bg-accent px-[18px] text-[14px] font-semibold text-white hover:bg-accent-hover transition-colors"
          >
            Otwórz Dashboard
          </Link>
        ) : (
          <>
            <Link
              href="/login"
              className="flex h-10 items-center rounded-lg border border-line px-4 text-[14px] font-semibold text-foreground hover:bg-surface-alt transition-colors"
            >
              Zaloguj się
            </Link>
            <Link
              href="/login?tab=request"
              className="flex h-10 items-center rounded-lg bg-accent px-[18px] text-[14px] font-semibold text-white hover:bg-accent-hover transition-colors"
            >
              Poproś o dostęp
            </Link>
          </>
        )}
      </div>
    </nav>
  )
}
