import type { ReactNode } from "react"

/** The small mono tag above every section heading. */
export function Label({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex items-center rounded-md border border-line bg-white/[0.03] px-3 py-1 font-mono text-[12px] tracking-[0.18em] text-neutral-300 uppercase">
      {children}
    </span>
  )
}

export function SectionHead({ label, children, id }: { label: string; children: ReactNode; id?: string }) {
  return (
    <div className="mx-auto flex max-w-3xl flex-col items-center gap-5 text-center">
      <Label>{label}</Label>
      <h2 id={id} className="text-[clamp(2rem,4.6vw,3.4rem)] leading-[1.05] font-medium tracking-[-0.035em] text-balance">
        {children}
      </h2>
    </div>
  )
}
