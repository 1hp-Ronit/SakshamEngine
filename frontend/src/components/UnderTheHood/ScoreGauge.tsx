import { useEffect, useState } from 'react'

const R = 100
const LEN = Math.PI * R
const frac = (s: number, min: number, max: number) => Math.min(1, Math.max(0, (s - min) / (max - min)))
const pt = (f: number, r = R) => { const a = Math.PI * (1 - f); return [120 + r * Math.cos(a), 124 - r * Math.sin(a)] as const }

function useCountUp(target: number | null, ms = 1100) {
  const [v, setV] = useState(0)
  useEffect(() => {
    if (target == null) { setV(0); return }
    let raf = 0
    const t0 = performance.now()
    const tick = (t: number) => {
      const p = Math.min(1, (t - t0) / ms)
      setV(target * (1 - Math.pow(1 - p, 3)))
      if (p < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [target, ms])
  return v
}

/** 300–900 semicircular gauge with the approval cutoff (and borderline floor) marked. Designed for the lavender tile. */
export default function ScoreGauge({ score, cutoff, floor, min = 300, max = 900, onDark = false }: { score: number | null; cutoff: number; floor?: number | null; min?: number; max?: number; onDark?: boolean }) {
  const ink = onDark ? '#ffffff' : '#0f2623', soft = onDark ? 'rgba(255,255,255,0.65)' : '#566b66', track = onDark ? 'rgba(255,255,255,0.16)' : 'rgba(15,38,35,0.10)'
  const [shown, setShown] = useState<number | null>(null)
  useEffect(() => { const t = setTimeout(() => setShown(score), 80); return () => clearTimeout(t) }, [score])
  const display = useCountUp(shown, 1100)
  const f = shown == null ? 0 : frac(shown, min, max)
  const color = score == null ? (onDark ? 'rgba(255,255,255,0.3)' : 'rgba(15,38,35,0.25)') : score >= cutoff ? (onDark ? '#5fe0b4' : '#2a9372') : (onDark ? '#f5b85c' : '#c9831a')
  const [cx1, cy1] = pt(frac(cutoff, min, max), R - 14), [cx2, cy2] = pt(frac(cutoff, min, max), R + 12), [lx, ly] = pt(frac(cutoff, min, max), R + 24)
  const arc = `M ${120 - R} 124 A ${R} ${R} 0 0 1 ${120 + R} 124`
  return (
    <figure className="mx-auto w-full max-w-[290px]" aria-label={score == null ? 'Score pending' : `Score ${Math.round(score)} out of 900, cutoff ${cutoff}`}>
      <svg viewBox="0 0 240 150" className="w-full overflow-visible">
        <path d={arc} fill="none" stroke={track} strokeWidth="14" strokeLinecap="round" />
        {floor != null && <path d={arc} fill="none" stroke="rgba(201,131,26,0.25)" strokeWidth="14" strokeDasharray={`${LEN * (frac(cutoff, min, max) - frac(floor, min, max))} ${LEN}`} strokeDashoffset={-LEN * frac(floor, min, max)} />}
        <path d={arc} fill="none" stroke={color} strokeWidth="14" strokeLinecap="round" strokeDasharray={`${LEN * f} ${LEN}`}
          style={{ transition: 'stroke-dasharray 1.1s cubic-bezier(.2,.8,.2,1), stroke .4s' }} />
        <line x1={cx1} y1={cy1} x2={cx2} y2={cy2} stroke={ink} strokeWidth="2" />
        <text x={lx} y={ly} textAnchor="middle" fontSize="9" fill={ink}>{cutoff}</text>
        <text x={120 - R} y="144" textAnchor="middle" fontSize="9" fill={soft}>{min}</text>
        <text x={120 + R} y="144" textAnchor="middle" fontSize="9" fill={soft}>{max}</text>
        <text x="120" y="108" textAnchor="middle" fontSize="46" fontWeight="300" fill={score == null ? soft : ink} style={{ fontVariantNumeric: 'tabular-nums' }}>
          {score == null ? '—' : Math.round(display)}
        </text>
        <text x="120" y="127" textAnchor="middle" fontSize="10" fill={soft}>{score == null ? 'awaiting score' : score >= cutoff ? 'above cutoff' : floor != null && score >= floor ? 'borderline' : 'below cutoff'}</text>
      </svg>
    </figure>
  )
}
