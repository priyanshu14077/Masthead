import type { AnchorHTMLAttributes, ReactNode } from "react"

type Props = AnchorHTMLAttributes<HTMLAnchorElement> & { variant?: "solid" | "ghost"; size?: "md" | "sm"; children: ReactNode }

/** Links styled as buttons, matching the template: a bright solid and a bordered ghost. */
export function ButtonLink({ variant = "solid", size = "md", className = "", children, ...rest }: Props) {
  const base = "inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors duration-200 whitespace-nowrap"
  const sizes = size === "sm" ? "h-9 px-4 text-[14px]" : "h-11 px-6 text-[15px]"
  const look =
    variant === "solid"
      ? "bg-gradient-to-b from-white to-neutral-300 text-black shadow-[inset_0_1px_0_rgba(255,255,255,0.9),0_0_0_1px_rgba(255,255,255,0.15)] hover:to-white"
      : "border border-white/15 bg-white/[0.04] text-white hover:bg-white/[0.09] hover:border-white/25"
  return (
    <a className={`${base} ${sizes} ${look} ${className}`} {...rest}>
      {children}
    </a>
  )
}
