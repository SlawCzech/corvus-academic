import { GUIDE_PATH } from "@/lib/guide"

/**
 * The message an admin pastes into their own mail after creating an account.
 * Corvus sends nothing itself, so this is plain text to copy; the admin can
 * still edit it before sending. A reply goes to the admin, which is why there
 * is no contact address in it.
 */
export function invitationText({
  origin,
  email,
  password,
  role,
}: {
  origin: string
  email: string
  password: string
  role: string
}): string {
  const access = [
    `Adres: ${origin}`,
    `Login: ${email}`,
    `Hasło tymczasowe: ${password}`,
  ].join("\n")

  if (role === "admin") {
    return [
      "Dzień dobry,",
      "",
      "w Corvusie czeka na Panią/Pana konto administratora.",
      "",
      access,
      "",
      "Przy pierwszym logowaniu Corvus poprosi o ustawienie własnego hasła. " +
        "Szkic rubryki z regulaminu uczelni powstaje na własnym kluczu Claude " +
        "(Anthropic) albo OpenAI, wpisanym w profilu.",
      "",
      "W razie pytań proszę odpowiedzieć na tę wiadomość.",
    ].join("\n")
  }

  return [
    "Dzień dobry,",
    "",
    "w Corvusie czeka na Panią/Pana konto promotora. Corvus pomaga prowadzić " +
      "seminarzystów: notatki ze spotkań, wersje i fragmenty pracy, recenzje " +
      "próbne i finalne oraz pytania na obronę.",
    "",
    access,
    "",
    "Przy pierwszym logowaniu Corvus poprosi o ustawienie własnego hasła, " +
      `a potem o akceptację regulaminu z umową powierzenia danych (${origin}/terms).`,
    "",
    "Akcje AI działają na Pani/Pana własnym kluczu Claude (Anthropic) albo " +
      "OpenAI, wpisanym w profilu. Bez klucza można prowadzić studentów i " +
      "notatki, ale żadna akcja AI się nie uruchomi.",
    "",
    `Przewodnik po aplikacji (po zalogowaniu): ${origin}${GUIDE_PATH}`,
    "",
    "W razie pytań proszę odpowiedzieć na tę wiadomość.",
  ].join("\n")
}
