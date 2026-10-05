import { useState } from 'react'
import type { ApplicationView, Message } from '../../api/types'
import { Badge, type Tone } from '../ui'
import QrCode from './QrCode'

const PURPOSE: Record<string, string> = { consent_request: 'Consent request', result: 'Decision / action plan', status_update: 'Status update' }
const STATUS: Record<string, { text: string; tone: Tone }> = {
  queued: { text: 'queued', tone: 'slate' }, sent: { text: '✓ sent', tone: 'slate' }, delivered: { text: '✓✓ delivered', tone: 'slate' },
  read: { text: '✓✓ read', tone: 'blue' }, failed: { text: 'failed', tone: 'amber' }, failed_real_send: { text: 'real send failed', tone: 'amber' },
}

function CopyButton({ text }: { text: string }) {
  const [done, setDone] = useState(false)
  return <button onClick={() => navigator.clipboard?.writeText(text).then(() => { setDone(true); setTimeout(() => setDone(false), 1500) })} className="btn-ghost !px-3 !py-1 !text-xs">{done ? 'Copied' : 'Copy link'}</button>
}

/** What was sent to the applicant's real phone, and whether it arrived. */
export default function MessageLog({ messages, app }: { messages: Message[]; app: ApplicationView | null }) {
  const out = messages.filter((m) => m.direction === 'OUTBOUND')
  const showLink = app?.status === 'AWAITING_CONSENT' && app.consent_url
  if (!out.length && !showLink) return <p className="text-sm text-ink-soft">Messages sent to the applicant appear here with their delivery status.</p>
  return (
    <div className="space-y-3">
      {showLink && app?.consent_url && (
        <div className="rounded-2xl bg-lav-50 p-4">
          <div className="mb-1.5 flex items-center justify-between"><span className="text-sm font-medium">Consent link</span><CopyButton text={app.consent_url} /></div>
          <p className="break-all text-xs text-ink-soft">{app.consent_url}</p>
          <QrCode url={app.consent_url} />
        </div>
      )}
      <ul className="space-y-2.5">
        {out.map((m) => {
          const st = STATUS[m.delivery_status] ?? { text: m.delivery_status, tone: 'slate' as Tone }
          const real = m.provider === 'whatsapp'
          return (
            <li key={m.id} className="rounded-2xl bg-ink/[0.03] p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-sm font-medium">{PURPOSE[m.purpose] ?? m.purpose}</span>
                <span className="flex items-center gap-1.5">
                  <Badge tone={real ? 'green' : 'slate'}>{real ? `WhatsApp ${m.message_type}${m.template_name ? ` · ${m.template_name}` : ''}` : 'not sent via WhatsApp'}</Badge>
                  <Badge tone={st.tone}>{st.text}</Badge>
                </span>
              </div>
              {m.error && <p className="mt-2 text-xs text-warn">{m.error}</p>}
              <details className="mt-2 text-xs text-ink-soft">
                <summary className="cursor-pointer select-none hover:text-ink">Message text</summary>
                <p className="mt-1.5 whitespace-pre-wrap break-words leading-relaxed text-ink">{m.body}</p>
              </details>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
