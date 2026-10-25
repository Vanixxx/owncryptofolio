import { ChevronDown } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useSettings } from '../../app/settings'
import { Button, Card, Segmented } from '../../components/ui'
import { SearchField } from '../../components/ui/SearchField'
import { Toggle } from '../../components/ui/Toggle'
import { api, type LogLevel, type LogLine } from '../../lib/api'
import { cx } from '../../lib/cx'

const LEVELS: LogLevel[] = ['DEBUG', 'INFO', 'WARNING', 'ERROR']
const RANK: Record<LogLevel, number> = { DEBUG: 0, INFO: 1, WARNING: 2, ERROR: 3 }
const KEEP = 2000
const EVERY_MS = 2000
const COLOR: Record<LogLevel, string> = { DEBUG: 'text-muted', INFO: 'text-fg', WARNING: 'text-warn', ERROR: 'text-down' }

type Origin = 'all' | 'backend' | 'frontend'

/** The log live (ADR 0047): backend and browser lines from the server's memory, asked for
 * every two seconds while the card is open. The level set here applies at once. Closed at
 * first (Vanixxx, 2026-10-18): it is for looking into a problem, not for every visit. */
export function LogsCard() {
  const { t } = useTranslation()
  const { settings, update } = useSettings()
  const tz = settings['general.timezone']
  const [lines, setLines] = useState<LogLine[]>([])
  const [open, setOpen] = useState(false)
  const [live, setLive] = useState(true)
  const [origin, setOrigin] = useState<Origin>('all')
  const [min, setMin] = useState<LogLevel>('DEBUG')
  const [query, setQuery] = useState('')
  const [failed, setFailed] = useState(false)
  const last = useRef(0)
  const box = useRef<HTMLDivElement>(null)
  const atEnd = useRef(true)

  useEffect(() => {
    if (!open || !live) return
    let stop = false
    let timer: ReturnType<typeof setTimeout> | undefined
    const poll = async () => {
      try {
        const r = await api.logs(last.current)
        if (stop) return
        // the server started anew: its counter begins again, so do we
        if (r.last < last.current) {
          last.current = 0
          setLines([])
        } else if (r.lines.length) {
          last.current = r.lines[r.lines.length - 1].seq
          setLines((old) => [...old, ...r.lines].slice(-KEEP))
        }
        setFailed(false)
      } catch {
        if (!stop) setFailed(true)
      }
      if (!stop && !document.hidden) timer = setTimeout(poll, EVERY_MS)
      else if (!stop) timer = setTimeout(poll, EVERY_MS * 5)
    }
    void poll()
    return () => {
      stop = true
      clearTimeout(timer)
    }
  }, [open, live])

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase()
    return lines.filter((l) => RANK[l.level] >= RANK[min] && (origin === 'all' || l.origin === origin)
      && (!q || l.message.toLowerCase().includes(q) || l.logger.toLowerCase().includes(q)))
  }, [lines, min, origin, query])

  // follows the newest line, unless one scrolled up to read
  useEffect(() => {
    const el = box.current
    if (el && atEnd.current) el.scrollTop = el.scrollHeight
  }, [shown])

  const time = useMemo(() => new Intl.DateTimeFormat(undefined, {
    timeZone: tz, hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
  }), [tz])
  const day = (at: string) => new Intl.DateTimeFormat(undefined, { timeZone: tz, day: '2-digit', month: '2-digit' }).format(new Date(at))
  const save = () => {
    const body = shown.map((l) => `${l.at} ${l.level} [${l.logger}] ${l.message}`).join('\n')
    const a = document.createElement('a')
    a.href = URL.createObjectURL(new Blob([body], { type: 'text/plain' }))
    a.download = `owncryptofolio-log-${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.txt`
    a.click()
    URL.revokeObjectURL(a.href)
  }

  return (
    <Card className="md:col-span-2">
      <button type="button" aria-expanded={open} onClick={() => setOpen(!open)}
        className="-m-1 flex items-center justify-between gap-2 rounded-ctl border-0 bg-transparent p-1 text-left text-fg">
        <h2 className="m-0 text-base font-semibold">{t('system.logs.title')}</h2>
        <ChevronDown size={18} aria-hidden="true" className={cx('text-muted transition-transform', !open && '-rotate-90')} />
      </button>
      {open && <div className="grid gap-3">
        <div className="flex flex-wrap items-end gap-x-4 gap-y-2">
          <label htmlFor="log-level" className="grid gap-1">
            <span className="label">{t('system.logs.level')}</span>
            <select id="log-level" value={settings['system.log_level']}
              onChange={(e) => void update({ 'system.log_level': e.target.value as LogLevel })}
              className="rounded-ctl border border-line bg-surface-2 px-3 py-1.5 text-sm text-fg">
              {LEVELS.map((l) => <option key={l} value={l}>{t(`system.logs.levels.${l}`)}</option>)}
            </select>
          </label>
          <label htmlFor="log-min" className="grid gap-1">
            <span className="label">{t('system.logs.show')}</span>
            <select id="log-min" value={min} onChange={(e) => setMin(e.target.value as LogLevel)}
              className="rounded-ctl border border-line bg-surface-2 px-3 py-1.5 text-sm text-fg">
              {LEVELS.map((l) => <option key={l} value={l}>{t(`system.logs.from.${l}`)}</option>)}
            </select>
          </label>
          <Segmented label={t('system.logs.origin')} value={origin} onChange={setOrigin}
            options={(['all', 'backend', 'frontend'] as const).map((o) => ({ value: o, label: t(`system.logs.origins.${o}`) }))} />
          <SearchField value={query} onChange={setQuery} placeholder={t('system.logs.search')} className="min-w-40 flex-1" />
        </div>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <Toggle id="log-live" label={t('system.logs.live')} checked={live} onChange={setLive} />
          <Button variant="ghost" onClick={() => setLines([])}>{t('system.logs.clear')}</Button>
          <Button variant="ghost" onClick={save} disabled={!shown.length}>{t('system.logs.save')}</Button>
          <span className="text-xs text-muted">
            {failed ? <span className="text-down">{t('system.logs.failed')}</span> : t('system.logs.count', { count: shown.length })}
          </span>
        </div>
        <div ref={box} role="log" aria-live="off"
          onScroll={(e) => {
            const el = e.currentTarget
            atEnd.current = el.scrollHeight - el.scrollTop - el.clientHeight < 24
          }}
          className="max-h-[60vh] min-h-48 overflow-auto rounded-ctl bg-surface-2/60 p-2 font-mono text-[0.72rem] leading-snug sm:text-xs">
          {shown.length === 0 && <p className="m-0 p-2 text-muted">{t('system.logs.empty')}</p>}
          {shown.map((l) => (
            <div key={l.seq} className="grid grid-cols-[auto_1fr] gap-x-2 border-b border-line/40 py-0.5 last:border-b-0">
              <span className="num whitespace-nowrap text-muted" title={l.at}>
                <span className="hidden sm:inline">{day(l.at)} </span>{time.format(new Date(l.at))}
              </span>
              <span className="min-w-0">
                <b className={cx('mr-1.5 font-semibold', COLOR[l.level])}>{l.level}</b>
                <span className={cx('mr-1.5', l.origin === 'frontend' ? 'text-accent' : 'text-muted')}>{l.logger}</span>
                <span className="whitespace-pre-wrap break-words">{l.message}</span>
              </span>
            </div>
          ))}
        </div>
        <p className="m-0 text-xs text-muted">{t('system.logs.hint')}</p>
      </div>}
    </Card>
  )
}
