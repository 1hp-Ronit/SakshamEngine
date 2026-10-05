import type { ApplicationView, TimelineStage } from '../../api/types'
import { Spinner } from '../ui'

type StepState = 'done' | 'active' | 'pending' | 'warn' | 'skipped'
interface Step { label: string; state: StepState; note?: string; latency?: number | null }

const by = (tl: TimelineStage[], stage: string) => tl.find((s) => s.stage === stage)

export function buildSteps(app: ApplicationView): Step[] {
  const tl = app.timeline
  const steps: Step[] = []
  const created = by(tl, 'CREATED')
  const bureau = by(tl, 'BUREAU_CHECK')
  steps.push({ label: 'Application created', state: created ? 'done' : 'active' })
  steps.push({
    label: 'Bureau check', state: bureau ? 'done' : 'pending', latency: bureau?.latency_ms,
    note: bureau ? (app.bureau.status === 'HIT' ? `HIT · score ${app.bureau.score}` : 'NO_HIT — no usable credit history') : undefined,
  })
  if (app.status === 'BYPASSED_TO_LOS') {
    steps.push({ label: 'Routed to standard LOS', state: 'done', note: 'Bureau score sufficient — Saksham not invoked', latency: by(tl, 'LOS_HANDOFF')?.latency_ms })
    return steps
  }
  const req = by(tl, 'CONSENT_REQUEST_SENT')
  steps.push({ label: 'Consent request sent', state: req ? (req.status === 'ok' ? 'done' : 'warn') : 'pending', latency: req?.latency_ms,
    note: req ? `${(req.details?.provider as string) === 'whatsapp' ? 'WhatsApp' : 'Not sent via WhatsApp'} · ${(req.details?.delivery_status as string) ?? ''}`.trim() : undefined })
  const granted = by(tl, 'CONSENT_GRANTED'), denied = by(tl, 'CONSENT_DENIED'), expired = by(tl, 'SESSION_EXPIRED')
  steps.push({
    label: denied ? 'Customer declined consent' : expired ? 'Consent link expired' : 'Customer consent',
    state: granted ? 'done' : denied || expired ? 'warn' : req ? 'active' : 'pending',
    note: denied ? 'No data was requested' : expired ? 'Session TTL elapsed' : granted ? 'Granular consent signed' : req ? 'Waiting for the customer…' : undefined,
  })
  if (denied || expired) return steps
  const ing = ['AA_INGESTION', 'TELECOM_INGESTION', 'BUSINESS_INGESTION'].map((s) => by(tl, s)).filter(Boolean) as TimelineStage[]
  const ingDone = ing.length === 3
  steps.push({
    label: 'Alternative data ingested (parallel)', state: ingDone ? (ing.some((s) => s.status === 'timeout') ? 'warn' : 'done') : granted ? 'active' : 'pending',
    latency: ingDone ? Math.max(...ing.map((s) => s.latency_ms ?? 0)) : undefined,
    note: ingDone ? ing.map((s) => `${s.stage.split('_')[0].toLowerCase()}:${s.status}`).join(' · ') : undefined,
  })
  if (app.status === 'INSUFFICIENT_DATA') {
    steps.push({ label: 'Insufficient data → manual review', state: 'warn', note: 'Fewer than 2 usable sources' })
    return steps
  }
  const feat = by(tl, 'FEATURE_BUILD'), score = by(tl, 'SCORING'), dec = by(tl, 'DECISION')
  steps.push({ label: 'Features built', state: feat ? 'done' : ingDone ? 'active' : 'pending', latency: feat?.latency_ms })
  steps.push({ label: 'Scored & explained (SHAP)', state: score ? 'done' : feat ? 'active' : 'pending', latency: score?.latency_ms })
  steps.push({ label: 'Decision', state: dec ? 'done' : score ? 'active' : 'pending', note: dec ? String(dec.details?.outcome ?? '').replaceAll('_', ' ').toLowerCase() : undefined })
  const msg = by(tl, 'RESULT_MESSAGE_SENT')
  steps.push({ label: 'Result sent to applicant', state: msg ? (msg.status === 'ok' ? 'done' : 'warn') : dec ? 'active' : 'pending',
    note: msg ? `${(msg.details?.provider as string) === 'whatsapp' ? 'WhatsApp' : 'Not sent via WhatsApp'} · ${(msg.details?.delivery_status as string) ?? ''}` : undefined })
  return steps
}

const DOT: Record<StepState, string> = {
  done: 'bg-ok', active: 'bg-lav-500 animate-pulse', pending: 'bg-ink/15', warn: 'bg-warn', skipped: 'bg-ink/10',
}

export default function StatusTimeline({ app }: { app: ApplicationView }) {
  const steps = buildSteps(app)
  return (
    <ol className="relative space-y-4 pl-7">
      <span className="absolute bottom-1 left-[7px] top-1 w-px bg-ink/10" aria-hidden />
      {steps.map((s, i) => (
        <li key={i} className="relative animate-[fadeIn_.35s_ease-out]">
          <span className={`absolute -left-7 top-1 h-3.5 w-3.5 rounded-full ring-4 ring-surface ${DOT[s.state]}`} />
          <div className="flex items-baseline justify-between gap-2">
            <span className={`text-sm ${s.state === 'pending' ? 'text-ink/35' : 'font-medium'}`}>{s.label} {s.state === 'active' && <Spinner className="ml-1 align-middle" />}</span>
            {s.latency != null && <span className="shrink-0 text-xs tabular-nums text-ink-soft">{s.latency} ms</span>}
          </div>
          {s.note && <p className="text-xs leading-snug text-ink-soft">{s.note}</p>}
        </li>
      ))}
    </ol>
  )
}
