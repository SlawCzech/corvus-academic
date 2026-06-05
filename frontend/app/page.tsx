import { cookies } from "next/headers"
import Nav from "@/components/landing/Nav"
import Hero from "@/components/landing/Hero"
import Capabilities from "@/components/landing/Capabilities"
import MetaBar from "@/components/landing/MetaBar"
import Footer from "@/components/landing/Footer"
import { decodeToken, isTokenExpired } from "@/lib/auth"

export default async function Home() {
  const cookieStore = await cookies()
  const token = cookieStore.get("access_token")?.value
  const payload = token && !isTokenExpired(token) ? decodeToken(token) : null

  return (
    <>
      <Nav role={payload?.role} isLoggedIn={!!payload} />
      <main>
        <Hero />
        <Capabilities />
        <MetaBar />
      </main>
      <Footer />
    </>
  )
}
