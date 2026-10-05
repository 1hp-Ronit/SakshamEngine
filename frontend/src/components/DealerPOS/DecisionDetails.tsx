import { useState } from 'react'
import { api } from '../../api/client'
import type { ApplicationView, Decision, Driver } from '../../api/types'
import { Badge, Spinner } from '../ui'

function DriverRow({ d, positive }: { d: Driver; positive: boolean }) {
  return (
    <li className="flex items-start justify-between gap-3 text-sm">
      <span className="flex gap-2 leading-snug"><span className={positive ? 'text-ok' : 'text-warn'}>{positive ? '▲' : '▼'}</span>{d.reason_text}</span>
      <span className="flex shrink-0 items-center gap-2">
        {d.reason_code && <Badge>{d.reason_code}</Badge>}
        <span className={`w-10 text-right tabular-nums ${positive ? 'text-ok' : 'text-warn'}`}>{d.points > 0 ? '+' : ''}{d.points.toFixed(0)}</span>
      </span>
    </li>
  )
}

/** Top positive / negative reason codes. */
export function Drivers({ decision }: { decision: Decision }) {
  const { positive, negative } = decision.shap_drivers
  return (
    <div className="grid gap-6 md:grid-cols-2">
      {positive.length > 0 && <div><h4 className="mb-3 text-xs font-semibold uppercase tracking-[0.12em] text-ok">Helping the score</h4><ul className="space-y-2.5">{positive.map((d) => <DriverRow key={d.feature} d={d} positive />)}</ul></div>}
      {negative.length > 0 && <div><h4 className="mb-3 text-xs font-semibold uppercase tracking-[0.12em] text-warn">Holding it back</h4><ul className="space-y-2.5">{negative.map((d) => <DriverRow key={d.feature} d={d} positive={false} />)}</ul></div>}
    </div>
  )
}

/** Audit record, consent artifact and the revoke action. */
export function AuditPanel({ app, decision, onChanged, reasons = [] }: { app: ApplicationView; decision: Decision | null; onChanged: () => void; reasons?: string[] }) {
  const [revoking, setRevoking] = useState(false)
  const [note, setNote] = useState<string | null>(null)
  const [reason, setReason] = useState(reasons[0] ?? '')
  const [confirming, setConfirming] = useState(false)
  const [withdrawing, setWithdrawing] = useState(false)
  const canWithdraw = app.outcome === 'APPROVED' && !app.withdrawal && reasons.length > 0
  const consentId = app.consent?.consent_id
  const canRevoke = consentId && !app.consent?.revoked && ['APPROVED', 'CONDITIONAL_APPROVAL', 'DECLINED_WITH_PLAN'].includes(app.status)

  const revoke = async () => {
    if (!consentId) return
    setRevoking(true)
    try {
      const r = await api.revoke(consentId)
      setNote(r.features_purged ? 'Consent revoked · stored features purged · further data access blocked' : 'Consent revoked · further data access blocked')
      onChanged()
    } finally { setRevoking(false) }
  }
  const withdraw = async () => {
    setWithdrawing(true)
    try {
      await api.withdraw(app.application_id, reason)
      setConfirming(false)
      setNote(`Approval withdrawn (${reason.toLowerCase().replaceAll('_', ' ')}). The loan is no longer on the approved list; the audit record and consent history are kept.`)
      onChanged()
    } catch (e) {
      setNote((e as Error).message)
    } finally { setWithdrawing(false) }
  }
  const rows: [string, string][] = []
  if (decision) rows.push(['Audit record', decision.audit_record_id.slice(0, 8)], ['Model', decision.model_version], ['Policy', decision.policy_version], ['Feature hash', `#${decision.feature_vector_hash?.slice(0, 12) ?? '—'}`])
  if (app.consent) rows.push(['Consent', `${app.consent.consent_id.slice(0, 8)} · ${Object.entries(app.consent.grants).filter(([, v]) => v).map(([k]) => k).join(', ')}`], ['Valid until', app.consent.expires_at.slice(0, 10)])
  return (
    <div className="space-y-4">
      {rows.length > 0 && <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 text-sm">{rows.map(([k, v]) => <div key={k} className="contents"><dt className="text-ink-soft">{k}</dt><dd className="break-all font-medium">{v}</dd></div>)}</dl>}
      <div className="flex flex-wrap items-center gap-3">
        {app.status === 'DECLINED_WITH_PLAN' && <a href={`/plan/${app.application_id}`} target="_blank" rel="noreferrer" className="btn-ghost">Open the action plan ↗</a>}
        {canRevoke && <button onClick={revoke} disabled={revoking} className="btn-ghost">Revoke consent (demo)</button>}
      </div>
      {canWithdraw && (
        <div className="space-y-3 rounded-2xl bg-warn-soft p-4">
          <p className="text-sm font-medium text-warn">Withdraw this approval</p>
          <p className="text-xs text-ink-soft">The loan leaves the approved list. The decision, audit record and consent history stay on file.</p>
          <div className="flex flex-wrap items-center gap-3">
            <select className="field !w-auto" value={reason} onChange={(e) => setReason(e.target.value)} disabled={withdrawing} aria-label="Reason">
              {reasons.map((r) => <option key={r} value={r}>{r.toLowerCase().replaceAll('_', ' ')}</option>)}
            </select>
            {!confirming
              ? <button onClick={() => setConfirming(true)} disabled={!reason} className="btn-ghost">Withdraw approval…</button>
              : <>
                  <button onClick={withdraw} disabled={withdrawing} className="btn-dark !bg-warn">{withdrawing && <Spinner />} Confirm withdrawal</button>
                  <button onClick={() => setConfirming(false)} disabled={withdrawing} className="btn-ghost">Cancel</button>
                </>}
          </div>
        </div>
      )}
      {app.withdrawal && (
        <p className="text-sm text-warn">Withdrawn {new Date(app.withdrawal.withdrawn_at).toLocaleString('en-IN')} · reason: {app.withdrawal.reason.toLowerCase().replaceAll('_', ' ')}</p>
      )}
      {(app.consent?.revoked || note) && <p className="text-sm text-ink-soft">{note ?? 'Consent revoked · stored features purged'}</p>}
    </div>
  )
}
