"use client"

import { useRouter } from "next/navigation"
import { useState } from "react"

export default function LogoutButton() {
  const router = useRouter()
  const [loading, setLoading] = useState(false)

  async function handleLogout() {
    setLoading(true)
    await fetch("/api/auth/logout", { method: "POST" })
    router.push("/login")
  }

  return (
    <button
      onClick={handleLogout}
      disabled={loading}
      className="flex h-8 items-center px-3.5 text-[13px] font-medium border border-gray-200 dark:border-gray-700 rounded-md bg-white dark:bg-gray-950 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors disabled:opacity-50"
    >
      {loading ? "Wylogowywanie…" : "Wyloguj"}
    </button>
  )
}
