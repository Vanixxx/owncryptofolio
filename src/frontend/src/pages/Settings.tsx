import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { ACCENTS, STYLES, useSettings } from '../app/settings'
import { BackupCard } from './BackupCard'
import { PricesCard } from './settings/PricesCard'
import { ScheduleCard } from './settings/ScheduleCard'
import { ServicesCard } from './settings/ServicesCard'
import { TaxCard } from './settings/TaxCard'
import { ApiCard, McpCard } from './settings/McpCard'
import { Button, Card, ErrorText, Field, PageHeader, Segmented } from '../components/ui'
import { api, type Settings as S, type Style } from '../lib/api'
import { copyText } from '../lib/copy'
import { cx } from '../lib/cx'
import { useErrorText } from '../lib/useErrorText'

const TIMEZONES: string[] = (() => {
  try {
    return Intl.supportedValuesOf('timeZone')
  } catch {
    return ['Europe/Berlin', 'UTC']
  }
})()

// a small value curve for each style tile (Vanixxx, 2026-10-20: the empty corner up right)
const SPARK = 'M0 20 L8 16 L16 18 L24 11 L32 13 L40 7 L48 9 L56 3'

export function StylePicker({ value, onChange, accents }: {
  value: Style; onChange: (s: Style) => void; accents?: Partial<Record<Style, string>>
}) {
  const { t } = useTranslation()
  const mode = document.documentElement.dataset.mode
  return (
    <div role="radiogroup" aria-label={t('settings.appearance.style')} className="grid grid-cols-2 gap-2 sm:grid-cols-3 sm:gap-3">
      {STYLES.map((s) => (
        <button
          key={s}
          type="button"
          role="radio"
          aria-checked={s === value}
          data-style={s}
          data-mode={mode}
          data-accent={accents?.[s] ?? 'default'}
          onClick={() => onChange(s)}
          className={cx(
            // two narrow columns on the phone: nine styles fit on one screen
            'grid min-w-0 grid-cols-[minmax(0,1fr)] content-start gap-1.5 rounded-card border bg-[var(--bg)] p-2.5 text-left sm:gap-2 sm:p-3',
            s === value ? 'border-accent ring-2 ring-accent' : 'border-line',
          )}
        >
          <span className="flex items-center justify-between gap-2">
            <span className="flex min-w-0 items-center gap-2">
              <span className="accent-fill h-5 w-5 shrink-0 rounded-ctl" aria-hidden="true" />
              <b className="truncate text-sm font-semibold sm:text-base">{t(`settings.appearance.styles.${s}`)}</b>
            </span>
            <svg viewBox="0 0 56 24" className="hidden h-6 w-16 shrink-0 sm:block" aria-hidden="true">
              {/* from --accent to --accent-2: Neon shows its gradient here too */}
              <defs>
                <linearGradient id={`spark-${s}`} x1="0" x2="1" y1="0" y2="0">
                  <stop offset="0" style={{ stopColor: 'var(--accent)' }} />
                  <stop offset="1" style={{ stopColor: 'var(--accent-2)' }} />
                </linearGradient>
              </defs>
              <path d={`${SPARK} L56 24 L0 24 Z`} fill={`url(#spark-${s})`} opacity="0.15" />
              <path d={SPARK} fill="none" stroke={`url(#spark-${s})`} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
            </svg>
          </span>
          <span className="num text-base font-semibold sm:text-lg">48.213,07 €</span>
          <span className="flex gap-2 text-xs">
            <span className="text-up">+12,4 %</span>
            <span className="text-down">−3,1 %</span>
          </span>
          <span className="hidden text-xs leading-snug text-muted sm:block">{t(`settings.appearance.styleHints.${s}`)}</span>
        </button>
      ))}
    </div>
  )
}

export function Settings() {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const { settings, update } = useSettings()
  const [error, setError] = useState<unknown>(null)
  const set = (changes: Partial<S>) => update(changes).then(() => setError(null), setError)

  return (
    <>
      <PageHeader title={t('settings.title')} subtitle={t('settings.subtitle')} />
      <ErrorText>{error ? errorText(error) : null}</ErrorText>

      <Card fold="settings-open-appearance" title={t('settings.appearance.title')}>
        <span className="label">{t('settings.appearance.style')}</span>
        <StylePicker value={settings['appearance.style']} onChange={(s) => set({ 'appearance.style': s })}
          accents={settings['appearance.accents']} />
        {/* a colour of one's own for the chosen style (Vanixxx, 2026-10-21); "Standard" is the
            style's own colour */}
        <div className="grid gap-1.5">
          <span className="label">{t('settings.appearance.accent')}</span>
          <div role="radiogroup" aria-label={t('settings.appearance.accent')} className="flex flex-wrap gap-2">
            {ACCENTS.map((a) => {
              const style = settings['appearance.style']
              const chosen = (settings['appearance.accents']?.[style] ?? 'default') === a
              return (
                <button key={a} type="button" role="radio" aria-checked={chosen}
                  data-style={style} data-mode={document.documentElement.dataset.mode} data-accent={a}
                  onClick={() => set({ 'appearance.accents': { ...settings['appearance.accents'], [style]: a } })}
                  className={cx('flex items-center gap-2 rounded-full border bg-transparent py-1 pl-1 pr-3 text-sm',
                    chosen ? 'border-accent ring-2 ring-accent' : 'border-line')}>
                  <span className="accent-fill h-6 w-6 rounded-full" aria-hidden="true" />
                  {t(`settings.appearance.accents.${a}`)}
                </button>
              )
            })}
          </div>
        </div>
        <span className="label mt-2">{t('settings.appearance.theme')}</span>
        <Segmented
          label={t('settings.appearance.theme')}
          value={settings['appearance.theme']}
          onChange={(v) => set({ 'appearance.theme': v })}
          options={(['system', 'light', 'dark'] as const).map((v) => ({ value: v, label: t(`settings.appearance.themes.${v}`) }))}
        />
      </Card>

      <div className="grid gap-4 md:gap-5">
        <IconCard />
        <Card fold="settings-open-regional" title={t('settings.regional.title')}>
          <span className="label">{t('settings.regional.language')}</span>
          <Segmented
            label={t('settings.regional.language')}
            value={settings['general.language']}
            onChange={(v) => set({ 'general.language': v })}
            options={(['de', 'en'] as const).map((v) => ({ value: v, label: t(`settings.regional.languages.${v}`) }))}
          />
          <span className="label mt-2">{t('settings.regional.currency')}</span>
          <Segmented
            label={t('settings.regional.currency')}
            value={settings['general.currency']}
            onChange={(v) => set({ 'general.currency': v })}
            options={(['EUR', 'USD'] as const).map((v) => ({ value: v, label: v }))}
          />
          <label htmlFor="timezone" className="mt-2 grid gap-1.5">
            <span className="label">{t('settings.regional.timezone')}</span>
            <select
              id="timezone"
              value={settings['general.timezone']}
              onChange={(e) => set({ 'general.timezone': e.target.value })}
              className="w-full rounded-ctl border border-line bg-surface-2 px-3 py-2.5 text-base text-fg"
            >
              {TIMEZONES.map((z) => <option key={z} value={z}>{z}</option>)}
            </select>
          </label>
        </Card>

        <PasswordCard />
        <ScheduleCard />
        <PricesCard />
        <TaxCard />
        <ServicesCard />
        <McpCard />
        <ApiCard />
        <BackupCard />
      </div>
    </>
  )
}

function PasswordCard() {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [state, setState] = useState<'idle' | 'busy' | 'done' | unknown>('idle')

  async function submit(e: FormEvent) {
    e.preventDefault()
    setState('busy')
    try {
      await api.changePassword(current, next)
      setCurrent(''); setNext(''); setState('done')
    } catch (err) {
      setState(err)
    }
  }
  const failed = state !== 'idle' && state !== 'busy' && state !== 'done'
  return (
    <Card fold="settings-open-security" title={t('settings.security.title')}>
      <form onSubmit={submit} className="grid gap-3">
        <Field id="pw-current" label={t('settings.security.current')} type="password" autoComplete="current-password"
          value={current} onChange={(e) => setCurrent(e.target.value)} required />
        <Field id="pw-new" label={t('settings.security.new')} type="password" autoComplete="new-password"
          value={next} onChange={(e) => setNext(e.target.value)} required />
        <ErrorText>{failed ? errorText(state) : null}</ErrorText>
        {state === 'done' && <p className="m-0 text-sm text-up">{t('settings.security.changed')}</p>}
        <Button type="submit" disabled={state === 'busy'} className="justify-self-start">{t('settings.security.change')}</Button>
      </form>
    </Card>
  )
}

export function KeyBox({ value }: { value: string }) {
  const { t } = useTranslation()
  const [copied, setCopied] = useState(false)
  const download = () => {
    const url = URL.createObjectURL(new Blob([value + '\n'], { type: 'text/plain' }))
    const a = Object.assign(document.createElement('a'), { href: url, download: 'owncryptofolio-backup-key.txt' })
    a.click()
    URL.revokeObjectURL(url)
  }
  return (
    <div className="grid gap-2">
      <code className="block break-all rounded-ctl border border-line bg-surface-2 p-3 font-mono text-sm select-all">{value}</code>
      <div className="flex flex-wrap gap-2">
        <Button type="button" variant="ghost" onClick={() => void copyText(value).then(setCopied)}>
          {copied ? t('common.copied') : t('common.copy')}
        </Button>
        <Button type="button" variant="ghost" onClick={download}>{t('common.download')}</Button>
      </div>
    </div>
  )
}

const ICONS = ['E5', 'B1', 'B2', 'B3', 'B4', 'E1', 'E2', 'E3', 'E4', 'E6', 'A1', 'A2', 'A3', 'C', 'C1', 'D']

/** The icon on the phone's home screen (Vanixxx, 2026-10-21): E5 unless chosen otherwise. */
function IconCard() {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const { settings, update } = useSettings()
  const [error, setError] = useState<unknown>(null)
  return (
    <Card fold="settings-open-icon" title={t('settings.icon.title')}>
      <p className="m-0 text-sm leading-relaxed text-muted">{t('settings.icon.text')}</p>
      <div role="radiogroup" aria-label={t('settings.icon.title')} className="grid grid-cols-4 gap-3 sm:grid-cols-8">
        {ICONS.map((k) => (
          <button key={k} type="button" role="radio" aria-checked={settings['appearance.icon'] === k} aria-label={k}
            onClick={() => void update({ 'appearance.icon': k }).then(() => setError(null), setError)}
            className={cx('grid justify-items-center gap-1 rounded-ctl border-0 bg-transparent p-1 text-xs text-muted',
              settings['appearance.icon'] === k && 'text-fg')}>
            <img src={`/app-icons/${k}-180.png`} alt="" width={56} height={56}
              className={cx('h-14 w-14 rounded-[13px]', settings['appearance.icon'] === k ? 'ring-2 ring-accent ring-offset-2 ring-offset-[var(--surface)]' : '')} />
            {k}
          </button>
        ))}
      </div>
      <p className="m-0 text-xs leading-relaxed text-muted">{t('settings.icon.hint')}</p>
      <ErrorText>{error ? errorText(error) : null}</ErrorText>
    </Card>
  )
}
