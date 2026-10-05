import QRCode from 'qrcode'
import { useEffect, useState } from 'react'

/** QR of the consent URL so a real phone can open it. */
export default function QrCode({ url }: { url: string }) {
  const [src, setSrc] = useState<string | null>(null)
  useEffect(() => {
    let alive = true
    QRCode.toDataURL(url, { margin: 1, width: 168, color: { dark: '#19152b', light: '#ffffff' } }).then((d) => alive && setSrc(d)).catch(() => alive && setSrc(null))
    return () => { alive = false }
  }, [url])
  if (!src) return null
  return (
    <div className="mt-3 flex items-center gap-4">
      <img src={src} alt="QR code of the consent link" className="h-[92px] w-[92px] rounded-xl bg-white p-1.5" />
      <p className="text-xs leading-relaxed text-ink-soft">Scan with a real phone to give consent there, or <a href={url} target="_blank" rel="noreferrer" className="font-medium text-lav-700 underline">open it in a new tab ↗</a>
        {/localhost|127\.0\.0\.1/.test(url) && <><br /><span className="text-warn">This is a localhost URL — set PUBLIC_BASE_URL to your tunnel so a phone can reach it.</span></>}</p>
    </div>
  )
}
