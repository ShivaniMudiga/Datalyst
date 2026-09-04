/** Turns a result set into a chart, or decides there isn't one worth drawing.
 *
 *  Numbers arrive as strings: the backend serialises tool output with
 *  `json.dumps(default=str)`, so a Postgres numeric is "1234.56" and a date is
 *  "2026-08-01". Everything here coerces rather than trusting the type.
 */
import type { QueryRow } from '../types/chat'

export type ColumnKind = 'number' | 'time' | 'category'
export interface Column {
  key: string
  kind: ColumnKind
}

export interface Plot {
  labelKey: string
  series: string[]
  points: { label: string; values: (number | null)[] }[]
  truncated: number
}

export type ChartSpec =
  | { form: 'stats'; tiles: { key: string; value: number }[] }
  | ({ form: 'bar' } & Plot)
  | ({ form: 'line' } & Plot)

const ID_COLUMN = /(^|_)id$/i
const TIME_TEXT = /^\d{4}-\d{2}(-\d{2})?([T ]|$)/

export function toNumber(value: unknown): number | null {
  if (typeof value === 'number') return Number.isFinite(value) ? value : null
  if (typeof value !== 'string') return null
  const trimmed = value.trim()
  if (!trimmed || TIME_TEXT.test(trimmed)) return null
  const parsed = Number(trimmed)
  return Number.isFinite(parsed) ? parsed : null
}

function toTime(value: unknown): number | null {
  if (typeof value !== 'string' || !TIME_TEXT.test(value.trim())) return null
  const text = value.trim()
  const parsed = Date.parse(text.length === 7 ? `${text}-01` : text)
  return Number.isNaN(parsed) ? null : parsed
}

export function classify(rows: QueryRow[], key: string): ColumnKind {
  const values = rows.map((row) => row[key]).filter((value) => value !== null && value !== undefined)
  if (!values.length) return 'category'
  if (values.every((value) => toTime(value) !== null)) return 'time'
  // An id is a number the way a phone number is a number: never a measure.
  if (!ID_COLUMN.test(key) && values.every((value) => toNumber(value) !== null)) return 'number'
  return 'category'
}

export function columnsOf(rows: QueryRow[]): Column[] {
  const keys = [...new Set(rows.flatMap((row) => Object.keys(row)))]
  return keys.map((key) => ({ key, kind: classify(rows, key) }))
}

const MAX_SERIES = 6
const MAX_BARS = 14

export function buildChart(rows: QueryRow[]): ChartSpec | null {
  if (!rows.length || rows.length > 400) return null

  const columns = columnsOf(rows)
  const measures = columns.filter((column) => column.kind === 'number').map((column) => column.key)
  const times = columns.filter((column) => column.kind === 'time').map((column) => column.key)
  const labels = columns.filter((column) => column.kind === 'category').map((column) => column.key)
  if (!measures.length) return null

  // One row of numbers is a headline, not a chart.
  if (rows.length === 1) {
    const tiles = measures.slice(0, 4).map((key) => ({ key, value: toNumber(rows[0][key]) ?? 0 }))
    return tiles.length ? { form: 'stats', tiles } : null
  }

  const series = measures.slice(0, MAX_SERIES)

  if (times.length) {
    const labelKey = times[0]
    const points = rows
      .map((row) => ({
        sort: toTime(row[labelKey]) ?? 0,
        label: String(row[labelKey] ?? ''),
        values: series.map((key) => toNumber(row[key])),
      }))
      .sort((a, b) => a.sort - b.sort)
    return { form: 'line', labelKey, series, points, truncated: 0 }
  }

  if (!labels.length) return null

  const labelKey = labels[0]
  const ranked = rows
    .map((row) => ({
      label: labels
        .slice(0, 2)
        .map((key) => String(row[key] ?? '—'))
        .join(' · '),
      values: series.map((key) => toNumber(row[key])),
    }))
    .sort((a, b) => Math.abs(b.values[0] ?? 0) - Math.abs(a.values[0] ?? 0))

  return {
    form: 'bar',
    labelKey,
    series,
    points: ranked.slice(0, MAX_BARS),
    // Never invent an "Other" bucket - averages and rates don't add up.
    truncated: Math.max(0, ranked.length - MAX_BARS),
  }
}

// ------------------------------------------------------------------ formats
// Only money and rates are detected; everything else counts. Listing the nouns
// that get counted would be a list of one industry's nouns, and the wrong guess
// there puts a currency symbol on a headcount. `total` and `value` stay out of
// CURRENCY for the same reason: `total_orders` is not money.
const CURRENCY = /(revenue|gmv|amount|price|spend|sales|cost|fee|salary|refund|payment|aov|loss|profit|margin|gross|net_|turnover|earning|balance)/i
const PERCENT = /(pct|percent|rate|ratio|share)/i

export type Unit = 'percent' | 'currency' | 'count'

export function unitOf(key: string): Unit {
  if (PERCENT.test(key)) return 'percent'
  return CURRENCY.test(key) ? 'currency' : 'count'
}

export function formatValue(key: string, value: number | null): string {
  if (value === null) return '—'
  const unit = unitOf(key)
  if (unit === 'percent') return `${round(value, 1)}%`
  return (unit === 'currency' ? '₹' : '') + compact(value)
}

/** Axis ticks a human would have chosen: 0, 25L, 50L - not 40.67L. */
export function niceTicks(min: number, max: number, count = 4): number[] {
  const span = (max - min) || Math.abs(max) || 1
  const rough = span / count
  const magnitude = 10 ** Math.floor(Math.log10(rough))
  const step = ([1, 2, 2.5, 5, 10].find((factor) => rough <= factor * magnitude) ?? 10) * magnitude
  // The top tick must sit at or above the maximum, or the plot clips its peak.
  const start = Math.floor(min / step) * step
  const end = Math.ceil(max / step) * step
  const ticks: number[] = []
  for (let tick = start; tick <= end + step * 0.001; tick += step) ticks.push(Number(tick.toPrecision(12)))
  return ticks.length > 1 ? ticks : [start, start + step]
}

/** Two measures on one axis is the classic lie: crores of GMV flatten a return
 *  rate into the baseline. When the scales are incomparable, split them into
 *  small multiples instead - one chart, one axis, one measure. */
export function needsSmallMultiples(series: string[], points: { values: (number | null)[] }[]): boolean {
  if (series.length < 2) return false
  if (new Set(series.map(unitOf)).size > 1) return true
  const peaks = series
    .map((_, index) => Math.max(...points.map((point) => Math.abs(point.values[index] ?? 0))))
    .filter((peak) => peak > 0)
  if (peaks.length < series.length) return true
  return Math.max(...peaks) / Math.min(...peaks) > 20
}

export function splitSeries<T extends Plot>(spec: T): T[] {
  return spec.series.map((key, index) => ({
    ...spec,
    series: [key],
    points: spec.points.map((point) => ({ ...point, values: [point.values[index]] })),
  }))
}

/** Indian units, because a marketplace reads its numbers in lakh and crore. */
export function compact(value: number): string {
  const sign = value < 0 ? '-' : ''
  const size = Math.abs(value)
  if (size >= 1e7) return `${sign}${round(size / 1e7, 2)} Cr`
  if (size >= 1e5) return `${sign}${round(size / 1e5, 2)} L`
  if (size >= 1e4) return `${sign}${round(size / 1e3, 1)} K`
  return sign + round(size, size < 100 ? 2 : 0).toLocaleString('en-IN')
}

function round(value: number, places: number): number {
  return Number(value.toFixed(places))
}

const ACRONYMS = /^(gmv|aov|sla|rto|cod|sku|upi|emi|id|ctr|cpm|roas|roi|arpu|ltv|cac|kpi|url|api)$/i

export function labelOf(key: string): string {
  return key
    .replace(/_/g, ' ')
    .split(' ')
    .map((word) => (ACRONYMS.test(word) ? word.toUpperCase() : word.replace(/^\w/, (letter) => letter.toUpperCase())))
    .join(' ')
}

/** Month-granular series get month labels; daily series get day labels. */
export function formatAxisLabel(raw: string): string {
  const time = toTime(raw)
  if (time === null) return raw
  const date = new Date(time)
  const monthly = /^\d{4}-\d{2}(-01)?([T ]00:00|$)/.test(raw)
  return date.toLocaleDateString('en-IN', monthly ? { month: 'short', year: '2-digit' } : { day: 'numeric', month: 'short' })
}
