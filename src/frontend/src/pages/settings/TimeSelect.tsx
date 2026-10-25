const pad = (n: number) => String(n).padStart(2, '0')
const HOURS = Array.from({ length: 24 }, (_, i) => pad(i))
const MINUTES = Array.from({ length: 12 }, (_, i) => pad(i * 5))

/** Two selects instead of <input type=time>: browsers show AM/PM by OS locale. */
export function TimeSelect({ id, label, value, onChange }: {
  id: string; label: string; value: string; onChange: (v: string) => void
}) {
  const [h, m] = value.split(':')
  const cls = 'num rounded-ctl border border-line bg-surface-2 px-2 py-2 text-base text-fg'
  return (
    <div className="grid gap-1.5">
      <span className="label" id={`${id}-label`}>{label}</span>
      <div className="flex items-center gap-1" role="group" aria-labelledby={`${id}-label`}>
        <select id={`${id}-h`} aria-label={`${label} h`} value={h} onChange={(e) => onChange(`${e.target.value}:${m}`)} className={cls}>
          {HOURS.map((o) => <option key={o} value={o}>{o}</option>)}
        </select>
        <span>:</span>
        <select id={`${id}-m`} aria-label={`${label} m`} value={m} onChange={(e) => onChange(`${h}:${e.target.value}`)} className={cls}>
          {MINUTES.map((o) => <option key={o} value={o}>{o}</option>)}
        </select>
      </div>
    </div>
  )
}
