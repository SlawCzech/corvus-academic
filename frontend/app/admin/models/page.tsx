import ModelAdmin from "@/components/admin/ModelAdmin"

export default function AdminModelsPage() {
  return (
    <main className="mx-auto max-w-4xl px-8 py-10">
      <h1 className="mb-2 font-serif text-[26px] font-semibold text-foreground">
        Modele AI
      </h1>
      <ModelAdmin />
    </main>
  )
}
