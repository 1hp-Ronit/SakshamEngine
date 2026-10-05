import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import type { Group, Ledger } from '../../api/types'
import { Badge, Spinner, type Tone } from '../ui'

const SOURCE: Record<Group, string> = { aa: 'Bank statement (AA)', telecom: 'Telecom recharge', business: 'Business records' }
const READ: Record<string, { text: string; tone: Tone }> = {
  ok: { text: 'read', tone: 'green' },
  timeout: { text: 'timed out', tone: 'amber' },
  error: { text: 'error', tone: 'amber' },
  no_data: { text: 'no records', tone: 'slate' },
  not_consented: { text: 'not read — no consent', tone: 'slate' },
}
const EVENT: Record<string, string> = { GRANTED: 'Consent granted', DENIED: 'Consent denied', REVOKED: 'Consent revoked' }
const when = (iso: string | null) => (iso ? new Date(iso).toLocaleString('en-IN', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—')

/** Everything the customer can ask about their data: what they agreed to, every read we attempted, and what we still hold. */
export default function ConsentLedger({ applicationId, version }: { applicationId: string; version: string }) {
  const [ledger, setLedger] = useState<Ledger | null>(null)
  const [error, setError] = useState<string | null>(null)

  // `version` changes when the status or consent changes, so the ledger refreshes after a revocation
  useEffect(() => {
    let alive = true
    api.ledger(applicationId).then((l) => { if (alive) { setLedger(l); setError(null) } }).catch(() => { if (alive) setError('Could not load the ledger.') })
    return () => { alive = false }
  }, [applicationId, version])

  if (error) return <p className="text-sm text-warn">{error}</p>
  if (!ledger) return <Spinner />

  const h = ledger.holdings
  const holds: [string, string][] = [
    ['Mobile number', h.mobile_number],
    ['PAN / Aadhaar', h.identifiers],
    ['Raw bank, telecom and GST payloads', h.raw_vendor_payloads],
    ['Extracted feature vector', h.feature_vector],
    ['Audit record', h.audit_record ? `${h.audit_record.slice(0, 8)} — kept permanently` : '—'],
  ]

  return (
    <div className="space-y-7">
      <div className="space-y-3">
        <h4 className="text-xs font-semibold uppercase tracking-[0.12em] text-ink-soft">Consent</h4>
        {ledger.consents.length === 0 && <p className="text-sm text-ink-soft">No consent was given. No data was read.</p>}
        {ledger.consents.map((c) => (
          <div key={c.consent_id} className="rounded-2xl bg-lav-50 p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-sm font-medium">{c.purpose}</span>
              <Badge tone={c.revoked ? 'red' : c.active ? 'green' : 'slate'}>{c.revoked ? 'revoked' : c.active ? 'active' : 'expired'}</Badge>
            </div>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {(Object.keys(c.grants) as Group[]).map((g) => (
                <Badge key={g} tone={c.grants[g] ? 'green' : 'slate'}>{c.grants[g] ? '✓' : '✗'} {SOURCE[g]}</Badge>
              ))}
            </div>
            <p className="mt-2 text-xs text-ink-soft">Granted {when(c.granted_at)} · valid until {when(c.expires_at)}{c.revoked_at && <> · revoked {when(c.revoked_at)}</>}</p>
          </div>
        ))}
        {ledger.events.length > 0 && (
          <ol className="relative space-y-3 border-l border-ink/10 pl-5 text-sm">
            {ledger.events.map((e, i) => (
              <li key={i} className="relative">
                <span className={`absolute -left-[25px] top-1.5 h-2.5 w-2.5 rounded-full ${e.event === 'REVOKED' ? 'bg-warn' : 'bg-ok'}`} aria-hidden />
                <span className="font-medium">{EVENT[e.event] ?? e.event}</span>
                <span className="ml-2 text-xs text-ink-soft">{when(e.timestamp)}</span>
                {e.event === 'REVOKED' && Boolean(e.details?.features_purged) && <p className="text-xs text-ink-soft">Stored features deleted; further data access blocked.</p>}
              </li>
            ))}
          </ol>
        )}
      </div>

      <div className="space-y-3">
        <h4 className="text-xs font-semibold uppercase tracking-[0.12em] text-ink-soft">Every data read we attempted</h4>
        {ledger.data_access.length === 0 && <p className="text-sm text-ink-soft">Nothing has been requested yet.</p>}
        {ledger.data_access.length > 0 && (
          <ul className="divide-y divide-ink/[0.07] rounded-2xl ring-1 ring-ink/[0.07]">
            {ledger.data_access.map((r, i) => {
              const s = READ[r.status] ?? { text: r.status, tone: 'slate' as Tone }
              return (
                <li key={i} className="flex flex-wrap items-center justify-between gap-2 px-4 py-3 text-sm">
                  <span className="font-medium">{SOURCE[r.source]}</span>
                  <span className="flex items-center gap-3 text-xs text-ink-soft">
                    {r.latency_ms != null && <span className="tabular-nums">{r.latency_ms} ms</span>}
                    <span>{when(r.accessed_at)}</span>
                    <Badge tone={s.tone}>{s.text}</Badge>
                  </span>
                </li>
              )
            })}
          </ul>
        )}
      </div>

      <div className="space-y-3">
        <h4 className="text-xs font-semibold uppercase tracking-[0.12em] text-ink-soft">What we hold</h4>
        <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-[auto_1fr]">
          {holds.map(([k, v]) => (
            <div key={k} className="contents">
              <dt className="text-ink-soft">{k}</dt>
              <dd className="font-medium">{v}</dd>
            </div>
          ))}
        </dl>
      </div>
    </div>
  )
}
