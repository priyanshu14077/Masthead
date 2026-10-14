/** The Masthead mark (an M over a copper rule) and wordmark, drawn for a dark ground. */
export function Logo({ className = "" }: { className?: string }) {
  return (
    <span className={`inline-flex items-center gap-2.5 ${className}`}>
      <svg width="26" height="26" viewBox="0 0 26 26" aria-hidden="true">
        <rect x="0.5" y="0.5" width="25" height="25" rx="5" fill="none" stroke="rgba(255,255,255,0.35)" />
        <path d="M6.5 17V8.5h1.9l4.6 5.6 4.6-5.6h1.9V17h-2.1v-5.3l-4.4 5.2-4.4-5.2V17z" fill="#fff" />
        <rect x="6.5" y="19" width="13" height="1.6" fill="var(--color-copper)" />
      </svg>
      <span className="text-[17px] font-medium tracking-[-0.02em]">Masthead</span>
    </span>
  )
}
