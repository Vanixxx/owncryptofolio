import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { CoinIcon } from '../../components/CoinIcon'
import { ErrorText } from '../../components/ui'
import { api, type TaxFree as Data } from '../../lib/api'
import { cx } from '../../lib/cx'
import { date, money, quantity, trend } from '../../lib/format'
import { useErrorText } from '../../lib/useErrorText'

/** Per coin today (Vanixxx 2026-10-16): how much is past the holding period and how much is
 * not yet, with values in the display currency. Independent of the year above. */
export function TaxFree() {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const [data, setData] = useState<Data | null>(null)
  const [error, setError] = useState<unknown>(null)
  useEffect(() => { api.taxFree().then(setData, setError) }, [])
  if (error) return <ErrorText>{errorText(error)}</ErrorText>
  if (!data) return <p className="m-0 text-sm text-muted">{t('common.loading')}</p>
  const cur = data.currency
  if (!data.coins.length) return <p className="m-0 text-sm text-muted">{t('tax.empty')}</p>

  const part = (qty: string | null, value: string | null, gain: string | null) => qty !== null && !(Number(qty) > 0) ? (
    <div className="text-right text-muted">—</div>
  ) : (
    <div className="grid justify-items-end gap-0.5">
      {qty !== null && <span className="num">{quantity(qty)}</span>}
      <b className="num font-medium">{value === null ? <span className="text-xs font-normal text-muted">{t('tax.freeCoins.noPrice')}</span> : money(value, cur)}</b>
      {gain !== null && <Gain v={gain} cur={cur} />}
    </div>
  )
  return (
    <div className="grid gap-3">
      <p className="m-0 text-xs leading-relaxed text-muted">{t('tax.freeCoins.hint', { currency: cur })}</p>
      <div className="card overflow-x-auto p-0">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-line text-left">
              <th className="label px-3 py-2 font-normal">{t('tax.freeCoins.coin')}</th>
              <th className="label px-3 py-2 text-right font-normal">{t('tax.freeCoins.free')}</th>
              <th className="label px-3 py-2 text-right font-normal">{t('tax.freeCoins.taxed')}</th>
              <th className="label hidden px-3 py-2 text-right font-normal sm:table-cell">{t('tax.freeCoins.next')}</th>
            </tr>
          </thead>
          <tbody>
            {data.coins.map((c) => (
              <tr key={c.asset} className="border-b border-line align-top last:border-0">
                <td className="px-3 py-2">
                  <span className="flex items-center gap-2"><CoinIcon asset={c.asset} size={20} /><b>{c.asset}</b></span>
                  {c.next_free && (
                    <span className="num mt-1 block text-xs text-muted sm:hidden">
                      {t('tax.freeCoins.nextOn', { qty: quantity(c.next_qty), date: date(c.next_free) })}
                    </span>
                  )}
                </td>
                <td className="px-3 py-2">{part(c.free, c.value_free, c.gain_free)}</td>
                <td className="px-3 py-2">{part(c.taxed, c.value_taxed, c.gain_taxed)}</td>
                <td className="num hidden px-3 py-2 text-right text-xs text-muted sm:table-cell">
                  {c.next_free ? <>{date(c.next_free)}<br />{quantity(c.next_qty)} {c.asset}</> : '—'}
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="border-t border-line">
              <td className="px-3 py-2 font-semibold">{t('tax.freeCoins.total')}</td>
              <td className="px-3 py-2">{part(null, data.total.value_free, data.total.gain_free)}</td>
              <td className="px-3 py-2">{part(null, data.total.value_taxed, data.total.gain_taxed)}</td>
              <td className="hidden sm:table-cell" />
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  )
}

function Gain({ v, cur }: { v: string; cur: string }) {
  const dir = trend(v)
  return <span className={cx('num text-xs', dir === 'up' ? 'text-up' : dir === 'down' ? 'text-down' : 'text-muted')}>{money(v, cur, true)}</span>
}
