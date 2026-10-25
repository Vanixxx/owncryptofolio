import type { SourceAlert } from './api'
import { date } from './format'

/** One line per threat to complete data: expiring or expired exchange keys, a look-back
 * running out, failing fetches (Vanixxx, 2026-10-05). */
export function alertText(t: (k: string, o?: Record<string, unknown>) => string, a: SourceAlert, name: string, message: string) {
  return t(`alerts.${a.kind}`, { source: name, date: a.date ? date(a.date, 'UTC') : '', count: a.days, message })
}
