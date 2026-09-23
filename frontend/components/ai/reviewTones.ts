/** The review tones the agent understands, from warmest to coldest. */
export const REVIEW_TONES: { value: string; label: string; description: string }[] = [
  {
    value: "enthusiastic",
    label: "Entuzjastyczny",
    description: "Wyróżniająca, wyjątkowy poziom",
  },
  {
    value: "commendable",
    label: "Pochlebny",
    description: "Bardzo dobra, warta podkreślenia",
  },
  {
    value: "positive",
    label: "Pozytywny",
    description: "Dobra praca, spełnia wymagania",
  },
  {
    value: "diplomatic",
    label: "Dyplomatyczny",
    description: "Spełnia minimum, bez pochwał",
  },
  {
    value: "reserved",
    label: "Powściągliwy",
    description: "Spełnia minimum, z wyraźnymi słabościami",
  },
  {
    value: "negative",
    label: "Negatywny",
    description: "Nie spełnia wymagań, wymaga poprawy",
  },
]
