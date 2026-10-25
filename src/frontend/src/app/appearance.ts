import type { Style, Theme } from '../lib/api'

export type Appearance = { style: Style; theme: Theme; accent?: string; language?: 'de' | 'en' }
const KEY = 'ocf.appearance'
const dark = window.matchMedia('(prefers-color-scheme: dark)')

/** Sets data-style / data-mode on <html>; the token CSS does the rest (ADR 0031). */
export function applyAppearance(a: Appearance) {
  const root = document.documentElement
  root.dataset.style = a.style
  root.dataset.accent = a.accent ?? 'default'
  root.dataset.mode = a.theme === 'dark' || (a.theme === 'system' && dark.matches) ? 'dark' : 'light'
  const bg = getComputedStyle(root).getPropertyValue('--bg').trim()
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', bg)
  try {
    localStorage.setItem(KEY, JSON.stringify(a))
  } catch { /* storage unavailable: only the pre-paint cache is lost */ }
}

const ICON_KEY = 'ocf.icon'

/** The app icon (Vanixxx, 2026-10-21) as favicon too; remembered for the login page. */
export function applyIcon(icon: string) {
  document.querySelector('link[rel="icon"]')?.setAttribute('href', `/app-icons/${icon}-192.png`)
  document.querySelector('link[rel="icon"]')?.setAttribute('type', 'image/png')
  document.querySelector('link[rel="apple-touch-icon"]')?.setAttribute('href', `/apple-touch-icon.png?i=${icon}`)
  try { localStorage.setItem(ICON_KEY, icon) } catch { /* storage unavailable: E5 next time */ }
}

export function cachedIcon(): string {
  try { return localStorage.getItem(ICON_KEY) || 'E5' } catch { return 'E5' }
}

export function cachedAppearance(): Appearance {
  try {
    const a = JSON.parse(localStorage.getItem(KEY) || '{}')
    return { style: a.style ?? 'night', theme: a.theme ?? 'system', accent: a.accent, language: a.language }
  } catch {
    return { style: 'night', theme: 'system' }
  }
}

export function onSystemThemeChange(fn: () => void) {
  dark.addEventListener('change', fn)
  return () => dark.removeEventListener('change', fn)
}
