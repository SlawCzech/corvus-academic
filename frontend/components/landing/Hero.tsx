import Link from "next/link"

export default function Hero() {
  return (
    <section className="mx-auto flex max-w-[1280px] items-center gap-16 px-16 pb-22 pt-24">
      <div className="max-w-[560px] flex-1">
        <span className="mb-5 block text-[12px] font-semibold uppercase tracking-wider text-accent">
          Dla promotorów i recenzentów
        </span>
        <h1 className="text-[46px] font-semibold leading-[1.15] tracking-[-0.01em] text-foreground">
          Mentoring prac dyplomowych, wsparty AI, bez utraty kontroli nad
          oceną.
        </h1>
        <p className="mt-6 max-w-[500px] text-[16px] leading-relaxed text-muted-strong">
          Corvus prowadzi Twoich studentów od propozycji tematu po pytania na
          obronę — analizuje kolejne wersje pracy, proponuje szkic recenzji z
          punktacją i pilnuje zgodności z wytycznymi uczelni. Ty zawsze
          decydujesz ostatni.
        </p>
        <div className="mt-9 flex gap-3.5">
          <Link
            href="/login?tab=request"
            className="flex h-11 items-center rounded-lg bg-accent px-6 text-[14px] font-semibold text-white hover:bg-accent-hover transition-colors"
          >
            Poproś o dostęp
          </Link>
          <Link
            href="/login"
            className="flex h-11 items-center rounded-lg border border-line px-5 text-[14px] font-semibold text-foreground hover:bg-surface-alt transition-colors"
          >
            Zaloguj się
          </Link>
        </div>
      </div>

      <div className="hidden flex-1 justify-center lg:flex">
        <div className="w-[400px] rounded-2xl border border-line bg-surface p-7 shadow-[0_4px_12px_rgba(28,35,51,0.08),0_16px_40px_rgba(28,35,51,0.08)]">
          <div className="mb-5 flex items-start justify-between">
            <div>
              <span className="block text-[11px] uppercase tracking-wider text-muted">
                Wynik łączny
              </span>
              <span className="font-serif text-[34px] font-semibold text-foreground">
                88%
              </span>
            </div>
            <span className="rounded-full border border-success-border bg-success-bg px-3 py-1 text-[12px] font-semibold text-success-text">
              Gotowe do obrony
            </span>
          </div>
          <div className="mb-5 h-2 w-full rounded-full bg-surface-alt">
            <div className="h-2 w-[88%] rounded-full bg-accent" />
          </div>
          <div className="flex flex-col gap-2.5">
            {[
              { label: "Metodologia badawcza", value: "13/15", pct: 87 },
              { label: "Dobór i wykorzystanie źródeł", value: "22/25", pct: 88 },
              { label: "Poprawność językowa", value: "9/10", pct: 90 },
            ].map((row) => (
              <div key={row.label}>
                <div className="mb-1 flex justify-between text-[12.5px] text-muted-strong">
                  <span>{row.label}</span>
                  <span>{row.value}</span>
                </div>
                <div className="h-[5px] w-full rounded-full bg-surface-alt">
                  <div
                    className="h-[5px] rounded-full bg-accent"
                    style={{ width: `${row.pct}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}
