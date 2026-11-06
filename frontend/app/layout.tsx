import type { Metadata } from "next";
import { headers } from "next/headers";
import { Source_Serif_4, Public_Sans } from "next/font/google";
import { ThemeProvider } from "@/components/ThemeProvider";
import "./globals.css";

const sourceSerif = Source_Serif_4({
  variable: "--font-source-serif",
  subsets: ["latin", "latin-ext"],
});

const publicSans = Public_Sans({
  variable: "--font-public-sans",
  subsets: ["latin", "latin-ext"],
});

export const metadata: Metadata = {
  metadataBase: new URL("https://corvus.saek.dev"),
  title: "Corvus",
  description: "Narzędzie do prowadzenia prac dyplomowych.",
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  // Set by `proxy.ts` with the page's Content-Security-Policy. Reading it
  // renders every page per request, which the nonce needs anyway.
  const nonce = (await headers()).get("x-nonce") ?? undefined;
  return (
    <html
      lang="pl"
      data-scroll-behavior="smooth"
      className={`${sourceSerif.variable} ${publicSans.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <body className="min-h-full flex flex-col">
        <ThemeProvider nonce={nonce}>{children}</ThemeProvider>
      </body>
    </html>
  );
}
