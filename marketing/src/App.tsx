import { CheckSandbox } from "./components/sections/check-sandbox"
import { Desk } from "./components/sections/desk"
import { Faq } from "./components/sections/faq"
import { Features } from "./components/sections/features"
import { Cta, Footer } from "./components/sections/footer"
import { Hero } from "./components/sections/hero"
import { HowItWorks } from "./components/sections/how-it-works"
import { Nav } from "./components/sections/nav"
import { Pricing } from "./components/sections/pricing"
import { Stack } from "./components/sections/stack"

// The page follows a post through Masthead: how it works, the desk running it, the check, where it plugs in, then price.
export default function App() {
  return (
    <>
      <Nav />
      <main id="main">
        <Hero />
        <HowItWorks />
        <Desk />
        <CheckSandbox />
        <Features />
        <Stack />
        <Pricing />
        <Faq />
        <Cta />
      </main>
      <Footer />
    </>
  )
}
