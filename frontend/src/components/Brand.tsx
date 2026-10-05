/** Brand marks. The Saksham Engine logo is a single SVG in public/brand/ — replace that file to change it everywhere.
 *  It is drawn through a CSS mask, so it inherits `currentColor` (dark on light cards, white on the ink tiles). */
export const SAKSHAM_LOGO_SRC = '/brand/saksham-logo.svg'

export function SakshamLogo({ className = 'h-7 w-7' }: { className?: string }) {
  const mask = `url(${SAKSHAM_LOGO_SRC}) center / contain no-repeat`
  return <span role="img" aria-label="Saksham Engine" className={`inline-block shrink-0 bg-current ${className}`} style={{ WebkitMask: mask, mask }} />
}

/** The official TVS Credit logo (public/brand/tvs-credit.png, transparent background). `className` styles the
 *  wrapper, `imgClass` sizes the logo. On the light UI it sits directly on the page — no chip needed. */
export const TVS_LOGO_SRC = '/brand/tvs-credit.png'

export function TvsCredit({ className = '', imgClass = 'h-5' }: { className?: string; imgClass?: string }) {
  return (
    <span className={`inline-flex items-center ${className}`}>
      <img src={TVS_LOGO_SRC} alt="TVS Credit" className={`w-auto select-none ${imgClass}`} draggable={false} />
    </span>
  )
}

/** Logo + product name, optionally followed by the TVS Credit logo. */
export function Lockup({ withTvs = true, size = 'md' }: { withTvs?: boolean; size?: 'md' | 'lg' }) {
  return (
    <div className="flex items-center gap-2.5">
      <SakshamLogo className={size === 'lg' ? 'h-9 w-9' : 'h-7 w-7'} />
      <span className={`${size === 'lg' ? 'text-xl' : 'text-[1.05rem]'} font-medium tracking-tight`}>Saksham Engine</span>
      {withTvs && <><span className="hidden h-4 w-px bg-ink/20 sm:block" aria-hidden /><TvsCredit className="hidden sm:inline-flex" /></>}
    </div>
  )
}
