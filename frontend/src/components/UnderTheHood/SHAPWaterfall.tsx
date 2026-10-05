import { Bar, BarChart, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { WaterfallItem } from '../../api/types'

/** Contributions in SCORE POINTS: green pushes the score up, amber pulls it down. base + Σ = final. */
export default function SHAPWaterfall({ items, base, final }: { items: WaterfallItem[]; base: number | null; final: number | null }) {
  if (!items.length) return null
  const data = items.map((i) => ({ ...i, name: i.label.length > 26 ? i.label.slice(0, 25) + '…' : i.label }))
  const max = Math.max(...data.map((d) => Math.abs(d.points)), 10)
  const pad = max * 0.35
  return (
    <div>
      <div className="mb-2 flex items-center justify-between text-xs text-ink-soft">
        <span>Average applicant <b className="font-semibold tabular-nums text-ink">{base != null ? Math.round(base) : '—'}</b></span>
        <span>This applicant <b className="font-semibold tabular-nums text-ink">{final != null ? Math.round(final) : '—'}</b></span>
      </div>
      <div style={{ height: data.length * 32 + 12 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ top: 0, right: 8, bottom: 0, left: 0 }} barCategoryGap={6}>
            <XAxis type="number" hide domain={[-max - pad, max + pad]} />
            <YAxis type="category" dataKey="name" width={148} tick={{ fill: '#6e6782', fontSize: 11 }} axisLine={false} tickLine={false} />
            <Tooltip cursor={{ fill: 'rgba(25,21,43,0.04)' }} contentStyle={{ background: '#ffffff', border: '1px solid rgba(25,21,43,.12)', borderRadius: 12, fontSize: 12, color: '#19152b', boxShadow: '0 8px 24px -8px rgba(25,21,43,.25)' }}
              formatter={(v) => [`${Number(v) > 0 ? '+' : ''}${Number(v).toFixed(1)} points`, 'Effect on score']} labelStyle={{ color: '#19152b' }} itemStyle={{ color: '#19152b' }} />
            <Bar dataKey="points" radius={6} isAnimationActive animationDuration={900}>
              {data.map((d) => <Cell key={d.feature} fill={d.points >= 0 ? '#3fd9a3' : '#f2b45a'} />)}
              <LabelList dataKey="points" content={(p) => {
                const { x = 0, y = 0, width = 0, height = 0, value = 0 } = p as { x?: number; y?: number; width?: number; height?: number; value?: number }
                const left = Math.min(x, x + width), right = Math.max(x, x + width), v = Number(value)
                return <text x={v >= 0 ? right + 5 : left - 5} y={y + height / 2 + 4} textAnchor={v >= 0 ? 'start' : 'end'} fontSize={11} fill="#19152b" style={{ fontVariantNumeric: 'tabular-nums' }}>{v > 0 ? '+' : ''}{v.toFixed(0)}</text>
              }} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
