import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Brand, Button, ErrorText, Field } from '../components/ui'
import { api } from '../lib/api'
import { useErrorText } from '../lib/useErrorText'

export function CenteredCard({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid min-h-dvh place-items-center px-4 py-8">
      <div className="card grid w-full max-w-[420px] gap-5 p-6">{children}</div>
    </div>
  )
}

export function Login({ onDone }: { onDone: () => void }) {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    try {
      await api.login(password)
      onDone()
    } catch (err) {
      setError(err)
      setBusy(false)
    }
  }
  return (
    <CenteredCard>
      <Brand />
      <h1 className="m-0 text-xl font-bold">{t('login.title')}</h1>
      <form onSubmit={submit} className="grid gap-4">
        <Field id="password" label={t('login.password')} type="password" autoComplete="current-password"
          autoFocus value={password} onChange={(e) => setPassword(e.target.value)} required />
        <ErrorText>{error ? errorText(error) : null}</ErrorText>
        <Button type="submit" disabled={busy}>{t('login.submit')}</Button>
      </form>
    </CenteredCard>
  )
}
