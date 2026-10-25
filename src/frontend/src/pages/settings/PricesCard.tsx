import { ArrowDown, ArrowUp } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useSettings } from '../../app/settings'
import { Button, Card, ErrorText } from '../../components/ui'
import { api } from '../../lib/api'
import { Toggle } from '../../components/ui/Toggle'
import { useErrorText } from '../../lib/useErrorText'
import { TimeSelect } from './TimeSelect'

const INTERVALS = [0, 5, 15, 30, 60]

/** Price history once a day, current prices in an interval (ADR 0019). */
export function PricesCard() {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const { settings, update } = useSettings()
  const [error, setError] = useState<unknown>(null)
  const [resuggested, setResuggested] = useState<number | null>(null)
  const set = (c: Parameters<typeof update>[0]) => update(c).then(() => setError(null), setError)
  const order = settings['prices.source_order']
  const move = (i: number, d: number) => {
    const next = [...order];
    [next[i], next[i + d]] = [next[i + d], next[i]]
    setResuggested(null)
    void set({ 'prices.source_order': next })
  }
  const resuggest = () =>
    api.resuggestPrices().then((r) => api.startJob('prices').then(() => setResuggested(r.assets)), setError)
  return (
    <Card fold="settings-open-prices" title={t('settings.prices.title')}>
      <p className="m-0 text-sm leading-relaxed text-muted">{t('settings.prices.text')}</p>
      <Toggle id="prices-enabled" label={t('settings.prices.enabled')} checked={settings['prices.enabled']}
        onChange={(v) => void set({ 'prices.enabled': v })} />
      <TimeSelect id="prices-time" label={t('settings.prices.time')} value={settings['prices.time']}
        onChange={(v) => void set({ 'prices.time': v })} />
      <label htmlFor="prices-latest" className="grid gap-1.5">
        <span className="label">{t('settings.prices.latest')}</span>
        <select id="prices-latest" value={settings['prices.latest_minutes']}
          onChange={(e) => void set({ 'prices.latest_minutes': Number(e.target.value) })}
          className="justify-self-start rounded-ctl border border-line bg-surface-2 px-3 py-2 text-base text-fg">
          {INTERVALS.map((m) => <option key={m} value={m}>{m === 0 ? t('settings.prices.off') : t('settings.prices.every', { count: m })}</option>)}
        </select>
      </label>
      <div className="grid gap-1.5">
        <span className="label">{t('settings.prices.order')}</span>
        <ol className="m-0 grid list-none gap-1 p-0">
          {order.map((src, i) => (
            <li key={src} className="flex items-center justify-between gap-2 rounded-ctl bg-surface-2 px-3 py-1.5 text-sm">
              <span>{i + 1}. {t(`prices.sources.${src}`)}</span>
              <span className="flex">
                <button type="button" aria-label={t('prices.up')} disabled={i === 0} onClick={() => move(i, -1)} className="p-1.5 text-muted disabled:opacity-30"><ArrowUp size={16} /></button>
                <button type="button" aria-label={t('prices.down')} disabled={i === order.length - 1} onClick={() => move(i, 1)} className="p-1.5 text-muted disabled:opacity-30"><ArrowDown size={16} /></button>
              </span>
            </li>
          ))}
        </ol>
        <span className="text-xs leading-relaxed text-muted">{t('settings.prices.orderHint')}</span>
        <Button variant="ghost" className="justify-self-start" onClick={() => void resuggest()}>{t('settings.prices.resuggest')}</Button>
        {resuggested !== null && <span className="text-xs text-up">{t('settings.prices.resuggested', { count: resuggested })}</span>}
      </div>
      <ErrorText>{error ? errorText(error) : null}</ErrorText>
    </Card>
  )
}
