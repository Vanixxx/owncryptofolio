import { CheckCircle2, CircleAlert } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useSettings } from '../../app/settings'
import { CoinIcon } from '../../components/CoinIcon'
import { Button, ErrorText, Field } from '../../components/ui'
import { api, type BalanceEntry } from '../../lib/api'
import { amount, dateTime } from '../../lib/format'
import { useErrorText } from '../../lib/useErrorText'

/** One-line state for the folded card (ADR 0039). */
export function BalanceBadge({ entry }: { entry?: BalanceEntry }) {
  const { t } = useTranslation()
  if (!entry || entry.status === 'none') return <span className="text-xs text-muted">{t('balances.unchecked')}</span>
  if (entry.status === 'ok') {
    return <span className="inline-flex items-center gap-1 text-xs text-up"><CheckCircle2 size={14} aria-hidden="true" />{t('balances.ok')}{entry.unchecked > 0 && <span className="text-muted"> · {t('balances.uncheckedCount', { count: entry.unchecked })}</span>}</span>
  }
  return (
    <span className="inline-flex items-center gap-1 text-xs text-warn">
      <CircleAlert size={14} aria-hidden="true" />{t('balances.differences', { count: entry.differences })}
    </span>
  )
}

/** Computed from the transactions against what the source reports, per coin. The heading
 * is the fold around it; the coins sit indented below it, the date of the balance at the
 * end (Vanixxx, 2026-10-10). */
export function BalanceTable({ entry, sourceId, manual, onChanged }: {
  entry?: BalanceEntry; sourceId: number; manual: boolean; onChanged: () => void
}) {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const tz = useSettings().settings['general.timezone']
  const [asset, setAsset] = useState('')
  const [value, setValue] = useState('')
  const [showSpam, setShowSpam] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const items = entry?.items ?? []
  const spam = items.filter((i) => i.spam)
  const shown = items.filter((i) => !i.spam || showSpam)

  function submit(e: FormEvent) {
    e.preventDefault()
    api.setBalance(sourceId, asset, value).then(() => { setAsset(''); setValue(''); setError(null); onChanged() }, setError)
  }

  return (
    <div className="grid gap-2 pl-6">
      {!entry?.checked && <p className="m-0 text-xs leading-relaxed text-muted">{t(manual ? 'balances.manualHint' : 'balances.fetchHint')}</p>}
      {shown.length > 0 && (
        <div className="-mx-1 overflow-x-auto">
          <table className="w-full border-collapse text-xs md:text-sm">
            <thead>
              <tr className="text-left">
                {['asset', 'computed', 'actual', 'diff'].map((c) => (
                  <th key={c} className="label px-1 py-1.5 font-normal">
                    {/* a phone has room for four short headings only */}
                    <span className="md:hidden">{t(`balances.colsShort.${c}`)}</span><span className="hidden md:inline">{t(`balances.cols.${c}`)}</span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {shown.map((i) => (
                <tr key={`${i.market}${i.asset}`} className={i.spam ? 'opacity-55' : undefined}>
                  <td className="px-1 py-1">
                    <span className="inline-flex items-center gap-2">
                      <CoinIcon asset={i.icon} size={18} />
                      <span>{i.asset}{i.market === 'futures' && <span className="text-xs text-muted"> · Futures</span>}</span>
                    </span>
                  </td>
                  <td className="num px-1 py-1">{i.computed ? amount(i.computed) : '—'}</td>
                  <td className="num px-1 py-1">{i.actual ? amount(i.actual) : '—'}</td>
                  <td className={i.ok === false ? 'num px-1 py-1 text-warn' : 'num px-1 py-1 text-muted'}>
                    {i.ok === null ? (entry?.checked ? t('balances.notChecked') : '') : i.ok ? '✓' : amount(i.diff)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {(spam.length > 0 || entry?.at) && (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          {spam.length > 0 && (
            <Button variant="ghost" onClick={() => setShowSpam(!showSpam)}>
              {showSpam ? t('balances.hideSpam') : t('balances.showSpam', { count: spam.length })}
            </Button>
          )}
          {entry?.at && <span className="text-xs text-muted">{t('balances.asOf', { at: dateTime(entry.at, tz) })}</span>}
        </div>
      )}
      {entry?.status === 'diff' && <p className="m-0 text-xs leading-relaxed text-muted">{t('balances.diffHint')}</p>}
      {manual && (
        <form onSubmit={submit} className="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto] items-end gap-2">
          <Field id={`bal-asset-${sourceId}`} label={t('balances.cols.asset')} value={asset} required autoCapitalize="characters"
            onChange={(e) => setAsset(e.target.value.toUpperCase())} placeholder="BTC" />
          <Field id={`bal-amount-${sourceId}`} label={t('balances.actualNow')} value={value} required inputMode="decimal"
            onChange={(e) => setValue(e.target.value)} placeholder="0,5" />
          <Button type="submit">{t('common.save')}</Button>
        </form>
      )}
      <ErrorText>{error ? errorText(error) : null}</ErrorText>
    </div>
  )
}
