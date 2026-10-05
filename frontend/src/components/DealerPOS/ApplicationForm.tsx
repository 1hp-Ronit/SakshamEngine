import { useEffect, useState } from 'react'
import type { Group, Lang, Persona, PublicConfig } from '../../api/types'
import { LANG_LABEL } from '../../i18n'
import { Section, Spinner, inr } from '../ui'

export interface FormValues {
  persona_id: number | null
  applicant_name: string
  mobile_number: string
  pan_token: string
  aadhaar_token: string
  requested_product_sku: string
  preferred_language: Lang
  simulate_outage: Group[]
}

export const emptyForm = (sku = 'TWO_WHEELER'): FormValues => ({
  persona_id: null, applicant_name: '', mobile_number: '', pan_token: '', aadhaar_token: '', requested_product_sku: sku, preferred_language: 'en', simulate_outage: [],
})

const label = 'mb-1.5 block text-xs font-medium text-ink-soft'

export default function ApplicationForm({ personas, config, busy, disabled, onSubmit }: {
  personas: Persona[]; config: PublicConfig | null; busy: boolean; disabled: boolean; onSubmit: (v: FormValues) => void
}) {
  const [v, setV] = useState<FormValues>(emptyForm())
  const set = <K extends keyof FormValues>(k: K, val: FormValues[K]) => setV((s) => ({ ...s, [k]: val }))

  useEffect(() => { if (config && !config.products[v.requested_product_sku]) set('requested_product_sku', Object.keys(config.products)[0]) }, [config]) // eslint-disable-line react-hooks/exhaustive-deps

  const pick = (id: string) => {
    const p = personas.find((x) => String(x.id) === id) ?? null
    if (!p) return setV(emptyForm(v.requested_product_sku))
    setV({ persona_id: p.id, applicant_name: p.name, mobile_number: p.mobile_number, pan_token: p.pan_token, aadhaar_token: p.aadhaar_token,
      requested_product_sku: p.product_sku, preferred_language: p.language, simulate_outage: p.simulate_outage ?? [] })
  }
  const persona = personas.find((p) => p.id === v.persona_id)
  const product = config?.products[v.requested_product_sku]
  const valid = v.applicant_name.trim() && v.mobile_number.replace(/\D/g, '').length >= 10 && v.pan_token && v.aadhaar_token

  return (
    <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); if (valid) onSubmit(v) }}>
      <div>
        <label className={label} htmlFor="persona">Demo persona</label>
        <div className="flex flex-col gap-3 sm:flex-row">
          <select id="persona" className="field flex-1" value={v.persona_id ?? ''} onChange={(e) => pick(e.target.value)} disabled={disabled}>
            <option value="">Choose a persona, or enter details below…</option>
            {personas.map((p) => <option key={p.id} value={p.id}>{p.id}. {p.name} · {p.product_label}</option>)}
          </select>
          <button type="submit" disabled={!valid || busy || disabled} className="btn-dark sm:min-w-[11rem]">{busy && <Spinner />} Start application</button>
        </div>
        {persona && <p className="mt-2.5 text-sm font-light leading-relaxed text-ink-soft">{persona.description}</p>}
      </div>

      <div className="space-y-2.5">
        <Section title="Applicant details" hint={v.applicant_name ? `${v.applicant_name} · ${product?.label ?? ''}` : 'Name, mobile, identifiers, product, language'} defaultOpen={false}>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="sm:col-span-2"><label className={label} htmlFor="name">Applicant name</label>
              <input id="name" className="field" value={v.applicant_name} onChange={(e) => set('applicant_name', e.target.value)} disabled={disabled} /></div>
            <div><label className={label} htmlFor="mobile">Mobile number</label>
              <input id="mobile" inputMode="numeric" className="field" value={v.mobile_number} onChange={(e) => set('mobile_number', e.target.value)} disabled={disabled} /></div>
            <div><label className={label} htmlFor="lang">Language</label>
              <select id="lang" className="field" value={v.preferred_language} onChange={(e) => set('preferred_language', e.target.value as Lang)} disabled={disabled}>
                {(config?.languages ?? ['en', 'hi', 'mr']).map((l) => <option key={l} value={l}>{LANG_LABEL[l]} — {{ en: 'English', hi: 'हिन्दी', mr: 'मराठी' }[l]}</option>)}
              </select></div>
            <div><label className={label} htmlFor="pan">PAN token</label>
              <input id="pan" className="field" value={v.pan_token} onChange={(e) => set('pan_token', e.target.value)} disabled={disabled} /></div>
            <div><label className={label} htmlFor="aadhaar">Aadhaar token</label>
              <input id="aadhaar" className="field" value={v.aadhaar_token} onChange={(e) => set('aadhaar_token', e.target.value)} disabled={disabled} /></div>
            <div className="sm:col-span-2"><label className={label} htmlFor="sku">Product</label>
              <select id="sku" className="field" value={v.requested_product_sku} onChange={(e) => set('requested_product_sku', e.target.value)} disabled={disabled}>
                {Object.entries(config?.products ?? {}).map(([k, p]) => <option key={k} value={k}>{p.label} — {inr(p.ticket)} · EMI {inr(p.emi)} × {p.tenure_months}</option>)}
              </select></div>
          </div>
        </Section>

        <Section title="Demo options" hint={v.simulate_outage.length ? `⚠ outage simulated: ${v.simulate_outage.join(', ')}` : 'Simulate a data-source outage'}>
          <p className="mb-3 text-sm font-light text-ink-soft">Make a source hang so it times out — shows graceful degradation. Leave everything off for a normal run.</p>
          <div className="flex flex-wrap gap-3">
            {(['aa', 'telecom', 'business'] as Group[]).map((g) => {
              const on = v.simulate_outage.includes(g)
              return (
                <button key={g} type="button" disabled={disabled} aria-pressed={on}
                  onClick={() => set('simulate_outage', on ? v.simulate_outage.filter((x) => x !== g) : [...v.simulate_outage, g])}
                  className={`rounded-full px-4 py-2 text-sm transition ${on ? 'bg-warn-soft font-medium text-warn ring-1 ring-warn/40' : 'bg-ink/5 text-ink-soft hover:bg-ink/10'}`}>
                  {on ? '⚠ ' : ''}{{ aa: 'Bank (AA)', telecom: 'Telecom', business: 'Business' }[g]}
                </button>
              )
            })}
          </div>
        </Section>
      </div>
    </form>
  )
}
