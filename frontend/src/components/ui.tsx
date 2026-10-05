import { useState, type ReactNode } from 'react'

export const inr = (n: number | null | undefined) => (n == null ? '—' : '₹' + Math.round(n).toLocaleString('en-IN'))

const TONES = {
  green: 'bg-ok-soft text-ok',
  amber: 'bg-warn-soft text-warn',
  blue: 'bg-lav-100 text-lav-700',
  slate: 'bg-ink/5 text-ink-soft',
  red: 'bg-rose-500/15 text-rose-300',
  dark: 'bg-white/10 text-white/85',
} as const
export type Tone = keyof typeof TONES

export function Badge({ tone = 'slate', children, className = '' }: { tone?: Tone; children: ReactNode; className?: string }) {
  return <span className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2.5 py-0.5 text-[11px] font-medium ${TONES[tone]} ${className}`}>{children}</span>
}

export function Spinner({ className = '' }: { className?: string }) {
  return <span className={`inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-t-transparent opacity-60 ${className}`} />
}

export const OUTCOME_META: Record<string, { label: string; tone: Tone }> = {
  APPROVED: { label: 'Approved', tone: 'green' },
  CONDITIONAL_APPROVAL: { label: 'Conditional approval', tone: 'amber' },
  DECLINED_WITH_PLAN: { label: 'Guidance plan sent', tone: 'amber' }, // amber, never red: this is guidance, not rejection
  INSUFFICIENT_DATA: { label: 'Manual review', tone: 'blue' },
  BYPASSED_TO_LOS: { label: 'Routed to LOS', tone: 'blue' },
  CONSENT_DENIED: { label: 'Consent denied', tone: 'slate' },
  EXPIRED: { label: 'Link expired', tone: 'slate' },
  AWAITING_CONSENT: { label: 'Awaiting consent', tone: 'blue' },
  INGESTING: { label: 'Reading data…', tone: 'blue' },
  CONSENT_GRANTED: { label: 'Consent granted', tone: 'green' },
  SCORED: { label: 'Scored', tone: 'blue' },
  CREATED: { label: 'Created', tone: 'slate' },
  BUREAU_CHECKED: { label: 'Bureau checked', tone: 'slate' },
}

export function StatusBadge({ status, className = '' }: { status: string; className?: string }) {
  const m = OUTCOME_META[status] ?? { label: status, tone: 'slate' as Tone }
  return <Badge tone={m.tone} className={className}>{m.label}</Badge>
}

export function ErrorNote({ children }: { children: ReactNode }) {
  return <div className="rounded-2xl bg-warn-soft px-4 py-3 text-sm text-warn">{children}</div>
}

/** A collapsible card. Content is hidden until toggled — the main tool for keeping the console uncluttered. */
export function Section({ title, hint, right, defaultOpen = false, open: controlled, onToggle, children }: {
  title: ReactNode; hint?: ReactNode; right?: ReactNode; defaultOpen?: boolean; open?: boolean; onToggle?: (o: boolean) => void; children: ReactNode
}) {
  const [inner, setInner] = useState(defaultOpen)
  const open = controlled ?? inner
  const toggle = () => { const n = !open; setInner(n); onToggle?.(n) }
  return (
    <section className="overflow-hidden rounded-[1.75rem] bg-surface shadow-sm ring-1 ring-ink/[0.07]">
      <button type="button" onClick={toggle} aria-expanded={open} className="flex w-full items-center justify-between gap-4 px-6 py-5 text-left">
        <span className="min-w-0">
          <span className="block text-lg font-normal tracking-tight">{title}</span>
          {hint && <span className="mt-0.5 block truncate text-xs text-ink-soft">{hint}</span>}
        </span>
        <span className="flex shrink-0 items-center gap-3">
          {right}
          <span className={`grid h-8 w-8 place-items-center rounded-full border border-ink/15 text-base leading-none transition-transform duration-300 ${open ? 'rotate-45 border-transparent bg-accent text-accent-ink' : ''}`} aria-hidden>+</span>
        </span>
      </button>
      <div className="acc" data-open={open}><div><div className="px-6 pb-6">{children}</div></div></div>
    </section>
  )
}
