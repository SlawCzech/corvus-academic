const LINKS = ["Możliwości", "Prywatność i model"] as const

export default function Footer() {
  return (
    <footer className="mx-auto flex max-w-[1280px] items-center justify-between border-t border-line px-16 py-8">
      <span className="text-[13px] text-muted">© 2026 Corvus</span>
      <div className="flex gap-7">
        {LINKS.map((link) => (
          <a
            key={link}
            href={`#${link === "Możliwości" ? "mozliwosci" : "prywatnosc"}`}
            className="text-[13px] text-muted-strong hover:text-accent transition-colors"
          >
            {link}
          </a>
        ))}
      </div>
    </footer>
  )
}
