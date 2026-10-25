import type { ManualEntry, RawRow } from './api'

/** Local "YYYY-MM-DDTHH:MM:SS" of an instant in the configured zone. */
function localTime(iso: string, timeZone: string): string {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat('en-CA', {
      timeZone, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23',
    }).formatToParts(new Date(iso)).map((p) => [p.type, p.value]),
  )
  return `${parts.year}-${parts.month}-${parts.day}T${parts.hour}:${parts.minute}:${parts.second}`
}

/** A raw row as a form entry: correcting a row from API, file or chain starts from it. */
export function entryOf(r: RawRow, timeZone: string): ManualEntry {
  return {
    id: r.id, timestamp: r.timestamp, time: localTime(r.timestamp, timeZone), kind: r.kind as ManualEntry['kind'],
    market: r.market, instrument: r.instrument, income_kind: r.income_kind,
    incoming_asset: r.incoming[0], incoming_amount: r.incoming[1], outgoing_asset: r.outgoing[0], outgoing_amount: r.outgoing[1],
    fee_asset: r.fee[0], fee_amount: r.fee[1], comment: r.comment, edited: r.edited, corrects: null, channel: r.channel, paid_by_card: (r as { paid_by_card?: boolean }).paid_by_card,
  }
}
