/**
 * Who runs this Corvus: named in the terms and the privacy policy.
 *
 * Read at request time from the server's environment (`OPERATOR_NAME`,
 * `OPERATOR_EMAIL` in `/srv/corvus/.env`), so a person's name and address are
 * not in the repository. Unset, the documents show a visible gap rather than
 * someone else's details.
 */
export interface Operator {
  name: string
  email: string
}

export function operator(): Operator {
  return {
    name: process.env.OPERATOR_NAME?.trim() || "[imię i nazwisko usługodawcy — OPERATOR_NAME]",
    email: process.env.OPERATOR_EMAIL?.trim() || "[adres kontaktowy — OPERATOR_EMAIL]",
  }
}
