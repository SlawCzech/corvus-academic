const POINTS = [
  {
    title: "Klucz zaszyfrowany",
    text: "Nigdy nie wraca w odpowiedzi API, nigdy nie trafia do logów.",
  },
  {
    title: "Twoje konto u dostawcy",
    text: "Claude albo OpenAI — przy każdej akcji wybierasz, na którym kluczu pójdzie.",
  },
  {
    title: "Zgodność z wytycznymi",
    text: "Każda praca sprawdzana pod kątem wymogów Waszej uczelni.",
  },
  {
    title: "Ostatnie słowo należy do Ciebie",
    text: "Każdy wynik trzeba świadomie zaakceptować, zanim trafi do akt.",
  },
]

export default function MetaBar() {
  return (
    <section id="prywatnosc" className="mx-auto max-w-[1280px] px-16 pb-24">
      <div className="flex flex-col gap-12 rounded-[20px] bg-navy p-16 lg:flex-row lg:items-center">
        <div className="flex-1">
          <span className="mb-4 block text-[12px] font-semibold uppercase tracking-wider text-[#e8b876]">
            Model i prywatność
          </span>
          <h2 className="text-[28px] font-semibold text-[#fbfaf8]">
            Twój klucz, Twój model.
          </h2>
          <p className="mt-4 max-w-[480px] text-[15px] leading-relaxed text-[#c9d3e0]">
            Akcje AI działają na Twoim kluczu Claude albo OpenAI — bez klucza
            nie ruszą. Gdy uruchamiasz akcję, tekst pracy trafia do wybranego
            dostawcy, a koszt idzie na Twoje konto.
          </p>
        </div>
        <div className="grid flex-1 grid-cols-1 gap-4 sm:grid-cols-2">
          {POINTS.map((p) => (
            <div
              key={p.title}
              className="rounded-xl border border-white/[0.14] bg-white/[0.06] p-5"
            >
              <span className="mb-1.5 block text-[13px] font-semibold text-[#fbfaf8]">
                {p.title}
              </span>
              <span className="text-[12.5px] leading-relaxed text-[#c9d3e0]">
                {p.text}
              </span>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
