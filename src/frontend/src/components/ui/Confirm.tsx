import { useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '.'

/** Inline confirmation instead of a browser dialog: the button turns into a question. */
export function Confirm({ label, question, onConfirm, disabled }: {
  label: ReactNode; question: string; onConfirm: () => void; disabled?: boolean
}) {
  const { t } = useTranslation()
  const [asking, setAsking] = useState(false)
  if (!asking) {
    return <Button variant="ghost" disabled={disabled} onClick={() => setAsking(true)}>{label}</Button>
  }
  return (
    <span className="flex flex-wrap items-center gap-2 text-sm">
      <span>{question}</span>
      <Button variant="primary" onClick={() => { setAsking(false); onConfirm() }}>{t('pages.sources.confirm')}</Button>
      <Button variant="ghost" onClick={() => setAsking(false)}>{t('pages.sources.cancel')}</Button>
    </span>
  )
}
