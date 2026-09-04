import { BarChart3, Download, Table2 } from 'lucide-react'
import { useMemo, useState } from 'react'
import { buildChart } from '../lib/chart'
import type { QueryRow } from '../types/chat'
import { DataChart } from './charts/DataChart'

interface QueryResultProps {
  rows: QueryRow[]
}

function csvValue(value: QueryRow[string]) {
  const text = value === null ? '' : String(value)
  return `"${text.replaceAll('"', '""')}"`
}

export function QueryResult({ rows }: QueryResultProps) {
  const chart = useMemo(() => buildChart(rows), [rows])
  const [view, setView] = useState<'chart' | 'table'>('chart')
  if (!rows.length) return null

  const columns = [...new Set(rows.flatMap((row) => Object.keys(row)))]
  const showChart = chart !== null && view === 'chart'

  const downloadCsv = () => {
    const csv = [columns.join(','), ...rows.map((row) => columns.map((column) => csvValue(row[column] ?? null)).join(','))].join('\n')
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }))
    const link = document.createElement('a')
    link.href = url
    link.download = 'query-results.csv'
    link.click()
    URL.revokeObjectURL(url)
  }

  return (
    <section className="overflow-hidden rounded-card border border-rule bg-surface">
      <div className="flex items-center justify-between gap-2 border-b border-rule bg-sunken px-4 py-2">
        <span className="t-label text-ink-faint">
          Results <span className="text-ink-faint">({rows.length} rows)</span>
        </span>
        <div className="flex items-center gap-1">
          {chart && (
            <div className="mr-1 flex rounded-chip border border-rule bg-surface p-0.5">
              {(['chart', 'table'] as const).map((option) => (
                <button
                  key={option}
                  onClick={() => setView(option)}
                  aria-pressed={view === option}
                  aria-label={option === 'chart' ? 'Chart view' : 'Table view'}
                  className={`flex size-6 items-center justify-center rounded-card ${
                    view === option ? 'bg-accent-soft text-accent' : 'text-ink-faint hover:text-ink'
                  }`}
                >
                  {option === 'chart' ? <BarChart3 className="size-3.5" /> : <Table2 className="size-3.5" />}
                </button>
              ))}
            </div>
          )}
          <button className="icon-button" onClick={downloadCsv} aria-label="Download CSV" title="Download CSV">
            <Download className="size-3.5" />
          </button>
        </div>
      </div>

      {showChart ? (
        <div className="p-4">
          <DataChart spec={chart} />
        </div>
      ) : (
        <div className="max-h-80 overflow-auto">
          <table className="w-full text-left">
            <thead className="sticky top-0 bg-sunken">
              <tr>
                {columns.map((column) => (
                  <th key={column} className="t-label whitespace-nowrap px-[18px] py-3.5 text-ink-faint">
                    {column}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-rule">
              {rows.map((row, rowIndex) => (
                <tr key={rowIndex}>
                  {columns.map((column) => (
                    <td key={column} className="t-data whitespace-nowrap px-[18px] py-3.5 text-ink-mid">
                      {row[column] === null || row[column] === undefined ? (
                        <span className="text-ink-faint">null</span>
                      ) : (
                        String(row[column])
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
