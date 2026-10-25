import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { useSettings } from '../../app/settings'
import { CoinIcon } from '../../components/CoinIcon'
import { SourceAvatar } from '../../components/SourceLogo'
import type { MergedItem, MergedRow } from '../../lib/api'
import { cx } from '../../lib/cx'
import { amount, date, money, quantity, time } from '../../lib/format'
import { rateText, tradeRate } from '../../lib/rate'
import { iconKind, kindLabel } from '../../lib/rows'
import type { SourceRef } from '../../lib/txFilter'
import { KindIcon } from './KindIcon'

type Move = { sign: '+' | '−' | ''; qty: string | null; asset: string | null; value: string | null }
const NONE: Move = { sign: '', qty: null, asset: null, value: null }

/** What one row did with a coin: in, out, or nothing (the coin was only the fee). */
function move(r: MergedRow, asset: string): Move {
  if (r.incoming[0] === asset) return { sign: '+', qty: r.incoming[1], asset, value: r.values?.incoming ?? null }
  if (r.outgoing[0] === asset) return { sign: '−', qty: r.outgoing[1], asset, value: r.values?.outgoing ?? null }
  if (r.fee[0] === asset) return { sign: '−', qty: r.fee[1], asset, value: r.values?.fee ?? null }
  return NONE
}
const side = (r: MergedRow, k: 'incoming' | 'outgoing'): Move =>
  r[k][0] ? { sign: k === 'incoming' ? '+' : '−', qty: r[k][1], asset: r[k][0], value: r.values?.[k] ?? null } : NONE

type Data = {
  kind: string; futures: boolean; title: string; at: string; places: number[]
  /** the phone: one move with its worth (holdings, transfers, positions), else in and out */
  short: Move[]
  /** the PC: what went out and what came in, each with its worth */
  out: Move; in: Move
  /** the PC: rate, fee, funding — whatever the card shows on its right */
  extra: string[]; note: string | null
}

/** One short line per transaction (Vanixxx, 2026-10-22): kind, date and place, and what moved.
 * With a focus coin (holdings) the phone shows only that coin and its worth. The PC has the
 * room for more: time, the places with their logos, out and in with their worth, rate and fee. */
export function CompactLine({ item, focus, name, lookup, tz, onOpen }: {
  item: MergedItem; focus?: string; name: (id: number) => string; lookup: (id: number) => SourceRef; tz: string; onOpen: () => void
}) {
  const { t } = useTranslation()
  const currency = useSettings().settings['general.currency']
  const feeText = (r: MergedRow) => r.fee[0] && r.fee[1]
    ? `${t('pages.transactions.fee')} ${amount(r.fee[1], 6)} ${r.fee[0]}${r.values?.fee && r.fee[0] !== currency ? ` ≈ ${money(r.values.fee, currency)}` : ''}`
    : null
  let d: Data
  if (item.type === 'position') {
    // a futures position: what it brought in the end (Vanixxx, 2026-10-22)
    const down = item.result.startsWith('-')
    const result: Move = { sign: down ? '−' : '+', qty: item.result.replace('-', ''), asset: item.coin, value: item.result_value?.replace('-', '') ?? null }
    d = {
      kind: 'futures_position', futures: true, at: item.closed, places: [item.source_id],
      title: `${item.instrument}${item.side ? ` · ${t(`holdings.futures.${item.side}`)}` : ''}`,
      short: [result], out: down ? result : NONE, in: down ? NONE : result,
      extra: [t('holdings.futures.parts', { pnl: quantity(item.pnl), funding: quantity(item.funding), fees: quantity(item.fees) })],
      note: null,
    }
  } else if (item.type === 'transfer') {
    const s = item.send
    const sent: Move = { sign: '', qty: s.outgoing[1], asset: s.outgoing[0], value: s.values?.outgoing ?? null }
    d = {
      kind: 'transfer', futures: s.market === 'futures', title: t('merged.transfer'), at: item.at,
      places: [s.source_id, item.receive.source_id], short: [sent],
      out: side(s, 'outgoing'), in: side(item.receive, 'incoming'),
      extra: [feeText(s)].filter((x): x is string => !!x), note: s.note ?? item.receive.note ?? null,
    }
  } else {
    const r = item.row
    const rate = tradeRate(r.incoming, r.outgoing)
    d = {
      kind: iconKind(r), futures: r.market === 'futures', title: kindLabel(t, r), at: item.at, places: [r.source_id],
      short: focus ? [move(r, focus)] : [{ ...side(r, 'incoming'), value: null }, { ...side(r, 'outgoing'), value: null }],
      out: side(r, 'outgoing'), in: side(r, 'incoming'),
      extra: [rate && t('merged.rate', { base: rate.base, price: rateText(rate.price), quote: rate.quote }), feeText(r)]
        .filter((x): x is string => !!x),
      note: r.note ?? null,
    }
  }
  const icon = <KindIcon kind={d.kind} className={d.futures ? 'futures-icon' : undefined} />
  const shown = d.short.filter((m) => m.qty)
  return (
    <li>
      <button type="button" onClick={onOpen} aria-expanded={false}
        className="w-full border-0 bg-transparent px-2.5 py-2 text-left text-fg hover:bg-surface-2/40 lg:px-3">
        {/* the phone: kind, date · place, and what moved */}
        <span className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-2.5 lg:hidden">
          {icon}
          <span className="grid min-w-0">
            <span className="truncate text-sm font-semibold">{d.title}</span>
            <span className="truncate text-xs text-muted">{date(d.at, tz)} · {d.places.map(name).join(' → ')}</span>
          </span>
          <span className="grid max-w-[55vw] justify-items-end">
            {shown.map((m, n) => (
              <span key={n} className={cx('num truncate text-sm', m.sign === '+' && 'text-up', m.sign === '−' && 'text-down')}>
                {m.sign}{amount(m.qty, 6)}{(!focus || m.asset !== focus) && <span className="text-xs"> {m.asset}</span>}
              </span>
            ))}
            {shown.length === 1 && shown[0].value && <span className="num text-xs text-muted">≈ {money(shown[0].value, currency)}</span>}
          </span>
        </span>
        {/* the PC: one row of columns, like a table */}
        <span className="hidden items-center gap-3 lg:grid lg:grid-cols-[2rem_minmax(0,0.8fr)_5.5rem_minmax(0,1.1fr)_minmax(0,1.25fr)_minmax(0,1.25fr)_minmax(0,1.2fr)]">
          {icon}
          <span className="grid min-w-0">
            <span className="truncate text-sm font-semibold">{d.title}</span>
            {d.note && <span className="truncate text-xs text-muted" title={d.note}>{d.note}</span>}
          </span>
          <span className="grid text-sm">
            <span className="num">{date(d.at, tz)}</span>
            <span className="num text-xs text-muted">{time(d.at, tz)}</span>
          </span>
          <span className="grid min-w-0 gap-0.5 text-sm">
            {d.places.map((id, n) => (
              <span key={n} className="flex min-w-0 items-center gap-1.5">
                {n > 0 && <span className="text-muted" aria-hidden="true">→</span>}
                <SourceAvatar {...lookup(id)} size={16} />
                <span className="truncate">{name(id)}</span>
              </span>
            ))}
          </span>
          <Amount m={d.out} currency={currency} />
          <Amount m={d.in} currency={currency} />
          <span className="grid min-w-0 text-xs text-muted">
            {d.extra.map((x) => <span key={x} className="num truncate" title={x}>{x}</span>)}
          </span>
        </span>
      </button>
    </li>
  )
}

/** One side on the PC: the coin's logo, the amount, its worth below. */
function Amount({ m, currency }: { m: Move; currency: string }): ReactNode {
  if (!m.qty || !m.asset) return <span className="text-sm text-muted">—</span>
  return (
    <span className="flex min-w-0 items-center gap-2">
      <CoinIcon asset={m.asset} size={20} />
      <span className="grid min-w-0">
        <span className={cx('num truncate text-sm', m.sign === '+' && 'text-up', m.sign === '−' && 'text-down')}>
          {m.sign}{amount(m.qty, 6)} <span className="text-xs">{m.asset}</span>
        </span>
        {m.value && m.asset !== currency && <span className="num truncate text-xs text-muted">≈ {money(m.value, currency)}</span>}
      </span>
    </span>
  )
}
