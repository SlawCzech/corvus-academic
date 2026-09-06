import { cookies } from "next/headers"
import { decodeToken } from "@/lib/auth"
import ApiKeySection from "@/components/ApiKeySection"
import ChangePasswordForm from "@/components/ChangePasswordForm"

export default async function ProfilePage() {
  const cookieStore = await cookies()
  const token = cookieStore.get("access_token")?.value ?? ""
  const payload = decodeToken(token)

  return (
    <main className="mx-auto max-w-2xl px-4 py-10">
      <h1 className="mb-8 text-2xl font-bold text-gray-900 dark:text-gray-50">Profil</h1>

      <section className="mb-10">
        <h2 className="mb-4 text-base font-semibold text-gray-900 dark:text-gray-100">Informacje</h2>
        <dl className="space-y-2 text-sm">
          <div className="flex gap-4">
            <dt className="w-20 text-gray-500">Email</dt>
            <dd className="text-gray-900 dark:text-gray-100">{payload?.email ?? "—"}</dd>
          </div>
          <div className="flex gap-4">
            <dt className="w-20 text-gray-500">Rola</dt>
            <dd className="text-gray-900 dark:text-gray-100">{payload?.role ?? "—"}</dd>
          </div>
        </dl>
      </section>

      <section className="mb-10">
        <h2 className="mb-4 text-base font-semibold text-gray-900 dark:text-gray-100">
          Własny klucz API
        </h2>
        <ApiKeySection />
      </section>

      <section>
        <h2 className="mb-4 text-base font-semibold text-gray-900 dark:text-gray-100">
          Zmień hasło
        </h2>
        <ChangePasswordForm />
      </section>
    </main>
  )
}
