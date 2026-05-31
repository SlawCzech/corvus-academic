"use client"

import Link from "next/link"
import { useTheme } from "next-themes"
import { IconSun, IconMoon } from "@tabler/icons-react"

export default function Nav() {
  const { resolvedTheme, setTheme } = useTheme()

  return (
    <nav className="h-14 flex items-center justify-between px-8 border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950">
      <Link
        href="/"
        aria-label="Corvus — strona główna"
        className="flex items-center gap-2"
      >
        <div className="flex h-6 w-6 items-center justify-center rounded-[5px] bg-gray-900 dark:bg-white text-white dark:text-gray-900 text-[13px] font-medium select-none">
          C
        </div>
        <span className="text-[15px] font-medium tracking-tight">Corvus</span>
      </Link>

      <div className="flex items-center gap-2">
        <button
          aria-label="Przełącz motyw"
          onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
          className="flex h-[30px] w-[30px] items-center justify-center rounded-md border border-gray-200 dark:border-gray-700 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
        >
          {resolvedTheme === "dark" ? (
            <IconSun size={14} aria-hidden />
          ) : (
            <IconMoon size={14} aria-hidden />
          )}
        </button>

        <Link
          href="/login"
          className="flex h-8 items-center px-3.5 text-[13px] font-medium border border-gray-200 dark:border-gray-700 rounded-md bg-white dark:bg-gray-950 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
        >
          Zaloguj się
        </Link>
      </div>
    </nav>
  )
}
