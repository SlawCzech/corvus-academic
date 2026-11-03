"use client"

import { ThemeProvider as NextThemesProvider } from "next-themes"

export function ThemeProvider({
  children,
  nonce,
}: {
  children: React.ReactNode
  // The page's CSP nonce: the provider's inline script runs before hydration.
  nonce?: string
}) {
  return (
    <NextThemesProvider attribute="class" defaultTheme="system" enableSystem nonce={nonce}>
      {children}
    </NextThemesProvider>
  )
}
