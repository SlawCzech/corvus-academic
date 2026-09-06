import Link from "next/link"

export default function Hero() {
  return (
    <section className="max-w-[580px] mx-auto px-8 pt-24 pb-20">
      <p className="text-[12px] uppercase tracking-wide text-gray-400 dark:text-gray-500 mb-5">
        Narzędzie dla promotorów
      </p>

      <h1 className="text-[32px] font-medium leading-[1.2] tracking-[-0.6px] text-gray-900 dark:text-gray-50 mb-4">
        Analiza prac dyplomowych
        <br />
        wspomagana przez AI
      </h1>

      <p className="text-[15px] leading-relaxed text-gray-500 dark:text-gray-400 max-w-[460px] mb-9">
        Wgraj PDF lub DOCX. Corvus sprawdzi strukturę, metodologię i zgodność z
        wymogami uczelnianymi, a następnie wygeneruje szkic recenzji.
      </p>

      <div className="flex gap-2.5">
        <Link
          href="/login"
          className="flex h-9 items-center px-[18px] text-[14px] font-medium bg-gray-900 dark:bg-white text-white dark:text-gray-900 rounded-md hover:opacity-85 transition-opacity"
        >
          Zaloguj się i zacznij
        </Link>
        <Link
          href="/students"
          className="flex h-9 items-center px-[18px] text-[14px] border border-gray-200 dark:border-gray-700 text-gray-500 dark:text-gray-400 rounded-md hover:bg-gray-50 dark:hover:bg-gray-800 hover:text-gray-900 dark:hover:text-gray-50 transition-colors"
        >
          Zobacz przykład
        </Link>
      </div>
    </section>
  )
}
