import {
  IconBulb,
  IconMessageQuestion,
  IconTrendingUp,
  IconFlask,
  IconNotes,
  IconFileCheck,
} from "@tabler/icons-react"
import type { FC } from "react"

interface Capability {
  Icon: FC<{ size?: number; stroke?: number; className?: string; "aria-hidden"?: boolean }>
  title: string
  description: string
}

const CAPABILITIES: Capability[] = [
  {
    Icon: IconBulb,
    title: "Propozycja tematu",
    description:
      "Trzy konkretne propozycje na podstawie kierunku studiów i notatek z pierwszych spotkań.",
  },
  {
    Icon: IconMessageQuestion,
    title: "Pytania na obronę",
    description:
      "Wygenerowane z ostatniej wersji pracy, gotowe do przekazania studentowi przed obroną.",
  },
  {
    Icon: IconTrendingUp,
    title: "Sprawdzenie postępu",
    description:
      "Porównanie dwóch ostatnich wersji — co się zmieniło i czy to krok naprzód.",
  },
  {
    Icon: IconFlask,
    title: "Ocena metodologii",
    description:
      "Uwagi do doboru metody badawczej, próby i wykorzystanej bibliografii.",
  },
  {
    Icon: IconNotes,
    title: "Szkic notatki",
    description:
      "Twoje skrócone punkty ze spotkania — rozwinięte w czytelną notatkę do akt.",
  },
  {
    Icon: IconFileCheck,
    title: "Szkic recenzji",
    description:
      "Pełna recenzja ostatniej wersji z punktacją per kryterium i rekomendacją końcową.",
  },
]

export default function Capabilities() {
  return (
    <section id="mozliwosci" className="mx-auto max-w-[1280px] px-16 pb-24">
      <h2 className="text-center text-[30px] font-semibold text-foreground">
        Sześć akcji, jedna decyzja na końcu
      </h2>
      <p className="mx-auto mt-3 max-w-[560px] text-center text-[15px] text-muted-strong">
        Model proponuje, promotor akceptuje albo poprawia. Nic nie trafia do
        akt studenta bez Twojej zgody.
      </p>

      <div className="mt-14 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {CAPABILITIES.map(({ Icon, title, description }) => (
          <div
            key={title}
            className="rounded-xl border border-line bg-surface p-6 shadow-[0_1px_2px_rgba(28,35,51,0.04)]"
          >
            <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-[10px] bg-accent-soft text-accent">
              <Icon size={20} stroke={1.75} aria-hidden />
            </div>
            <p className="mb-1.5 text-[16px] font-semibold text-foreground">
              {title}
            </p>
            <p className="text-[13.5px] leading-[1.55] text-muted-strong">
              {description}
            </p>
          </div>
        ))}
      </div>
    </section>
  )
}
