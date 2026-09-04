/** Inline SVG charts. No chart library: the whole surface here is three forms,
 *  and a dependency would cost more to theme than it saves to draw. */
import { useState } from 'react'
import type { ChartSpec, Plot } from '../../lib/chart'
import { compact, formatAxisLabel, formatValue, labelOf, needsSmallMultiples, niceTicks, splitSeries, unitOf } from '../../lib/chart'

const SERIES_COLOR = (index: number) => `var(--series-${(index % 6) + 1})`

interface Hover {
  x: number
  y: number
  title: string
  rows: { label: string; value: string; color: string }[]
}

function Tooltip({ hover }: { hover: Hover | null }) {
  if (!hover) return null
  return (
    <div
      className="pointer-events-none absolute z-10 min-w-32 rounded-chip border border-rule bg-surface px-2.5 py-2 shadow-lg"
      style={{ left: `${hover.x}%`, top: hover.y, transform: 'translate(-50%, -110%)' }}
    >
      <p className="t-label mb-1 text-ink-faint">{hover.title}</p>
      {hover.rows.map((row) => (
        <p key={row.label} className="flex items-center gap-1.5 whitespace-nowrap text-[12px] text-ink-mid">
          <i className="size-2 shrink-0 rounded-full" style={{ background: row.color }} />
          {row.label}
          <span className="ml-auto pl-3 font-medium text-ink">{row.value}</span>
        </p>
      ))}
    </div>
  )
}

function Legend({ series }: { series: string[] }) {
  if (series.length < 2) return null
  return (
    <div className="mb-3 flex flex-wrap gap-x-4 gap-y-1.5">
      {series.map((key, index) => (
        <span key={key} className="flex items-center gap-1.5 text-[12px] text-ink-soft">
          <i className="size-2 rounded-full" style={{ background: SERIES_COLOR(index) }} />
          {labelOf(key)}
        </span>
      ))}
    </div>
  )
}

/** The headline numbers for one measure - the "so what" above the plot.
 *  A rate has no meaningful total, so it doesn't get one. */
function Summary({ label, values, compactLayout }: { label: string; values: (number | null)[]; compactLayout?: boolean }) {
  const present = values.filter((value): value is number => value !== null)
  if (present.length < 2) return null
  const sum = present.reduce((total, value) => total + value, 0)
  const isRate = unitOf(label) === 'percent' || /(avg|average|mean|median|ratio|aov|per_)/i.test(label)
  const tiles = [
    ...(isRate ? [] : [{ label: 'Total', value: formatValue(label, sum) }]),
    { label: 'Average', value: formatValue(label, sum / present.length) },
    { label: 'Peak', value: formatValue(label, Math.max(...present)) },
    { label: 'Low', value: formatValue(label, Math.min(...present)) },
  ]
  if (compactLayout) {
    return (
      <p className="t-secondary mb-2 flex flex-wrap gap-x-3 text-ink-faint">
        {tiles.map((tile) => (
          <span key={tile.label}>
            {tile.label} <span className="font-medium tabular-nums text-ink-mid">{tile.value}</span>
          </span>
        ))}
      </p>
    )
  }
  return (
    <div className="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
      {tiles.map((tile) => (
        <div key={tile.label} className="rounded-chip bg-sunken px-3 py-2">
          <p className="t-label truncate text-ink-faint">{`${tile.label} ${labelOf(label)}`}</p>
          <p className="mt-0.5 text-[16px] font-semibold tabular-nums text-ink">{tile.value}</p>
        </div>
      ))}
    </div>
  )
}

function StatTiles({ tiles }: { tiles: { key: string; value: number }[] }) {
  return (
    <div className={`grid gap-3 ${tiles.length > 1 ? 'sm:grid-cols-2' : ''}`}>
      {tiles.map((tile) => (
        <div key={tile.key} className="rounded-card border border-rule bg-sunken px-4 py-3.5">
          <p className="t-label text-ink-faint">{labelOf(tile.key)}</p>
          <p className="t-kpi mt-1 text-ink">{formatValue(tile.key, tile.value)}</p>
        </div>
      ))}
    </div>
  )
}

const W = 760

function BarChart({ spec, compactLayout, colorIndex = 0 }: { spec: Extract<ChartSpec, { form: 'bar' }>; compactLayout?: boolean; colorIndex?: number }) {
  const [hover, setHover] = useState<Hover | null>(null)
  const { points, series } = spec
  const labelW = 176
  const plotW = W - labelW - 78
  const barH = series.length > 1 ? 9 : 16
  const rowH = series.length * (barH + 3) + 16
  const height = points.length * rowH + 8

  const values = points.flatMap((point) => point.values.filter((value): value is number => value !== null))
  const max = Math.max(1, ...values.map(Math.abs))
  const labelCap = compactLayout ? 16 : 26

  return (
    <div className="relative">
      <Legend series={series} />
      <svg viewBox={`0 0 ${W} ${height}`} className="w-full" role="img" onMouseLeave={() => setHover(null)}>
        {points.map((point, rowIndex) => {
          const top = rowIndex * rowH + 4
          return (
            <g key={point.label + rowIndex}>
              <text x={labelW - 12} y={top + rowH / 2} textAnchor="end" dominantBaseline="middle" className="fill-ink-mid text-[13px]">
                {point.label.length > labelCap ? `${point.label.slice(0, labelCap - 1)}…` : point.label}
              </text>
              {point.values.map((value, seriesIndex) => {
                const width = value === null ? 0 : (Math.abs(value) / max) * plotW
                const y = top + 8 + seriesIndex * (barH + 3)
                return (
                  <g key={seriesIndex}>
                    <rect
                      x={labelW}
                      y={y}
                      width={Math.max(2, width)}
                      height={barH}
                      rx={4}
                      fill={SERIES_COLOR(seriesIndex + colorIndex)}
                      onMouseEnter={() =>
                        setHover({
                          x: ((labelW + width) / W) * 100,
                          y,
                          title: point.label,
                          rows: series.map((key, index) => ({
                            label: labelOf(key),
                            value: formatValue(key, point.values[index]),
                            color: SERIES_COLOR(index + colorIndex),
                          })),
                        })
                      }
                    />
                    {seriesIndex === 0 && (
                      <text x={labelW + Math.max(2, width) + 8} y={y + barH / 2} dominantBaseline="middle" className="fill-ink-soft text-[12px] tabular-nums">
                        {formatValue(series[0], value)}
                      </text>
                    )}
                  </g>
                )
              })}
            </g>
          )
        })}
      </svg>
      <Tooltip hover={hover} />
      {spec.truncated > 0 && (
        <p className="t-secondary mt-2 text-ink-faint">
          Top {points.length} shown · {spec.truncated} more in the table
        </p>
      )}
    </div>
  )
}

function LineChart({ spec, compactLayout, colorIndex = 0 }: { spec: Extract<ChartSpec, { form: 'line' }>; compactLayout?: boolean; colorIndex?: number }) {
  const [hover, setHover] = useState<Hover | null>(null)
  const { points, series } = spec
  const H = compactLayout ? 190 : 260
  const pad = { left: 62, right: 18, top: 14, bottom: 30 }
  const plotW = W - pad.left - pad.right
  const plotH = H - pad.top - pad.bottom

  const values = points.flatMap((point) => point.values.filter((value): value is number => value !== null))
  const ticks = niceTicks(Math.min(...values, 0), Math.max(...values, 0))
  const min = ticks[0]
  const max = ticks[ticks.length - 1]
  const span = max - min || 1
  const x = (index: number) => pad.left + (points.length === 1 ? plotW / 2 : (index / (points.length - 1)) * plotW)
  const y = (value: number) => pad.top + plotH - ((value - min) / span) * plotH
  const labelEvery = Math.ceil(points.length / (compactLayout ? 4 : 7))

  const move = (event: React.MouseEvent<SVGSVGElement>) => {
    const rect = event.currentTarget.getBoundingClientRect()
    const ratio = ((event.clientX - rect.left) / rect.width) * W
    const index = Math.round(((ratio - pad.left) / plotW) * (points.length - 1))
    const point = points[Math.min(points.length - 1, Math.max(0, index))]
    if (!point) return
    setHover({
      x: (x(points.indexOf(point)) / W) * 100,
      y: pad.top + 8,
      title: formatAxisLabel(point.label),
      rows: series.map((key, seriesIndex) => ({
        label: labelOf(key),
        value: formatValue(key, point.values[seriesIndex]),
        color: SERIES_COLOR(seriesIndex + colorIndex),
      })),
    })
  }

  const hoverIndex = hover ? Math.round((((hover.x / 100) * W) - pad.left) / plotW * (points.length - 1)) : -1

  return (
    <div className="relative">
      <Legend series={series} />
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" onMouseMove={move} onMouseLeave={() => setHover(null)}>
        {ticks.map((tick) => (
          <g key={tick}>
            <line x1={pad.left} x2={W - pad.right} y1={y(tick)} y2={y(tick)} className="stroke-rule" strokeWidth={1} />
            <text x={pad.left - 10} y={y(tick)} textAnchor="end" dominantBaseline="middle" className="fill-ink-faint text-[11px] tabular-nums">
              {unitOf(series[0]) === 'percent' ? `${compact(tick)}%` : compact(tick)}
            </text>
          </g>
        ))}

        {series.map((key, seriesIndex) => {
          const drawn = points
            .map((point, index) => ({ index, value: point.values[seriesIndex] }))
            .filter((point): point is { index: number; value: number } => point.value !== null)
          if (!drawn.length) return null
          const path = drawn.map((point, order) => `${order ? 'L' : 'M'}${x(point.index)},${y(point.value)}`).join(' ')
          return (
            <g key={key}>
              {series.length === 1 && (
                <path
                  d={`${path} L${x(drawn[drawn.length - 1].index)},${y(min)} L${x(drawn[0].index)},${y(min)} Z`}
                  fill={SERIES_COLOR(seriesIndex + colorIndex)}
                  opacity={0.1}
                />
              )}
              <path d={path} fill="none" stroke={SERIES_COLOR(seriesIndex + colorIndex)} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
              {drawn.length <= (compactLayout ? 14 : 40) &&
                drawn.map((point) => (
                  <circle key={point.index} cx={x(point.index)} cy={y(point.value)} r={3.5} fill={SERIES_COLOR(seriesIndex + colorIndex)} className="stroke-surface" strokeWidth={2} />
                ))}
            </g>
          )
        })}

        {hoverIndex >= 0 && hoverIndex < points.length && (
          <g>
            <line x1={x(hoverIndex)} x2={x(hoverIndex)} y1={pad.top} y2={pad.top + plotH} className="stroke-rule-strong" strokeWidth={1} />
            {series.map((key, seriesIndex) => {
              const value = points[hoverIndex].values[seriesIndex]
              return value === null ? null : (
                <circle key={key} cx={x(hoverIndex)} cy={y(value)} r={4.5} fill={SERIES_COLOR(seriesIndex + colorIndex)} className="stroke-surface" strokeWidth={2} />
              )
            })}
          </g>
        )}

        {points.map((point, index) =>
          index % labelEvery === 0 ? (
            <text key={index} x={x(index)} y={H - 8} textAnchor="middle" className="fill-ink-faint text-[11px]">
              {formatAxisLabel(point.label)}
            </text>
          ) : null,
        )}
      </svg>
      <Tooltip hover={hover} />
    </div>
  )
}

function Panel({ spec, compactLayout, colorIndex = 0 }: { spec: Exclude<ChartSpec, { form: 'stats' }>; compactLayout?: boolean; colorIndex?: number }) {
  return (
    <div>
      {compactLayout && (
        <p className="t-card-title mb-1 flex items-center gap-2 text-ink">
          <i className="size-2 rounded-full" style={{ background: SERIES_COLOR(colorIndex) }} />
          {labelOf(spec.series[0])}
        </p>
      )}
      <Summary label={spec.series[0]} values={spec.points.map((point) => point.values[0])} compactLayout={compactLayout} />
      {spec.form === 'bar' ? (
        <BarChart spec={spec} compactLayout={compactLayout} colorIndex={colorIndex} />
      ) : (
        <LineChart spec={spec} compactLayout={compactLayout} colorIndex={colorIndex} />
      )}
    </div>
  )
}

export function DataChart({ spec }: { spec: ChartSpec }) {
  if (spec.form === 'stats') return <StatTiles tiles={spec.tiles} />

  if (needsSmallMultiples(spec.series, spec.points)) {
    const panels = splitSeries(spec as Plot & typeof spec)
    return (
      <div className={`grid gap-x-6 gap-y-5 ${panels.length > 2 ? 'lg:grid-cols-2' : ''}`}>
        {panels.map((panel, index) => (
          <Panel key={panel.series[0]} spec={panel} compactLayout colorIndex={index} />
        ))}
      </div>
    )
  }

  return <Panel spec={spec} />
}
