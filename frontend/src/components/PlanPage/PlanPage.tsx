import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api, ApiError } from '../../api/client'
import type { Lang, PlanView } from '../../api/types'
import { t } from '../../i18n'
import { Spinner } from '../ui'
import { MobileShell } from '../ConsentPage/ConsentPage'
import VideoBg from '../VideoBg'

const ICONS = ['💡', '🎯', '🌱']
const Card = ({ children, className = '' }: { children: React.ReactNode; className?: string }) => <div className={`rounded-[1.75rem] p-5 ${className}`}>{children}</div>

export default function PlanPage() {
  const { applicationId = '' } = useParams()
  const [lang, setLang] = useState<Lang | undefined>(undefined)
  const [plan, setPlan] = useState<PlanView | null>(null)
  const [state, setState] = useState<'loading' | 'ok' | 'none' | 'offline'>('loading')

  useEffect(() => {
    setState('loading')
    api.plan(applicationId, lang).then((p) => { setPlan(p); setState('ok') })
      .catch((e: ApiError) => setState(e.code === 'NO_PLAN' || e.status === 404 ? 'none' : 'offline'))
  }, [applicationId, lang])

  const l = plan?.language ?? lang ?? 'en'

  return (
    <MobileShell lang={l} onLang={plan ? setLang : undefined} title={plan ? t('planTitle', l) : undefined} subtitle={plan ? `${plan.greeting}  ·  ${t('planFor', l, { product: plan.product_label })}` : undefined}>
      {state === 'loading' && !plan && <Card className="grid place-items-center bg-surface py-16"><Spinner className="h-6 w-6" /></Card>}
      {state === 'none' && <Card className="bg-surface py-12 text-center text-sm font-light text-ink-soft">🔍 {t('planNotFound', l)}</Card>}
      {state === 'offline' && <Card className="bg-surface py-12 text-center text-sm font-light text-ink-soft">📡 {t('offline', l)}</Card>}
      {plan && state !== 'none' && (
        <div className={`space-y-3 transition-opacity ${state === 'loading' ? 'opacity-50' : ''}`}>
          <Card className="bg-surface shadow-sm ring-1 ring-ink/[0.07]"><p className="text-sm font-light leading-relaxed text-ink-soft">{plan.summary}</p></Card>
          {plan.steps.map((s, i) => {
            const alt = i % 2 === 1
            return (
              <Card key={i} className={`flex gap-4 shadow-sm ${alt ? 'bg-surface-2 ring-1 ring-accent/25' : 'bg-surface ring-1 ring-ink/[0.07]'}`}>
                <div className={`grid h-11 w-11 shrink-0 place-items-center rounded-2xl text-xl ${alt ? 'bg-accent/15' : 'bg-lav-100'}`} aria-hidden>{ICONS[i % ICONS.length]}</div>
                <div>
                  <div className={`text-[11px] font-semibold uppercase tracking-[0.14em] text-lav-700`}>{t('step', l, { n: i + 1 })}</div>
                  <p className="mt-1 text-[15px] font-light leading-relaxed">{s}</p>
                </div>
              </Card>
            )
          })}
          <VideoBg className="rounded-[1.75rem] p-5"><p className="text-sm leading-relaxed">{plan.closing}</p></VideoBg>
        </div>
      )}
    </MobileShell>
  )
}
