import { useEffect, useRef, useState } from 'react'
import { api } from '../../api/client'
import type { Ladder } from '../../api/types'
import { Badge, Spinner, inr } from '../ui'

const TIER_LABEL: Record<string, string> = { STARTER: 'Starter', GROWTH: 'Growth', ESTABLISHED: 'Established' }

export default function LadderVisual({ ladder, onChanged }: { ladder: Ladder; onChanged: () => void }) {
  const [view, setView] = useState<Ladder>(ladder)
  const [busy, setBusy] = useState(false)
  const [flash, setFlash] = useState<string | null>(null)
  const animating = useRef(false)
  useEffect(() => { if (!animating.current) setView(ladder) }, [ladder])

  const run = async (count: number, status: 'ON_TIME' | 'LATE' | 'MISSED') => {
    setBusy(true); animating.current = true
    try {
      const r = await api.simulateRepayments(ladder.loan_id, count, status)
      const tiers = Object.fromEntries(ladder.tiers.map((t) => [t.name, t]))
      for (const s of r.steps ?? []) {                      // step through each EMI so the bar visibly climbs
        setView((v) => ({ ...v, behaviour_score: s.behaviour_score, current_tier: s.tier, current_limit: Math.max(v.current_limit, tiers[s.tier]?.limits[v.product_sku] ?? 0) }))
        await new Promise((res) => setTimeout(res, 280))
      }
      setView(r)
      if (r.tier_changed) setFlash(`Tier unlocked: ${TIER_LABEL[r.current_tier] ?? r.current_tier}`)
      onChanged()
    } finally { animating.current = false; setBusy(false) }
  }
  useEffect(() => { if (!flash) return; const t = setTimeout(() => setFlash(null), 4000); return () => clearTimeout(t) }, [flash])

  const pct = (view.behaviour_score / view.max_score) * 100
  return (
    <div>
      <div className="flex items-end justify-between">
        <div><div className="text-xs text-ink-soft">Behaviour score</div><div className="text-5xl font-light tabular-nums tracking-tight">{view.behaviour_score}<span className="text-base text-ink-soft"> / {view.max_score}</span></div></div>
        <div className="text-right"><Badge tone="green">{TIER_LABEL[view.current_tier] ?? view.current_tier}</Badge><div className="mt-1.5 text-xs text-ink-soft">limit <b className="font-semibold text-ink">{inr(view.current_limit)}</b></div></div>
      </div>
      <div className="relative mt-6 h-3 rounded-full bg-ink/[0.07]">
        <div className="h-full rounded-full bg-gradient-to-r from-lav-300 to-ok transition-all duration-300" style={{ width: `${pct}%` }} />
        {view.tiers.filter((t) => t.min_behaviour_score > 0).map((t) => (
          <div key={t.name} className="absolute -top-1 h-5 w-px bg-ink/40" style={{ left: `${(t.min_behaviour_score / view.max_score) * 100}%` }}>
            <span className="absolute left-1/2 top-6 -translate-x-1/2 whitespace-nowrap text-[10px] text-ink-soft">{TIER_LABEL[t.name]} ≥{t.min_behaviour_score}</span>
          </div>
        ))}
      </div>
      <div className="mt-10 space-y-1 text-sm">
        {view.next_tier ? (<>
          <p>Next: <b className="font-semibold">{TIER_LABEL[view.next_tier]}</b> — {view.next_tier_requirement}</p>
          {view.next_tier_limits && <p className="text-ink-soft">Unlocks: {Object.entries(view.next_tier_limits).filter(([, v]) => v > 0).map(([k, v]) => `${k.replaceAll('_', ' ').toLowerCase()} ${inr(v)}`).join(' · ')}</p>}
        </>) : <p className="text-ok">Top tier reached.</p>}
      </div>
      {flash && <p className="mt-3 animate-[popIn_.3s_ease-out] rounded-2xl bg-ok-soft px-4 py-2.5 text-sm font-medium text-ok">{flash}</p>}
      <div className="mt-5 flex flex-wrap gap-2.5">
        <button disabled={busy} onClick={() => run(6, 'ON_TIME')} className="btn-dark">{busy && <Spinner />}Simulate 6 on-time EMIs</button>
        <button disabled={busy} onClick={() => run(1, 'LATE')} className="btn-ghost">1 late</button>
        <button disabled={busy} onClick={() => run(1, 'MISSED')} className="btn-ghost">1 missed</button>
      </div>
    </div>
  )
}
