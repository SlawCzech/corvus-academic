import AnalysisHistoryTable from "@/components/AnalysisHistoryTable"

export default function AnalysisHistoryPage() {
  return (
    <main className="mx-auto max-w-4xl px-4 py-10">
      <h1 className="mb-8 text-2xl font-bold text-gray-900 dark:text-gray-50">
        Historia analiz
      </h1>
      <AnalysisHistoryTable />
    </main>
  )
}
