import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import type { ApprovedLoan, ApprovedLoansResponse } from '../../api/types'
import { Badge, Section, Spinner, inr } from '../ui'

const TIER: Record<string, string> = { STARTER: 'Starter', GROWTH: 'Growth', ESTABLISHED: 'Established' }
const when = (iso: string | null) => (iso ? new Date(iso).toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) : '—')

function Detail({ l }: { l: ApprovedLoan }) {
  const rows: [string, string][] = [
    ['Mobile', l.mobile_masked],
    ['EMI × tenure', `${inr(l.requested_emi)} × ${l.tenure_months} months`],
    ['Default probability', l.pd != null ? `${(l.pd * 100).toFixed(1)}%` : '—'],
    ['LOS reference', l.los_reference ?? '—'],
    ['Consent', l.consent_active ? 'active' : 'revoked or expired'],
    ['Graduation tier', l.loan ? `${TIER[l.loan.current_tier] ?? l.loan.current_tier} · behaviour score ${l.loan.behaviour_score}` : '—'],
    ['Pre-approved limit', l.loan ? inr(l.loan.current_limit) : '—'],
  ]
  return (
    <dl className="mt-4 grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
      {rows.map(([k, v]) => (
        <div key={k} className="flex justify-between gap-3 border-b border-ink/[0.06] pb-2">
          <dt className="text-ink-soft">{k}</dt>
          <dd className="text-right font-medium">{v}</dd>
        </div>
      ))}
    </dl>
  )
}

/** Every approved application, newest first. Collapsed by default; tap a row for the loan details. */
export default function ApprovedLoans() {
  const [data, setData] = useState<ApprovedLoansResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [openId, setOpenId] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const load = () => {
    setLoading(true)
    api.approvedLoans().then((d) => { setData(d); setError(null) }).catch(() => setError('Could not load approved loans.')).finally(() => setLoading(false))
  }
  useEffect(load, [])

  const loans = data?.loans ?? []
  const totalTicket = loans.reduce((s, l) => s + (l.ticket_size || 0), 0)
  const avgScore = loans.filter((l) => l.score != null).reduce((s, l, _, arr) => s + (l.score ?? 0) / arr.length, 0)

  return (
    <Section
      title="Approved loans"
      hint={data ? `${data.count} approved · ${inr(totalTicket)} disbursement value · tap a row for details` : 'Loading…'}
      right={loading ? <Spinner /> : undefined}
    >
      {error && <p className="text-sm text-warn">{error}</p>}
      {!error && data && loans.length === 0 && (
        <p className="text-sm text-ink-soft">No approved loans yet. Approved applications appear here with their LOS reference, consent status and graduation tier.</p>
      )}
      {loans.length > 0 && (
        <>
          <div className="mb-4 flex flex-wrap gap-2">
            <Badge tone="green">Average score {Math.round(avgScore)}</Badge>
            <Badge tone="slate">{loans.filter((l) => l.consent_active).length} with active consent</Badge>
          </div>
          <ul className="divide-y divide-ink/[0.07] rounded-2xl ring-1 ring-ink/[0.07]">
            {loans.map((l) => {
              const open = openId === l.application_id
              return (
                <li key={l.application_id} className="px-4">
                  <button type="button" onClick={() => setOpenId(open ? null : l.application_id)} aria-expanded={open}
                    className="flex w-full flex-wrap items-center justify-between gap-x-4 gap-y-1 py-3.5 text-left">
                    <span className="min-w-0">
                      <span className="block font-medium">{l.applicant_name || 'Applicant'}</span>
                      <span className="block text-xs text-ink-soft">{l.product_label} · {inr(l.ticket_size)} · EMI {inr(l.requested_emi)}</span>
                    </span>
                    <span className="flex items-center gap-3 text-xs text-ink-soft">
                      <span className="tabular-nums">score <b className="font-semibold text-ink">{l.score != null ? Math.round(l.score) : '—'}</b></span>
                      <span>{when(l.decided_at)}</span>
                      <Badge tone={l.consent_active ? 'green' : 'slate'}>{l.consent_active ? 'consent active' : 'consent revoked'}</Badge>
                      <span className={`grid h-6 w-6 place-items-center rounded-full border border-ink/15 transition-transform ${open ? 'rotate-45' : ''}`} aria-hidden>+</span>
                    </span>
                  </button>
                  {open && <div className="pb-4"><Detail l={l} /></div>}
                </li>
              )
            })}
          </ul>
        </>
      )}
    </Section>
  )
}
