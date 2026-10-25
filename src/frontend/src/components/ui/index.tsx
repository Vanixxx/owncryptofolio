import { ChevronDown } from 'lucide-react'
import { useContext, useState, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { cx } from '../../lib/cx'
import { SettingsContext } from '../../app/settings'
import { cachedIcon } from '../../app/appearance'

export function Card({ title, action, children, className, fold }: {
  title?: ReactNode; action?: ReactNode; children?: ReactNode; className?: string
  /** folds to its title, closed at first; the key keeps the choice in this browser */
  fold?: string
}) {
  const [open, setOpen] = useState(() => !fold || remembered(fold))
  const toggle = (e?: { stopPropagation: () => void }) => {
    e?.stopPropagation()
    setOpen(!open)
    try { if (fold) localStorage.setItem(fold, open ? '0' : '1') } catch { /* private mode: fine */ }
  }
  return (
    // closed, the whole card opens it (Vanixxx, 2026-10-19); open, only the title closes it
    <section className={cx('card grid content-start gap-3', fold && !open && 'cursor-pointer', className)}
      onClick={fold && !open ? () => toggle() : undefined}>
      {(title || action) && (
        <div className="flex flex-wrap items-center justify-between gap-2">
          {title && (fold ? (
            <button type="button" onClick={toggle} aria-expanded={open}
              className="flex min-w-0 items-center gap-2 border-0 bg-transparent p-0 text-left text-fg">
              <ChevronDown size={18} aria-hidden="true" className={cx('shrink-0 text-muted transition-transform', !open && '-rotate-90')} />
              <h2 className="m-0 text-base font-semibold">{title}</h2>
            </button>
          ) : <h2 className="m-0 text-base font-semibold">{title}</h2>)}
          {open && action}
        </div>
      )}
      {open && children}
    </section>
  )
}

function remembered(key: string): boolean {
  try { return localStorage.getItem(key) === '1' } catch { return false }
}

export function PageHeader({ title, subtitle, aside }: { title: string; subtitle?: string; aside?: ReactNode }) {
  // on the phone the title sits in the top bar and the explanation goes: more room
  return (
    <header className="hidden items-start justify-between gap-4 md:flex">
      <div className="grid gap-1">
        <h1 className="m-0 text-2xl font-bold tracking-tight [text-wrap:balance]">{title}</h1>
        {subtitle && <p className="m-0 text-sm text-muted">{subtitle}</p>}
      </div>
      {aside}
    </header>
  )
}

export function Segmented<T extends string>({ options, value, onChange, label }: {
  options: { value: T; label: ReactNode }[]; value: T; onChange: (v: T) => void; label: string
}) {
  return (
    <div role="group" aria-label={label} className="inline-flex flex-wrap gap-0.5 justify-self-start rounded-ctl bg-surface-2 p-[3px]">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          aria-pressed={o.value === value}
          onClick={() => onChange(o.value)}
          className={cx(
            'rounded-ctl border-0 px-3 py-1.5 text-[0.82rem]',
            o.value === value ? 'accent-fill font-semibold' : 'bg-transparent text-muted hover:text-fg',
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

export function Button({ variant = 'primary', className, ...props }:
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'ghost' }) {
  return (
    <button
      {...props}
      className={cx(
        'inline-flex items-center justify-center gap-2 rounded-ctl px-4 py-2.5 text-sm font-semibold disabled:opacity-50',
        variant === 'primary' ? 'accent-fill border-0' : 'border border-line bg-transparent text-fg hover:bg-surface-2',
        className,
      )}
    />
  )
}

export function Field({ label, id, ...props }: InputHTMLAttributes<HTMLInputElement> & { label: string; id: string }) {
  return (
    <label htmlFor={id} className="grid gap-1.5">
      <span className="label">{label}</span>
      <input
        id={id}
        {...props}
        className="w-full rounded-ctl border border-line bg-surface-2 px-3 py-2.5 text-base text-fg outline-none focus:border-accent"
      />
    </label>
  )
}

export function ErrorText({ children }: { children?: ReactNode }) {
  if (!children) return null
  return <p role="alert" className="m-0 text-sm text-down">{children}</p>
}

export function Row({ label, children }: { label: ReactNode; children: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-t border-line py-2.5 text-sm first:border-t-0">
      <span className="text-muted">{label}</span>
      <span className="min-w-0 text-right [overflow-wrap:anywhere]">{children}</span>
    </div>
  )
}

export function StatusPill({ ok, children }: { ok: boolean; children: ReactNode }) {
  return (
    <span className={cx('inline-flex items-center gap-1.5 text-sm font-medium', ok ? 'text-up' : 'text-warn')}>
      <span aria-hidden="true">{ok ? '●' : '▲'}</span>
      {children}
    </span>
  )
}

/** Logo with the app name — or, on the phone, with the page title (Vanixxx, 2026-10-06:
 * the header took too much room for a name you know). */
export function Brand({ label }: { label?: string }) {
  const { t } = useTranslation()
  // the app icon chosen in the settings, also before login (cached in the browser)
  const icon = useContext(SettingsContext)?.settings['appearance.icon'] ?? cachedIcon()
  return (
    <div className="flex items-center gap-2.5 font-bold tracking-tight">
      <img src={`/app-icons/${icon}-180.png`} alt="" width={28} height={28} className="h-7 w-7 shrink-0 rounded-ctl" />
      <span className={label ? 'truncate text-xl' : undefined}>{label ?? t('app.name')}</span>
    </div>
  )
}
