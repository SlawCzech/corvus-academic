import { cookies } from "next/headers"
import { decodeToken } from "@/lib/auth"
import ApiKeySection from "@/components/ApiKeySection"
import ProfileAiDefaults from "@/components/ProfileAiDefaults"
import ChangePasswordForm from "@/components/ChangePasswordForm"

export default async function ProfilePage() {
  const cookieStore = await cookies()
  const token = cookieStore.get("access_token")?.value ?? ""
  const payload = decodeToken(token)

  return (
    <main className="mx-auto max-w-2xl px-8 py-10">
      <h1 className="mb-8 text-[26px] font-semibold text-foreground">Profil</h1>

      <section className="mb-10">
        <h2 className="mb-4 text-[15px] font-semibold text-foreground">Informacje</h2>
        <dl className="space-y-2 text-[13.5px]">
          <div className="flex gap-4">
            <dt className="w-20 text-muted">Email</dt>
            <dd className="text-foreground">{payload?.email ?? "—"}</dd>
          </div>
          <div className="flex gap-4">
            <dt className="w-20 text-muted">Rola</dt>
            <dd className="text-foreground">{payload?.role ?? "—"}</dd>
          </div>
        </dl>
      </section>

      <section className="mb-10">
        <h2 className="mb-4 text-[15px] font-semibold text-foreground">
          Własny klucz API
        </h2>
        <ApiKeySection />
      </section>

      <section className="mb-10">
        <h2 className="mb-4 text-[15px] font-semibold text-foreground">
          Domyślne ustawienia AI
        </h2>
        <ProfileAiDefaults />
      </section>

      <section>
        <h2 className="mb-4 text-[15px] font-semibold text-foreground">
          Zmień hasło
        </h2>
        <ChangePasswordForm />
      </section>
    </main>
  )
}
