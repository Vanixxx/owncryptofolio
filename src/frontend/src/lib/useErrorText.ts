import { useTranslation } from 'react-i18next'
import { ApiError } from './api'

/** Turns an API error code into the user's language; unknown codes stay readable. */
export function useErrorText() {
  const { t } = useTranslation()
  return (err: unknown): string => {
    const code = err instanceof ApiError ? err.code : 'unknown'
    const params = err instanceof ApiError ? { ...err.params } : {}
    // a side of a movement is named in the user's words, not as "incoming"
    if (typeof params.side === 'string') params.side = t(`manual.sides.${params.side}`, { defaultValue: params.side })
    return t(`errors.${code}`, { ...params, code, defaultValue: t('errors.unknown', { code }) })
  }
}

/** A stored job message is either an error code or the source's own words. */
export function useMessageText() {
  const { t, i18n } = useTranslation()
  return (message: string): string =>
    /^[a-z_]+\.[a-z_]+$/.test(message) && i18n.exists(`errors.${message}`) ? t(`errors.${message}`) : message
}
