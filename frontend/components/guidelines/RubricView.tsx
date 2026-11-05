import { RUBRIC_SECTIONS, boldRuns, parseRubric, toBlocks } from "./rubric"

function Text({ text }: { text: string }) {
  return (
    <>
      {boldRuns(text).map((run, i) =>
        run.bold ? (
          <strong key={i} className="font-semibold text-foreground">
            {run.text}
          </strong>
        ) : (
          <span key={i}>{run.text}</span>
        ),
      )}
    </>
  )
}

function Markdown({ source }: { source: string }) {
  return (
    <div className="space-y-2.5 text-[13.5px] leading-relaxed text-foreground">
      {toBlocks(source).map((block, i) => {
        if (block.kind === "heading") {
          return (
            <h4 key={i} className="pt-1.5 text-[13.5px] font-semibold text-foreground">
              {block.text}
            </h4>
          )
        }
        if (block.kind === "list") {
          return (
            <ul key={i} className="list-disc space-y-1 pl-5 marker:text-muted">
              {block.items.map((item, j) => (
                <li key={j}>
                  <Text text={item} />
                </li>
              ))}
            </ul>
          )
        }
        return (
          <p key={i} className="text-muted-strong">
            <Text text={block.text} />
          </p>
        )
      })}
    </div>
  )
}

/**
 * The rubric as a promoter reads it: the four sections, each saying which
 * actions are given it, and the severity rules set apart as Corvus's own
 * reading. A version from before rubrics had sections shows as written.
 */
export default function RubricView({ rubric }: { rubric: string }) {
  const parsed = parseRubric(rubric)
  if (!parsed) {
    return (
      <section className="rounded-xl border border-line bg-surface p-5">
        <h2 className="mb-3 text-[11.5px] font-semibold uppercase tracking-wide text-muted">
          Rubryka dla modelu
        </h2>
        <pre
          data-testid="rubric"
          className="whitespace-pre-wrap font-sans text-[13.5px] leading-relaxed text-foreground"
        >
          {rubric}
        </pre>
      </section>
    )
  }

  return (
    <div data-testid="rubric" className="space-y-5">
      {parsed.preamble && (
        <div className="text-[12.5px] text-muted">
          <Markdown source={parsed.preamble} />
        </div>
      )}
      {RUBRIC_SECTIONS.map(({ key, heading, readBy }) => {
        const corvus = key === "severity"
        return (
          <section
            key={key}
            data-testid={`rubric-${key}`}
            className={`rounded-xl border p-5 ${
              corvus ? "border-major-text/30 bg-major-bg/40" : "border-line bg-surface"
            }`}
          >
            <div className="mb-3 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
              <h2 className="text-[15px] font-semibold text-foreground">
                {corvus ? "Jak Corvus waży uchybienia" : heading}
              </h2>
              <span className="text-[12px] text-muted">Czyta: {readBy}</span>
            </div>
            <Markdown source={parsed.sections[key]} />
          </section>
        )
      })}
    </div>
  )
}
