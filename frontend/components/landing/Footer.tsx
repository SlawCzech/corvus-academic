const LINKS = ["Dokumentacja", "GitHub"] as const

export default function Footer() {
  return (
    <footer className="border-t border-gray-200 dark:border-gray-800 px-8 py-4 flex justify-between items-center">
      <span className="text-[12px] text-gray-400 dark:text-gray-500">
        © 2026 Corvus
      </span>
      <div className="flex gap-4">
        {LINKS.map((link) => (
          <a
            key={link}
            href="#"
            className="text-[12px] text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
          >
            {link}
          </a>
        ))}
      </div>
    </footer>
  )
}
