import Link from "next/link";
import Logo from "@/components/Logo";
import { homeFor } from "@/lib/auth";

interface NavProps {
  role?: string | null;
  isLoggedIn?: boolean;
}

const ANCHORS = [
  { href: "#recenzja", label: "Recenzja" },
  { href: "#prowadzenie", label: "Prowadzenie pracy" },
  { href: "#dane", label: "Dane i klucze" },
];

export default function Nav({ role, isLoggedIn }: NavProps) {
  return (
    <nav className="mx-auto flex h-[76px] w-full max-w-[1280px] items-center justify-between px-4 sm:px-8 lg:px-16">
      <Link href="/" className="flex items-center gap-2.5 text-foreground">
        <Logo />
      </Link>

      <div className="hidden items-center gap-9 md:flex">
        {ANCHORS.map((a) => (
          <a
            key={a.href}
            href={a.href}
            className="text-[14px] font-medium text-muted-strong hover:text-accent"
          >
            {a.label}
          </a>
        ))}
      </div>

      <Link
        href={isLoggedIn ? homeFor(role) : "/login"}
        className="flex h-10 items-center rounded-lg border border-line px-4 text-[14px] font-semibold text-foreground transition-colors hover:bg-surface-alt"
      >
        {isLoggedIn ? "Przejdź do aplikacji" : "Zaloguj się"}
      </Link>
    </nav>
  );
}
