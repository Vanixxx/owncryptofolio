import { Download, Lock } from 'lucide-react'
import { useEffect, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { useSettings } from '../../app/settings'
import { Button, Card, ErrorText, Row, Segmented, StatusPill } from '../../components/ui'
import { Toggle } from '../../components/ui/Toggle'
import { api, type TaxMethod, type TaxReport } from '../../lib/api'
import { cx } from '../../lib/cx'
import { date, dateTime, money, quantity, trend } from '../../lib/format'
import { useErrorText } from '../../lib/useErrorText'
import { Tabs } from '../transactions/parts'
import { TaxHistory } from './TaxHistory'
import { TaxFree } from './TaxFree'
import { TaxCarry } from './TaxCarry'

type Tab = 'disposals' | 'incomes' | 'futures' | 'losses' | 'open' | 'sources' | 'holdings' | 'yearEnd' | 'free' | 'forms'
const PAGE = 50

/** The tax report of a year (ADR 0042): § 23, § 22, § 20 and what is not counted, as Excel
 * and PDF, and kept on request so a later change shows. */
export function Tax() {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const { settings } = useSettings()
  const tz = settings['general.timezone']
  const [years, setYears] = useState<number[] | null>(null)
  const [year, setYear] = useState<number | null>(null)
  const [method, setMethod] = useState<TaxMethod>(settings['tax.method'])
  const [rep, setRep] = useState<{ key: string; data: TaxReport } | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [tab, setTab] = useState<Tab>('disposals')
  const [stamp, setStamp] = useState(0)

  useEffect(() => {
    api.taxYears().then((ys) => {
      setYears(ys)
      // the last finished year is the one to file
      const now = new Date().getFullYear()
      setYear(ys.find((y) => y < now) ?? ys[0] ?? null)
    }, setError)
  }, [])
  const key = `${year}-${method}-${stamp}`
  useEffect(() => {
    if (year === null) return
    let live = true
    api.taxReport(year, method).then(
      (data) => { if (live) { setRep({ key: `${year}-${method}-${stamp}`, data }); setError(null) } },
      (e) => { if (live) setError(e) },  // an old year's error is not the new year's
    )
    return () => { live = false }
  }, [year, method, stamp])
  // keeping asks for an optional word first ("an den Steuerberater")
  const [note, setNote] = useState<string | null>(null)
  const freeze = () => year !== null && api.taxFreeze(year, method, note ?? '').then(() => { setNote(null); setStamp((s) => s + 1) }, setError)

  if (years !== null && years.length === 0) return <p className="m-0 text-sm text-muted">{t('tax.none')}</p>
  const r = rep?.key === key ? rep.data : null
  const s = r?.summary

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2 text-sm">
          <span className="label">{t('tax.year')}</span>
          <select value={year ?? ''} onChange={(e) => setYear(Number(e.target.value))}
            className="rounded-ctl border border-line bg-surface-2 px-3 py-2 text-base text-fg">
            {(years ?? []).map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
        </label>
        <Segmented label={t('tax.method')} value={method} onChange={setMethod}
          options={[{ value: 'fifo', label: 'FIFO' }, { value: 'lifo', label: 'LIFO' }]} />
        {year !== null && (
          <span className="flex flex-wrap gap-2">
            {(['xlsx', 'pdf'] as const).map((k) => (
              <a key={k} href={api.taxFile(year, method, k)} download
                className="inline-flex items-center gap-1.5 rounded-ctl border border-line px-3 py-2 text-sm text-fg no-underline hover:bg-surface-2">
                <Download size={15} aria-hidden="true" />{t(`tax.file.${k}`)}
              </a>
            ))}
            <Button variant="ghost" onClick={() => setNote(note === null ? '' : null)} disabled={!r} aria-expanded={note !== null}>
              <Lock size={15} aria-hidden="true" className="mr-1.5 inline" />{t('tax.freeze')}
            </Button>
          </span>
        )}
      </div>
      {note !== null && (
        <form className="card flex flex-wrap items-end gap-2 p-3" onSubmit={(e) => { e.preventDefault(); void freeze() }}>
          <label className="grid min-w-0 flex-1 gap-1.5 text-sm">
            <span className="label">{t('tax.freezeNote')}</span>
            <input value={note} maxLength={200} autoFocus onChange={(e) => setNote(e.target.value)} placeholder={t('tax.freezeNoteHint')}
              className="rounded-ctl border border-line bg-surface-2 px-3 py-2 text-base text-fg" />
          </label>
          <Button type="submit">{t('tax.freezeNow', { year, method: method.toUpperCase() })}</Button>
        </form>
      )}
      <p className="m-0 text-xs leading-relaxed text-muted">{t('tax.note')}</p>
      <ErrorText>{error ? errorText(error) : null}</ErrorText>
      {!r || !s ? <p className="m-0 text-sm text-muted">{t('common.loading')}</p> : (
        <>
          <div className="grid gap-4 md:grid-cols-2">
            <Card title={t('tax.s23.title')}>
              <Big value={s.s23.net} label={t('tax.net')} />
              <div className="grid gap-1.5 text-sm">
                <Row label={t('tax.gains')}><Eur v={s.s23.gains} /></Row>
                <Row label={t('tax.losses')}><Eur v={s.s23.losses} /></Row>
                <Row label={t('tax.limit')}><Eur v={s.s23.limit} plain /></Row>
                <Row label={t('tax.s23.free')}><Eur v={s.s23.tax_free_gain} /></Row>
              </div>
              <Limit taxable={s.s23.taxable} share={s.s23.share} />
              <p className="m-0 text-xs text-muted">{t('tax.s23.count', { count: s.s23.count, taxed: s.s23.count_taxed })}</p>
            </Card>
            {year !== null && s.carry && (
              <TaxCarry year={year} rows={s.carry.rows} opening={s.carry.opening} onChanged={() => setStamp((x) => x + 1)} />
            )}
            <Card title={t('tax.s22.title')}>
              <Big value={s.s22.total} label={t('tax.sum')} />
              <div className="grid gap-1.5 text-sm">
                <Row label={t('tax.limit')}><Eur v={s.s22.limit} plain /></Row>
                {Object.entries(s.s22.by_kind ?? {}).map(([k, v]) => (
                  <Row key={k} label={t('tax.s22.of', { kind: t(`tax.income.${k}`, { defaultValue: k }) })}><Eur v={v} plain /></Row>
                ))}
                <Row label={t('tax.s22.count')}><span className="num">{s.s22.count}</span></Row>
              </div>
              <Limit taxable={s.s22.taxable} share={s.s22.share} />
            </Card>
            <Card title={t('tax.s20.title')}>
              <Big value={s.s20.net} label={t('tax.net')} />
              <div className="grid gap-1.5 text-sm">
                <Row label={t('tax.gains')}><Eur v={s.s20.gains} /></Row>
                <Row label={t('tax.losses')}><Eur v={s.s20.losses} /></Row>
                <Row label={t('tax.s20.fundingIn')}><Eur v={s.s20.funding_in} /></Row>
                <Row label={t('tax.s20.fundingOut')}><Eur v={s.s20.funding_out} /></Row>
                <Row label={t('tax.s20.fees')}><Eur v={s.s20.fees} /></Row>
                {s.s20.bonus !== undefined && <Row label={t('tax.s20.bonus')}><Eur v={s.s20.bonus} /></Row>}
              </div>
              <p className="m-0 text-xs text-muted">{t('tax.s20.hint')}</p>
            </Card>
            <Card title={t('tax.lost.title')} className={s.carry ? 'md:col-span-2' : undefined}>
              <Big value={s.lost.cost === '0.00' ? '0.00' : `-${s.lost.cost}`} label={t('tax.lost.cost')} />
              <p className="m-0 text-xs leading-relaxed text-muted">{t('tax.lost.hint', { count: s.lost.count })}</p>
              {(s.open.uncovered + s.open.open_sends > 0 || s.s23.estimated > 0) && (
                <p className="m-0 text-xs text-warn">
                  {t('tax.openHint', { count: s.open.uncovered + s.open.open_sends, estimated: s.s23.estimated })}
                </p>
              )}
            </Card>
          </div>
          {r.frozen.length > 0 && year !== null && <TaxHistory year={year} kept={r.frozen} tz={tz} onChanged={() => setStamp((x) => x + 1)} />}
          <Tabs value={tab} onChange={setTab} tabs={[
            { value: 'disposals', label: t('tax.tabs.disposals') },
            { value: 'incomes', label: t('tax.tabs.incomes') },
            { value: 'futures', label: t('tax.tabs.futures') },
            { value: 'losses', label: t('tax.tabs.losses') },
            { value: 'open', label: t('tax.tabs.open') },
            { value: 'sources', label: t('tax.tabs.sources') },
            { value: 'holdings', label: t('tax.tabs.holdings') },
            { value: 'yearEnd', label: t('tax.tabs.yearEnd') },
            { value: 'free', label: t('tax.tabs.free') },
            { value: 'forms', label: t('tax.tabs.forms') },
          ]} />
          {tab === 'free' ? <TaxFree /> : <Lines key={`${key}-${tab}`} report={r} tab={tab} tz={tz} />}
        </>
      )}
    </div>
  )
}

function Eur({ v: raw, plain = false }: { v: string | null; plain?: boolean }) {
  // a loss of a fraction of a cent reads "−0,00 €": it is zero
  const v = raw !== null && Math.abs(Number(raw)) < 0.005 ? '0' : raw
  const dir = plain ? 'flat' : trend(v)
  return <span className={cx('num whitespace-nowrap', dir === 'up' && 'text-up', dir === 'down' && 'text-down')}>{money(v, 'EUR', !plain)}</span>
}

function Big({ value, label }: { value: string; label: string }) {
  const dir = trend(value)
  return (
    <div className="grid gap-0.5">
      <span className="label">{label}</span>
      <span className={cx('num text-2xl font-semibold', dir === 'up' && 'text-up', dir === 'down' && 'text-down')}>{money(value, 'EUR', true)}</span>
    </div>
  )
}

/** Below or over the limit, and how much of it is used (ADR 0044): a bar that turns
 * yellow from 80 % and red once the limit is reached. */
function Limit({ taxable, share }: { taxable: boolean; share?: string }) {
  const { t } = useTranslation()
  const pct = share === undefined ? null : Number(share)
  return (
    <div className="grid gap-1.5">
      <StatusPill ok={!taxable}>{taxable ? t('tax.taxable') : t('tax.belowLimit')}</StatusPill>
      {pct !== null && (
        <>
          <span className="h-1.5 w-full overflow-hidden rounded-full bg-surface-2" aria-hidden="true">
            <span className={cx('block h-full rounded-full', taxable ? 'bg-down' : pct >= 80 ? 'bg-warn' : 'accent-fill')}
              style={{ width: `${Math.min(100, pct)}%` }} />
          </span>
          <span className={cx('text-xs', !taxable && pct >= 80 ? 'text-warn' : 'text-muted')}>{t('tax.limitShare', { share: Math.round(pct) })}</span>
        </>
      )}
    </div>
  )
}

function Lines({ report, tab, tz }: { report: TaxReport; tab: Tab; tz: string }) {
  const { t } = useTranslation()
  const [withFutures, setWithFutures] = useState(false)
  const [onlyTaxed, setOnlyTaxed] = useState(false)
  const [shown, setShown] = useState(PAGE)
  const l = report.lines
  const place = (p: string | null) => p ?? t('holdings.outside')

  let items: ReactNode[] = []
  let tools: ReactNode = null
  if (tab === 'disposals') {
    const list = l.disposals.filter((d) => (withFutures || d.how !== 'futures') && (!onlyTaxed || !d.tax_free))
    const futures = l.disposals.length - l.disposals.filter((d) => d.how !== 'futures').length
    tools = (
      <div className="flex flex-wrap gap-4">
        <Toggle id="tax-only-taxed" label={t('tax.onlyTaxed')} checked={onlyTaxed} onChange={setOnlyTaxed} />
        {futures > 0 && <Toggle id="tax-futures" label={t('tax.withFutures', { count: futures })} checked={withFutures} onChange={setWithFutures} />}
      </div>
    )
    items = list.map((d, i) => (
      <Line key={i} title={<>{quantity(d.qty)} {d.asset}</>} value={<Eur v={d.gain} />}
        sub={<>{date(d.sold, tz)} · {place(d.place)} · {t('tax.bought', { date: date(d.acquired, tz), count: d.days })}</>}
        extra={<>{t('tax.proceeds')} {money(d.proceeds)} · {t('tax.cost')} {money(d.cost)}</>}
        chips={[d.tax_free && t('tax.chip.free'), d.estimated && t('tax.chip.estimated'), d.how !== 'trade' && t(`tax.how.${d.how}`)]} />
    ))
  } else if (tab === 'incomes') {
    items = l.incomes.map((x, i) => (
      <Line key={i} title={<>{quantity(x.qty)} {x.asset}</>} value={<Eur v={x.value} plain />}
        sub={<>{date(x.at, tz)} · {place(x.place)}</>} chips={[t(`tax.income.${x.kind}`, { defaultValue: x.kind })]} />
    ))
  } else if (tab === 'futures') {
    items = l.futures.map((f, i) => (
      <Line key={i} title={t(`tax.flow.${f.kind}`)} value={<Eur v={f.value} />}
        sub={<>{dateTime(f.at, tz)} · {place(f.place)}</>} extra={<>{quantity(f.amount)} {f.asset}</>} />
    ))
  } else if (tab === 'losses') {
    items = l.losses.map((x, i) => (
      <Line key={i} title={<>{quantity(x.qty)} {x.asset}</>} value={<Eur v={x.cost === null ? null : `-${x.cost}`} />}
        sub={<>{date(x.at, tz)} · {place(x.place)}{x.acquired && <> · {t('tax.boughtOn', { date: date(x.acquired, tz) })}</>}</>} />
    ))
  } else if (tab === 'open') {
    items = l.uncovered.map((u, i) => (
      <Line key={i} title={<>{quantity(u.qty)} {u.asset}</>} value={u.proceeds ? <Eur v={u.proceeds} plain /> : null}
        sub={<>{date(u.at, tz)} · {place(u.place)}</>} chips={[t(`tax.reason.${u.reason}`)]} />
    ))
  } else if (tab === 'forms') {
    const forms = report.summary.forms ?? []
    items = forms.map((f) => (
      <Line key={f.key} title={<>{t('tax.forms.where', { form: f.form })}{f.line ? ` · ${t('tax.forms.line', { line: f.line })}` : ''}</>}
        value={<Eur v={f.value} plain />} sub={t(`tax.forms.${f.key}`)} />
    ))
    tools = <p className="m-0 text-xs text-muted">{forms.some((f) => f.line) ? t('tax.forms.hint2024') : t('tax.forms.noLines')}</p>
  } else if (tab === 'sources') {
    items = (l.by_source ?? []).map((b, i) => (
      <Line key={i} title={place(b.place)} value={<Eur v={b.net} />}
        sub={<>{t('tax.gains')} {money(b.gains)} · {t('tax.losses')} {money(b.losses)}</>}
        extra={Number(b.free_gains) || Number(b.free_losses) ? t('tax.sources.free', { net: money(b.free_net) }) : undefined} />
    ))
  } else if (tab === 'holdings') {
    items = (l.holdings ?? []).map((h, i) => (
      <Line key={i} title={<>{h.asset} · {place(h.place)}</>} value={<Eur v={h.value} plain />}
        sub={<>{t('tax.holdings.start')} {quantity(h.start)} · {t('tax.holdings.in')} {quantity(h.in)} · {t('tax.holdings.out')} {quantity(h.out)}</>}
        extra={<>{t('tax.holdings.end')} {quantity(h.end)} {h.asset}</>} />
    ))
  } else {
    items = l.year_end.map((b, i) => (
      <Line key={i} title={<>{quantity(b.qty)} {b.asset}</>} value={<Eur v={b.cost} plain />}
        sub={<>{place(b.place)}{b.market === 'futures' && ' · Futures'} · {t('tax.boughtOn', { date: date(b.acquired, tz) })}</>}
        extra={t('tax.freeFrom', { date: date(b.free_from) })} chips={[b.estimated && t('tax.chip.estimated')]} />
    ))
  }
  return (
    <div className="grid gap-3">
      {tools}
      {items.length === 0 ? <p className="m-0 text-sm text-muted">{t('tax.empty')}</p> : (
        <ul className="m-0 grid list-none gap-2 p-0">{items.slice(0, shown)}</ul>
      )}
      {items.length > shown && (
        <Button variant="ghost" className="justify-self-start" onClick={() => setShown((n) => n + PAGE * 4)}>
          {t('tax.more', { count: items.length - shown })}
        </Button>
      )}
    </div>
  )
}

function Line({ title, value, sub, extra, chips = [] }: {
  title: ReactNode; value: ReactNode; sub: ReactNode; extra?: ReactNode; chips?: (string | false | null | undefined)[]
}) {
  return (
    <li className="card grid gap-1 p-3 text-sm">
      <div className="flex items-baseline justify-between gap-3">
        <b className="num min-w-0 truncate">{title}</b>
        <b className="shrink-0">{value}</b>
      </div>
      <div className="text-xs text-muted">{sub}</div>
      {(extra || chips.some(Boolean)) && (
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
          {extra && <span className="num">{extra}</span>}
          {chips.filter(Boolean).map((c) => (
            <span key={c as string} className="rounded-full bg-surface-2 px-2 py-0.5">{c}</span>
          ))}
        </div>
      )}
    </li>
  )
}
