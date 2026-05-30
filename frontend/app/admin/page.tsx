import AdminApiKeySection from "@/components/AdminApiKeySection"

export default function AdminPage() {
  return (
    <main className="mx-auto max-w-3xl px-4 py-10">
      <h1 className="mb-8 text-2xl font-bold text-gray-900">Admin Panel</h1>

      <div className="space-y-12">
        <AdminApiKeySection />

        <section data-testid="guidelines-section">
          <h2 className="mb-4 text-lg font-semibold text-gray-900">
            Guidelines
          </h2>
          <p className="mb-4 text-sm text-gray-500">
            Upload university and promoter guidelines. They are loaded as static
            context for every analysis.
          </p>
          <div className="rounded-xl border-2 border-dashed border-gray-300 p-10 text-center text-sm text-gray-400">
            PDF upload (coming in a future release)
          </div>
        </section>

        <section data-testid="users-section">
          <h2 className="mb-4 text-lg font-semibold text-gray-900">Users</h2>
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="pb-2 font-medium text-gray-700">Email</th>
                <th className="pb-2 font-medium text-gray-700">Role</th>
                <th className="pb-2 font-medium text-gray-700">Created</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td
                  colSpan={3}
                  className="py-6 text-center text-gray-400"
                  data-testid="users-empty"
                >
                  No users found.
                </td>
              </tr>
            </tbody>
          </table>
        </section>
      </div>
    </main>
  )
}
