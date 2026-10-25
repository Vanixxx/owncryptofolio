import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { api, type Settings } from '../lib/api'
import { onSystemThemeChange } from './appearance'
import { SettingsContext, applySettings } from './settings'

export function SettingsProvider({ initial, children }: { initial: Settings; children: ReactNode }) {
  const [settings, setSettings] = useState(initial)
  const [saved, setSaved] = useState(initial)

  useEffect(() => applySettings(settings), [settings])
  useEffect(() => onSystemThemeChange(() => applySettings(settings)), [settings])

  const update = useCallback(async (changes: Partial<Settings>) => {
    const before = settings
    setSettings({ ...settings, ...changes }) // optimistic: style switches feel instant
    try {
      const stored = await api.updateSettings(changes)
      setSettings(stored)
      setSaved(stored)
    } catch (err) {
      setSettings(before)
      throw err
    }
  }, [settings])

  return <SettingsContext.Provider value={{ settings, saved, update }}>{children}</SettingsContext.Provider>
}
