import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import de from './locales/de.json'
import en from './locales/en.json'

// Adding a language: add locales/<code>.json, register it here and in the backend
// settings registry (general.language). The parity test lists missing keys.
export const LANGUAGES = { de: 'de-DE', en: 'en-GB' } as const
export type Language = keyof typeof LANGUAGES

export const resources = { de: { translation: de }, en: { translation: en } }

function initialLanguage(): Language {
  try {
    const stored = JSON.parse(localStorage.getItem('ocf.appearance') || '{}').language
    if (stored in LANGUAGES) return stored
  } catch { /* storage unavailable */ }
  return navigator.language.toLowerCase().startsWith('de') ? 'de' : 'en'
}

void i18n.use(initReactI18next).init({
  resources,
  lng: initialLanguage(),
  fallbackLng: 'de',
  interpolation: { escapeValue: false },
})

export const locale = () => LANGUAGES[(i18n.language as Language) ?? 'de'] ?? 'de-DE'
export default i18n
