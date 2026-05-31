import {
  IconLayoutList,
  IconMicroscope,
  IconChecklist,
  IconFileDescription,
} from "@tabler/icons-react"
import type { FC } from "react"

interface Capability {
  Icon: FC<{ size?: number; className?: string; "aria-hidden"?: boolean }>
  title: string
  description: string
}

const CAPABILITIES: Capability[] = [
  {
    Icon: IconLayoutList,
    title: "Struktura i spójność",
    description:
      "Weryfikuje obecność i kompletność wymaganych rozdziałów: wstęp z hipotezami, przegląd literatury, metodologia, wyniki, wnioski.",
  },
  {
    Icon: IconMicroscope,
    title: "Metodologia i bibliografia",
    description:
      "Ocenia poprawność metod badawczych, jakość i liczbę źródeł, obecność źródeł obcojęzycznych, poprawność cytowań APA.",
  },
  {
    Icon: IconChecklist,
    title: "Zgodność z wymogami",
    description:
      "Sprawdza pracę pod kątem wytycznych uczelnianych. Osobne profile dla licencjatu i magistra (artykuł naukowy).",
  },
  {
    Icon: IconFileDescription,
    title: "Szkic recenzji",
    description:
      "Generuje recenzję z oceną punktową każdego kryterium i rekomendacją: dopuścić do obrony lub zwrócić do poprawy.",
  },
]

export default function Capabilities() {
  return (
    <div className="max-w-[580px] mx-auto px-8 mb-12">
      <div className="border border-gray-200 dark:border-gray-800 rounded-xl overflow-hidden">
        {CAPABILITIES.map(({ Icon, title, description }, index) => (
          <div
            key={title}
            className={`flex gap-3.5 px-5 py-4 bg-white dark:bg-gray-950 ${
              index < CAPABILITIES.length - 1
                ? "border-b border-gray-100 dark:border-gray-800"
                : ""
            }`}
          >
            <Icon
              size={16}
              aria-hidden
              className="text-gray-400 dark:text-gray-500 mt-0.5 shrink-0"
            />
            <div>
              <p className="text-[14px] font-medium text-gray-900 dark:text-gray-50 mb-0.5">
                {title}
              </p>
              <p className="text-[13px] leading-[1.55] text-gray-500 dark:text-gray-400">
                {description}
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
