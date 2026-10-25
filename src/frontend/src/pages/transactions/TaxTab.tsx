import { useEffect, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import { ErrorText } from '../../components/ui'
import { api, type TaxRows } from '../../lib/api'
import { cx } from '../../lib/cx'
import { date, money, quantity, trend } from '../../lib/format'
import { useErrorText } from '../../lib/useErrorText'

const ZERO = '0'

function sum(values: (string | null)[]): string | null {
  if (values.some((v) => v === null)) return null
  return String(values.reduce((a, v) => a + Number(v), 0))
}

/** The tax side of one transaction (ADR 0042, Vanixxx 2026-10-13): what it sold and from
 * which purchases, what it bought and what became of it, what a transfer carried along. */
export function TaxTab({ ids, tz }: { ids: number[]; tz: string }) {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const [data, setData] = useState<TaxRows | null>(null)
  const [error, setError] = useState<unknown>(null)
  const key = ids.join(',')
  useEffect(() => {
    let live = true
    api.taxRows(key.split(',').map(Number)).then((d) => { if (live) setData(d) }, setError)
    return () => { live = false }
  }, [key])
  if (error) return <ErrorText>{errorText(error)}</ErrorText>
  if (!data) return <p className="m-0 text-sm text-muted">{t('common.loading')}</p>
  const d = data
  const taxed = d.sold.filter((x) => !x.tax_free)
  const free = d.sold.filter((x) => x.tax_free)
  const nothing = !d.sold.length && !d.incomes.length && !d.futures.length && !d.losses.length
    && !d.uncovered.length && !d.created.length && !d.moved.length
  const later = d.later.sold.length + d.later.losses.length + d.later.open.length > 0
  const year = (iso: string) => new Date(iso).getFullYear()

  return (
    <div className="grid gap-3 text-sm">
      <span className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted">
        {t('tax.row.method', { method: d.method.toUpperCase() })}
        {/* a sale or a transfer: where its money came from (ADR 0046) */}
        {(d.sold.length > 0 || d.moved.length > 0) && (
          <Link to={`/reports?view=origin&row=${ids[0]}`} className="text-accent no-underline">{t('origin.link')}</Link>
        )}
      </span>
      {nothing && <p className="m-0 text-muted">{t('tax.row.nothing')}</p>}

      {d.sold.length > 0 && (
        <Section title={t('tax.row.sold', { year: year(d.sold[0].sold) })}>
          {d.sold.map((x, i) => (
            <Item key={i} left={<>{quantity(x.qty)} {x.asset} · {t('tax.bought', { date: date(x.acquired, tz), count: x.days })}</>}
              right={<Eur v={x.gain} signed />}
              sub={<>{t('tax.proceeds')} {money(x.proceeds)} · {t('tax.cost')} {money(x.cost)}</>}
              chips={[x.tax_free && t('tax.chip.free'), x.estimated && t('tax.chip.estimated'), x.how !== 'trade' && t(`tax.how.${x.how}`)]} />
          ))}
          <div className="grid gap-1 border-t border-line pt-1.5">
            {taxed.length > 0 && <Total label={t('tax.row.taxedGain')} v={sum(taxed.map((x) => x.gain))} />}
            {free.length > 0 && <Total label={t('tax.row.freeGain')} v={sum(free.map((x) => x.gain))} />}
          </div>
        </Section>
      )}

      {d.incomes.map((x, i) => (
        <Section key={`i${i}`} title={t('tax.row.income')}>
          <Item left={<>{quantity(x.qty)} {x.asset} · {t(`tax.income.${x.kind}`, { defaultValue: x.kind })}</>} right={<Eur v={x.value} />}
            sub={t('tax.row.incomeHint')} />
        </Section>
      ))}

      {d.futures.length > 0 && (
        <Section title={t('tax.row.futures')}>
          {d.futures.map((x, i) => (
            <Item key={i} left={<>{t(`tax.flow.${x.kind}`)} · {quantity(x.amount)} {x.asset}</>} right={<Eur v={x.value} signed />} />
          ))}
        </Section>
      )}

      {d.losses.length > 0 && (
        <Section title={t('tax.row.lost')}>
          {d.losses.map((x, i) => (
            <Item key={i} left={<>{quantity(x.qty)} {x.asset}{x.acquired && <> · {t('tax.boughtOn', { date: date(x.acquired, tz) })}</>}</>}
              right={<Eur v={x.cost === null ? null : `-${x.cost}`} signed />} />
          ))}
          <p className="m-0 text-xs text-muted">{t('tax.row.lostHint')}</p>
        </Section>
      )}

      {d.uncovered.map((x, i) => (
        <p key={`u${i}`} className="m-0 text-xs text-warn">{t('tax.row.uncovered', { qty: quantity(x.qty), asset: x.asset, reason: t(`tax.reason.${x.reason}`) })}</p>
      ))}

      {d.moved.length > 0 && !d.sold.length && (
        <Section title={t('tax.row.moved')}>
          {d.moved.map((x, i) => (
            <Item key={i} left={<>{quantity(x.qty)} {x.asset} · {t('tax.boughtOn', { date: date(x.acquired, tz) })}</>}
              right={<span className="num">{money(x.cost)}</span>} sub={t('tax.freeFrom', { date: date(x.free_from) })} />
          ))}
        </Section>
      )}

      {d.created.length > 0 && (
        <Section title={t('tax.row.created')}>
          {d.created.map((x, i) => (
            <Item key={i} left={<>{quantity(x.qty)} {x.asset}</>} right={<span className="num">{money(x.cost)}</span>}
              sub={t('tax.freeFrom', { date: date(x.free_from) })} chips={[x.estimated && t('tax.chip.estimated')]} />
          ))}
        </Section>
      )}

      {later && (
        <Section title={t('tax.row.later')}>
          {d.later.open.map((x, i) => (
            <Item key={`o${i}`} left={<>{quantity(x.qty)} {x.asset} · {t('tax.row.held', { place: x.place ?? t('holdings.outside') })}</>}
              right={<span className="num">{money(x.cost)}</span>}
              sub={t('tax.freeFrom', { date: date(x.free_from) })} />
          ))}
          {d.later.sold.map((x, i) => (
            <Item key={`s${i}`} left={<>{quantity(x.qty)} {x.asset} · {t('tax.row.soldOn', { date: date(x.sold, tz) })}</>}
              right={<Eur v={x.gain} signed />} chips={[x.tax_free && t('tax.chip.free'), x.how !== 'trade' && t(`tax.how.${x.how}`)]} />
          ))}
          {d.later.losses.map((x, i) => (
            <Item key={`l${i}`} left={<>{quantity(x.qty)} {x.asset} · {t('tax.row.lostOn', { date: date(x.at, tz) })}</>}
              right={<Eur v={x.cost === null ? null : `-${x.cost}`} signed />} />
          ))}
        </Section>
      )}
    </div>
  )
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="grid gap-1.5">
      <span className="label">{title}</span>
      <ul className="m-0 grid list-none gap-1 p-0">{children}</ul>
    </div>
  )
}

function Item({ left, right, sub, chips = [] }: {
  left: ReactNode; right: ReactNode; sub?: ReactNode; chips?: (string | false | null | undefined)[]
}) {
  return (
    <li className="grid gap-0.5 rounded-ctl bg-surface-2 px-2.5 py-1.5">
      <div className="flex items-baseline justify-between gap-3">
        <span className="num min-w-0">{left}</span>
        <b className="shrink-0">{right}</b>
      </div>
      {(sub || chips.some(Boolean)) && (
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
          {sub && <span className="num">{sub}</span>}
          {chips.filter(Boolean).map((c) => <span key={c as string} className="rounded-full border border-line px-2 py-0.5">{c}</span>)}
        </div>
      )}
    </li>
  )
}

function Eur({ v, signed = false }: { v: string | null; signed?: boolean }) {
  const shown = v !== null && Math.abs(Number(v)) < 0.005 ? ZERO : v
  const dir = signed ? trend(shown) : 'flat'
  return <span className={cx('num', dir === 'up' && 'text-up', dir === 'down' && 'text-down')}>{money(shown, 'EUR', signed)}</span>
}

function Total({ label, v }: { label: string; v: string | null }) {
  return (
    <div className="flex items-baseline justify-between gap-3 px-2.5">
      <span className="text-muted">{label}</span>
      <b><Eur v={v} signed /></b>
    </div>
  )
}
