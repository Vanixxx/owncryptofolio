import {
  ArrowDownLeft, ArrowLeftRight, ArrowRight, ArrowUpRight, CandlestickChart, CircleHelp, Gift, Landmark,
  Award, Coins, Percent, PiggyBank, Receipt, RefreshCw, Repeat, Sprout, TrendingUp, type LucideIcon,
} from 'lucide-react'
import { cx } from '../../lib/cx'

const ICONS: Record<string, [LucideIcon, 'up' | 'down' | 'accent' | 'muted']> = {
  trade: [ArrowLeftRight, 'accent'],
  send: [ArrowUpRight, 'down'],
  receive: [ArrowDownLeft, 'up'],
  transfer: [ArrowRight, 'accent'],
  income: [Gift, 'up'],
  fiat_deposit: [Landmark, 'up'],
  fiat_withdrawal: [Landmark, 'down'],
  internal_transfer: [Repeat, 'muted'],
  migration: [RefreshCw, 'muted'],
  fee: [Receipt, 'down'],
  realized_pnl: [TrendingUp, 'accent'],
  funding: [Percent, 'muted'],
  futures_position: [CandlestickChart, 'muted'],
  other: [CircleHelp, 'muted'],
  // the kinds of income, each its own (Vanixxx, 2026-10-08): "income:staking" and so on
  'income:staking': [Sprout, 'up'],
  'income:reward': [Award, 'up'],
  'income:interest': [PiggyBank, 'up'],
  'income:airdrop': [Gift, 'up'],
  'income:': [Coins, 'up'],
}


const TONE = {
  up: 'bg-up/12 text-up', down: 'bg-down/12 text-down', accent: 'bg-accent/12 text-accent', muted: 'bg-surface-2 text-muted',
}

/** The kind at a glance: a tinted round chip, the same colours as the amounts. */
export function KindIcon({ kind, className, small = false }: { kind: string; className?: string; small?: boolean }) {
  const [Icon, tone] = ICONS[kind] ?? ICONS.other
  return (
    <span aria-hidden="true" className={cx('inline-grid shrink-0 place-items-center rounded-full', small ? 'h-[18px] w-[18px]' : 'h-8 w-8', TONE[tone], className)}>
      <Icon size={small ? 11 : 16} strokeWidth={2.2} />
    </span>
  )
}
