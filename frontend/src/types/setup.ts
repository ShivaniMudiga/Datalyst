export interface ConnectionInput {
  host: string
  port: string
  database: string
  username: string
  password: string
  db_type: string
  permission: string
  purpose: string
}

export interface Connection {
  id: string
  db_type: string
  host: string
  port: string
  database: string
  username: string
  permission: string
  purpose: string
  created_at: string
  is_active: boolean
}

export interface ConnectionState {
  connection: Connection | null
  has_snapshot: boolean
}

export interface SnapshotColumn {
  name: string
  type: string
  nullable: boolean
  primary_key: boolean
}

export interface SnapshotForeignKey {
  column: string
  references_table: string
  references_column: string
}

export interface SnapshotTable {
  name: string
  row_count: number
  columns: SnapshotColumn[]
  foreign_keys: SnapshotForeignKey[]
}

export interface Relationship {
  from_table: string
  from_column: string
  to_table: string
  to_column: string
}

export interface Snapshot {
  database: string
  read_at: string
  stored_at?: string
  tables: SnapshotTable[]
  relationships: Relationship[]
  totals: { tables: number; columns: number; relationships: number; rows: number }
}

export interface AnalyseStep {
  event: 'step' | 'done' | 'error'
  key?: string
  label?: string
  result?: string
  index?: number
  total?: number
  snapshot?: Snapshot
  message?: string
}
