import type { Trace } from '../../api/types'
import { Badge, type Tone } from '../ui'

const LABEL: Record<string, string> = {
  CREATED: 'Application created', BUREAU_CHECK: 'Bureau check', CONSENT_REQUEST_SENT: 'Consent request', CONSENT_GRANTED: 'Consent granted', CONSENT_DENIED: 'Consent denied',
  SESSION_EXPIRED: 'Session expired', AA_INGESTION: 'AA bank statement', TELECOM_INGESTION: 'Telecom recharge', BUSINESS_INGESTION: 'Business records',
  FEATURE_BUILD: 'Feature pipeline', SCORING: 'Model + SHAP', DECISION: 'Policy decision', ADVISORY: 'Vernacular advisory', LOS_HANDOFF: 'LOS handoff (mock)',
  LMS_ACCOUNT: 'LMS account (mock)', RESULT_MESSAGE_SENT: 'Result message', CONSENT_REVOKED: 'Consent revoked', PIPELINE_ERROR: 'Pipeline error',
}
const TONE: Record<string, { bar: string; tone: Tone }> = {
  ok: { bar: 'bg-ok', tone: 'green' }, timeout: { bar: 'bg-warn', tone: 'amber' }, error: { bar: 'bg-warn', tone: 'amber' },
  not_consented: { bar: 'bg-ink/30', tone: 'slate' }, no_data: { bar: 'bg-ink/30', tone: 'slate' }, skipped: { bar: 'bg-ink/30', tone: 'slate' },
}

function detail(d: Record<string, unknown> | null): string {
  if (!d) return ''
  const bits: string[] = []
  if (d.result) bits.push(String(d.result))
  if (d.provider) bits.push(`${d.provider}${d.delivery_status ? ` · ${d.delivery_status}` : ''}`)
  if (d.outcome) bits.push(String(d.outcome).replaceAll('_', ' ').toLowerCase())
  if (d.source) bits.push(`${d.source}${d.language ? ` · ${d.language}` : ''}`)
  if (d.reference) bits.push(String(d.reference))
  if (d.simulated_outage) bits.push('⚠ outage simulated via the demo option')
  if (d.detail && !bits.length) bits.push(String(d.detail))
  if (d.score != null && d.outcome == null) bits.push(`score ${d.score}`)
  return bits.join(' · ')
}

const TICK: Record<string, string> = { sent: '✓ sent', delivered: '✓✓ delivered', read: '✓✓ read', failed_real_send: '! real send failed', queued: '… queued' }

export default function PipelineTrace({ trace }: { trace: Trace | null }) {
  if (!trace || trace.stages.length === 0) return <p className="text-sm text-ink-soft">The trace fills in as the application moves through the pipeline.</p>
  const max = Math.max(...trace.stages.map((s) => s.latency_ms ?? 0), 1)
  const d = trace.message_delivery
  return (
    <div>
      <ul className="space-y-3">
        {trace.stages.map((s, i) => {
          const m = TONE[s.status] ?? TONE.ok
          const w = s.latency_ms != null ? Math.max(3, (s.latency_ms / max) * 100) : 0
          return (
            <li key={i} className="animate-[fadeIn_.3s_ease-out]">
              <div className="flex items-center justify-between gap-2 text-sm">
                <span className="truncate">{LABEL[s.stage] ?? s.stage}</span>
                <span className="flex shrink-0 items-center gap-2">
                  {s.status !== 'ok' && <Badge tone={m.tone}>{s.status.replace('_', ' ')}</Badge>}
                  <span className="w-16 text-right text-xs tabular-nums text-ink-soft">{s.latency_ms != null ? `${s.latency_ms} ms` : '—'}</span>
                </span>
              </div>
              <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-ink/[0.06]"><div className={`h-full rounded-full ${m.bar} transition-all duration-700`} style={{ width: `${w}%` }} /></div>
              {detail(s.details) && <p className="mt-1 truncate text-[11px] text-ink-soft">{detail(s.details)}</p>}
            </li>
          )
        })}
      </ul>
      {(d.consent_request || d.result_delivery) && (
        <div className="mt-4 flex flex-wrap gap-4 border-t border-ink/10 pt-3 text-xs text-ink-soft">
          {d.consent_request && <span>Consent message <b className="font-semibold text-ink">{TICK[d.consent_request] ?? d.consent_request}</b></span>}
          {d.result_delivery && <span>Result message <b className="font-semibold text-ink">{TICK[d.result_delivery] ?? d.result_delivery}</b></span>}
        </div>
      )}
    </div>
  )
}
