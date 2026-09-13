import Link from "next/link"
import AuthTabs from "@/components/AuthTabs"

interface LoginPageProps {
  searchParams: Promise<{ tab?: string }>
}

export default async function LoginPage({ searchParams }: LoginPageProps) {
  const { tab } = await searchParams
  const initialTab = tab === "request" ? "request" : "login"

  return (
    <div className="flex min-h-screen">
      <div className="hidden w-[45%] flex-col justify-between bg-navy p-14 lg:flex">
        <Link href="/" className="flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-white/10 font-serif text-[17px] font-semibold text-[#e8b876]">
            C
          </div>
          <span className="font-serif text-[19px] font-semibold text-[#fbfaf8]">
            Corvus
          </span>
        </Link>

        <div>
          <h2 className="font-serif text-[30px] font-semibold leading-[1.35] text-[#fbfaf8]">
            „Model proponuje. Ja decyduję, co trafia do recenzji.”
          </h2>
          <p className="mt-5 text-[14px] text-[#9fb0c7]">
            Promotor korzystający z Corvus przy prowadzeniu prac
            dyplomowych.
          </p>
        </div>

        <div className="flex gap-8">
          <div>
            <span className="block font-serif text-[26px] font-semibold text-[#fbfaf8]">
              6
            </span>
            <span className="text-[12px] text-[#9fb0c7]">
              akcji AI do wyboru
            </span>
          </div>
          <div>
            <span className="block font-serif text-[26px] font-semibold text-[#fbfaf8]">
              100%
            </span>
            <span className="text-[12px] text-[#9fb0c7]">
              decyzji zostaje przy Tobie
            </span>
          </div>
        </div>
      </div>

      <div className="flex flex-1 items-center justify-center p-8">
        <AuthTabs initialTab={initialTab} />
      </div>
    </div>
  )
}
