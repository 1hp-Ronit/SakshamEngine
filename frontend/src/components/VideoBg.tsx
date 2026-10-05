import { useEffect, useRef, type ReactNode } from 'react'

export const HERO_VIDEO_SRC = '/brand/hero-bg.mp4'
export const HERO_POSTER_SRC = '/brand/hero-poster.jpg'

/** Looping muted video background (public/brand/hero-bg.mp4). Content on top is white; a soft scrim keeps text legible.
 *  Respects "reduce motion" (shows the poster frame instead) and falls back to the poster if autoplay is blocked. */
/** `startAt` offsets playback so several video cards on one page don't look like identical copies. */
export default function VideoBg({ className = '', children, scrim = true, startAt = 0 }: { className?: string; children?: ReactNode; scrim?: boolean; startAt?: number }) {
  const ref = useRef<HTMLVideoElement>(null)
  useEffect(() => {
    const v = ref.current
    if (!v) return
    const seek = () => { if (startAt && v.duration) v.currentTime = startAt % v.duration }
    if (v.readyState >= 1) seek(); else v.addEventListener('loadedmetadata', seek, { once: true })
    if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) { v.pause(); return }
    v.play().catch(() => undefined)
  }, [startAt])
  return (
    <div className={`relative isolate overflow-hidden bg-[#06201d] text-white ring-1 ring-white/10 ${className}`}>
      <video ref={ref} autoPlay loop muted playsInline preload="auto" poster={HERO_POSTER_SRC} aria-hidden className="pointer-events-none absolute inset-0 -z-10 h-full w-full object-cover">
        <source src={HERO_VIDEO_SRC} type="video/mp4" />
      </video>
      {scrim && <div className="pointer-events-none absolute inset-0 -z-10 bg-gradient-to-b from-black/25 via-transparent to-black/35" />}
      {children}
    </div>
  )
}
