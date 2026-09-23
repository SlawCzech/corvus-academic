import ModelAdmin from "@/components/admin/ModelAdmin"

export default function AdminModelsPage() {
  return (
    <main className="mx-auto max-w-4xl px-8 py-10">
      <h1 className="mb-2 font-serif text-[26px] font-semibold text-foreground">
        Modele AI
      </h1>
      <p className="mb-8 text-[13.5px] text-muted">
        Promotorzy wybierają tylko spośród udostępnionych modeli. Domyślny działa,
        gdy promotor niczego nie wybierze, i nie da się go wyłączyć, dopóki nie
        wskażesz innego. Nowy model instaluje się na serwerze (
        <code className="font-mono text-[12.5px]">ollama pull</code>) — pojawi się
        tu wtedy sam, jako nieudostępniony.
      </p>
      <ModelAdmin />
    </main>
  )
}
