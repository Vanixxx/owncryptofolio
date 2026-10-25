import { cx } from '../../lib/cx'

/** A labelled on/off switch. */
export function Toggle({ id, label, checked, onChange }: {
  id: string; label: string; checked: boolean; onChange: (v: boolean) => void
}) {
  return (
    <label htmlFor={id} className="inline-flex cursor-pointer items-center gap-2 text-sm">
      <button id={id} type="button" role="switch" aria-checked={checked} onClick={() => onChange(!checked)}
        className={cx('relative h-6 w-10 rounded-full border-0 transition-colors', checked ? 'accent-fill' : 'bg-surface-2')}>
        <span className={cx('absolute top-0.5 h-5 w-5 rounded-full bg-fg transition-all', checked ? 'left-[18px]' : 'left-0.5')} />
      </button>
      {label}
    </label>
  )
}
