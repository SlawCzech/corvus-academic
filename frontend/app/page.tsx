import { cookies } from "next/headers";
import Nav from "@/components/landing/Nav";
import Hero from "@/components/landing/Hero";
import Actions from "@/components/landing/Actions";
import DataAndKeys from "@/components/landing/DataAndKeys";
import { LegalLinks } from "@/components/legal/LegalPage";
import { decodeToken, isTokenExpired } from "@/lib/auth";

export default async function Home() {
  const cookieStore = await cookies();
  const token = cookieStore.get("access_token")?.value;
  const payload = token && !isTokenExpired(token) ? decodeToken(token) : null;

  return (
    <>
      <Nav role={payload?.role} isLoggedIn={!!payload} />
      <main>
        <Hero />
        <Actions />
        <DataAndKeys />
      </main>
      <footer className="mx-auto flex w-full max-w-[1280px] items-center justify-between gap-4 border-t border-line px-4 py-8 text-[13px] text-muted sm:px-8 lg:px-16">
        <span>Corvus</span>
        <LegalLinks />
      </footer>
    </>
  );
}
