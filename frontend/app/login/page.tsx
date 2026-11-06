import Link from "next/link";
import AuthTabs from "@/components/AuthTabs";
import { LegalLinks } from "@/components/legal/LegalPage";
import Logo from "@/components/Logo";

interface LoginPageProps {
  searchParams: Promise<{ tab?: string }>;
}

export default async function LoginPage({ searchParams }: LoginPageProps) {
  const { tab } = await searchParams;
  const initialTab = tab === "request" ? "request" : "login";

  return (
    <div className="flex min-h-screen flex-col items-center justify-center px-4 py-12">
      <div className="w-full max-w-[380px]">
        <Link
          href="/"
          className="mb-10 flex items-center gap-2.5 text-foreground"
        >
          <Logo size="sm" />
        </Link>
        <AuthTabs initialTab={initialTab} />
        <LegalLinks className="mt-10 justify-center" />
      </div>
    </div>
  );
}
