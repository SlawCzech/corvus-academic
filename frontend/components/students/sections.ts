// Not in `StudentSubNav`: the student page reads `?section=` on the server, and
// a server component cannot call a function from a "use client" module.
const SECTIONS = ["overview", "timeline", "actions", "drafts", "notes", "history"] as const

export type Section = (typeof SECTIONS)[number]

export function isSection(value: string): value is Section {
  return (SECTIONS as readonly string[]).includes(value)
}
