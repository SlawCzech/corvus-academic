import UserManagementTable from "@/components/UserManagementTable"

export default function AdminUsersPage() {
  return (
    <main className="mx-auto max-w-4xl px-4 py-10">
      <h1 className="mb-8 text-2xl font-bold text-gray-900 dark:text-gray-50">
        Zarządzanie użytkownikami
      </h1>
      <UserManagementTable />
    </main>
  )
}
