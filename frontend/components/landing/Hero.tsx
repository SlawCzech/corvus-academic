const STAGES = [
  { name: "Temat", note: "propozycje z kierunku i pierwszych spotkań" },
  { name: "Spotkania", note: "notatki, które zostają w aktach studenta" },
  { name: "Fragmenty", note: "rozdziały oddawane w rundach, z feedbackiem" },
  { name: "Wersje pracy", note: "co się zmieniło od poprzedniej" },
  { name: "Recenzja próbna", note: "co poprawić przed złożeniem" },
  { name: "Recenzja finalna", note: "ocena skończonej pracy" },
  { name: "Obrona", note: "pytania na egzamin" },
];

export default function Hero() {
  return (
    <section className="mx-auto flex max-w-[1280px] items-center gap-16 px-4 pb-20 pt-16 sm:px-8 lg:px-16 lg:pt-20">
      <div className="max-w-[580px] flex-1">
        <p className="mb-5 text-[14px] font-medium text-accent">
          Dla promotorów i recenzentów
        </p>
        <h1 className="font-serif text-[34px] font-semibold leading-[1.2] text-foreground sm:text-[42px]">
          Recenzowanie i prowadzenie prac dyplomowych
        </h1>
        <p className="mt-6 max-w-[520px] text-[16px] leading-relaxed text-muted-strong">
          Corvus czyta pracę razem z wytycznymi uczelni i przygotowuje szkic
          recenzji: z punktacją według rubryki i z uwagami, z których każda
          wskazuje cytat w tekście. Pomaga też prowadzić studenta od tematu do
          obrony. Każdy szkic promotor czyta i akceptuje albo odrzuca.
        </p>
      </div>

      <div className="hidden flex-1 justify-center lg:flex">
        <ol className="w-[400px] rounded-2xl border border-line bg-surface p-7">
          {STAGES.map((s, i) => (
            <li key={s.name} className="relative flex gap-4 pb-5 last:pb-0">
              {i < STAGES.length - 1 && (
                <span
                  aria-hidden
                  className="absolute left-[5px] top-4 h-full w-px bg-line"
                />
              )}
              <span
                aria-hidden
                className="mt-1.5 h-[11px] w-[11px] shrink-0 rounded-full border-2 border-accent bg-surface"
              />
              <div>
                <p className="text-[14px] font-semibold text-foreground">
                  {s.name}
                </p>
                <p className="text-[13px] text-muted-strong">{s.note}</p>
              </div>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
