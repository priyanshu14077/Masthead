import { Menu, X } from "lucide-react"
import { useEffect, useState } from "react"
import { app, DEMO_URL } from "../../lib/links"
import { ButtonLink } from "../ui/button"
import { Logo } from "../ui/logo"

const LINKS = [
  ["How it works", "#flow"],
  ["The desk", "#desk"],
  ["The check", "#check"],
  ["Features", "#features"],
  ["Pricing", "#pricing"],
  ["FAQ", "#faq"],
] as const

export function Nav() {
  const [scrolled, setScrolled] = useState(false)
  const [open, setOpen] = useState(false)
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 12)
    onScroll()
    window.addEventListener("scroll", onScroll, { passive: true })
    return () => window.removeEventListener("scroll", onScroll)
  }, [])
  return (
    <header className={`fixed inset-x-0 top-0 z-50 transition-colors duration-300 ${scrolled || open ? "border-b border-line bg-black/80 backdrop-blur-xl" : "border-b border-transparent"}`}>
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:top-3 focus:left-3 focus:rounded-md focus:bg-white focus:px-3 focus:py-2 focus:text-black">
        Skip to content
      </a>
      <nav className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-6 px-4 sm:px-8" aria-label="Main">
        <a href="#top" aria-label="Masthead home">
          <Logo />
        </a>
        <ul className="hidden items-center gap-2 lg:flex">
          {LINKS.map(([label, href]) => (
            <li key={href}>
              <a href={href} className="rounded-lg border border-white/10 bg-gradient-to-b from-white/[0.08] to-white/[0.02] px-3.5 py-1.5 text-[14px] text-neutral-200 transition-colors hover:border-white/25 hover:text-white">
                {label}
              </a>
            </li>
          ))}
        </ul>
        <div className="hidden items-center gap-3 lg:flex">
          <ButtonLink href={DEMO_URL} variant="ghost" size="sm">Book a demo</ButtonLink>
          <ButtonLink href={app("/signup")} size="sm">Start free</ButtonLink>
        </div>
        <button className="rounded-lg border border-line p-2 lg:hidden" aria-expanded={open} aria-controls="mobile-menu" aria-label={open ? "Close menu" : "Open menu"} onClick={() => setOpen(!open)}>
          {open ? <X size={18} /> : <Menu size={18} />}
        </button>
      </nav>
      {open && (
        <div id="mobile-menu" className="border-t border-line px-4 pt-3 pb-5 lg:hidden">
          <ul className="flex flex-col">
            {LINKS.map(([label, href]) => (
              <li key={href}>
                <a href={href} onClick={() => setOpen(false)} className="block border-b border-line py-3 text-[15px] text-neutral-200">{label}</a>
              </li>
            ))}
          </ul>
          <div className="mt-4 grid grid-cols-2 gap-3">
            <ButtonLink href={DEMO_URL} variant="ghost" size="sm">Book a demo</ButtonLink>
            <ButtonLink href={app("/signup")} size="sm">Start free</ButtonLink>
          </div>
        </div>
      )}
    </header>
  )
}
