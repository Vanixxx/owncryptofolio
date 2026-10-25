import { createContext, useContext } from 'react'
import i18n from '../i18n'
import type { Settings, Style } from '../lib/api'
import { applyAppearance, applyIcon } from './appearance'

export const STYLES: Style[] = ['night', 'neon', 'terminal', 'graphite', 'rose', 'contrast', 'amethyst', 'sand', 'ios']
/** A colour of one's own per style (Vanixxx, 2026-10-21); "default" is the style's own. */
export const ACCENTS = ['default', 'petrol', 'blue', 'purple', 'amber', 'green', 'rose', 'red'] as const

export type SettingsCtx = {
  settings: Settings
  /** what the server has stored: data loaded with it matches (shown ones switch at once) */
  saved: Settings
  update: (changes: Partial<Settings>) => Promise<void>
}
export const SettingsContext = createContext<SettingsCtx | null>(null)

export function useSettings() {
  const ctx = useContext(SettingsContext)
  if (!ctx) throw new Error('useSettings outside SettingsProvider')
  return ctx
}

export function applySettings(s: Settings) {
  applyAppearance({
    style: s['appearance.style'],
    theme: s['appearance.theme'],
    accent: s['appearance.accents']?.[s['appearance.style']] ?? 'default',
    language: s['general.language'],
  })
  if (i18n.language !== s['general.language']) void i18n.changeLanguage(s['general.language'])
  document.documentElement.lang = s['general.language']
  // the icon: favicon, the logo up left and a fresh "add to home screen" (Vanixxx, 2026-10-21)
  applyIcon(s['appearance.icon'])
}
