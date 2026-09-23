"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { useTheme } from "next-themes"
import {
  IconLayoutDashboard,
  IconUserCircle,
  IconUsers,
  IconClipboardList,
  IconSun,
  IconMoon,
  IconLogout,
  IconBook,
  IconBooks,
} from "@tabler/icons-react"
import LogoutButton from "@/components/LogoutButton"

interface SidebarProps {
  email: string | null
  role: string | null
}

interface NavItem {
  href: string
  label: string
  icon: React.ReactNode
}

function useActive(href: string): boolean {
  const pathname = usePathname()
  return href === "/students" ? pathname.startsWith("/students") : pathname.startsWith(href)
}

function NavLink({ item }: { item: NavItem }) {
  const active = useActive(item.href)
  return (
    <Link
      href={item.href}
      className={`flex h-10 items-center gap-3 rounded-lg px-4 text-[13.5px] font-medium transition-colors ${
        active
          ? "bg-white/8 text-white"
          : "text-[#a8b6c7] hover:bg-white/5 hover:text-white"
      }`}
    >
      {item.icon}
      {item.label}
    </Link>
  )
}

export default function Sidebar({ email, role }: SidebarProps) {
  const { resolvedTheme, setTheme } = useTheme()

  const items: NavItem[] = [
    {
      href: "/students",
      label: "Dashboard",
      icon: <IconLayoutDashboard size={17} stroke={1.75} />,
    },
    {
      href: "/guidelines",
      label: "Wytyczne",
      icon: <IconBook size={17} stroke={1.75} />,
    },
    {
      href: "/profile",
      label: "Profil",
      icon: <IconUserCircle size={17} stroke={1.75} />,
    },
  ]

  if (role === "admin") {
    items.push(
      {
        href: "/admin/users",
        label: "Użytkownicy",
        icon: <IconUsers size={17} stroke={1.75} />,
      },
      {
        href: "/admin/guidelines",
        label: "Katalog wytycznych",
        icon: <IconBooks size={17} stroke={1.75} />,
      },
      {
        href: "/admin/login-events",
        label: "Logi logowań",
        icon: <IconClipboardList size={17} stroke={1.75} />,
      },
    )
  }

  const initials = (email ?? "?")
    .split(/[.@]/)
    .filter(Boolean)
    .slice(0, 2)
    .map((s) => s[0]?.toUpperCase())
    .join("")

  return (
    <aside className="flex w-60 shrink-0 flex-col justify-between bg-navy px-4 py-6">
      <div>
        <Link href="/" className="mb-9 flex items-center gap-2.5 px-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-white/10 font-serif text-[15px] font-semibold text-[#e8b876]">
            C
          </div>
          <span className="font-serif text-[17px] font-semibold text-[#fbfaf8]">
            Corvus
          </span>
        </Link>

        <nav className="flex flex-col gap-0.5">
          {items.map((item) => (
            <NavLink key={item.href} item={item} />
          ))}
          <button
            type="button"
            onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
            className="flex h-10 items-center gap-3 rounded-lg px-4 text-[13.5px] font-medium text-[#a8b6c7] transition-colors hover:bg-white/5 hover:text-white"
          >
            {resolvedTheme === "dark" ? (
              <IconSun size={17} stroke={1.75} />
            ) : (
              <IconMoon size={17} stroke={1.75} />
            )}
            {resolvedTheme === "dark" ? "Jasny motyw" : "Ciemny motyw"}
          </button>
        </nav>
      </div>

      <div className="flex items-center gap-2.5 border-t border-white/10 px-2 pt-3">
        <div className="flex h-[30px] w-[30px] shrink-0 items-center justify-center rounded-full bg-navy-soft text-[12px] font-semibold text-[#e8b876]">
          {initials || "?"}
        </div>
        <div className="min-w-0 flex-1">
          <span className="block truncate text-[12.5px] font-medium text-[#fbfaf8]">
            {email ?? "—"}
          </span>
          <span className="block text-[11px] text-[#8a97ab]">
            {role === "admin" ? "Administrator" : "Promotor"}
          </span>
        </div>
        <LogoutButton className="flex h-7 w-7 items-center justify-center rounded-md text-[#8a97ab] hover:bg-white/5 hover:text-white transition-colors">
          <IconLogout size={16} stroke={1.75} />
        </LogoutButton>
      </div>
    </aside>
  )
}
