import { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api, ApiError } from '../../api/client'
import type { ConsentSessionInfo, Group, Lang } from '../../api/types'
import { LANG_LABEL, t } from '../../i18n'
import { SakshamLogo, TvsCredit } from '../Brand'
import VideoBg from '../VideoBg'
import { Spinner } from '../ui'

const ICON: Record<Group, string> = { aa: '🏦', telecom: '📱', business: '🧾' }

function Switch({ on, onChange, label }: { on: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <button type="button" role="switch" aria-checked={on} aria-label={label} onClick={() => onChange(!on)}
      className={`relative h-8 w-14 shrink-0 rounded-full transition-colors ${on ? 'bg-accent' : 'bg-ink/20'}`}>
      <span className={`absolute top-1 h-6 w-6 rounded-full bg-white shadow transition-all ${on ? 'left-7' : 'left-1'}`} />
    </button>
  )
}

export function LangChips({ lang, onChange, langs = ['en', 'hi', 'mr'] }: { lang: Lang; onChange: (l: Lang) => void; langs?: Lang[] }) {
  return (
    <div className="flex gap-0.5 rounded-full bg-black/35 p-1 backdrop-blur" role="group" aria-label="Language">
      {langs.map((l) => (
        <button key={l} onClick={() => onChange(l)} aria-pressed={lang === l}
          className={`rounded-full px-3 py-1 text-xs font-medium transition ${lang === l ? 'bg-accent text-accent-ink' : 'text-white/70'}`}>{LANG_LABEL[l]}</button>
      ))}
    </div>
  )
}

/** Shared phone layout: video hero card, content card overlapping it. */
export function MobileShell({ children, lang, onLang, title, subtitle }: { children: React.ReactNode; lang: Lang; onLang?: (l: Lang) => void; title?: string; subtitle?: string }) {
  return (
    <div className="min-h-screen bg-paper pb-8 pt-[max(0.75rem,env(safe-area-inset-top))]">
      <div className="mx-auto max-w-md px-3">
        <VideoBg className="rounded-[2rem]">
          <div className="relative px-5 pb-28 pt-5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2"><SakshamLogo className="h-7 w-7" /><span className="font-medium leading-tight tracking-tight">Saksham<br /><span className="text-[11px] font-normal text-white/65">Engine</span></span></div>
              {onLang && <LangChips lang={lang} onChange={onLang} />}
            </div>
            {title && <h1 className="mt-8 text-4xl font-light leading-tight tracking-tight">{title}</h1>}
            {subtitle && <p className="mt-2 text-sm font-light text-white/80">{subtitle}</p>}
          </div>
        </VideoBg>
        <main className="relative z-10 -mt-20 space-y-3 px-1">{children}</main>
        <footer className="mt-8 px-2 text-center text-[11px] text-ink-soft"><p className="flex items-center justify-center gap-2.5">A service by <TvsCredit imgClass="h-4" /></p></footer>
      </div>
    </div>
  )
}

const fmt = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
const Card = ({ children, className = '' }: { children: React.ReactNode; className?: string }) => <div className={`rounded-[1.75rem] bg-surface p-5 shadow-sm ring-1 ring-ink/[0.07] ${className}`}>{children}</div>

export default function ConsentPage() {
  const { sessionId = '' } = useParams()
  const [info, setInfo] = useState<ConsentSessionInfo | null>(null)
  const [lang, setLang] = useState<Lang>('en')
  const [grants, setGrants] = useState<Record<Group, boolean>>({ aa: true, telecom: true, business: true })
  const [phase, setPhase] = useState<'loading' | 'form' | 'granted' | 'denied' | 'expired' | 'used' | 'notfound' | 'offline'>('loading')
  const [busy, setBusy] = useState(false)
  const [remaining, setRemaining] = useState(0)
  const [waLink, setWaLink] = useState<string | null>(null)
  const [showMore, setShowMore] = useState(false)

  const load = () => {
    setPhase('loading')
    api.consentSession(sessionId).then((i) => {
      setInfo(i); setLang(i.language); setRemaining(i.seconds_remaining); setWaLink(i.whatsapp_link)
      setPhase(i.status === 'EXPIRED' ? 'expired' : i.status === 'OPEN' ? 'form' : i.status === 'DENIED' ? 'denied' : 'used')
    }).catch((e: ApiError) => setPhase(e.status === 404 ? 'notfound' : 'offline'))
  }
  useEffect(load, [sessionId]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (phase !== 'form') return
    const id = setInterval(() => setRemaining((r) => { if (r <= 1) { setPhase('expired'); return 0 } return r - 1 }), 1000)
    return () => clearInterval(id)
  }, [phase])

  const anyOn = useMemo(() => Object.values(grants).some(Boolean), [grants])

  const submit = async (grant: boolean) => {
    if (!info) return
    setBusy(true)
    try {
      if (grant) { const r = await api.authorize(info.session_id, grants, info.purpose); setPhase(r.denied ? 'denied' : 'granted') }
      else { await api.deny(info.session_id); setPhase('denied') }
    } catch (e) {
      const err = e as ApiError
      setPhase(err.code === 'SESSION_EXPIRED' ? 'expired' : err.status === 409 ? 'used' : 'offline')
    } finally { setBusy(false) }
  }

  const name = info?.applicant_name?.split(' ')[0] ?? ''
  const product = info?.product_labels?.[lang] ?? info?.product_label ?? ''
  const form = phase === 'form' && info

  return (
    <MobileShell lang={lang} onLang={setLang} title={form ? t('consentTitle', lang) : undefined} subtitle={form ? t('hello', lang, { name }) : undefined}>
      {phase === 'loading' && <Card className="grid place-items-center py-16"><Spinner className="h-6 w-6" /></Card>}

      {form && info && (<>
        <Card>
          <p className="text-sm font-light leading-relaxed text-ink-soft">{t('intro', lang, { product })}</p>
        </Card>
        {info.groups.map((g) => (
          <Card key={g} className={`flex items-center gap-4 transition ${grants[g] ? '' : 'opacity-70'}`}>
            <div className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-lav-100 text-2xl" aria-hidden>{ICON[g]}</div>
            <div className="min-w-0 flex-1">
              <div className="font-medium">{t(g, lang)}</div>
              <p className="mt-0.5 text-xs font-light leading-relaxed text-ink-soft">{t(`${g}Desc` as 'aaDesc', lang)}</p>
            </div>
            <Switch on={grants[g]} onChange={(v) => setGrants((s) => ({ ...s, [g]: v }))} label={t(g, lang)} />
          </Card>
        ))}
        <Card className="!p-0">
          <button onClick={() => setShowMore((v) => !v)} aria-expanded={showMore} className="flex w-full items-center justify-between px-5 py-4 text-sm">
            <span>{t('purpose', lang)} · {t('timer', lang, { time: fmt(remaining) })}</span>
            <span className={`grid h-7 w-7 place-items-center rounded-full border border-ink/15 transition-transform ${showMore ? 'rotate-45 border-transparent bg-accent text-accent-ink' : ''}`}>+</span>
          </button>
          <div className="acc" data-open={showMore}><div><div className="space-y-1 px-5 pb-4 text-xs text-ink-soft"><p>{info.purpose}</p><p>{t('valid', lang, { days: info.consent_valid_days })}</p></div></div></div>
        </Card>
        {!anyOn && <p className="text-center text-xs text-warn">{t('pickOne', lang)}</p>}
        <div className="space-y-2 pt-1">
          <button disabled={!anyOn || busy} onClick={() => submit(true)} className="btn-dark w-full !py-4 !text-base">{busy && <Spinner />} {t('authorize', lang)}</button>
          <button disabled={busy} onClick={() => submit(false)} className="w-full py-3 text-sm text-ink-soft">{t('deny', lang)}</button>
        </div>
      </>)}

      {phase === 'granted' && (
        <Card className="space-y-4 py-10 text-center">
          <div className="mx-auto grid h-14 w-14 place-items-center rounded-full bg-ok-soft text-2xl text-ok">✓</div>
          <h2 className="text-2xl font-light tracking-tight">{t('thanks', lang)}</h2>
          <p className="text-sm font-light leading-relaxed text-ink-soft">{t('granted', lang)}</p>
          {waLink && <a href={waLink} target="_blank" rel="noreferrer" className="btn-dark !bg-[#25d366] !text-[#03140f]">💬 {t('continueWa', lang)}</a>}
        </Card>
      )}
      {phase === 'denied' && <Notice icon="🔒" text={t('denied', lang)} />}
      {phase === 'expired' && <Notice icon="⏳" text={t('expired', lang)} />}
      {phase === 'used' && <Notice icon="✓" text={t('alreadyDone', lang)} />}
      {phase === 'notfound' && <Notice icon="🔍" text={t('notFound', lang)} />}
      {phase === 'offline' && <Notice icon="📡" text={t('offline', lang)} action={<button onClick={load} className="btn-ghost mt-4">{t('retry', lang)}</button>} />}
    </MobileShell>
  )
}

function Notice({ icon, text, action }: { icon: string; text: string; action?: React.ReactNode }) {
  return (
    <Card className="space-y-3 py-12 text-center">
      <div className="text-4xl">{icon}</div>
      <p className="mx-auto max-w-xs text-sm font-light leading-relaxed text-ink-soft">{text}</p>
      {action}
    </Card>
  )
}
