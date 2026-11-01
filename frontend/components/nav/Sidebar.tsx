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
  IconSchool,
  IconCpu,
} from "@tabler/icons-react"
import Logo from "@/components/Logo"
import LogoutButton from "@/components/LogoutButton"
import { useHydrated } from "@/hooks/useHydrated"

interface SidebarProps {
  email: string | null
  role: string | null
}

interface NavItem {
  href: string
  label: string
  icon: React.ReactNode
  /** Other path prefixes that belong to this item. */
  also?: string[]
}

function useActive(item: NavItem): boolean {
  const pathname = usePathname()
  return [item.href, ...(item.also ?? [])].some(
    (p) => pathname === p || pathname.startsWith(`${p}/`),
  )
}

function NavLink({ item, compact }: { item: NavItem; compact: boolean }) {
  const active = useActive(item)
  return (
    <Link
      href={item.href}
      title={compact ? item.label : undefined}
      className={`flex h-10 items-center gap-3 whitespace-nowrap rounded-lg text-[13.5px] font-medium transition-colors ${
        compact ? "px-3" : "px-4"
      } ${
        active
          ? "bg-white/8 text-white"
          : "text-[#a8b6c7] hover:bg-white/5 hover:text-white"
      }`}
    >
      <span className="shrink-0">{item.icon}</span>
      {item.label}
    </Link>
  )
}

/**
 * A student's page brings its own sub-nav, and two full-width menus side by
 * side crowd out the content. There the main menu folds to an icon rail and
 * slides out over the page on hover or keyboard focus — without pushing the
 * layout around.
 */
function useCompact(): boolean {
  const pathname = usePathname()
  return /^\/students\/[^/]+/.test(pathname)
}

export default function Sidebar({ email, role }: SidebarProps) {
  const { resolvedTheme, setTheme } = useTheme()
  const isDark = useHydrated() && resolvedTheme === "dark"
  const compact = useCompact()

  // Two roles, two menus: an admin runs the platform, a promoter supervises
  // students. The profile is the only screen they share.
  const items: NavItem[] =
    role === "admin"
      ? [
          {
            href: "/admin/users",
            label: "Użytkownicy",
            icon: <IconUsers size={17} stroke={1.75} />,
          },
          {
            href: "/admin/guidelines",
            label: "Wytyczne",
            icon: <IconBook size={17} stroke={1.75} />,
            // A version's own page is shared with promoters.
            also: ["/guidelines"],
          },
          {
            href: "/admin/models",
            label: "Modele AI",
            icon: <IconCpu size={17} stroke={1.75} />,
          },
          {
            href: "/admin/login-events",
            label: "Logi logowań",
            icon: <IconClipboardList size={17} stroke={1.75} />,
          },
          {
            href: "/profile",
            label: "Profil",
            icon: <IconUserCircle size={17} stroke={1.75} />,
          },
        ]
      : [
          {
            href: "/dashboard",
            label: "Dashboard",
            icon: <IconLayoutDashboard size={17} stroke={1.75} />,
          },
          {
            href: "/students",
            label: "Studenci",
            icon: <IconSchool size={17} stroke={1.75} />,
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

  const initials = (email ?? "?")
    .split(/[.@]/)
    .filter(Boolean)
    .slice(0, 2)
    .map((s) => s[0]?.toUpperCase())
    .join("")

  return (
    <aside
      className={compact ? "group/nav relative z-40 w-16 shrink-0" : "flex w-60 shrink-0"}
    >
      <div
        className={`flex flex-col justify-between bg-navy py-6 ${
          compact
            ? "absolute inset-y-0 left-0 w-16 overflow-hidden px-3 transition-[width,box-shadow] duration-200 ease-out group-hover/nav:w-60 group-hover/nav:shadow-2xl group-focus-within/nav:w-60 group-focus-within/nav:shadow-2xl"
            : "w-full px-4"
        }`}
      >
        <div>
          <Link
            href="/"
            className="mb-9 flex items-center gap-2.5 whitespace-nowrap px-2 text-[#fbfaf8]"
          >
            <Logo size="sm" />
          </Link>

          <nav className="flex flex-col gap-0.5">
            {items.map((item) => (
              <NavLink key={item.href} item={item} compact={compact} />
            ))}
            <button
              type="button"
              onClick={() => setTheme(isDark ? "light" : "dark")}
              title={compact ? "Zmień motyw" : undefined}
              className={`flex h-10 items-center gap-3 whitespace-nowrap rounded-lg text-[13.5px] font-medium text-[#a8b6c7] transition-colors hover:bg-white/5 hover:text-white ${
                compact ? "px-3" : "px-4"
              }`}
            >
              <span className="shrink-0">
                {isDark ? (
                  <IconSun size={17} stroke={1.75} />
                ) : (
                  <IconMoon size={17} stroke={1.75} />
                )}
              </span>
              {isDark ? "Jasny motyw" : "Ciemny motyw"}
            </button>
          </nav>
        </div>

        <div className="flex items-center gap-2.5 whitespace-nowrap border-t border-white/10 px-2 pt-3">
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
      </div>
    </aside>
  )
}
