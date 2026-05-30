"use client"

import AnalysisResultView from "@/components/AnalysisResult"
import FileUpload from "@/components/FileUpload"
import { useAnalysis } from "@/hooks/useAnalysis"

export default function AnalysisPage() {
  const { submit, status, result, error } = useAnalysis()

  return (
    <main className="mx-auto max-w-2xl px-4 py-10">
      <h1 className="mb-6 text-2xl font-bold text-gray-900">
        Thesis Analysis
      </h1>

      {(status === "idle" || status === "uploading") && (
        <FileUpload
          onFileSelect={submit}
          disabled={status === "uploading"}
        />
      )}

      {(status === "uploading" || status === "analyzing") && (
        <div className="mt-6 flex items-center gap-3 text-gray-600">
          <svg
            className="h-5 w-5 animate-spin"
            viewBox="0 0 24 24"
            fill="none"
            aria-label="Loading"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
            />
          </svg>
          <span>
            {status === "uploading" ? "Uploading…" : "Analyzing thesis…"}
          </span>
        </div>
      )}

      {status === "done" && result && (
        <div className="mt-6">
          <AnalysisResultView result={result} />
        </div>
      )}

      {status === "error" && (
        <p className="mt-6 rounded bg-red-50 p-4 text-sm text-red-700">
          {error ?? "An unexpected error occurred."}
        </p>
      )}
    </main>
  )
}
