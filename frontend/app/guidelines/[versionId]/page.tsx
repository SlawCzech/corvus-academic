import GuidelineVersionView from "@/components/guidelines/GuidelineVersionView"

export default async function GuidelineVersionPage({
  params,
}: {
  params: Promise<{ versionId: string }>
}) {
  const { versionId } = await params
  return (
    <main className="mx-auto max-w-4xl px-8 py-10">
      <GuidelineVersionView versionId={versionId} />
    </main>
  )
}
