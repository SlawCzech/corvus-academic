import GuidelineAdmin from "@/components/guidelines/GuidelineAdmin"

export default function AdminGuidelinesPage() {
  return (
    <main className="mx-auto max-w-4xl px-8 py-10">
      <h1 className="mb-2 font-serif text-[26px] font-semibold text-foreground">
        Wytyczne
      </h1>
      <p className="mb-8 text-[13.5px] text-muted">
        Promotorzy widzą tylko opublikowane wersje. Opublikowanej wersji nie zmienisz —
        poprawka to nowa wersja, zaczynająca od treści obowiązującej.
      </p>
      <GuidelineAdmin />
    </main>
  )
}
