import { useEffect, type ReactNode } from 'react'
import { createPortal } from 'react-dom'

/** A window over the page (Vanixxx, 2026-10-08: adding a transaction made him scroll back to
 * the top, and back down again). The page stays where it is underneath. Esc closes; a click
 * beside it does not, so a half-filled form is not lost by accident. Phone: a full sheet. */
export function Modal({ label, onClose, children }: { label: string; onClose: () => void; children: ReactNode }) {
  useEffect(() => {
    const key = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', key)
    return () => document.removeEventListener('keydown', key)
  }, [onClose])
  return createPortal(
    <div className="fixed inset-0 z-50 grid overscroll-contain bg-black/55 backdrop-blur-sm md:place-items-center md:p-6" role="presentation">
      <div role="dialog" aria-modal="true" aria-label={label}
        className="h-full w-full overflow-y-auto overscroll-contain bg-bg p-3 md:h-auto md:max-h-[90vh] md:max-w-3xl md:rounded-card md:border md:border-line md:p-4 md:shadow-2xl">
        {children}
      </div>
    </div>,
    document.body,
  )
}
