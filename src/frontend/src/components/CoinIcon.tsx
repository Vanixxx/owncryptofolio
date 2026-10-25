import { useState, type SyntheticEvent } from 'react'
import { cx } from '../lib/cx'
import { useLogoUrl } from '../lib/logos'

const dark = new Map<string, boolean>()

/** True for a logo that is mostly dark (FET, some tokens): it would vanish on a dark card.
 * Measured once per symbol on a tiny canvas; the SVGs are same-origin, so it is allowed. */
function isDark(img: HTMLImageElement): boolean {
  try {
    const c = document.createElement('canvas')
    c.width = c.height = 16
    const ctx = c.getContext('2d', { willReadFrequently: true })
    if (!ctx) return false
    ctx.drawImage(img, 0, 0, 16, 16)
    const px = ctx.getImageData(0, 0, 16, 16).data
    let sum = 0, n = 0
    for (let i = 0; i < px.length; i += 4) {
      if (px[i + 3] < 128) continue
      sum += 0.2126 * px[i] + 0.7152 * px[i + 1] + 0.0722 * px[i + 2]
      n++
    }
    return n > 0 && sum / n < 60
  } catch {
    return false
  }
}

/** The coin's real symbol from public/coins (generated from free icon packages, offline).
 * Unknown coins get a badge with their first letters instead of a broken image. A dark
 * logo gets a light disc behind it in dark mode (`.coin-dark`). */
export function CoinIcon({ asset, size = 28, className }: { asset: string; size?: number; className?: string }) {
  const clean = asset.replace(/[^A-Z0-9]/gi, '').toUpperCase()
  // a failure belongs to that symbol: while typing "E…" → "EUR" the field's icon must not stay
  // the grey badge of "E" (Vanixxx, 2026-10-09)
  const [failedFor, setFailedFor] = useState<string | null>(null)
  const failed = failedFor === clean
  const [isDarkLogo, setDark] = useState(() => dark.get(clean) ?? false)
  const own = useLogoUrl('coin', clean || null)
  if (own) return <img src={own} alt="" width={size} height={size} className={cx('shrink-0 rounded-full object-cover', className)} />
  if (failed || !clean || clean.length > 12) {
    return (
      <span aria-hidden="true" style={{ width: size, height: size, fontSize: size * 0.34 }}
        className={cx('inline-grid shrink-0 place-items-center rounded-full bg-surface-2 font-semibold text-muted ring-1 ring-line', className)}>
        {(clean || '?').slice(0, 3)}
      </span>
    )
  }
  const loaded = (e: SyntheticEvent<HTMLImageElement>) => {
    if (!dark.has(clean)) dark.set(clean, isDark(e.currentTarget))
    setDark(dark.get(clean) ?? false)
  }
  return (
    <img src={`/coins/${clean}.svg`} alt="" width={size} height={size} loading="lazy" onError={() => setFailedFor(clean)} onLoad={loaded}
      className={cx('shrink-0 rounded-full', isDarkLogo && 'coin-dark', className)} />
  )
}
