import LoginEventsTable from "@/components/LoginEventsTable"

export default function LoginEventsPage() {
  return (
    <main className="mx-auto max-w-5xl px-4 py-10">
      <h1 className="mb-8 text-2xl font-bold text-gray-900 dark:text-gray-50">
        Logi logowań
      </h1>
      <LoginEventsTable />
    </main>
  )
}
