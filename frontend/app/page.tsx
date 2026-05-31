import Nav from "@/components/landing/Nav"
import Hero from "@/components/landing/Hero"
import Capabilities from "@/components/landing/Capabilities"
import MetaBar from "@/components/landing/MetaBar"
import Footer from "@/components/landing/Footer"

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
