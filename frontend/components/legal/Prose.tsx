/**
 * Building blocks for the legal documents: plain headings, paragraphs and
 * numbered lists in the site's type, without a typography plugin.
 */
import type { ReactNode } from "react"

export function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="mt-8">
      <h2 className="mb-3 text-[16px] font-semibold text-foreground">{title}</h2>
      <div className="flex flex-col gap-2.5 text-[14px] leading-relaxed text-muted-strong">
        {children}
      </div>
    </section>
  )
}

export function Items({ children }: { children: ReactNode }) {
  return <ol className="flex list-decimal flex-col gap-2 pl-5">{children}</ol>
}

export function Bullets({ children }: { children: ReactNode }) {
  return <ul className="flex list-disc flex-col gap-1.5 pl-5">{children}</ul>
}
