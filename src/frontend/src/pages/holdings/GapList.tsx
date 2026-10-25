import { ArrowRight } from 'lucide-react'
import { useEffect, useId, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import { CoinIcon } from '../../components/CoinIcon'
import { Card, ErrorText } from '../../components/ui'
import { api, type Gap } from '../../lib/api'
import { date, money, quantity } from '../../lib/format'
import { useErrorText } from '../../lib/useErrorText'

/** Where data is missing (ADR 0040): a place whose computed holding runs below zero, from
 * when; or a balance that differs. Sorted by what is missing, in money. */
export function GapList({ name, tz, currency }: { name: (id: number) => string; tz: string; currency: string }) {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const [gaps, setGaps] = useState<Gap[] | null>(null)
  const [error, setError] = useState<unknown>(null)
  useEffect(() => void api.portfolioGaps().then(setGaps, setError), [])

  return (
    <>
      <p className="m-0 text-sm leading-relaxed text-muted">{t('holdings.gaps.intro')}</p>
      <ErrorText>{error ? errorText(error) : null}</ErrorText>
      {gaps === null ? (
        <p className="text-sm text-muted">{t('common.loading')}</p>
      ) : gaps.length === 0 ? (
        <Card><p className="m-0 text-sm text-up">{t('holdings.gaps.none')}</p></Card>
      ) : (
        <ul className="m-0 grid list-none gap-2 p-0">
          {gaps.map((g) => {
            const to = g.from ? g.from.slice(0, 10) : undefined
            const link = `/transactions?${new URLSearchParams({ source: `s:${g.source_id}`, asset: g.asset, ...(to ? { to } : {}) })}`
            return (
              <li key={`${g.source_id}${g.market}${g.asset}`} className="card grid gap-2 p-3">
                <div className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-3">
                  <CoinIcon asset={g.icon} size={28} />
                  <span className="grid min-w-0">
                    <b className="truncate text-sm">{g.asset} · {name(g.source_id)}{g.market === 'futures' && ' · Futures'}</b>
                    <span className="text-xs text-muted">
                      {g.type === 'negative'
                        ? t('holdings.gaps.from', { date: date(g.from ?? null, tz) })
                        : t('holdings.gaps.balance')}
                    </span>
                  </span>
                  {g.missing_value && <span className="num text-sm text-warn">{money(g.missing_value, currency)}</span>}
                </div>
                {g.points.length > 1 && <GapChart points={g.points} />}
                <p className="m-0 text-xs leading-relaxed text-muted">
                  {g.type === 'negative'
                    ? t('holdings.gaps.negativeText', { lowest: quantity(g.lowest ?? '0'), asset: g.asset, now: quantity(g.now ?? '0') })
                    : t('holdings.gaps.balanceText', { computed: quantity(g.computed ?? '0'), actual: quantity(g.actual ?? '0'), asset: g.asset })}
                </p>
                <Link to={link} className="inline-flex items-center gap-1 justify-self-start text-xs text-accent no-underline">
                  {t('holdings.gaps.toTransactions')}<ArrowRight size={13} aria-hidden="true" />
                </Link>
              </li>
            )
          })}
        </ul>
      )}
    </>
  )
}

/** The computed holding over time as steps, with the zero line; below zero is filled red:
 * that is the missing part. Plain SVG, it is a thumbnail. */
function GapChart({ points, height = 56 }: { points: [string, string][]; height?: number }) {
  const width = 320
  const xs = points.map(([at]) => new Date(at).getTime())
  const ys = points.map(([, q]) => Number(q))
  const x0 = xs[0], x1 = xs[xs.length - 1] || x0 + 1
  const lo = Math.min(0, ...ys), hi = Math.max(0, ...ys), span = hi - lo || 1
  const x = (v: number) => ((v - x0) / (x1 - x0 || 1)) * width
  const y = (v: number) => height - 3 - ((v - lo) / span) * (height - 6)
  let d = `M ${x(xs[0])} ${y(ys[0])}`
  for (let i = 1; i < xs.length; i++) d += ` H ${x(xs[i])} V ${y(ys[i])}`
  d += ` H ${width}`
  const zero = y(0)
  const clip = useId()
  return (
    <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" className="h-14 w-full" aria-hidden="true">
      <defs>
        <clipPath id={clip}><rect x="0" y={zero} width={width} height={height - zero} /></clipPath>
      </defs>
      <path d={`${d} V ${zero} H 0 Z`} fill="var(--down)" opacity="0.22" clipPath={`url(#${clip})`} />
      <line x1="0" x2={width} y1={zero} y2={zero} stroke="var(--line)" strokeDasharray="3 3" vectorEffect="non-scaling-stroke" />
      <path d={d} fill="none" stroke="var(--accent)" strokeWidth="1.6" vectorEffect="non-scaling-stroke" />
    </svg>
  )
}
