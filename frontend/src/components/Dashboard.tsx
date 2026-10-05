import { useCallback, useEffect, useState } from 'react'
import { api, ApiError } from '../api/client'
import type { ApplicationView, Decision, Persona, PublicConfig } from '../api/types'
import { useApplication } from '../hooks/useApplication'
import { Lockup, SakshamLogo, TvsCredit } from './Brand'
import ApplicationForm, { type FormValues } from './DealerPOS/ApplicationForm'
import { AuditPanel, Drivers } from './DealerPOS/DecisionDetails'
import StatusTimeline from './DealerPOS/StatusTimeline'
import ApprovedLoans from './ApprovedLoans/ApprovedLoans'
import ConsentLedger from './ConsentLedger/ConsentLedger'
import MessageLog from './Messages/MessageLog'
import LadderVisual from './UnderTheHood/LadderVisual'
import PipelineTrace from './UnderTheHood/PipelineTrace'
import ScoreGauge from './UnderTheHood/ScoreGauge'
import SHAPWaterfall from './UnderTheHood/SHAPWaterfall'
import SourceStatus from './UnderTheHood/SourceStatus'
import VideoBg from './VideoBg'
import { ErrorNote, Section, StatusBadge, inr } from './ui'

const KEY = 'saksham.applicationId'
const load = () => { try { return localStorage.getItem(KEY) } catch { return null } }
const save = (v: string | null) => { try { v ? localStorage.setItem(KEY, v) : localStorage.removeItem(KEY) } catch { /* private mode */ } }

const HEADLINE: Record<string, string> = {
  APPROVED: 'Approved into the existing loan flow.', CONDITIONAL_APPROVAL: 'So close — a smaller ticket or a co-applicant could work.',
  DECLINED_WITH_PLAN: 'Not yet — a plan to get there was sent in their language.', INSUFFICIENT_DATA: 'Not enough data to score — referred for manual review.',
  BYPASSED_TO_LOS: 'Strong bureau score — handled by the standard LOS.', CONSENT_DENIED: 'The customer declined — no data was requested.',
  EXPIRED: 'The consent link expired before the customer responded.', AWAITING_CONSENT: 'Waiting for the customer to give consent on their phone.',
  CONSENT_GRANTED: 'Consent received — reading data now.', INGESTING: 'Reading alternative data sources in parallel.', SCORED: 'Scoring…',
}

function Nav({ config, hasApp, busy, onNew, onReset }: { config: PublicConfig | null; hasApp: boolean; busy: boolean; onNew: () => void; onReset: () => void }) {
  const msg = config?.messaging
  return (
    <header className="flex items-center justify-between gap-3 py-4">
      <Lockup />
      <div className="flex items-center gap-2">
        <details className="group relative">
          <summary className="btn-ghost cursor-pointer list-none select-none">System <span className="text-[10px] transition group-open:rotate-180">▾</span></summary>
          <div className="absolute right-0 z-20 mt-2 w-72 space-y-2.5 rounded-3xl bg-surface-2 p-5 text-sm shadow-2xl shadow-ink/10 ring-1 ring-ink/10">
            <Row k="Dealer" v={config?.dealer ?? '…'} />
            <Row k="WhatsApp" v={msg?.real_sends_enabled ? 'live' : msg?.whatsapp_configured ? 'configured, sends off' : 'off (outbox only)'} ok={!!msg?.real_sends_enabled} />
            <Row k="Advisory LLM" v={config?.llm.available ? config.llm.model : 'deterministic templates'} ok={!!config?.llm.available} />
            <Row k="Model" v={config?.model.loaded ? `${config.model.version}` : 'not trained'} ok={!!config?.model.loaded} />
            {config?.model.metrics && <Row k="Test AUC" v={config.model.metrics.auc.toFixed(3)} />}
            <Row k="Approve cutoff" v={String(config?.policy.approve_cutoff ?? '…')} />
          </div>
        </details>
        <button onClick={onReset} disabled={busy} className="btn-ghost">Reset demo</button>
        {hasApp && <button onClick={onNew} className="btn-dark">New application</button>}
      </div>
    </header>
  )
}
const Row = ({ k, v, ok }: { k: string; v: string; ok?: boolean }) => <div className="flex justify-between gap-3"><span className="text-ink-soft">{k}</span><span className={`text-right font-medium ${ok ? 'text-ok' : ''}`}>{v}</span></div>

function Tile({ title, video = false, children }: { title: string; video?: boolean; children: React.ReactNode }) {
  const cls = 'flex min-h-[300px] flex-col justify-between gap-5 rounded-[1.75rem] p-6'
  const body = (
    <>
      <h3 className="text-xl font-light tracking-tight">{title}</h3>
      <div>{children}</div>
    </>
  )
  return video
    ? <VideoBg className={cls}>{body}</VideoBg>
    : <div className={`${cls} bg-surface text-ink shadow-sm ring-1 ring-ink/[0.07]`}>{body}</div>
}

/** What a dealer actually needs on one card: the loan being asked for, whether the EMI is affordable, and what to do next. */
function nextStep(app: ApplicationView, decision: Decision | null): string {
  const los = app.timeline.find((t) => t.stage === 'LOS_HANDOFF')?.details?.reference as string | undefined
  switch (app.status) {
    case 'APPROVED': return `Collect KYC documents and complete the e-NACH mandate.${los ? ` LOS reference ${los}.` : ''}`
    case 'CONDITIONAL_APPROVAL': return `Offer a ticket up to ${inr(app.suggested_ticket)} or add a co-applicant, then re-submit.`
    case 'DECLINED_WITH_PLAN': return 'Walk the customer through the plan on WhatsApp. Suggest re-applying in 2–3 months.'
    case 'INSUFFICIENT_DATA': return 'Refer to credit operations for manual review.'
    case 'BYPASSED_TO_LOS': return 'Continue in the standard LOS — Saksham was not needed.'
    case 'CONSENT_DENIED': return 'No data was accessed. Offer the standard documentation route.'
    case 'EXPIRED': return 'The link expired. Start a new application.'
    case 'AWAITING_CONSENT': return 'Ask the customer to open the WhatsApp message and tap “I Authorize”.'
    default: return decision ? 'See the details below.' : 'Reading data — result in a moment.'
  }
}

function LoanSummary({ app, decision, comfortable }: { app: ApplicationView; decision: Decision | null; comfortable: number }) {
  const income = decision?.affordability?.est_monthly_income
  const ratio = income ? app.requested_emi / income : null
  const tone = ratio == null ? 'bg-ink/15' : ratio <= comfortable ? 'bg-ok' : ratio <= comfortable * 1.4 ? 'bg-warn' : 'bg-rose-400'
  const verdict = ratio == null ? null : ratio <= comfortable ? 'comfortable' : ratio <= comfortable * 1.4 ? 'stretching' : 'too high'
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-3">
        {[['Ticket', inr(app.ticket_size)], ['EMI', inr(app.requested_emi)], ['Tenure', `${app.tenure_months} mo`]].map(([k, v]) => (
          <div key={k}><div className="text-[11px] uppercase tracking-[0.12em] text-ink-soft">{k}</div><div className="mt-0.5 text-lg font-light tabular-nums text-ink">{v}</div></div>
        ))}
      </div>
      <div>
        <div className="mb-1.5 flex items-center justify-between text-xs text-ink-soft">
          <span>{ratio != null ? <>EMI is <b className="font-semibold text-ink">{Math.round(ratio * 100)}%</b> of est. income {inr(income)}/mo</> : 'EMI vs estimated income'}</span>
          {verdict && <span className={ratio! <= comfortable ? 'text-ok' : 'text-warn'}>{verdict}</span>}
        </div>
        <div className="relative h-2 rounded-full bg-ink/10">
          <div className={`h-full rounded-full transition-all duration-700 ${tone}`} style={{ width: `${ratio == null ? 0 : Math.min(100, (ratio / (comfortable * 2)) * 100)}%` }} />
          <div className="absolute -top-1 h-4 w-px bg-ink/30" style={{ left: '50%' }} title={`comfortable up to ${Math.round(comfortable * 100)}%`} />
        </div>
        {ratio == null && <p className="mt-1.5 text-[11px] text-ink-soft/70">Appears once the applicant is scored.</p>}
      </div>
      <div className="rounded-2xl bg-lav-50 p-3.5">
        <div className="text-[11px] uppercase tracking-[0.12em] text-ink-soft">Next step</div>
        <p className="mt-1 text-sm leading-snug text-ink">{nextStep(app, decision)}</p>
      </div>
    </div>
  )
}

export default function Dashboard() {
  const [config, setConfig] = useState<PublicConfig | null>(null)
  const [personas, setPersonas] = useState<Persona[]>([])
  const [appId, setAppId] = useState<string | null>(load)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const { app, trace, messages, decision, error: pollError, refreshAll } = useApplication(appId)

  useEffect(() => {
    api.config().then(setConfig).catch(() => setError('Backend is not reachable. Start it with `make dev`.'))
    api.personas().then(setPersonas).catch(() => undefined)
  }, [])
  // A stale id (e.g. after a DB reset) must not leave the UI stuck
  useEffect(() => { if ((pollError as ApiError | null)?.status === 404) { setAppId(null); save(null) } }, [pollError])

  const submit = useCallback(async (v: FormValues) => {
    setBusy(true); setError(null)
    try {
      const persona = personas.find((p) => p.id === v.persona_id)
      const res = await api.create({
        mobile_number: v.mobile_number, pan_token: v.pan_token, aadhaar_token: v.aadhaar_token, requested_product_sku: v.requested_product_sku,
        applicant_name: v.applicant_name, preferred_language: v.preferred_language, persona_name: persona?.key,
        demo_options: v.simulate_outage.length ? { simulate_outage: v.simulate_outage } : undefined,
      })
      setAppId(res.application_id); save(res.application_id)
    } catch (e) { setError((e as ApiError).message) } finally { setBusy(false) }
  }, [personas])

  const reset = async () => {
    setBusy(true)
    try { await api.reset(); setAppId(null); save(null); setError(null) } catch (e) { setError((e as ApiError).message) } finally { setBusy(false) }
  }
  const newApp = () => { setAppId(null); save(null) }

  return (
    <div className="min-h-screen bg-paper text-ink">
      <div className="mx-auto max-w-[1160px] px-4 pb-10 sm:px-6">
        <Nav config={config} hasApp={!!app} busy={busy} onNew={newApp} onReset={reset} />
        {error && <div className="mb-4"><ErrorNote>{error}</ErrorNote></div>}
        {config && !config.model.loaded && <div className="mb-4"><ErrorNote>The scoring model has not been trained yet — run <code>make train</code> and restart.</ErrorNote></div>}

        {app ? <Console app={app} config={config} trace={trace} messages={messages} decision={decision} refreshAll={refreshAll} />
          : <Landing personas={personas} config={config} busy={busy} onSubmit={submit} />}

        <footer className="pt-10 text-center text-xs text-ink-soft"><p className="flex items-center justify-center gap-2">Built for <TvsCredit /></p></footer>
      </div>
    </div>
  )
}

function Landing({ personas, config, busy, onSubmit }: { personas: Persona[]; config: PublicConfig | null; busy: boolean; onSubmit: (v: FormValues) => void }) {
  return (
    <>
      <VideoBg className="rounded-[2rem]">
        <div className="relative px-6 pb-52 pt-14 text-center sm:pb-60 sm:pt-16">
          <SakshamLogo className="mx-auto h-12 w-12 text-white" />
          <h1 className="mx-auto mt-4 max-w-2xl text-4xl font-light leading-[1.08] tracking-tight sm:text-6xl">Where credit grows</h1>
          <p className="mx-auto mt-4 max-w-md text-sm font-light leading-relaxed text-white/80 sm:text-base">A consent-based safety net for customers the bureau cannot see — scored in milliseconds from the signals they already leave behind.</p>
        </div>
      </VideoBg>
      <section className="relative z-10 mx-auto -mt-40 max-w-3xl rounded-[1.75rem] bg-surface p-5 text-ink shadow-[0_30px_80px_-30px_rgba(25,21,43,0.25)] ring-1 ring-ink/[0.07] sm:-mt-48 sm:p-7">
        <h2 className="mb-5 text-2xl font-light tracking-tight">Start an application</h2>
        <ApplicationForm personas={personas} config={config} busy={busy} disabled={false} onSubmit={onSubmit} />
      </section>
      <div className="mx-auto mt-6 max-w-3xl pb-4"><ApprovedLoans /></div>
    </>
  )
}

function Console({ app, config, trace, messages, decision, refreshAll }: {
  app: ApplicationView; config: PublicConfig | null; trace: ReturnType<typeof useApplication>['trace']; messages: ReturnType<typeof useApplication>['messages']
  decision: Decision | null; refreshAll: () => Promise<void>
}) {
  const cutoff = config?.policy.approve_cutoff ?? 650
  const decided = ['APPROVED', 'CONDITIONAL_APPROVAL', 'DECLINED_WITH_PLAN'].includes(app.status)
  const score = decision?.score ?? app.score ?? null
  const inProgress = !app.terminal
  const sourcesOk = trace ? Object.values(trace.sources).filter((s) => s.status === 'ok').length : 0
  return (
    <>
      <VideoBg className="rounded-[2rem]">
        <div className="relative flex flex-col gap-3 px-6 pb-14 pt-9 sm:px-10 sm:pb-20 sm:pt-12">
          <div><StatusBadge status={app.status} className="!bg-black/35 backdrop-blur" /></div>
          <h1 className="text-4xl font-light tracking-tight sm:text-6xl">{app.applicant_name || 'Applicant'}</h1>
          <p className="text-sm font-light text-white/80 sm:text-base">{app.product_label} · EMI {inr(app.requested_emi)} · {app.mobile_masked} · {app.language.toUpperCase()}</p>
          {app.simulated_outage.length > 0 && <p className="w-fit rounded-full bg-black/35 px-3 py-1 text-xs text-warn backdrop-blur">⚠ Outage deliberately simulated for: {app.simulated_outage.join(', ')}</p>}
        </div>
      </VideoBg>

      <div className="mt-12 grid items-end gap-5 md:grid-cols-[1.15fr_1fr]">
        <h2 className="text-3xl font-light leading-[1.12] tracking-tight sm:text-4xl lg:text-[2.75rem]">{HEADLINE[app.status] ?? app.status}</h2>
        <p className="text-base font-light leading-relaxed text-ink-soft sm:text-lg">
          {decision?.score != null
            ? <>Score <b className="font-medium text-ink">{Math.round(decision.score)}</b> · default probability {(decision.pd! * 100).toFixed(1)}% · approval cutoff {cutoff}.{app.status === 'CONDITIONAL_APPROVAL' && app.suggested_ticket != null && <> Suggested ticket up to <b className="font-medium text-ink">{inr(app.suggested_ticket)}</b>.</>}</>
            : inProgress ? 'Every step is timed and logged below as it happens.' : 'See the details below.'}
        </p>
      </div>

      <div className="mt-8 grid gap-4 md:grid-cols-[1.1fr_1.3fr_1fr]">
        <Tile title="Score" video><ScoreGauge score={score} cutoff={cutoff} floor={config?.policy.borderline_floor} onDark /></Tile>
        <Tile title="Loan summary"><LoanSummary app={app} decision={decision} comfortable={config?.policy.comfortable_emi_ratio ?? 0.33} /></Tile>
        <Tile title="Data sources">
          <SourceStatus trace={trace} app={app} />
          <p className="mt-3 text-xs text-ink-soft">{trace && Object.keys(trace.sources).length ? `${sourcesOk} of 3 usable · fetched in parallel` : 'fetched in parallel, per-source timeout'}</p>
        </Tile>
      </div>

      <div className="mt-6 space-y-3">
        <Section title="Messages to applicant" defaultOpen={app.status === 'AWAITING_CONSENT'} hint={app.status === 'AWAITING_CONSENT' ? 'Consent link, QR code and delivery status' : `${messages.filter((m) => m.direction === 'OUTBOUND').length} sent · ${config?.messaging.real_sends_enabled ? 'via WhatsApp' : 'WhatsApp off'}`}>
          <MessageLog messages={messages} app={app} />
        </Section>
        {decision && decision.score != null && (
          <Section title="Why this score" hint="Reason codes and the SHAP waterfall, in score points" defaultOpen={decided}>
            <div className="space-y-8"><Drivers decision={decision} /><div className="border-t border-ink/10 pt-6"><SHAPWaterfall items={decision.waterfall} base={decision.base_score} final={decision.score} /></div></div>
          </Section>
        )}
        {app.loan && (
          <Section title="Graduation ladder" hint={`${app.loan.current_tier.toLowerCase()} tier · behaviour score ${app.loan.behaviour_score}`} defaultOpen={app.status === 'APPROVED'}>
            <LadderVisual ladder={app.loan} onChanged={refreshAll} />
          </Section>
        )}
        <Section title="Application timeline" hint={inProgress ? 'In progress…' : 'Every state transition'} defaultOpen={inProgress && app.status !== 'AWAITING_CONSENT'}><StatusTimeline app={app} /></Section>
        <Section title="Pipeline trace" hint={trace?.total_latency_ms != null ? `Consent → decision in ${trace.total_latency_ms} ms · per-stage latency and delivery` : 'Per-stage latency and delivery status'}><PipelineTrace trace={trace} /></Section>
        <Section title="Audit & consent" hint="Immutable audit record, signed consent, revocation"><AuditPanel app={app} decision={decision} onChanged={refreshAll} reasons={config?.withdrawal_reasons} /></Section>
        <Section title="Consent & data-rights ledger" hint={`${app.consent ? 'Consent given' : 'No consent'} · every read we attempted · what we still hold`}>
          <ConsentLedger applicationId={app.application_id} version={`${app.status}|${app.consent?.revoked ? 'revoked' : 'live'}`} />
        </Section>
      </div>
    </>
  )
}
