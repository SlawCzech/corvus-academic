import { describe, expect, it } from "vitest"
import { invitationText } from "../invitation"

const BASE = { origin: "https://corvus.example", email: "p@uczelnia.pl", password: "Tmp-123" }

describe("invitationText", () => {
  it("gives a promoter the access, the terms, the key and the guide", () => {
    const text = invitationText({ ...BASE, role: "promotor" })

    expect(text).toContain("Adres: https://corvus.example")
    expect(text).toContain("Login: p@uczelnia.pl")
    expect(text).toContain("Hasło tymczasowe: Tmp-123")
    expect(text).toContain("https://corvus.example/terms")
    expect(text).toContain("https://corvus.example/przewodnik.pdf")
    expect(text).toContain("własnym kluczu Claude")
  })

  it("spares an admin the terms and the guide", () => {
    const text = invitationText({ ...BASE, role: "admin" })

    expect(text).toContain("konto administratora")
    expect(text).toContain("Hasło tymczasowe: Tmp-123")
    expect(text).not.toContain("/terms")
    expect(text).not.toContain("przewodnik")
  })
})
