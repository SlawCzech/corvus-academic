# Corvus — landing page implementation spec

> Design spec for Claude Code.
> Approved mockup: minimal, professional, no marketing.
> Style reference: Linear, Raycast, Zed.

---

## Stack

- Next.js App Router
- TypeScript strict
- Tailwind CSS
- shadcn/ui
- `@tabler/icons-react`
- `next-themes` (dark/light toggle)

```bash
npm install next-themes @tabler/icons-react
```

---

## File structure

```
frontend/app/
└── page.tsx

frontend/components/landing/
├── Nav.tsx
├── Hero.tsx
├── Capabilities.tsx
├── MetaBar.tsx
└── Footer.tsx
```

---

## Design principles

- Monochromatic — no color accents, no brand colors
- All interactive elements use `var(--color-text-primary)` /
  `var(--color-background-primary)` and their Tailwind equivalents
- Hierarchy through font size and opacity only
- No decorative elements, no illustrations, no background fills
- One clear action: "Zaloguj się i zacznij" → /login

---

## Theme setup

`app/layout.tsx`:
```tsx
import { ThemeProvider } from 'next-themes'

export default function RootLayout({ children }) {
  return (
    <html lang="pl" suppressHydrationWarning>
      <body>
        <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
          {children}
        </ThemeProvider>
      </body>
    </html>
  )
}
```

`tailwind.config.ts`: `darkMode: 'class'`

---

## Components

### Nav

```
height: 56px
border-bottom border-gray-200 dark:border-gray-800
background: white dark:bg-gray-950
flex justify-between items-center px-8

Left — logo:
  Logo mark: 24x24px, bg-gray-900 dark:bg-white,
    rounded-[5px], text-white dark:text-gray-900,
    text-[13px] font-medium, letter "C"
  Logo text: "Corvus", 15px, font-medium, tracking-tight

Right — actions:
  Theme toggle: 30x30px, border border-gray-200 dark:border-gray-700,
    rounded-md, hover:bg-gray-100 dark:hover:bg-gray-800
    <IconSun size={14} /> in light mode
    <IconMoon size={14} /> in dark mode
    aria-label="Przełącz motyw"

  Sign in button: h-8, px-3.5, text-[13px], font-medium,
    border border-gray-200 dark:border-gray-700, rounded-md,
    bg-white dark:bg-gray-950,
    hover:bg-gray-50 dark:hover:bg-gray-800
    text: "Zaloguj się" → /login
```

### Hero

```
max-width: 580px, mx-auto, px-8
padding-top: 96px, padding-bottom: 80px

Eyebrow:
  "Narzędzie dla promotorów"
  text-[12px], uppercase, tracking-wide,
  text-gray-400 dark:text-gray-500
  margin-bottom: 20px

H1:
  "Analiza prac dyplomowych"
  "wspomagana przez AI"
  text-[32px], font-medium, leading-[1.2],
  tracking-[-0.6px], text-gray-900 dark:text-gray-50
  margin-bottom: 16px

Subtitle:
  "Wgraj PDF lub DOCX. Corvus sprawdzi strukturę, metodologię
  i zgodność z wymogami uczelnianymi, a następnie wygeneruje
  szkic recenzji."
  text-[15px], leading-relaxed,
  text-gray-500 dark:text-gray-400
  max-width: 460px
  margin-bottom: 36px

Actions (flex gap-2.5):
  Primary: "Zaloguj się i zacznij" → /login
    h-9, px-[18px], text-[14px], font-medium,
    bg-gray-900 dark:bg-white,
    text-white dark:text-gray-900,
    rounded-md, border-none
    hover:opacity-85

  Secondary: "Zobacz przykład" → /analysis
    h-9, px-[18px], text-[14px],
    border border-gray-200 dark:border-gray-700,
    text-gray-500 dark:text-gray-400, rounded-md,
    hover:bg-gray-50 dark:hover:bg-gray-800
    hover:text-gray-900 dark:hover:text-gray-50
```

### Capabilities

```
max-width: 580px, mx-auto, px-8
margin-bottom: 48px

Outer container:
  border border-gray-200 dark:border-gray-800
  rounded-xl, overflow-hidden

Four rows (flex, gap-3.5, px-5 py-4):
  border-b border-gray-100 dark:border-gray-800 (last: no border)
  bg-white dark:bg-gray-950

  Icon: text-gray-400 dark:text-gray-500, size={16}, mt-0.5, shrink-0
  Content:
    Title: text-[14px], font-medium,
           text-gray-900 dark:text-gray-50, mb-0.5
    Desc:  text-[13px], leading-[1.55],
           text-gray-500 dark:text-gray-400

Rows:
1. <IconLayoutList />
   "Struktura i spójność"
   "Weryfikuje obecność i kompletność wymaganych rozdziałów:
   wstęp z hipotezami, przegląd literatury, metodologia,
   wyniki, wnioski."

2. <IconMicroscope />
   "Metodologia i bibliografia"
   "Ocenia poprawność metod badawczych, jakość i liczbę źródeł,
   obecność źródeł obcojęzycznych, poprawność cytowań APA."

3. <IconChecklist />
   "Zgodność z wymogami"
   "Sprawdza pracę pod kątem wytycznych uczelnianych. Osobne
   profile dla licencjatu i magistra (artykuł naukowy)."

4. <IconFileDescription />
   "Szkic recenzji"
   "Generuje recenzję z oceną punktową każdego kryterium
   i rekomendacją: dopuścić do obrony lub zwrócić do poprawy."
```

### MetaBar

```
max-width: 580px, mx-auto, px-8

flex, flex-wrap, gap-x-5, gap-y-2

Three items (flex items-center gap-1.5):
  text-[12px], text-gray-400 dark:text-gray-500
  icon: size={13}

1. <IconServer size={13} />
   "Działa lokalnie — dane nie wychodzą z sieci"

2. <IconRefresh size={13} />
   "Qwen lokalnie lub Claude / GPT przez API"

3. <IconFileTypePdf size={13} />
   "PDF i DOCX do 50 MB"
```

### Footer

```
border-t border-gray-200 dark:border-gray-800
px-8 py-4
flex justify-between items-center

Left:  "© 2026 Corvus"
       text-[12px], text-gray-400 dark:text-gray-500

Right: links "Dokumentacja" | "GitHub"
       flex gap-4
       text-[12px], text-gray-400 dark:text-gray-500
       hover:text-gray-600 dark:hover:text-gray-300
```

---

## page.tsx composition

```tsx
export default function Home() {
  return (
    <>
      <Nav />
      <main>
        <Hero />
        <Capabilities />
        <MetaBar />
      </main>
      <Footer />
    </>
  )
}
```

---

## Accessibility

- `<html lang="pl">`
- Nav logo: `aria-label="Corvus — strona główna"`
- Theme toggle: `aria-label="Przełącz motyw"`
- All icons: `aria-hidden={true}`
- `<main>` wraps Hero, Capabilities, MetaBar

---

## Rules

- All UI text in Polish
- All code, comments, type annotations in English
- No inline styles — Tailwind classes only
- No hardcoded hex colors — Tailwind palette only
- No gradients, shadows, or decorative backgrounds
- ESLint and tsc must pass with zero errors or warnings

---

## Verification

```bash
npm run typecheck    # zero errors
npm run lint         # zero errors
npm run build        # builds successfully
```

Manual checks:
- [ ] dark/light toggle works, persists on reload
- [ ] "Zaloguj się i zacznij" → /login
- [ ] "Zobacz przykład" → /analysis
- [ ] "Zaloguj się" in nav → /login
- [ ] layout correct on narrow viewport (< 640px)
