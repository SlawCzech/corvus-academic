import { cookies } from "next/headers"
import Logo from "@/components/Logo"
import ChangePasswordForm from "@/components/ChangePasswordForm"
import { getRole, homeFor } from "@/lib/auth"

/**
 * The one page open on a temporary password from an admin. The proxy sends
 * every other screen here, and away from here once the password is the
 * user's own.
 */
export default async function PasswordPage() {
  const token = (await cookies()).get("access_token")?.value ?? ""

  return (
    <div className="flex min-h-screen flex-col items-center justify-center px-4 py-12">
      <div className="w-full max-w-[380px]">
        <div className="mb-10 flex items-center gap-2.5 text-foreground">
          <Logo size="sm" />
        </div>
        <h1 className="mb-2 text-[20px] font-semibold text-foreground">
          Ustaw własne hasło
        </h1>
        <p className="mb-6 text-[13.5px] text-muted">
          Logujesz się hasłem tymczasowym od administratora. Zanim przejdziesz
          dalej, wpisz je jeszcze raz i wybierz nowe, znane tylko Tobie.
        </p>
        <ChangePasswordForm temporaryThen={homeFor(getRole(token))} />
      </div>
    </div>
  )
}
