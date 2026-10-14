import { useRef, type ReactNode } from "react"

/** A card whose border and surface light up under the pointer. */
export function SpotlightCard({ children, className = "", as: Tag = "div" }: { children: ReactNode; className?: string; as?: "div" | "article" | "li" }) {
  const ref = useRef<HTMLElement>(null)
  const move = (e: React.PointerEvent) => {
    const el = ref.current
    if (!el) return
    const r = el.getBoundingClientRect()
    el.style.setProperty("--x", `${e.clientX - r.left}px`)
    el.style.setProperty("--y", `${e.clientY - r.top}px`)
  }
  return (
    <Tag
      ref={ref as never}
      onPointerMove={move}
      className={`group relative overflow-hidden rounded-xl border border-line bg-gradient-to-b from-[#121212] to-[#070707] ${className}`}
    >
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 opacity-0 transition-opacity duration-300 group-hover:opacity-100"
        style={{ background: "radial-gradient(420px circle at var(--x) var(--y), rgba(255,255,255,0.07), transparent 45%)" }}
      />
      <div className="relative">{children}</div>
    </Tag>
  )
}
