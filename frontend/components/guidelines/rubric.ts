/**
 * A rubric's four sections, read the way `app` reads them
 * (`app/src/guidelines/domain/rubric.py`): the exact `## ` headings, each
 * once. Text above the first is the preamble — for people, never for a model.
 */

export type RubricSectionKey = "elements" | "formal" | "merit" | "severity"

export interface RubricSectionSpec {
  key: RubricSectionKey
  heading: string
  /** Which actions are given this section, as a promoter would say it. */
  readBy: string
}

export const RUBRIC_SECTIONS: RubricSectionSpec[] = [
  {
    key: "elements",
    heading: "Elementy pracy",
    readBy: "recenzja, ocena metodologii i sprawdzenie wymogów",
  },
  { key: "formal", heading: "Wymogi formalne", readBy: "sprawdzenie wymogów" },
  {
    key: "merit",
    heading: "Co praca ma wykazać",
    readBy: "recenzja i ocena metodologii",
  },
  { key: "severity", heading: "Waga uchybień", readBy: "sprawdzenie wymogów" },
]

export interface ParsedRubric {
  preamble: string
  sections: Record<RubricSectionKey, string>
}

/** The rubric by section, or null when it does not have exactly the four. */
export function parseRubric(markdown: string): ParsedRubric | null {
  const byHeading = new Map(RUBRIC_SECTIONS.map((s) => [s.heading, s.key]))
  const found = new Map<RubricSectionKey, string[]>()
  const preamble: string[] = []
  let current: RubricSectionKey | null = null
  for (const line of markdown.split("\n")) {
    if (line.startsWith("## ")) {
      const key = byHeading.get(line.slice(3).trim())
      if (key === undefined || found.has(key)) return null
      found.set(key, [])
      current = key
    } else if (current === null) {
      preamble.push(line)
    } else {
      found.get(current)!.push(line)
    }
  }
  if (found.size !== RUBRIC_SECTIONS.length) return null
  const sections = Object.fromEntries(
    [...found.entries()].map(([key, lines]) => [key, lines.join("\n").trim()]),
  ) as Record<RubricSectionKey, string>
  return { preamble: preamble.join("\n").trim(), sections }
}

export type Block =
  | { kind: "heading"; text: string }
  | { kind: "list"; items: string[] }
  | { kind: "paragraph"; text: string }

/**
 * The little markdown a rubric uses: `###` headings, `-` lists whose items may
 * wrap onto indented lines, `>` notes and plain paragraphs. A top `#` title
 * is dropped — the page already names the set.
 */
export function toBlocks(markdown: string): Block[] {
  const blocks: Block[] = []
  let paragraph: string[] = []
  let list: string[] | null = null

  const flush = (): void => {
    if (paragraph.length) blocks.push({ kind: "paragraph", text: paragraph.join(" ") })
    if (list) blocks.push({ kind: "list", items: list })
    paragraph = []
    list = null
  }

  for (const raw of markdown.split("\n")) {
    const line = raw.trimEnd()
    if (!line.trim()) {
      flush()
    } else if (/^#\s/.test(line)) {
      flush()
    } else if (/^#{3,}\s/.test(line)) {
      flush()
      blocks.push({ kind: "heading", text: line.replace(/^#+\s*/, "") })
    } else if (/^\s*-\s/.test(line) && !/^\s{2,}/.test(line)) {
      if (paragraph.length) flush()
      list = list ?? []
      list.push(line.replace(/^\s*-\s+(\[ \]\s*)?/, ""))
    } else if (list && /^\s+\S/.test(line)) {
      list[list.length - 1] += ` ${line.trim()}`
    } else {
      if (list) flush()
      paragraph.push(line.replace(/^>\s?/, ""))
    }
  }
  flush()
  return blocks
}

/** Split `**bold**` runs out of a line, for rendering without HTML. */
export function boldRuns(text: string): { text: string; bold: boolean }[] {
  return text
    .split(/(\*\*[^*]+\*\*)/)
    .filter(Boolean)
    .map((part) =>
      part.startsWith("**") && part.endsWith("**")
        ? { text: part.slice(2, -2), bold: true }
        : { text: part, bold: false },
    )
}
