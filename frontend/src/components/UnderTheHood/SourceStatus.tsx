import type { ApplicationView, Trace } from '../../api/types'
import { Badge, Spinner, type Tone } from '../ui'

const META: Record<string, { label: string; icon: string }> = {
  aa: { label: 'Bank statement (AA)', icon: '🏦' }, telecom: { label: 'Telecom recharge', icon: '📱' }, business: { label: 'Business records', icon: '🧾' },
}
const STATUS: Record<string, { text: string; tone: Tone }> = {
  ok: { text: 'OK', tone: 'green' }, timeout: { text: 'Timed out', tone: 'amber' }, not_consented: { text: 'Not consented', tone: 'slate' },
  no_data: { text: 'No data', tone: 'slate' }, error: { text: 'Error', tone: 'amber' },
}

/** Compact per-source status. `dark` = rendered on the ink tile. */
export default function SourceStatus({ trace, app, dark = false }: { trace: Trace | null; app: ApplicationView | null; dark?: boolean }) {
  const pending = app?.status === 'INGESTING' || app?.status === 'CONSENT_GRANTED'
  return (
    <ul className="space-y-2.5">
      {Object.entries(META).map(([k, m]) => {
        const s = trace?.sources?.[k]
        const st = s ? STATUS[s.status] ?? { text: s.status, tone: 'slate' as Tone } : null
        return (
          <li key={k} className="flex items-center justify-between gap-3 text-sm">
            <span className="flex items-center gap-2"><span aria-hidden>{m.icon}</span><span className={dark ? 'text-white/85' : ''}>{m.label}</span></span>
            <span className="flex items-center gap-2">
              {s?.latency_ms != null && <span className={`text-xs tabular-nums ${dark ? 'text-white/50' : 'text-ink-soft'}`}>{s.latency_ms} ms</span>}
              {st ? <Badge tone={dark && st.tone === 'green' ? 'dark' : st.tone}>{dark && st.tone === 'green' ? '✓ OK' : st.text}</Badge> : pending ? <Spinner className={dark ? 'text-white' : ''} /> : <span className={`text-xs ${dark ? 'text-white/30' : 'text-ink/30'}`}>—</span>}
            </span>
          </li>
        )
      })}
    </ul>
  )
}
