import { ArrowRight } from 'lucide-react'
import type { ReactNode } from 'react'
import { useSettings } from '../../app/settings'
import { SourceAvatar } from '../../components/SourceLogo'
import { cx } from '../../lib/cx'
import { amount, date, money, quantity, time } from '../../lib/format'
import type { SourceRef } from '../../lib/txFilter'
import { KindIcon } from './KindIcon'
import { CoinIcon } from '../../components/CoinIcon'

/** One transaction line (Vanixxx, 2026-10-06). PC: date large on the left with the time and
 * the kind under it; the boxes in the middle starting at the date's height; fees, source
 * and notes on the right — a lower line. Phone: kind and date on top, boxes, details. */
export function TxShell({ at, tz, kind, title, badge, action, side, children, dim = false, below, lead, onPick, picked = false, onToggle, mark, futures = false }: {
  at: string; tz: string; kind: string; title: ReactNode; badge?: ReactNode; action: ReactNode; lead?: ReactNode
  /** a small mark up right ("edited"): phone header, PC details column */
  mark?: ReactNode
  /** a futures line: tinted card and a "Futures" label (Vanixxx, 2026-10-09) */
  futures?: boolean
  onPick?: () => void; picked?: boolean; onToggle?: () => void
  side: ReactNode; children: ReactNode; dim?: boolean; below?: ReactNode
}) {
  // a click on the card opens it like "⋯" (Vanixxx, 2026-10-06); while picking it picks.
  // Not from a control, not inside the opened part, not when text was selected.
  const target = onPick ?? onToggle
  const click = target ? (e: React.MouseEvent) => {
    const el = e.target as HTMLElement
    if (el.closest('button, a, input, select, textarea, label, [data-below], [data-menu]')) return
    if (window.getSelection()?.toString()) return
    target()
  } : undefined
  return (
    // picking: the whole card is the target — the box alone is too small on a phone
    <li className={cx('card relative grid gap-2 p-3 transition-colors focus-within:z-20', futures && 'futures-card', !!below && 'card-open', target && 'cursor-pointer md:hover:border-accent/50 md:hover:bg-surface-2/40',
      onPick && 'select-none', picked && 'ring-2 ring-accent')} onClick={click}>
      <div className={cx('grid gap-2.5 md:grid-cols-[10.5rem_minmax(0,1fr)_minmax(0,15rem)] md:items-start md:gap-5', dim && 'opacity-55')}>
        {/* phone header */}
        <div className="flex items-center justify-between gap-2 md:hidden">
          <span className="flex min-w-0 items-center gap-2.5">{lead}<KindIcon kind={kind} /><b className="truncate text-sm">{title}</b></span>
          <span className="flex shrink-0 items-center gap-1 text-xs text-muted">{date(at, tz)} {time(at, tz)}{mark}{action}</span>
        </div>
        {/* phone: the tags on a line of their own, the header stays readable */}
        {(futures || badge) && <div className="-mt-1 flex flex-wrap items-center gap-1.5 md:hidden">{futures && <FuturesTag />}{badge}</div>}
        {/* PC: date first */}
        <div className="hidden content-start gap-1 md:grid">
          <span className="flex items-center gap-2">{lead}<b className="num text-base leading-tight">{date(at, tz)}</b></span>
          <span className="num text-xs text-muted">{time(at, tz)}</span>
          <span className="mt-1 flex min-w-0 items-center gap-2"><KindIcon kind={kind} className="h-6 w-6" /><span className="truncate text-sm font-semibold">{title}</span></span>
          {(futures || badge) && <span className="flex flex-wrap items-center gap-1.5">{futures && <FuturesTag />}{badge}</span>}
        </div>
        <div className="min-w-0">{children}</div>
        <div className="flex min-w-0 items-start justify-between gap-2 text-xs text-muted">
          <div className="grid min-w-0 flex-1 gap-1">{mark && <span className="hidden md:inline">{mark}</span>}{side}</div>
          <span className="hidden md:block">{action}</span>
        </div>
      </div>
      {below && <div data-below className="grid gap-2 cursor-auto">{below}</div>}
    </li>
  )
}

type Box = { who?: SourceRef; fallback?: string; side: [string | null, string | null]; worth?: string | null; sign: string; tone: 'up' | 'down' | 'flat'; label?: string }

/** Amount boxes: one (a send, an income) or two with an arrow (transfer, trade). A box
 * shows the wallet or exchange where that matters, the amount (readable, exact on hover)
 * and its value at the time in the display currency. */
export function Flow({ from, to }: { from?: Box; to?: Box }) {
  if (from && to) {
    return (
      <div className="grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-stretch gap-2">
        <FlowBox {...from} />
        <span className="grid place-items-center text-muted"><ArrowRight size={18} aria-hidden="true" /></span>
        <FlowBox {...to} />
      </div>
    )
  }
  const one = from ?? to
  return one ? <div className="grid md:max-w-[50%]"><FlowBox {...one} /></div> : null
}

function FlowBox({ who, fallback, side: [asset, value], worth, sign, tone, label }: Box) {
  const currency = useSettings().settings['general.currency']
  const title = who ? who.wallet?.name ?? who.source?.label ?? fallback : null
  // "Ronin / Ronin" says nothing twice: the network line only when it adds something
  const sub = who?.wallet && who.source?.label !== who.wallet.name ? who.source?.label : null
  return (
    <div className="grid min-w-0 content-start gap-1 rounded-ctl bg-surface-2 p-2 md:p-2.5">
      {label && <span className="sr-only">{label}</span>}
      {who && (
        <span className="mb-0.5 flex min-w-0 items-center gap-2">
          <SourceAvatar source={who.source} wallet={who.wallet} size={26} />
          <span className="grid min-w-0 leading-tight">
            <b className="truncate text-sm">{title}</b>
            {sub && <span className="truncate text-xs text-muted">{sub}</span>}
          </span>
        </span>
      )}
      {/* the number large on its own line, coin and value small below: nothing wraps or
          spills on a phone (Vanixxx, 2026-10-06); the exact amount on hover */}
      <span className="grid grid-cols-[auto_minmax(0,1fr)] items-center gap-x-1.5 md:gap-x-2" title={value ? `${sign}${amount(value, 18)} ${asset}` : undefined}>
        <CoinIcon asset={asset ?? ''} size={30} className="row-span-2 h-7 w-7 md:h-[30px] md:w-[30px]" />
        <span className={cx('num truncate text-sm font-semibold leading-tight md:text-[0.95rem]', tone === 'up' ? 'text-up' : tone === 'down' ? 'text-down' : '')}>
          {value ? `${sign}${quantity(value)}` : ''}
        </span>
        <span className="num truncate text-xs text-muted">
          {asset}
          {/* an amount in the display currency is its own value (Vanixxx, 2026-10-08) */}
          {worth && asset !== currency && <> · {Math.abs(Number(worth)) < 0.005 ? `< ${money('0.01', currency)}` : `≈ ${money(worth, currency)}`}</>}
        </span>
      </span>
    </div>
  )
}

function FuturesTag() {
  return (
    <span className="shrink-0 rounded-full bg-[color-mix(in_srgb,#a855f7_18%,transparent)] px-2 py-0.5 text-[0.7rem] font-semibold uppercase tracking-wide text-[#c4a1ff]">
      Futures
    </span>
  )
}
