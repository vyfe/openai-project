export type SqlRow = Record<string, unknown>

export interface SqlExecutionData {
  columns: string[]
  rows: SqlRow[]
  summary: string
}

export interface SqlMetaColumn {
  name: string
  data_type: string
  nullable: boolean
  primary_key: boolean
}

export interface SqlMetaTable {
  table_name: string
  row_count: number
  columns: SqlMetaColumn[]
}

export interface SqlMetadata {
  databasePath: string
  tables: SqlMetaTable[]
}

const isRecord = (value: unknown): value is Record<string, unknown> => (
  typeof value === 'object' && value !== null && !Array.isArray(value)
)

const columnsFromRows = (rows: SqlRow[]): string[] => {
  const columns = new Set<string>()
  rows.forEach((row) => Object.keys(row).forEach((column) => columns.add(column)))
  return [...columns]
}

export function normalizeSqlExecutionData(data: unknown): SqlExecutionData {
  if (Array.isArray(data)) {
    const rows = data.filter(isRecord) as SqlRow[]
    return { columns: columnsFromRows(rows), rows, summary: '' }
  }

  if (!isRecord(data)) {
    return { columns: [], rows: [], summary: '' }
  }

  const rows = Array.isArray(data.rows) ? data.rows.filter(isRecord) as SqlRow[] : []
  const explicitColumns = Array.isArray(data.columns)
    ? data.columns.filter((column): column is string => typeof column === 'string')
    : []

  if (rows.length > 0 || explicitColumns.length > 0 || 'summary' in data) {
    return {
      columns: explicitColumns.length > 0 ? explicitColumns : columnsFromRows(rows),
      rows,
      summary: typeof data.summary === 'string' ? data.summary : ''
    }
  }

  return { columns: Object.keys(data), rows: [data], summary: '' }
}

export function formatSqlCell(value: unknown): string {
  if (value === null || value === undefined || value === '') return '-'
  if (typeof value === 'object') {
    try {
      return JSON.stringify(value)
    } catch {
      return String(value)
    }
  }
  return String(value)
}

export function normalizeSqlMetadata(data: unknown): SqlMetadata {
  if (!isRecord(data)) return { databasePath: '', tables: [] }

  const database = isRecord(data.database) ? data.database : {}
  const rawTables = Array.isArray(data.tables) ? data.tables : []
  const tables = rawTables.flatMap((table): SqlMetaTable[] => {
    if (typeof table === 'string') {
      return [{ table_name: table, row_count: 0, columns: [] }]
    }
    if (!isRecord(table) || typeof table.table_name !== 'string') return []
    const rawColumns = Array.isArray(table.columns) ? table.columns : []
    const columns = rawColumns.flatMap((column): SqlMetaColumn[] => {
      if (!isRecord(column) || typeof column.name !== 'string') return []
      return [{
        name: column.name,
        data_type: typeof column.data_type === 'string' ? column.data_type : '',
        nullable: Boolean(column.nullable),
        primary_key: Boolean(column.primary_key)
      }]
    })
    return [{
      table_name: table.table_name,
      row_count: typeof table.row_count === 'number' ? table.row_count : 0,
      columns
    }]
  })

  return {
    databasePath: typeof database.path === 'string' ? database.path : '',
    tables
  }
}
