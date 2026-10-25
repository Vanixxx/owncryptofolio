import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { applySettings } from '../app/settings'
import { Brand, Button, ErrorText, Field, Segmented } from '../components/ui'
import { api, type Settings } from '../lib/api'
import { useErrorText } from '../lib/useErrorText'
import { CenteredCard } from './Login'
import { KeyBox, StylePicker } from './Settings'
import { RestorePanel } from '../components/RestorePanel'

const MIN_PASSWORD = 10
type Step = 'code' | 'password' | 'backup' | 'basics' | 'restore'
const STEPS: Step[] = ['code', 'password', 'backup', 'basics']

/** First-start wizard (ADR 0030): setup code from the log, password, backup key, basics.
 * The code only when the server already had keys; a brand-new install starts with a welcome. */
export function Setup({ codeRequired, onDone }: { codeRequired: boolean; onDone: () => void }) {
  const { t, i18n } = useTranslation()
  const errorText = useErrorText()
  const [step, setStep] = useState<Step>('code')
  const [code, setCode] = useState('')
  const [password, setPassword] = useState('')
  const [repeat, setRepeat] = useState('')
  const [backupKey, setBackupKey] = useState('')
  const [confirmed, setConfirmed] = useState(false)
  const [settings, setSettings] = useState<Settings | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const [localError, setLocalError] = useState('')

  async function run(fn: () => Promise<void>) {
    setBusy(true); setError(null); setLocalError('')
    try { await fn() } catch (err) { setError(err) } finally { setBusy(false) }
  }

  const submitCode = (e: FormEvent) => {
    e.preventDefault()
    void run(async () => { await api.verifySetupCode(code); setStep('password') })
  }
  const submitPassword = (e: FormEvent) => {
    e.preventDefault()
    if (password !== repeat) return setLocalError(t('setup.password.mismatch'))
    void run(async () => {
      const { backup_key } = await api.setup(code, password)
      setBackupKey(backup_key)
      // Start from the language the visitor is already reading.
      const s = await api.updateSettings({ 'general.language': i18n.language === 'en' ? 'en' : 'de' })
      setSettings(s)
      setStep('backup')
    })
  }
  const change = (changes: Partial<Settings>) =>
    run(async () => {
      const s = await api.updateSettings(changes)
      setSettings(s)
      applySettings(s)
    })

  return (
    <CenteredCard>
      <div className="flex items-center justify-between gap-3">
        <Brand />
        {step !== 'restore' && <span className="label">{t('setup.step', { n: STEPS.indexOf(step) + 1, total: STEPS.length })}</span>}
      </div>

      {step === 'code' && !codeRequired && (
        <div className="grid gap-4">
          <h1 className="m-0 text-xl font-bold">{t('setup.welcome.title')}</h1>
          <p className="m-0 text-sm leading-relaxed text-muted">{t('setup.welcome.text')}</p>
          <Button type="button" autoFocus onClick={() => setStep('password')}>{t('setup.welcome.new')}</Button>
          <Button type="button" variant="ghost" onClick={() => setStep('restore')}>{t('restore.atSetup')}</Button>
        </div>
      )}

      {step === 'code' && codeRequired && (
        <form onSubmit={submitCode} className="grid gap-4">
          <h1 className="m-0 text-xl font-bold">{t('setup.code.title')}</h1>
          <p className="m-0 text-sm leading-relaxed text-muted">{t('setup.code.why')}</p>
          {/* where the code is, step by step (Vanixxx, 2026-10-22) */}
          <div className="grid gap-1 rounded-ctl border border-line bg-surface-2 p-3 text-sm leading-relaxed">
            <b>{t('setup.code.whereTitle')}</b>
            <span className="text-muted">{t('setup.code.where')}</span>
            <code className="justify-self-start font-mono text-xs">First start: open the web UI and enter the setup code  123-456</code>
            <span className="text-xs text-muted">{t('setup.code.restart')}</span>
          </div>
          <Field id="setup-code" label={t('setup.code.label')} placeholder={t('setup.code.placeholder')}
            inputMode="numeric" autoComplete="one-time-code" autoFocus value={code}
            onChange={(e) => setCode(e.target.value)} required className="num" />
          <ErrorText>{error ? errorText(error) : null}</ErrorText>
          <Button type="submit" disabled={busy}>{t('common.next')}</Button>
          {/* instead of starting empty: a backup back (Vanixxx, 2026-10-21) */}
          <Button type="button" variant="ghost" disabled={busy || !code.trim()}
            onClick={() => void run(async () => { await api.verifySetupCode(code); setStep('restore') })}>
            {t('restore.atSetup')}
          </Button>
        </form>
      )}

      {step === 'restore' && (
        <div className="grid min-w-0 gap-4">
          <h1 className="m-0 text-xl font-bold">{t('restore.setupTitle')}</h1>
          <p className="m-0 text-sm leading-relaxed text-muted">{t('restore.setupText')}</p>
          <RestorePanel code={code} onDone={onDone} />
          <Button variant="ghost" className="justify-self-start" onClick={() => setStep('code')}>{t('common.back')}</Button>
        </div>
      )}

      {step === 'password' && (
        <form onSubmit={submitPassword} className="grid gap-4">
          <h1 className="m-0 text-xl font-bold">{t('setup.password.title')}</h1>
          <p className="m-0 text-sm leading-relaxed text-muted">{t('setup.password.text', { min: MIN_PASSWORD })}</p>
          <Field id="setup-password" label={t('setup.password.label')} type="password" autoComplete="new-password"
            minLength={MIN_PASSWORD} autoFocus value={password} onChange={(e) => setPassword(e.target.value)} required />
          <Field id="setup-repeat" label={t('setup.password.repeat')} type="password" autoComplete="new-password"
            value={repeat} onChange={(e) => setRepeat(e.target.value)} required />
          <ErrorText>{localError || (error ? errorText(error) : null)}</ErrorText>
          <Button type="submit" disabled={busy}>{t('common.next')}</Button>
        </form>
      )}

      {step === 'backup' && (
        <div className="grid gap-4">
          <h1 className="m-0 text-xl font-bold">{t('setup.backup.title')}</h1>
          <p className="m-0 text-sm leading-relaxed text-muted">{t('setup.backup.text')}</p>
          <KeyBox value={backupKey} />
          <label htmlFor="setup-confirm" className="flex items-start gap-3 text-sm">
            <input id="setup-confirm" type="checkbox" checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)}
              className="mt-0.5 h-5 w-5 accent-[var(--accent)]" />
            {t('setup.backup.confirm')}
          </label>
          <Button type="button" disabled={!confirmed} onClick={() => setStep('basics')}>{t('common.next')}</Button>
        </div>
      )}

      {step === 'basics' && settings && (
        <div className="grid gap-4">
          <h1 className="m-0 text-xl font-bold">{t('setup.basics.title')}</h1>
          <p className="m-0 text-sm leading-relaxed text-muted">{t('setup.basics.text')}</p>
          <span className="label">{t('settings.regional.language')}</span>
          <Segmented label={t('settings.regional.language')} value={settings['general.language']}
            onChange={(v) => change({ 'general.language': v })}
            options={(['de', 'en'] as const).map((v) => ({ value: v, label: t(`settings.regional.languages.${v}`) }))} />
          <span className="label">{t('settings.appearance.style')}</span>
          <StylePicker value={settings['appearance.style']} onChange={(s) => change({ 'appearance.style': s })} />
          <span className="label">{t('settings.appearance.theme')}</span>
          <Segmented label={t('settings.appearance.theme')} value={settings['appearance.theme']}
            onChange={(v) => change({ 'appearance.theme': v })}
            options={(['system', 'light', 'dark'] as const).map((v) => ({ value: v, label: t(`settings.appearance.themes.${v}`) }))} />
          <span className="label">{t('settings.regional.currency')}</span>
          <Segmented label={t('settings.regional.currency')} value={settings['general.currency']}
            onChange={(v) => change({ 'general.currency': v })}
            options={(['EUR', 'USD'] as const).map((v) => ({ value: v, label: v }))} />
          <ErrorText>{error ? errorText(error) : null}</ErrorText>
          <Button type="button" disabled={busy} onClick={onDone}>{t('setup.basics.finish')}</Button>
        </div>
      )}
    </CenteredCard>
  )
}
