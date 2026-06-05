"use client"

import Link from "next/link"
import { useTheme } from "next-themes"
import { IconSun, IconMoon, IconChevronDown } from "@tabler/icons-react"
import { useState } from "react"
import LogoutButton from "@/components/LogoutButton"

interface NavProps {
  role?: string | null
  isLoggedIn?: boolean
}

export default function Nav({ role, isLoggedIn }: NavProps) {
  const { resolvedTheme, setTheme } = useTheme()
  const [adminOpen, setAdminOpen] = useState(false)

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
        {isLoggedIn && (
          <>
            <Link
              href="/analysis/history"
              className="flex h-8 items-center px-3.5 text-[13px] font-medium text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white transition-colors"
            >
              Historia
            </Link>
            <Link
              href="/profile"
              className="flex h-8 items-center px-3.5 text-[13px] font-medium text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white transition-colors"
            >
              Profil
            </Link>
            {role === "ADMIN" && (
              <div className="relative">
                <button
                  onClick={() => setAdminOpen((o) => !o)}
                  className="flex h-8 items-center gap-1 px-3.5 text-[13px] font-medium text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white transition-colors"
                >
                  Admin
                  <IconChevronDown size={12} aria-hidden />
                </button>
                {adminOpen && (
                  <div className="absolute right-0 top-full mt-1 w-44 rounded-md border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-950 shadow-md z-50">
                    <Link
                      href="/admin/users"
                      onClick={() => setAdminOpen(false)}
                      className="block px-4 py-2 text-[13px] text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800"
                    >
                      Użytkownicy
                    </Link>
                    <Link
                      href="/admin/login-events"
                      onClick={() => setAdminOpen(false)}
                      className="block px-4 py-2 text-[13px] text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800"
                    >
                      Logi logowań
                    </Link>
                    <Link
                      href="/admin"
                      onClick={() => setAdminOpen(false)}
                      className="block px-4 py-2 text-[13px] text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800"
                    >
                      Panel admina
                    </Link>
                  </div>
                )}
              </div>
            )}
          </>
        )}

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

        {isLoggedIn ? (
          <LogoutButton />
        ) : (
          <Link
            href="/login"
            className="flex h-8 items-center px-3.5 text-[13px] font-medium border border-gray-200 dark:border-gray-700 rounded-md bg-white dark:bg-gray-950 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
          >
            Zaloguj się
          </Link>
        )}
      </div>
    </nav>
  )
}
