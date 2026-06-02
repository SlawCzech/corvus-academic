"use client"

import { useState } from "react"
import AnalysisResultView from "@/components/AnalysisResult"
import FileUpload from "@/components/FileUpload"
import { useAnalysis } from "@/hooks/useAnalysis"

const MODELS = [
  { value: "qwen3:30b-a3b", label: "Qwen 3 · 30B" },
  { value: "gemma4:26b", label: "Gemma 4 · 26B" },
  { value: "deepseek-r1:32b", label: "DeepSeek R1 · 32B" },
] as const

const MODES = [
  {
    value: "full",
    label: "Pełna analiza",
    description: "Struktura, metodologia, wymogi i recenzja",
  },
  {
    value: "review_only",
    label: "Tylko recenzja",
    description: "Pomija analizę szczegółową, generuje recenzję bezpośrednio",
  },
] as const

const TONES = [
  {
    value: "auto",
    label: "Automatyczny",
    description: "Model dobiera ton na podstawie analizy",
  },
  {
    value: "enthusiastic",
    label: "Entuzjastyczny",
    description: "Wyróżniająca, wysoka ocena",
  },
  {
    value: "positive",
    label: "Pozytywny",
    description: "Dobra praca, bez przesady",
  },
  {
    value: "diplomatic",
    label: "Dyplomatyczny",
    description: "Spełnia minimum, powściągliwy",
  },
  {
    value: "negative",
    label: "Negatywny",
    description: "Krytyczny, wymaga poprawy",
  },
] as const

type ModelValue = (typeof MODELS)[number]["value"]
type ModeValue = (typeof MODES)[number]["value"]
type ToneValue = (typeof TONES)[number]["value"]

export default function AnalysisPage() {
  const { submit, status, result, error } = useAnalysis()
  const [model, setModel] = useState<ModelValue>("qwen3:30b-a3b")
  const [mode, setMode] = useState<ModeValue>("full")
  const [tone, setTone] = useState<ToneValue>("auto")

  const idle = status === "idle" || status === "uploading"
  const busy = status === "uploading" || status === "analyzing"

  return (
    <main className="mx-auto max-w-2xl px-4 py-10">
      <h1 className="mb-6 text-2xl font-bold text-gray-900 dark:text-gray-50">
        Analiza pracy dyplomowej
      </h1>

      {idle && (
        <div className="space-y-6">
          <fieldset disabled={status === "uploading"}>
            <legend className="mb-2 text-[13px] font-medium text-gray-700 dark:text-gray-300">
              Model AI
            </legend>
            <div className="flex flex-col gap-2">
              {MODELS.map(({ value, label }) => (
                <label
                  key={value}
                  className="flex items-center gap-2.5 cursor-pointer"
                >
                  <input
                    type="radio"
                    name="model"
                    value={value}
                    checked={model === value}
                    onChange={() => setModel(value)}
                    className="accent-gray-900 dark:accent-white"
                  />
                  <span className="text-[14px] text-gray-900 dark:text-gray-100">
                    {label}
                  </span>
                  <span className="text-[12px] text-gray-400 font-mono">
                    {value}
                  </span>
                </label>
              ))}
            </div>
          </fieldset>

          <fieldset disabled={status === "uploading"}>
            <legend className="mb-2 text-[13px] font-medium text-gray-700 dark:text-gray-300">
              Tryb analizy
            </legend>
            <div className="flex flex-col gap-2">
              {MODES.map(({ value, label, description }) => (
                <label
                  key={value}
                  className="flex items-start gap-2.5 cursor-pointer"
                >
                  <input
                    type="radio"
                    name="mode"
                    value={value}
                    checked={mode === value}
                    onChange={() => setMode(value)}
                    className="mt-0.5 accent-gray-900 dark:accent-white"
                  />
                  <div>
                    <span className="text-[14px] text-gray-900 dark:text-gray-100">
                      {label}
                    </span>
                    <p className="text-[12px] text-gray-400 leading-snug">
                      {description}
                    </p>
                  </div>
                </label>
              ))}
            </div>
          </fieldset>

          <fieldset disabled={status === "uploading"}>
            <legend className="mb-2 text-[13px] font-medium text-gray-700 dark:text-gray-300">
              Ton recenzji
            </legend>
            <div className="flex flex-col gap-2">
              {TONES.map(({ value, label, description }) => (
                <label
                  key={value}
                  className="flex items-start gap-2.5 cursor-pointer"
                >
                  <input
                    type="radio"
                    name="tone"
                    value={value}
                    checked={tone === value}
                    onChange={() => setTone(value)}
                    className="mt-0.5 accent-gray-900 dark:accent-white"
                  />
                  <div>
                    <span className="text-[14px] text-gray-900 dark:text-gray-100">
                      {label}
                    </span>
                    <p className="text-[12px] text-gray-400 leading-snug">
                      {description}
                    </p>
                  </div>
                </label>
              ))}
            </div>
          </fieldset>

          <FileUpload
            onFileSelect={(file) => submit(file, { model, mode, review_tone: tone })}
            disabled={status === "uploading"}
          />
        </div>
      )}

      {busy && (
        <div className="mt-6 flex items-center gap-3 text-gray-600 dark:text-gray-400">
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
            {status === "uploading" ? "Wysyłanie…" : "Analiza w toku…"}
          </span>
        </div>
      )}

      {status === "done" && result && (
        <div className="mt-6">
          <AnalysisResultView result={result} />
        </div>
      )}

      {status === "error" && (
        <p className="mt-6 rounded bg-red-50 p-4 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
          {error ?? "Wystąpił nieoczekiwany błąd."}
        </p>
      )}
    </main>
  )
}
