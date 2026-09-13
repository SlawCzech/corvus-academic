import LoginEventsTable from "@/components/LoginEventsTable"

export default function LoginEventsPage() {
  return (
    <main className="mx-auto max-w-5xl px-8 py-10">
      <h1 className="mb-8 font-serif text-[26px] font-semibold text-foreground">
        Logi logowań
      </h1>
      <LoginEventsTable />
    </main>
  )
}
