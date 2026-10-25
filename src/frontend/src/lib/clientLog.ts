/** The browser's errors and warnings go to the backend log (ADR 0047): one place to look,
 * live on the system page. Sent in small batches; nothing is sent before login (401 drops). */

type Line = { level: 'WARNING' | 'ERROR'; message: string; page: string }

const queue: Line[] = []
let sent = 0, minute = 0
let timer: ReturnType<typeof setTimeout> | undefined

function text(v: unknown): string {
  if (v instanceof Error) return `${v.name}: ${v.message}${v.stack ? `\n${v.stack.split('\n').slice(1, 6).join('\n')}` : ''}`
  if (typeof v === 'string') return v
  try { return JSON.stringify(v) } catch { return String(v) }
}

function flush() {
  timer = undefined
  const lines = queue.splice(0, 50)
  if (!lines.length) return
  // plain fetch: a failing send must not log itself again
  void fetch('/api/system/logs/client', {
    method: 'POST', credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(lines),
  }).catch(() => {})
}

export function clientLog(level: Line['level'], ...parts: unknown[]) {
  // at most 30 lines a minute: an error in a render loop must not flood the log
  const now = Math.floor(Date.now() / 60000)
  if (now !== minute) { minute = now; sent = 0 }
  if (++sent > 30) return
  queue.push({ level, message: parts.map(text).join(' ').slice(0, 4000), page: location.pathname + location.search })
  timer ??= setTimeout(flush, 2000)
}

export function startClientLog() {
  window.addEventListener('error', (e) => clientLog('ERROR', e.error ?? e.message))
  window.addEventListener('unhandledrejection', (e) => clientLog('ERROR', e.reason))
  for (const [name, level] of [['error', 'ERROR'], ['warn', 'WARNING']] as const) {
    const original = console[name].bind(console)
    console[name] = (...args: unknown[]) => {
      original(...args)
      clientLog(level, ...args)
    }
  }
}
