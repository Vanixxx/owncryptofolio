import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Segmented } from '../../components/ui'

export type TxView = 'compact' | 'cards'

/** Compact lines or full cards, remembered per place; the phone starts compact (Vanixxx, 2026-10-22). */
export function useTxView(key: string) {
  const [view, setState] = useState<TxView>(() => {
    try {
      const v = localStorage.getItem(key)
      if (v === 'compact' || v === 'cards') return v
    } catch { /* private mode */ }
    return window.matchMedia('(min-width: 768px)').matches ? 'cards' : 'compact'
  })
  const set = (v: TxView) => {
    setState(v)
    try { localStorage.setItem(key, v) } catch { /* private mode */ }
  }
  return [view, set] as const
}

export function TxViewSwitch({ value, onChange }: { value: TxView; onChange: (v: TxView) => void }) {
  const { t } = useTranslation()
  return (
    <Segmented label={t('merged.view')} value={value} onChange={onChange}
      options={(['compact', 'cards'] as const).map((v) => ({ value: v, label: t(`merged.views.${v}`) }))} />
  )
}
