import { useEffect, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'

/** A page's own buttons in the phone's top bar, left of the currency switch (Vanixxx,
 * 2026-10-19: on the prices page "fetch" belongs up there like on the other pages). */
export function TopBarActions({ children }: { children: ReactNode }) {
  const [slot, setSlot] = useState<HTMLElement | null>(null)
  useEffect(() => setSlot(document.getElementById('topbar-actions')), [])
  return slot ? createPortal(children, slot) : null
}
