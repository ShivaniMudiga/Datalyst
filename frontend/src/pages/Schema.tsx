import { RefreshCw, Repeat, X } from 'lucide-react'
import { useMemo, useState } from 'react'
import { BackButton } from '../components/BackButton'
import { engineName } from '../lib/databases'
import type { Connection, Relationship, Snapshot, SnapshotTable } from '../types/setup'

const NODE_WIDTH = 200
const COLUMN_GAP = 150
const ROW_GAP = 40
const HEADER_HEIGHT = 46
const ROW_HEIGHT = 22
const PADDING = 32
const VISIBLE_COLUMNS = 5

interface Node {
  table: SnapshotTable
  x: number
  y: number
  height: number
}

/** Parents on the left, the tables that reference them to the right.
 *  ponytail: layered by reference depth, no crossing minimisation. Good enough
 *  for the eight-to-twenty tables a snapshot actually has; reach for elkjs only
 *  if a real schema comes out unreadable. */
function layout(snapshot: Snapshot): { nodes: Map<string, Node>; width: number; height: number } {
  const byName = new Map(snapshot.tables.map((table) => [table.name, table]))

  const depth = new Map<string, number>()
  const resolve = (name: string, seen: Set<string>): number => {
    if (depth.has(name)) return depth.get(name)!
    if (seen.has(name)) return 0
    seen.add(name)
    const table = byName.get(name)
    const parents = (table?.foreign_keys ?? [])
      .map((key) => key.references_table)
      .filter((parent) => parent !== name && byName.has(parent))
    const value = parents.length ? 1 + Math.max(...parents.map((parent) => resolve(parent, seen))) : 0
    depth.set(name, value)
    return value
  }
  snapshot.tables.forEach((table) => resolve(table.name, new Set()))

  const layers: SnapshotTable[][] = []
  snapshot.tables.forEach((table) => {
    const level = depth.get(table.name) ?? 0
    ;(layers[level] ??= []).push(table)
  })

  const heightOf = (table: SnapshotTable) => {
    const rows = Math.min(table.columns.length, VISIBLE_COLUMNS)
    const extra = table.columns.length > VISIBLE_COLUMNS ? 1 : 0
    return HEADER_HEIGHT + (rows + extra) * ROW_HEIGHT + 24
  }

  const columnHeights = layers.map((layer) =>
    layer.reduce((total, table) => total + heightOf(table) + ROW_GAP, -ROW_GAP),
  )
  const tallest = Math.max(...columnHeights, 0)

  const nodes = new Map<string, Node>()
  layers.forEach((layer, level) => {
    let y = PADDING + (tallest - columnHeights[level]) / 2
    layer
      .slice()
      .sort((a, b) => a.name.localeCompare(b.name))
      .forEach((table) => {
        const height = heightOf(table)
        nodes.set(table.name, { table, x: PADDING + level * (NODE_WIDTH + COLUMN_GAP), y, height })
        y += height + ROW_GAP
      })
  })

  return {
    nodes,
    width: PADDING * 2 + layers.length * NODE_WIDTH + Math.max(layers.length - 1, 0) * COLUMN_GAP,
    height: PADDING * 2 + tallest,
  }
}

export function Schema({
  snapshot,
  connection,
  onBack,
  onRefresh,
  onConnectNew,
  onStart,
}: {
  snapshot: Snapshot
  connection: Connection | null
  onBack: () => void
  onRefresh: () => void
  onConnectNew: () => void
  onStart: () => void
}) {
  const [selected, setSelected] = useState<string | null>(null)
  const { nodes, width, height } = useMemo(() => layout(snapshot), [snapshot])

  const isConnected = (relationship: Relationship) =>
    selected === relationship.from_table || selected === relationship.to_table

  return (
    <div className="flex min-h-dvh flex-col bg-ground px-12 py-10">
      <div className="mb-4">
        <BackButton onBack={onBack} />
      </div>
      <header className="flex items-center justify-between gap-6">
        <div className="min-w-0">
          <h1 className="t-page-title truncate text-ink">{snapshot.database}</h1>
          <p className="t-secondary mt-1 text-ink-faint">
            {connection ? `${engineName(connection.db_type)} · ${connection.host}:${connection.port}` : 'Connected'}
            {' · '}Last read {readAt(snapshot)}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-3">
          <button className="btn btn-secondary" onClick={onRefresh}>
            <RefreshCw className="size-3.5" /> Refresh schema
          </button>
          <button className="btn btn-secondary" onClick={onConnectNew}>
            <Repeat className="size-3.5" /> Connect a different database
          </button>
        </div>
      </header>

      <div className="mt-10 flex gap-12">
        <Stat label="Tables" value={snapshot.totals.tables} />
        <Stat label="Columns" value={snapshot.totals.columns} />
        <Stat label="Relationships" value={snapshot.totals.relationships} />
        <Stat label="Rows" value={snapshot.totals.rows} />
      </div>

      <div className="relative mt-10 min-h-[480px] flex-1 overflow-auto rounded-card border border-rule bg-surface">
        <div className="dot-grid relative" style={{ width, height, minWidth: '100%' }}>
          <svg className="absolute inset-0" width={width} height={height} aria-hidden>
            <defs>
              <marker id="arrow" markerWidth="7" markerHeight="7" refX="6" refY="3" orient="auto">
                <path d="M0,0 L6,3 L0,6 z" fill="var(--rule-strong)" />
              </marker>
              <marker id="arrow-on" markerWidth="7" markerHeight="7" refX="6" refY="3" orient="auto">
                <path d="M0,0 L6,3 L0,6 z" fill="var(--accent)" />
              </marker>
            </defs>
            {snapshot.relationships.map((relationship, index) => {
              const child = nodes.get(relationship.from_table)
              const parent = nodes.get(relationship.to_table)
              if (!child || !parent || child === parent) return null

              const on = selected ? isConnected(relationship) : false
              const dim = selected && !on
              const startX = child.x
              const startY = child.y + HEADER_HEIGHT / 2 + 6
              const endX = parent.x + NODE_WIDTH
              const endY = parent.y + HEADER_HEIGHT / 2 + 6
              const midX = (startX + endX) / 2

              return (
                <g key={index} opacity={dim ? 0.3 : 1}>
                  <polyline
                    points={`${startX},${startY} ${midX},${startY} ${midX},${endY} ${endX},${endY}`}
                    fill="none"
                    stroke={on ? 'var(--accent)' : 'var(--rule-strong)'}
                    strokeWidth={1.5}
                    markerEnd={`url(#${on ? 'arrow-on' : 'arrow'})`}
                  />
                  <text
                    x={midX}
                    y={(startY + endY) / 2 - 6}
                    textAnchor="middle"
                    className="font-mono"
                    fontSize="10"
                    fill={on ? 'var(--accent)' : 'var(--ink-faint)'}
                  >
                    {relationship.from_column}
                  </text>
                </g>
              )
            })}
          </svg>

          {[...nodes.values()].map((node) => (
            <TableNode
              key={node.table.name}
              node={node}
              selected={selected === node.table.name}
              dimmed={Boolean(selected) && selected !== node.table.name}
              onSelect={() => setSelected(node.table.name)}
            />
          ))}
        </div>

        <div className="elevated pointer-events-none absolute bottom-4 right-4 flex gap-4 rounded-card border border-rule bg-surface px-4 py-2">
          <span className="t-label text-ink-faint">PK primary key</span>
          <span className="t-label text-ink-faint">FK foreign key</span>
          <span className="t-label text-ink-faint">→ references</span>
        </div>
      </div>

      <div className="mt-8 flex justify-end">
        <button className="btn btn-primary" onClick={onStart}>
          Start asking questions
        </button>
      </div>

      {selected && (
        <TableDetail
          table={nodes.get(selected)!.table}
          relationships={snapshot.relationships}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  )
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <p className="t-label text-ink-faint">{label}</p>
      <p className="t-kpi text-ink">{value.toLocaleString()}</p>
    </div>
  )
}

function TableNode({
  node,
  selected,
  dimmed,
  onSelect,
}: {
  node: Node
  selected: boolean
  dimmed: boolean
  onSelect: () => void
}) {
  const { table } = node
  const hidden = table.columns.length - VISIBLE_COLUMNS
  const foreignKeys = new Set(table.foreign_keys.map((key) => key.column))

  return (
    <button
      type="button"
      onClick={onSelect}
      style={{ left: node.x, top: node.y, width: NODE_WIDTH }}
      className={`absolute rounded-card border bg-surface p-4 text-left ${
        selected ? 'border-2 border-accent' : 'border-rule'
      } ${dimmed ? 'opacity-40' : ''}`}
    >
      <div className="flex items-baseline justify-between gap-2">
        <span className="t-card-title truncate text-ink">{table.name}</span>
        <span className="t-data shrink-0 text-ink-faint">{table.row_count.toLocaleString()}</span>
      </div>
      <div className="my-2 h-px bg-rule" />
      {table.columns.slice(0, VISIBLE_COLUMNS).map((column) => (
        <div key={column.name} className="flex items-center gap-1.5" style={{ height: ROW_HEIGHT }}>
          <span className="truncate font-mono text-[11.5px] text-ink-mid">{column.name}</span>
          {column.primary_key && <Chip>PK</Chip>}
          {foreignKeys.has(column.name) && <Chip>FK</Chip>}
          <span className="ml-auto shrink-0 truncate font-mono text-[11.5px] text-ink-faint">
            {shortType(column.type)}
          </span>
        </div>
      ))}
      {hidden > 0 && (
        <div className="font-mono text-[11.5px] text-accent" style={{ height: ROW_HEIGHT }}>
          + {hidden} more
        </div>
      )}
    </button>
  )
}

function Chip({ children }: { children: React.ReactNode }) {
  return (
    <span className="rounded-chip bg-accent-soft px-1 font-mono text-[9.5px] font-medium text-accent">
      {children}
    </span>
  )
}

function TableDetail({
  table,
  relationships,
  onClose,
}: {
  table: SnapshotTable
  relationships: Relationship[]
  onClose: () => void
}) {
  return (
    <aside className="fixed inset-y-0 right-0 w-[360px] overflow-y-auto border-l border-rule bg-surface p-6">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="t-page-title text-ink">{table.name}</h2>
          <p className="t-data mt-1 text-ink-faint">{table.row_count.toLocaleString()} rows</p>
        </div>
        <button className="icon-button" onClick={onClose} title="Close" aria-label="Close">
          <X className="size-4" />
        </button>
      </div>

      <p className="t-label mt-10 mb-4 text-ink-faint">Columns</p>
      <div className="flex flex-col gap-2">
        {table.columns.map((column) => (
          <div key={column.name} className="flex items-center gap-2">
            <span className="font-mono text-[12.5px] text-ink">{column.name}</span>
            {column.primary_key && <Chip>PK</Chip>}
            {!column.nullable && !column.primary_key && <Chip>NOT NULL</Chip>}
            <span className="ml-auto font-mono text-[12.5px] text-ink-faint">
              {shortType(column.type)}
            </span>
          </div>
        ))}
      </div>

      <p className="t-label mt-10 mb-4 text-ink-faint">Relationships</p>
      <ul className="flex flex-col gap-2">
        {sentences(table.name, relationships).map((sentence) => (
          <li key={sentence} className="t-secondary text-ink-mid">
            {sentence}
          </li>
        ))}
      </ul>
    </aside>
  )
}

/* Plain language, not a diagram: the same rule the rest of the product follows. */
function sentences(name: string, relationships: Relationship[]): string[] {
  const one = (value: string) => (value.endsWith('s') ? value.slice(0, -1) : value)
  const article = (value: string) => (/^[aeiou]/i.test(value) ? 'an' : 'a')

  const lines = relationships
    .filter((relationship) => relationship.from_table === name)
    .map((relationship) =>
      relationship.to_table === name
        ? `Each ${one(name)} may reference another ${one(name)}.`
        : `Each ${one(name)} belongs to one ${one(relationship.to_table)}.`,
    )
    .concat(
      relationships
        .filter((relationship) => relationship.to_table === name && relationship.from_table !== name)
        .map(
          (relationship) =>
            `${article(one(name))[0].toUpperCase()}${article(one(name)).slice(1)} ${one(name)} has many ${relationship.from_table} records.`,
        ),
    )
  return [...new Set(lines)].length ? [...new Set(lines)] : ['No relationships to other tables.']
}

function shortType(type: string): string {
  return type
    .replace('character varying', 'varchar')
    .replace('timestamp with time zone', 'timestamptz')
    .replace('double precision', 'float8')
}

function readAt(snapshot: Snapshot): string {
  const stamp = new Date(snapshot.stored_at ?? snapshot.read_at)
  const minutes = Math.round((Date.now() - stamp.getTime()) / 60000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes} minute${minutes === 1 ? '' : 's'} ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours} hour${hours === 1 ? '' : 's'} ago`
  return stamp.toLocaleDateString()
}
