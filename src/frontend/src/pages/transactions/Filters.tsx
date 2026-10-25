import { FileText, Hand, Link, Plug, SlidersHorizontal, X } from 'lucide-react'
import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { CoinIcon } from '../../components/CoinIcon'
import { SourceAvatar, SourceLogo, WalletLogo } from '../../components/SourceLogo'
import { Button, Segmented } from '../../components/ui'
import { Combobox, type ComboOption } from '../../components/ui/Combobox'
import { SearchField } from '../../components/ui/SearchField'
import { api, type CoinOption, type MergedSummary, type Source, type Wallet } from '../../lib/api'
import { KINDS, NO_FILTER, type TxFilter } from '../../lib/txFilter'
import { KindIcon } from './KindIcon'

const select = 'rounded-ctl border border-line bg-surface-2 px-3 py-2 text-sm text-fg'

const INCOMES = ['staking', 'reward', 'interest', 'airdrop'] as const
const ORIGINS = [['api', Plug], ['file', FileText], ['chain', Link], ['manual', Hand]] as const
const NOTICES = ['normal', 'clean', 'short', 'auto', 'card', 'open', 'ambiguous', 'dust', 'marked', 'edited', 'noted', 'mcp', 'spam'] as const
const NOTICE_COUNT: Partial<Record<string, (s: MergedSummary) => number>> = {
  open: (s) => s.open + s.ambiguous, ambiguous: (s) => s.ambiguous, dust: (s) => s.dust, spam: (s) => s.spam,
  edited: (s) => s.edited, noted: (s) => s.noted, marked: (s) => s.marked, short: (s) => s.short, auto: (s) => s.auto, card: (s) => s.card,
}

export type Facets = { assets: string[]; kinds: string[]; sources: number[] }

export function Filters({ value, onChange, sources, wallets, merged, extra, phoneExtra, summary, facets }: {
  value: TxFilter; onChange: (f: TxFilter) => void; sources: Source[]; wallets: Wallet[]; merged: boolean; extra?: ReactNode
  /** only in the phone's button row (the PC has it elsewhere) */
  phoneExtra?: ReactNode
  /** what the other filters leave: the rest is shown dimmed (Vanixxx, 2026-10-08) */
  facets?: Facets | null
  summary?: MergedSummary | null
}) {
  const { t } = useTranslation()
  const set = (patch: Partial<TxFilter>) => onChange({ ...value, ...patch })
  // free search (coin, transaction ID, comment, note): asks the server once typing pauses
  const [text, setText] = useState(value.q)
  const [lastQ, setLastQ] = useState(value.q)
  if (value.q !== lastQ) { setLastQ(value.q); setText(value.q) }
  useEffect(() => {
    if (text === value.q) return
    const id = window.setTimeout(() => onChange({ ...value, q: text }), 350)
    return () => window.clearTimeout(id)
  }, [text, value, onChange])
  // every coin of the valid rows, chosen from a list with search (no free text)
  const [coins, setCoins] = useState<CoinOption[]>([])
  useEffect(() => void api.mergedAssets().then(setCoins, () => {}), [])
  const left = useMemo(() => facets && {
    assets: new Set(facets.assets), kinds: new Set(facets.kinds), sources: new Set(facets.sources),
  }, [facets])
  const coinOptions: ComboOption[] = useMemo(() => coins.map((c) => ({
    value: c.asset, label: c.asset, hint: c.name ?? undefined, icon: <CoinIcon asset={c.icon} size={18} />,
    dim: !!left && !left.assets.has(c.asset),
  })), [coins, left])
  const count = (Object.keys(NO_FILTER) as (keyof TxFilter)[]).filter((k) => value[k] !== NO_FILTER[k]).length
  const active = count > 0
  // phone: the filters fold away behind one button (ADR 0013); wider screens show them
  const [shown, setShown] = useState(false)
  // kinds with their icon and a search, several at once (Vanixxx, 2026-10-07)
  // each kind of income on its own, right after "income" (Vanixxx, 2026-10-08)
  const kindOptions: ComboOption[] = useMemo(() => (merged ? ['transfer', ...KINDS] : KINDS).flatMap((k) => [
    { value: k, label: k === 'transfer' ? t('merged.transfer') : t(`kinds.${k}`), icon: <KindIcon kind={k} small />, dim: !!left && !left.kinds.has(k) },
    ...(k === 'income' ? INCOMES.map((x) => ({
      value: `income:${x}`, label: `${t('kinds.income')} · ${t(`manual.income.${x}`)}`, icon: <KindIcon kind={`income:${x}`} small />,
      dim: !!left && !left.kinds.has(`income:${x}`),
    })) : []),
  ]), [merged, t, left])
  const originOptions: ComboOption[] = useMemo(() => ORIGINS.map(([v, Icon]) => ({
    value: v, label: t(`pages.sources.channels.${v}`), icon: <Icon size={15} aria-hidden="true" className="text-muted" />,
  })), [t])
  const exchanges = sources.filter((s) => s.kind === 'exchange')
  const sourceOptions: ComboOption[] = useMemo(() => [
    ...exchanges.map((s) => ({ value: `s:${s.id}`, label: s.label, group: t('pages.sources.exchanges'), icon: <SourceLogo source={s} size={18} />, dim: !!left && !left.sources.has(s.id) })),
    ...wallets.flatMap((w) => {
      const networks = sources.filter((s) => s.wallet_id === w.id)
      return networks.length === 0 ? [] : [
        { value: `w:${w.id}`, label: t('pages.transactions.allNetworks', { wallet: w.name }), group: w.name, icon: <WalletLogo name={w.name} id={w.id} size={18} />,
          dim: !!left && !networks.some((s) => left.sources.has(s.id)) },
        ...networks.map((s) => ({ value: `s:${s.id}`, label: `${w.name} – ${s.label}`, group: w.name, icon: <SourceAvatar source={s} wallet={w} size={18} />, dim: !!left && !left.sources.has(s.id) })),
      ]
    }),
  ], [exchanges, wallets, sources, t, left])

  return (
    <>
    {/* phone: the pick button sits next to the folded filters, on wider screens next to "reset" */}
    <div className="flex flex-wrap items-center gap-2 md:hidden">
      <Button variant="ghost" aria-expanded={shown} onClick={() => setShown(!shown)}>
        <SlidersHorizontal size={15} aria-hidden="true" />{t('pages.transactions.filters')}{active && ` (${count})`}
      </Button>
      {extra}
      {phoneExtra}
    </div>
    {/* phone: two columns, the source over the full width; wider screens: one wrapping row */}
    <div className={`${shown ? 'grid' : 'hidden'} relative grid-cols-2 items-center gap-2 md:flex md:flex-wrap`}>
      {merged && <SearchField value={text} onChange={setText} placeholder={t('pages.transactions.search')} className="col-span-2 md:w-72" />}
      <Combobox label={t('pages.transactions.source')} allLabel={t('pages.transactions.allSources')} value={value.source}
        onChange={(source) => set({ source })} options={sourceOptions} className="col-span-2 md:w-64" multiple />
      <Combobox multiple label={t('pages.transactions.kind')} allLabel={t('pages.transactions.allKinds')} value={value.kind}
        onChange={(kind) => set({ kind })} options={kindOptions} className="min-w-0 md:w-48" />
      {merged && (
        // notices: what wants a look — no counterpart, dust, edited, with a note … (Vanixxx, 2026-10-06)
        <select aria-label={t('merged.filter')} value={value.show} onChange={(e) => set({ show: e.target.value })} className={`${select} min-w-0`}>
          {NOTICES.map((n) => {
            const count = summary ? NOTICE_COUNT[n]?.(summary) : undefined
            return <option key={n} value={n}>{t(`merged.filters.${n}`)}{count !== undefined ? ` (${count})` : ''}</option>
          })}
        </select>
      )}
      {merged && (
        // where lines came from: API, file, chain, by hand (Vanixxx, 2026-10-09)
        <Combobox multiple label={t('merged.details.channel')} allLabel={t('pages.transactions.allOrigins')} value={value.origin}
          onChange={(origin) => set({ origin })} options={originOptions} className="min-w-0 md:w-44" />
      )}
      <Combobox label={t('pages.transactions.asset')} allLabel={t('pages.transactions.allCoins')} value={value.asset}
        onChange={(asset) => set({ asset })} options={coinOptions} className="md:w-44" multiple />
      <label className="flex min-w-0 items-center gap-1.5 text-sm text-muted">
        {t('pages.transactions.from')}
        <input type="date" value={value.from} max={value.to || undefined} onChange={(e) => set({ from: e.target.value })} className={`${select} min-w-0 flex-1 px-2`} />
      </label>
      <label className="flex min-w-0 items-center gap-1.5 text-sm text-muted">
        {t('pages.transactions.to')}
        <input type="date" value={value.to} min={value.from || undefined} onChange={(e) => set({ to: e.target.value })} className={`${select} min-w-0 flex-1 px-2`} />
      </label>
      <div className="col-span-2 flex flex-wrap items-center gap-2">
      <Segmented label={t('pages.transactions.allMarkets')} value={value.market} onChange={(market) => set({ market })}
        options={[
          { value: '', label: t('pages.transactions.allMarkets') },
          { value: 'spot', label: t('pages.transactions.spot') },
          { value: 'futures', label: t('pages.transactions.futures') },
        ]} />
      {active && (
        <Button variant="ghost" onClick={() => onChange(NO_FILTER)}>
          <X size={14} aria-hidden="true" />{t('pages.transactions.resetFilters')}
        </Button>
      )}
      <span className="hidden md:contents">{extra}</span>
      </div>
    </div>
    </>
  )
}
