import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router'
import { applyAppearance, cachedAppearance } from './app/appearance'
import { SettingsProvider } from './app/SettingsContext'
import { AppShell } from './components/layout/AppShell'
import { Button, ErrorText } from './components/ui'
import { api, ApiError, setDbLostHandler, setSessionLostHandler, type Settings as S } from './lib/api'
import { useErrorText } from './lib/useErrorText'
import { Dashboard } from './pages/Dashboard'
import { CenteredCard, Login } from './pages/Login'
import { More } from './pages/More'
import { Settings } from './pages/Settings'
import { Setup } from './pages/Setup'
import { Prices } from './pages/prices/Prices'
import { Reports } from './pages/Simple'
import { Stats } from './pages/stats/Stats'
import { Holdings } from './pages/holdings/Holdings'
import { Sources } from './pages/sources/Sources'
import { Transactions } from './pages/Transactions'
import { SystemStatus } from './pages/SystemStatus'

type Gate = { kind: 'loading' } | { kind: 'error'; error: unknown } | { kind: 'setup'; code: boolean } | { kind: 'login' } | { kind: 'nodb' }
  | { kind: 'app'; settings: S }

export default function App() {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const [gate, setGate] = useState<Gate>({ kind: 'loading' })

  const check = useCallback(async () => {
    try {
      const status = await api.authStatus()
      if (status.setup_required) return setGate({ kind: 'setup', code: status.code_required !== false })
      if (!status.authenticated) return setGate({ kind: 'login' })
      setGate({ kind: 'app', settings: await api.settings() })
    } catch (error) {
      if (error instanceof ApiError && error.code === 'db.unavailable') return setGate({ kind: 'nodb' })
      setGate({ kind: 'error', error })
    }
  }, [])
  // without a database: ask again every few seconds, the app opens by itself once it is back
  useEffect(() => {
    if (gate.kind !== 'nodb') return
    const id = window.setInterval(() => void check(), 5000)
    return () => window.clearInterval(id)
  }, [gate.kind, check])

  useEffect(() => {
    applyAppearance(cachedAppearance())
    setSessionLostHandler(() => setGate({ kind: 'login' }))
    setDbLostHandler(() => setGate({ kind: 'nodb' }))
    // check() only sets state after awaiting the server, never synchronously.
    // oxlint-disable-next-line react/set-state-in-effect
    void check()
    return () => { setSessionLostHandler(null); setDbLostHandler(null) }
  }, [check])

  const logout = () => void api.logout().finally(() => setGate({ kind: 'login' }))

  switch (gate.kind) {
    case 'loading':
      return null
    case 'error':
      return (
        <CenteredCard>
          <ErrorText>{errorText(gate.error)}</ErrorText>
          <Button onClick={() => void check()}>{t('common.retry')}</Button>
        </CenteredCard>
      )
    case 'nodb':
      return (
        <CenteredCard>
          <b className="text-base">{t('nodb.title')}</b>
          <p className="m-0 text-sm leading-relaxed text-muted">{t('nodb.text')}</p>
          <p className="m-0 flex items-center gap-2 text-xs text-muted">
            <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-warn" aria-hidden="true" />{t('nodb.retrying')}
          </p>
          <Button onClick={() => void check()}>{t('common.retry')}</Button>
        </CenteredCard>
      )
    case 'setup':
      return <Setup codeRequired={gate.code} onDone={() => void check()} />
    case 'login':
      return <Login onDone={() => void check()} />
    case 'app':
      return (
        <SettingsProvider initial={gate.settings}>
          <BrowserRouter>
            <Routes>
              <Route element={<AppShell onLogout={logout} />}>
                <Route index element={<Dashboard />} />
                <Route path="holdings" element={<Holdings />} />
                <Route path="transactions" element={<Transactions />} />
                <Route path="prices" element={<Prices />} />
                <Route path="sources" element={<Sources />} />
                <Route path="stats" element={<Stats />} />
                <Route path="reports" element={<Reports />} />
                <Route path="settings" element={<Settings />} />
                <Route path="system" element={<SystemStatus />} />
                <Route path="more" element={<More onLogout={logout} />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Route>
            </Routes>
          </BrowserRouter>
        </SettingsProvider>
      )
  }
}
