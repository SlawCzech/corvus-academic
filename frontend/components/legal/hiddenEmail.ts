/**
 * An address that is not in the page as text until someone asks for it.
 *
 * The legal pages are public, and an address in plain HTML is in every
 * scraper's list within weeks. Encoded as reversed character codes, it is
 * neither text nor a pattern an address harvester looks for; the browser
 * puts it back together on a click (`RevealEmail`). A person needs one click,
 * which keeps the contact details "easily accessible" (art. 12 GDPR).
 */
export function hideEmail(email: string): string {
  return Array.from(email, (c) => c.codePointAt(0) ?? 0)
    .reverse()
    .join(".")
}

export function revealEmail(hidden: string): string {
  return String.fromCodePoint(...hidden.split(".").map(Number).reverse())
}
