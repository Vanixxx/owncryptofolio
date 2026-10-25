// The one place that talks to the backend. Errors arrive as code + params (ADR 0026).

import { clientLog } from './clientLog'

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly params: Record<string, unknown>
  constructor(status: number, code: string, params: Record<string, unknown> = {}) {
    super(code)
    this.status = status
    this.code = code
    this.params = params
  }
}

let onSessionLost: (() => void) | null = null
export function setSessionLostHandler(fn: (() => void) | null) {
  onSessionLost = fn
}
let onDbLost: (() => void) | null = null
/** The database is not reachable (power cut, container not up yet): the app shows it and
 * keeps trying (Vanixxx, 2026-10-15). */
export function setDbLostHandler(fn: (() => void) | null) {
  onDbLost = fn
}

let restoring = false
/** While a restore runs, "no database" answers are expected and must not switch the page. */
export function setRestoring(v: boolean) { restoring = v }

async function request<T>(method: string, path: string, body?: unknown, extra?: Record<string, string>): Promise<T> {
  let res: Response
  const form = body instanceof FormData
  try {
    res = await fetch(path, {
      method,
      credentials: 'same-origin',
      headers: { ...(body === undefined || form ? {} : { 'Content-Type': 'application/json' }), ...extra },
      body: body === undefined ? undefined : form ? body : JSON.stringify(body),
    })
  } catch {
    throw new ApiError(0, 'network')
  }
  if (res.ok) return (res.status === 204 ? undefined : await res.json()) as T
  let code = `http_${res.status}`
  let params: Record<string, unknown> = {}
  try {
    const data = await res.json()
    if (data?.error?.code) ({ code, params = {} } = data.error)
  } catch { /* not JSON */ }
  if (res.status === 401 && code === 'auth.required') onSessionLost?.()
  // during a restore the database is away on purpose: the page stays (Vanixxx, 2026-10-21)
  if (res.status === 503 && code === 'db.unavailable' && !restoring) onDbLost?.()
  // a server error the backend logged already; the page it hit says where it came from
  if (res.status >= 500 && code !== 'db.unavailable') clientLog('ERROR', `${method} ${path}: ${res.status} ${code}`)
  throw new ApiError(res.status, code, params)
}

export type Settings = {
  'appearance.style': Style
  'appearance.theme': Theme
  'appearance.accents': Partial<Record<Style, Accent>>
  'appearance.icon': string
  'general.language': 'de' | 'en'
  'general.currency': 'EUR' | 'USD'
  'general.timezone': string
  'backup.enabled': boolean
  'backup.time': string
  'backup.keep_daily': number
  'backup.keep_monthly': number
  'fetch.enabled': boolean
  'fetch.time': string
  'prices.enabled': boolean
  'prices.time': string
  'prices.latest_minutes': number
  'prices.source_order': ('yahoo' | 'bitget' | 'binance')[]
  'tax.method': TaxMethod
  'tax.airdrop_taxable': boolean
  'report.name': string
  'report.address': string
  'report.tax_number': string
  'system.log_level': LogLevel
  'mcp.enabled': boolean
  'api.enabled': boolean
}

export type TokenKind = 'mcp' | 'api'
export type TokenLevel = 'read' | 'edit'
export type AccessToken = { id: number; name: string; kind: TokenKind; level: TokenLevel; created_at: string; last_used_at: string | null }
export type McpStatus = {
  enabled: boolean; api_enabled: boolean; tokens: AccessToken[]
  last_call: { tool: string; token: string; at: string } | null
}

export type LogLevel = 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR'
export type LogLine = { seq: number; at: string; level: LogLevel; logger: string; origin: 'backend' | 'frontend'; message: string }

export type ChangeSpan = 'd1' | 'h24' | 'd7' | 'd30' | 'd90'
export type StatsData = {
  currency: 'EUR' | 'USD'
  fees: { year: number; place: string | null; value: string }[]
  incomes: { month: string; kind: string; value: string }[]
  futures: { months: { month: string; pnl: string; funding: string; fees: string; bonus: string; net: string }[]
    positions: number; wins: number; best: string | null; worst: string | null }
  activity: { month: string; trades: number; transfers: number; deposits: string; withdrawals: string }[]
  benchmark: { day: string; value: string | null }[]
  spot: { realized: string; unrealized: string | null; income: string; sales: number; wins: number; best: string | null; worst: string | null
    months: { month: string; gain: string }[] }
  health: { key: string; count: number; to: string; assets?: string[] }[]
}
export type TaxMethod = 'fifo' | 'lifo'
/** One year of the § 23 loss carry (ADR 0045); losses and carries as positive amounts. */
export type TaxCarryRow = { year: number; net: string; limit: string; taxable: boolean; start: string; used: string
  back_in: string; back_out: string; loss: string; remaining: string; end: string
  assessed: string | null; note: string | null; diff: string | null; running: boolean }
/** Source of funds (ADR 0046). */
export type OriginStep = { row: number; kind: string; at: string; place: string | null; to: string | null; asset: string; qty: string; value: string
  into_asset?: string; into_qty?: string }
export type OriginNode = Partial<OriginStep> & { kind: string; share: string; tx?: string | null; detail?: string
  count?: number; mix?: Record<string, string>; children?: OriginNode[] }
export type PlannedOption = { source: number; place: string | null; asset: string; qty: string }
export type OriginFlowNode = { id: string; kind: string; goal?: boolean; place?: string | null; from?: string; to?: string; count?: number
  at?: string; asset?: string; qty?: string; detail?: string }
export type OriginFlowData = { nodes: OriginFlowNode[]; links: { source: string; target: string; value: string; loss: boolean }[] }
export type OriginData = {
  target: OriginStep & { amount: string }; method: TaxMethod
  mix: { kind: string; value: string; share: string }[]
  tree: OriginNode; steps: (OriginStep & { share: string; tx: string | null; channel?: string | null })[]
  lost: { count: number; assets: string[] }
  overview?: { from: string; to: string; transactions: number; channels: Record<string, number>
    sources: { place: string | null; kind: string; address: string | null; count: number; channels: Record<string, number> }[] }
  deposits?: (OriginStep & { share: string; tx: string | null; channel: string | null; detail?: string })[]
  diagram?: { simple: OriginFlowData; full: OriginFlowData }
  coins?: { asset: string; qty: string; value: string; cost: string; priced: boolean; mix: Record<string, string> }[]
}
export type TaxSummary = {
  year: number; method: TaxMethod; airdrop_taxable: boolean
  s23: { gains: string; losses: string; net: string; limit: string; taxable: boolean; tax_free_gain: string; share?: string
    count: number; count_taxed: number; estimated: number; unvalued: number }
  s22: { total: string; limit: string; taxable: boolean; count: number; unvalued: number; by_kind?: Record<string, string>; share?: string }
  s20: { gains: string; losses: string; funding_in: string; funding_out: string; fees: string; net: string; count: number
    bonus?: string; kap_gains?: string; kap_losses?: string }
  forms?: { form: 'SO' | 'KAP'; line: number | null; key: 's23' | 's22' | 'kap19' | 'kap21' | 'kap24'; value: string }[]
  lost: { cost: string; count: number; unknown_cost: number }
  carry?: { year: TaxCarryRow | null; rows: TaxCarryRow[]; opening: { year: number; amount: string; note: string | null } | null }
  open: { uncovered: number; open_sends: number; unvalued_assets: string[] }
}
export type TaxDisposal = { asset: string; place: string | null; sold: string; acquired: string; days: number; qty: string
  proceeds: string | null; cost: string; gain: string | null; tax_free: boolean; estimated: boolean
  how: 'trade' | 'external' | 'fee' | 'futures'; row: number; origin: number }
export type TaxIncome = { asset: string; place: string | null; at: string; qty: string; value: string | null; kind: string; row: number }
export type TaxFutures = { place: string | null; at: string; kind: 'pnl' | 'funding' | 'fee'; asset: string; amount: string; value: string | null; row: number }
export type TaxLoss = { asset: string; place: string | null; at: string; acquired: string | null; qty: string; cost: string | null; row: number }
export type TaxUncovered = { asset: string; place: string | null; at: string; qty: string; proceeds: string | null
  reason: 'no_lot' | 'transfer' | 'migration' | 'open_send'; row: number }
export type TaxLot = { asset: string; place: string | null; market: string | null; qty: string; acquired: string; cost: string
  free_from: string; estimated: boolean; origin: number }
export type TaxReport = {
  summary: TaxSummary; digest: string
  lines: { by_source?: TaxBySource[]; holdings?: TaxHoldingChange[]; disposals: TaxDisposal[]; incomes: TaxIncome[]; futures: TaxFutures[]; losses: TaxLoss[]
    uncovered: TaxUncovered[]; year_end: TaxLot[] }
  frozen: TaxKept[]
}
export type TaxBySource = { place: string | null; gains: string; losses: string; net: string; free_gains: string; free_losses: string; free_net: string }
export type TaxHoldingChange = { place: string | null; asset: string; start: string; in: string; out: string; end: string; value: string | null }
export type TaxKept = { id: number; created_at: string; method: TaxMethod; same: boolean; note: string | null; summary: TaxSummary }
export type TaxCompare = {
  old: { id: number; created_at: string; method: TaxMethod; note: string | null }; new: string | null
  figures: { pot: 's23' | 's22' | 's20' | 'lost'; key: string; old: string | null; new: string | null; delta: string | null }[]
  changes: { cat: 'disposals' | 'incomes' | 'futures' | 'losses' | 'uncovered' | 'year_end'; state: 'added' | 'removed' | 'changed'
    asset: string; at: string | null; row: number | null; old: { qty: string; amount: string | null } | null
    new: { qty: string; amount: string | null } | null }[]
  lines_known: boolean
}
export type TaxMoved = { asset: string; qty: string; acquired: string; cost: string; origin: number; free_from: string }
export type TaxRows = {
  method: TaxMethod; sold: TaxDisposal[]; incomes: TaxIncome[]; futures: TaxFutures[]; losses: TaxLoss[]
  uncovered: TaxUncovered[]; created: TaxLot[]; moved: TaxMoved[]
  later: { sold: TaxDisposal[]; losses: TaxLoss[]; open: TaxLot[] }
}
export type TaxHolding = { qty: string; free: string; days: number; next_free: string | null }
export type TaxFreeCoin = { asset: string; free: string; taxed: string; value_free: string | null; value_taxed: string | null; gain_free: string | null; gain_taxed: string | null; next_free: string | null; next_qty: string | null }
export type TaxFree = { currency: string; coins: TaxFreeCoin[]; total: { value_free: string; value_taxed: string; gain_free: string; gain_taxed: string } }
export type ServiceKey = { service: string; name: string; url: string; stored: boolean; used_by: string[] }

export type Channel = 'api' | 'file' | 'chain' | 'manual'
export type Provider = {
  provider: string
  name: string
  kind: 'exchange' | 'wallet'
  native_asset?: string | null
  channels: { plugin: string; channel: Channel; history_days: number | null; futures: boolean;
    expected_files: string[]; not_read: string[]; description: string; version: string; status: 'tested' | 'beta' }[]
  credentials: { fields: string[]; secret: string[]; multiline?: string[]; alternatives?: string[][] } | null
  address_pattern: string | null
  family: string | null
}
export type Wallet = { id: number; name: string }
export type BackupFile = { name: string; size: number; at: string; keys: boolean }
export type BackupInfo = { file: string; rows: number; sources: number; first: string | null; last: string | null; login: boolean; keys: boolean }
export type RestoreResult = { file: string; keys_restored: boolean; safety: string | null }
export type MappingForm = 'movement' | 'trade'
export type Mapping = {
  form: MappingForm; sheet: string | null; header_row: number; delimiter: string | null; decimal: '.' | ','
  date_format: string | null; timezone: string; columns: Record<string, string>; values: Record<string, string>
  income_kind: 'staking' | 'reward' | 'interest' | 'airdrop'; kind?: string | null
}
export type MappedInfo = {
  sheets: string[]; columns: string[]; rows: number; top: string[][]; sample: Record<string, string>[]
  distinct: Record<string, string[]>; mapping: Mapping; saved: boolean
}
export type MappedSide = [string | null, string | null]
export type MappedPreview = {
  read: number; new: number; duplicates: number; skipped: number; rejected: number
  problems: { row: number; message: string }[]; date_format: string | null
  rows: { row: number; at: string; kind: string; duplicate: boolean; incoming: MappedSide; outgoing: MappedSide; fee: MappedSide }[]
  data_from: string | null; data_to: string | null
}
export type SourceAlert = {
  source_id: number; kind: 'key_rejected' | 'history_at_risk' | 'fetch_failed'
  date: string | null; days: number; message?: string | null
}
export type ImportRun = {
  id: number; channel: Channel; label: string; status: string; read: number; added: number
  duplicates: number; rejected: number; changed?: number; problems: string[]; data_from: string | null
  data_to: string | null; created_at: string; revertible: boolean
}
type ChangeSide = { timestamp: string; kind: string; incoming: [string | null, string | null]; outgoing: [string | null, string | null]; fee: [string | null, string | null]; external_id: string | null }
/** A row the source delivered again with other values, waiting for a decision. */
export type SourceChange = { id: number; source_id: number; channel: Channel; raw_id: number; old: ChangeSide; new: ChangeSide; found_at: string | null }
export type Source = {
  id: number; provider: string; kind: 'exchange' | 'wallet'; label: string; address: string | null
  wallet_id: number | null; auto_fetch: boolean
  api_coverage: Partial<Record<'spot' | 'futures', string>>; credentials: string[]
  last_check: { at: string; ok: boolean; message: string | null } | null
  rows: number; runs: ImportRun[]; last_fetch: string | null
}
export type Preview = {
  file: string; read: number; new: number; duplicates: number; rejected: number
  problems: string[]; covered_by_api: number; kinds: Record<string, number>
  skipped: Record<string, number>
  data_from: string | null; data_to: string | null
}
export type Job = {
  id: number; kind: 'fetch' | 'backup' | 'prices' | 'fine'; source_id: number | null
  status: 'queued' | 'running' | 'done' | 'failed'
  progress: { step?: string; done?: number; total?: number; rows?: number }
  result: Record<string, unknown>; message: string | null
  created_at: string | null; started_at: string | null; finished_at: string | null
}
export type RawRow = {
  id: number; source_id: number; channel: Channel; timestamp: string; kind: string
  income_kind: string | null; market: 'spot' | 'futures'; instrument: string | null
  incoming: [string | null, string | null]; outgoing: [string | null, string | null]
  fee: [string | null, string | null]; external_id: string | null; comment: string | null
  counterparty: string | null; covered_by_api: boolean
  state: 'current' | 'replaced' | 'hidden'; edited: boolean; corrects: number | null
  /** merged view: changed by hand ("edited" mark), and where the original came from */
  modified?: boolean; origin?: Channel
  /** an extra of a transfer: when it was attached */
  attached_at?: string | null
  paid_by_card?: boolean
  /** Vanixxx's own note (merged view) */
  note?: string | null
  /** merged view: balance of each moved coin at its place right after this row; coins below zero */
  after?: Record<string, string>; short?: string[]
  /** money assumed paid in by card at this row: [fiat, amount] */
  auto_deposit?: [string, string] | null
  card?: boolean
}
export type HistoryEntry = ManualEntry & { channel: Channel; state: RawRow['state']; recorded_at: string }
export type BackupRun = {
  id: number; trigger: string; status: string; probe_ok: boolean | null; rows: number | null
  size_bytes: number | null; message: string | null; dump_file: string | null
  export_file: string | null; deleted: boolean; started_at: string | null; finished_at: string | null
}
export type Style = 'night' | 'neon' | 'terminal' | 'graphite' | 'rose' | 'contrast' | 'amethyst' | 'sand' | 'ios'
export type Accent = 'default' | 'petrol' | 'blue' | 'purple' | 'amber' | 'green' | 'rose' | 'red'
export type Theme = 'system' | 'light' | 'dark'

export type SystemStatus = {
  version: string
  started_at: string
  uptime_seconds: number
  python: string
  database: { connected: boolean; name: string; server_version: string; created_on_start: boolean }
  migration: { current: string | null; head: string | null; up_to_date: boolean }
  data_dir: string
  keys: Record<string, 'file' | 'env'>
  /** does everything run: backups, fetches, prices, tools, disk (M8) */
  operations: {
    backup: { enabled: boolean; next_at: string | null; last_at: string | null; status: string | null; probe_ok: boolean | null; message: string | null }
    fetch: { enabled: boolean; next_at: string | null; last_at: string | null; status: string | null; failed: number }
    prices: { enabled: boolean; next_at: string | null; last_at: string | null; status: string | null; failed: number; live_at: string | null }
    fine?: { enabled: boolean; next_at: string | null; last_at: string | null; status: string | null; failed: number }
    tools: { pg_dump: number | null; server: number; ok: boolean }
    disk: { data: { path: string; free: number; total: number; used: number } | null; backups: { path: string; free: number; total: number; used: number } | null; database: number }
  }
}

export type ManualKind = 'trade' | 'receive' | 'send' | 'fiat_deposit' | 'fiat_withdrawal' | 'income' | 'fee'
  | 'internal_transfer' | 'migration' | 'realized_pnl' | 'funding'
export type ManualInput = {
  kind: ManualKind; market?: 'spot' | 'futures'; instrument?: string; income_kind?: string | null; time: string
  incoming_asset?: string; incoming_amount?: string; outgoing_asset?: string; outgoing_amount?: string
  fee_asset?: string; fee_amount?: string; comment?: string
  /** editing: the correction belongs to this source instead */
  source_id?: number
  /** a trade paid by card: its euro count as paid in */
  paid_by_card?: boolean
}
export type ManualEntry = {
  id: number; timestamp: string; time: string; kind: ManualKind; income_kind: string | null
  market: 'spot' | 'futures'; instrument: string | null; corrects: number | null; channel?: Channel
  incoming_asset: string | null; incoming_amount: string | null; outgoing_asset: string | null; outgoing_amount: string | null
  fee_asset: string | null; fee_amount: string | null; comment: string | null; edited: boolean
  paid_by_card?: boolean
}
export type TemplateProblem = { row: number; code: string; params: Record<string, unknown> }
export type TemplatePreview = {
  file: string; read: number; new: number; duplicates: number; rejected: number
  problems: TemplateProblem[]; kinds: Record<string, number>; data_from: string | null; data_to: string | null
}

export type PriceSourceRow = { rank: number; source: 'yahoo' | 'bitget' | 'binance' | 'coingecko'; ticker: string; quote: string }
export type PriceAssetRow = {
  asset: string; name: string | null; confirmed: boolean; ignored: boolean; icon: string | null; aliases: string[]
  sources: PriceSourceRow[]
  needed_from: string | null; rows: number; days: number; first_day: string | null; last_day: string | null
  gap: { from: string; to: string; reason: string } | null; price: string | null; currency: 'EUR' | 'USD'; price_at: string | null; ended_on: string | null
  contributions: Record<string, number>; spark: string[]
  changes?: Record<ChangeSpan, string | null>
  /** declared worthless from this day on: valued at 0 */
  worthless_since: string | null
  /** prices end on this day (a coin merged into another): nothing fetched after it */
  prices_until: string | null
}
export type PricePoint = { day: string; close: string; high: string | null; low: string | null; source: string }
export type PriceChange = { field: string; before: string | null; after: string | null; reason: string | null; at: string }
export type Crosscheck = { asset: string; days: number; verdict: 'ok' | 'deviates' | 'no_overlap' | 'unavailable'; mean_pct?: string; max_pct?: string; reason?: string }

/** a send or receive without counterpart, marked (receives since 2026-10-11) */
export type OpenMark = 'external' | 'own_untracked' | 'lost' | 'bought' | 'income'

export type MergedRow = RawRow & { raw_symbols: string[]; values?: { incoming: string | null; outgoing: string | null; fee: string | null } }
export type MergedItem =
  | { type: 'transfer'; at: string; reason: 'tx' | 'match' | 'manual'; send: MergedRow; receive: MergedRow; network_fee: [string, string] | null; extras: MergedRow[]; linked_at: string | null; short?: boolean }
  | { type: 'row'; at: string; row: MergedRow; short?: boolean; spam: 'tx' | 'asset' | null; dust: boolean; open: boolean; ambiguous: boolean;
      open_mark: OpenMark | null; result?: TradeResult | null }
  | ({ type: 'position'; at: string; rows: MergedRow[]; short?: boolean } & FuturesPosition)
export type TradeResult = {
  side: 'buy' | 'sell'; asset: string; qty: string; then: string; now: string; result: string; pct: string | null
  price_then: string | null; price_now: string | null; currency: 'EUR' | 'USD'
}
export type MergedSummary = { transfers: number; open: number; ambiguous: number; dust: number; spam: number; rows: number
  edited: number; noted: number; marked: number; short: number; auto: number; card: number }
export type TransferCandidate = { partner: MergedRow; receive: MergedRow; send_id: number; receive_id: number; minutes: number; diff_pct: string; sharp: boolean; split_before: boolean }

export type BalanceItem = {
  market: 'spot' | 'futures'; asset: string; computed: string | null; actual: string | null; diff: string | null
  ok: boolean | null; spam: boolean; icon: string; at: string | null; origin: 'api' | 'chain' | 'manual' | null
}
export type BalanceEntry = { source_id: number; checked: boolean; status: 'none' | 'ok' | 'diff'; differences: number
  unchecked: number; at: string | null; items: BalanceItem[] }

export type CoinOption = { asset: string; name: string | null; icon: string }
export type HoldingPlace = { source_id: number | null; market: 'spot' | 'futures'; qty: string; outside: boolean }
export type Holding = {
  asset: string; name: string | null; icon: string; fiat: boolean; qty: string; cost: string | null; avg_price: string | null
  price: string | null; value: string | null; unrealized: string | null; unrealized_pct: string | null
  realized: string; realized_pct: string | null; income: string; since: string | null; days_held: number | null
  unclear_qty: string | null; unclear_value: string | null; open_qty: string | null; places: HoldingPlace[]
}
export type PortfolioSummary = {
  currency: 'EUR' | 'USD'; value: string; crypto: string; cash: string; cost: string
  unrealized: string; unrealized_pct: string | null; realized: string; realized_pct: string | null
  futures: { pnl: string; funding: string; fees: string; result: string }
  result: string; income: string; net_deposited: string; card_deposits: string; external_in: string
  unclear: string; open: string; high: { day: string; value: string } | null; unvalued: string[]; first: string | null
}
export type HistoryPoint = { day: string; value: string; cost: string; deposited: string }
export type Gap = {
  type: 'negative' | 'balance'; source_id: number; market: 'spot' | 'futures'; asset: string; icon: string
  from?: string; row_id?: number; lowest?: string; lowest_at?: string; now?: string
  computed?: string | null; actual?: string | null; diff?: string | null
  missing_value: string | null; points: [string, string][]
}
export type FuturesPosition = {
  id: number | null; source_id: number; instrument: string; side: 'long' | 'short' | null
  opened: string; closed: string; entry: string | null; exit: string | null; known: boolean
  coin: string | null; pnl: string; funding: string; fees: string; result: string; result_value: string | null; flows: number
  open: boolean; row_ids: number[]
}

export const api = {
  sourceChanges: () => request<SourceChange[]>('GET', '/api/raw/changes'),
  decideChange: (id: number, take: boolean) => request<void>('POST', `/api/raw/changes/${id}/${take ? 'take' : 'keep'}`),
  logos: () => request<{ kind: string; key: string; v: number }[]>('GET', '/api/logos'),
  uploadLogo: (kind: string, key: string | number, file: File) => {
    const data = new FormData()
    data.append('file', file)
    return request<void>('PUT', `/api/logos/${kind}/${key}`, data)
  },
  removeLogo: (kind: string, key: string | number) => request<void>('DELETE', `/api/logos/${kind}/${key}`),
  authStatus: () => request<{ setup_required: boolean; code_required?: boolean; authenticated: boolean }>('GET', '/api/auth/status'),
  verifySetupCode: (code: string) => request<void>('POST', '/api/auth/setup/verify', { code }),
  setup: (code: string, password: string) =>
    request<{ backup_key: string }>('POST', '/api/auth/setup', { code, password }),
  login: (password: string) => request<void>('POST', '/api/auth/login', { password }),
  logout: () => request<void>('POST', '/api/auth/logout'),
  changePassword: (current: string, next: string) =>
    request<void>('POST', '/api/auth/password', { current, new: next }),
  settings: () => request<Settings>('GET', '/api/settings'),
  updateSettings: (changes: Partial<Settings>) => request<Settings>('PATCH', '/api/settings', changes),
  systemStatus: () => request<SystemStatus>('GET', '/api/system/status'),
  logs: (after: number) => request<{ lines: LogLine[]; last: number; level: LogLevel }>('GET', `/api/system/logs?after=${after}`),
  mcp: () => request<McpStatus>('GET', '/api/mcp'),
  mcpCreateToken: (name: string, kind: TokenKind, level: TokenLevel = 'read') =>
    request<{ id: number; name: string; token: string }>('POST', '/api/mcp/tokens', { name, kind, level }),
  mcpSetLevel: (id: number, level: TokenLevel) => request<void>('PATCH', `/api/mcp/tokens/${id}`, { level }),
  mcpRevokeToken: (id: number) => request<void>('DELETE', `/api/mcp/tokens/${id}`),
  backupKey: () => request<{ backup_key: string }>('GET', '/api/system/backup-key'),
  // restore (Vanixxx, 2026-10-21): in the settings, and at first start with the setup code
  backupFiles: () => request<BackupFile[]>('GET', '/api/backups/files'),
  backupUpload: (files: File[]) => request<{ name: string }>('POST', '/api/backups/upload', fileForm(files)),
  backupInspect: (name: string, key?: string) => request<BackupInfo>('POST', '/api/backups/inspect', { name, key: key || null }),
  backupRestore: (name: string, key?: string) =>
    request<RestoreResult>('POST', '/api/backups/restore', { name, key: key || null, confirm: true }),
  setupBackups: (code: string) => request<BackupFile[]>('POST', '/api/auth/setup/backups', { code }),
  setupBackupUpload: (code: string, files: File[]) => request<{ name: string }>('POST', '/api/auth/setup/backup-upload', fileForm(files), { 'X-Setup-Code': code }),
  setupRestoreInspect: (code: string, name: string, key: string) =>
    request<BackupInfo>('POST', '/api/auth/setup/restore-inspect', { code, name, key }),
  setupRestore: (code: string, name: string, key: string) =>
    request<RestoreResult>('POST', '/api/auth/setup/restore', { code, name, key, confirm: true }),
  plugins: () => request<{ providers: Provider[]; errors: Record<string, string> }>('GET', '/api/plugins'),
  sources: () => request<Source[]>('GET', '/api/sources'),
  createSource: (provider: string, label: string, address?: string, walletId?: number) =>
    request<{ id: number }>('POST', '/api/sources', { provider, label, address, wallet_id: walletId }),
  wallets: () => request<Wallet[]>('GET', '/api/wallets'),
  setAutoFetch: (id: number, autoFetch: boolean) => request<void>('PATCH', `/api/sources/${id}`, { auto_fetch: autoFetch }),
  serviceKeys: () => request<ServiceKey[]>('GET', '/api/service-keys'),
  setServiceKey: (service: string, key: string) => request<void>('PUT', `/api/service-keys/${service}`, { key }),
  deleteServiceKey: (service: string) => request<void>('DELETE', `/api/service-keys/${service}`),
  createWallet: (name: string) => request<Wallet>('POST', '/api/wallets', { name }),
  renameWallet: (id: number, name: string) => request<Wallet>('PATCH', `/api/wallets/${id}`, { name }),
  deleteWallet: (id: number) => request<void>('DELETE', `/api/wallets/${id}`),
  deleteSource: (id: number) => request<void>('DELETE', `/api/sources/${id}`),
  sourceAlerts: () => request<SourceAlert[]>('GET', '/api/sources/alerts'),
  setCredentials: (id: number, values: Record<string, string>) =>
    request<void>('PUT', `/api/sources/${id}/credentials`, values),
  deleteCredentials: (id: number) => request<void>('DELETE', `/api/sources/${id}/credentials`),
  checkSource: (id: number) => request<{ ok: boolean; message: string | null }>('POST', `/api/sources/${id}/check`),
  mappedInspect: (sourceId: number, file: File, opts: { sheet?: string | null; header_row?: number; delimiter?: string | null } = {}) =>
    request<MappedInfo>('POST', '/api/imports/mapped/inspect', mappedForm(sourceId, file, opts)),
  mappedPreview: (sourceId: number, file: File, mapping: Mapping) =>
    request<MappedPreview>('POST', '/api/imports/mapped/preview', mappedForm(sourceId, file, { mapping: JSON.stringify(mapping) })),
  mappedImport: (sourceId: number, file: File, mapping: Mapping) =>
    request<ImportRun & { added: number; duplicates: number }>('POST', '/api/imports/mapped', mappedForm(sourceId, file, { mapping: JSON.stringify(mapping) })),
  previewImport: (sourceId: number, files: File[]) => request<Preview>('POST', '/api/imports/preview', upload(sourceId, files)),
  importFile: (sourceId: number, files: File[]) => request<ImportRun>('POST', '/api/imports', upload(sourceId, files)),
  manualEntries: (sourceId: number) =>
    request<{ timezone: string; entries: ManualEntry[] }>('GET', `/api/sources/${sourceId}/manual`),
  addManual: (sourceId: number, entry: ManualInput) => request<ManualEntry>('POST', `/api/sources/${sourceId}/manual`, entry),
  editRaw: (id: number, entry: ManualInput) => request<ManualEntry>('PUT', `/api/raw/${id}`, entry),
  hideRaw: (id: number) => request<void>('POST', `/api/raw/${id}/hide`),
  restoreRaw: (id: number) => request<void>('POST', `/api/raw/${id}/restore`),
  rawHistory: (id: number) => request<HistoryEntry[]>('GET', `/api/raw/${id}/history`),
  deleteManual: (id: number) => request<void>('DELETE', `/api/manual/${id}`),
  templateUrl: (lang: string) => `/api/manual/template?lang=${lang === 'de' ? 'de' : 'en'}`,
  previewTemplate: (sourceId: number, file: File) =>
    request<TemplatePreview>('POST', `/api/sources/${sourceId}/manual/template/preview`, single(file)),
  importTemplate: (sourceId: number, file: File) =>
    request<{ added: number; duplicates: number; rejected: number; problems: TemplateProblem[] }>(
      'POST', `/api/sources/${sourceId}/manual/template`, single(file)),
  revertRun: (runId: number) => request<{ rows: number }>('DELETE', `/api/import-runs/${runId}`),
  merged: (params: Record<string, string | number | undefined>) =>
    request<{ total: number; summary: MergedSummary; items: MergedItem[] }>('GET', `/api/merged?${query(params)}`),
  mergedFacets: (params: Record<string, string | undefined>) => {
    const q = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined && v !== '') as [string, string][])
    return request<{ assets: string[]; kinds: string[]; sources: number[] }>('GET', `/api/merged/facets?${q}`)
  },
  mergedAssets: () => request<CoinOption[]>('GET', '/api/merged/assets'),
  transferCandidates: (rawId: number) => request<TransferCandidate[]>('GET', `/api/merged/candidates/${rawId}`),
  /** what lay at a source at a local moment, before the row being edited (Vanixxx, 2026-10-11) */
  balanceAt: (sourceId: number, asset: string, at: string, market: string, skip?: number) =>
    request<{ amount: string | null }>('GET', `/api/portfolio/balance-at?${new URLSearchParams({ source_id: String(sourceId), asset, at, market, ...(skip ? { skip: String(skip) } : {}) })}`),
  makeTransfer: (sendId: number, targetId: number) =>
    request<{ receive_id: number; created: boolean }>('POST', '/api/merged/make-transfer', { send_id: sendId, target_source_id: targetId }),
  attachable: (sendId: number) => request<MergedRow[]>('GET', `/api/merged/attachable/${sendId}`),
  transfersFor: (extraId: number) => request<{ send: MergedRow; receive: MergedRow }[]>('GET', `/api/merged/transfers-for/${extraId}`),
  setDust: (rawIds: number[], dust: boolean) => request<{ rows: number }>('POST', '/api/merged/dust', { raw_ids: rawIds, dust }),
  setNote: (rawId: number, text: string) => request<void>('PUT', '/api/merged/note', { raw_id: rawId, text }),
  attachExtra: (sendId: number, extraId: number) => request<void>('POST', '/api/merged/attach', { send_id: sendId, extra_id: extraId }),
  detachExtra: (extraId: number) => request<void>('POST', `/api/merged/detach/${extraId}`),
  linkTransfer: (sendId: number, receiveId: number) => request<void>('POST', '/api/merged/link', { send_id: sendId, receive_id: receiveId }),
  splitTransfer: (sendId: number, receiveId: number) => request<void>('POST', '/api/merged/split', { send_id: sendId, receive_id: receiveId }),
  markOpenSend: (sendId: number, mark: OpenMark | null, note?: string) =>
    request<void>('POST', '/api/merged/open-mark', { send_id: sendId, mark, note }),
  setSpam: (rawIds: number[], spam: boolean) => request<{ rows: number }>('POST', '/api/merged/spam', { raw_ids: rawIds, spam }),
  raw: (params: Record<string, string | number | boolean | undefined>) =>
    request<{ total: number; rows: RawRow[] }>('GET', `/api/raw?${query(params)}`),
  jobs: () => request<Job[]>('GET', '/api/jobs'),
  balances: () => request<BalanceEntry[]>('GET', '/api/balances'),
  portfolio: () => request<{ summary: PortfolioSummary; items: Holding[] }>('GET', '/api/portfolio'),
  priceAt: (asset: string, at?: string) =>
    request<{ asset: string; price: string | null; currency: 'EUR' | 'USD'; day: string; latest: boolean }>('GET', `/api/prices/at?asset=${encodeURIComponent(asset)}${at ? `&at=${encodeURIComponent(at)}` : ''}`),
  stats: () => request<StatsData>('GET', '/api/stats'),
  taxYears: () => request<number[]>('GET', '/api/tax/years'),
  taxReport: (year: number, method: TaxMethod) => request<TaxReport>('GET', `/api/tax/${year}?method=${method}`),
  originList: () => request<OriginStep[]>('GET', '/api/tax/origin'),
  origin: (row: number) => request<OriginData>('GET', `/api/tax/origin/${row}`),
  originPlannedOptions: () => request<PlannedOption[]>('GET', '/api/tax/origin/planned/options'),
  originPlanned: (source: number, asset: string, qty: string, day: string) =>
    request<OriginData>('GET', `/api/tax/origin/planned?${new URLSearchParams({ source: String(source), asset, qty, day })}`),
  originPlannedFile: (kind: 'xlsx' | 'pdf', source: number, asset: string, qty: string, day: string) =>
    `/api/tax/origin/planned/file?${new URLSearchParams({ kind, source: String(source), asset, qty, day })}`,
  originHoldings: (asset?: string) =>
    request<OriginData>('GET', `/api/tax/origin/holdings${asset ? `?asset=${encodeURIComponent(asset)}` : ''}`),
  originHoldingsFile: (kind: 'xlsx' | 'pdf', asset?: string) =>
    `/api/tax/origin/holdings/file?kind=${kind}${asset ? `&asset=${encodeURIComponent(asset)}` : ''}`,
  originFile: (row: number, kind: 'xlsx' | 'pdf') => `/api/tax/origin/${row}/file?kind=${kind}`,
  taxSetCarry: (year: number, amount: string | null, note: string) =>
    request<void>('PUT', `/api/tax/carry/${year}`, { amount, note }),
  taxFreeze: (year: number, method: TaxMethod, note: string) =>
    request<{ id: number }>('POST', `/api/tax/${year}/freeze?method=${method}`, { note }),
  taxCompare: (year: number, a: number, b?: number) =>
    request<TaxCompare>('GET', `/api/tax/${year}/compare?a=${a}${b ? `&b=${b}` : ''}`),
  taxKeptNote: (id: number, note: string) => request<{ id: number; note: string | null }>('PATCH', `/api/tax/kept/${id}`, { note }),
  taxKeptDelete: (id: number) => request<void>('DELETE', `/api/tax/kept/${id}`),
  taxKeptFile: (id: number, kind: 'xlsx' | 'pdf') => `/api/tax/kept/${id}/file?kind=${kind}`,
  taxRows: (ids: number[]) => request<TaxRows>('GET', `/api/tax/rows?ids=${ids.join(',')}`),
  taxFile: (year: number, method: TaxMethod, kind: 'xlsx' | 'pdf') => `/api/tax/${year}/file?kind=${kind}&method=${method}`,
  taxLimits: () => request<{ year: number } & Record<'s23' | 's22', { value: string; limit: string; share: string; level: 'ok' | 'near' | 'over' }>>('GET', '/api/tax/limits'),
  taxUpcoming: (days: number) =>
    request<{ asset: string; free_on: string; qty: string; value: string | null; gain: string | null }[]>('GET', `/api/tax/upcoming?days=${days}`),
  taxHoldings: () => request<Record<string, TaxHolding>>('GET', '/api/tax/holdings'),
  taxFree: () => request<TaxFree>('GET', '/api/tax/free'),
  portfolioDca: (asset: string) => request<{ day: string; value: string | null }[]>('GET', `/api/portfolio/dca/${encodeURIComponent(asset)}`),
  portfolioHistory: () => request<HistoryPoint[]>('GET', '/api/portfolio/history'),
  portfolioTicks: (hours: number) => request<{ at: string; value: string }[]>('GET', `/api/portfolio/ticks?hours=${hours}`),
  portfolioGaps: () => request<Gap[]>('GET', '/api/portfolio/gaps'),
  futuresPositions: () => request<FuturesPosition[]>('GET', '/api/portfolio/futures'),
  setBalance: (sourceId: number, asset: string, amount: string) =>
    request<void>('POST', `/api/balances/${sourceId}`, { asset, amount }),
  priceAssets: () => request<PriceAssetRow[]>('GET', '/api/prices/assets'),
  priceSparks: (span: ChangeSpan) => request<Record<string, string[]>>('GET', `/api/prices/sparks?span=${span}`),
  priceHistory: (asset: string, days: number) =>
    request<PricePoint[]>('GET', `/api/prices/assets/${encodeURIComponent(asset)}/history?days=${days}`),
  priceChanges: (asset: string) => request<PriceChange[]>('GET', `/api/prices/assets/${encodeURIComponent(asset)}/changes`),
  priceCrosscheck: (asset: string) => request<Crosscheck>('GET', `/api/prices/assets/${encodeURIComponent(asset)}/crosscheck`),
  fetchPrice: (asset: string) =>
    request<{ asset: string; prices: number; latest: number; with_errors: string[] }>('POST', `/api/prices/assets/${encodeURIComponent(asset)}/fetch`),
  confirmPrice: (asset: string) => request<void>('POST', `/api/prices/assets/${encodeURIComponent(asset)}/confirm`),
  setWorthless: (asset: string, since: string | null, reason?: string) =>
    request<void>('POST', `/api/prices/assets/${encodeURIComponent(asset)}/worthless`, { since, reason }),
  setPricesUntil: (asset: string, until: string | null, reason?: string) =>
    request<void>('POST', `/api/prices/assets/${encodeURIComponent(asset)}/until`, { until, reason }),
  ignorePrice: (asset: string, ignored: boolean, reason?: string) =>
    request<void>('POST', `/api/prices/assets/${encodeURIComponent(asset)}/ignore`, { ignored, reason }),
  setPriceAlias: (asset: string, target: string, name: string, reason: string) =>
    request<void>('POST', `/api/prices/assets/${encodeURIComponent(asset)}/alias`, { target, name, reason }),
  removePriceAlias: (alias: string) => request<void>('DELETE', `/api/prices/aliases/${encodeURIComponent(alias)}`),
  resuggestPrices: () => request<{ assets: number }>('POST', '/api/prices/resuggest'),
  livePrices: () => request<Record<string, { price: string; at: string; currency: 'EUR' | 'USD' }>>('POST', '/api/prices/live'),
  updatePriceMapping: (asset: string, body: { name: string | null; sources: { source: string; ticker: string }[]; reason?: string; icon?: string }) =>
    request<void>('PUT', `/api/prices/assets/${encodeURIComponent(asset)}`, body),
  startJob: (kind: 'fetch' | 'backup' | 'prices', sourceId?: number) =>
    request<Job>('POST', '/api/jobs', { kind, source_id: sourceId }),
  backups: () => request<{ folder: string; unmounted?: boolean; runs: BackupRun[] }>('GET', '/api/backups'),
}

function fileForm(files: File[], fields: Record<string, string> = {}) {
  const data = new FormData()
  for (const [k, v] of Object.entries(fields)) data.append(k, v)
  for (const f of files) data.append('files', f)
  return data
}

function single(file: File) {
  const data = new FormData()
  data.append('file', file)
  return data
}

function mappedForm(sourceId: number, file: File, fields: Record<string, string | number | null | undefined>) {
  const data = new FormData()
  data.append('source_id', String(sourceId))
  data.append('file', file)
  for (const [k, v] of Object.entries(fields)) if (v !== null && v !== undefined) data.append(k, String(v))
  return data
}

function upload(sourceId: number, files: File[]) {
  const data = new FormData()
  data.append('source_id', String(sourceId))
  for (const f of files) data.append('files', f)
  return data
}

function query(params: Record<string, string | number | boolean | undefined>) {
  return new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== undefined && v !== '').map(([k, v]) => [k, String(v)]),
  ).toString()
}
