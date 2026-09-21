import { describe, expect, it } from 'vitest'

import {
  formatSqlCell,
  normalizeSqlExecutionData,
  normalizeSqlMetadata
} from '@/utils/adminData'

describe('admin data normalizers', () => {
  it('解析 SQL 接口的 columns/rows 响应', () => {
    expect(normalizeSqlExecutionData({
      columns: ['id', 'name'],
      rows: [{ id: 1, name: 'admin' }],
      summary: 'statement=select target=users params_count=0'
    })).toEqual({
      columns: ['id', 'name'],
      rows: [{ id: 1, name: 'admin' }],
      summary: 'statement=select target=users params_count=0'
    })
  })

  it('兼容旧版 SQL 数组和单对象响应', () => {
    expect(normalizeSqlExecutionData([{ id: 1, active: true }]).columns).toEqual(['id', 'active'])
    expect(normalizeSqlExecutionData({ id: 1 }).rows).toEqual([{ id: 1 }])
  })

  it('解析元信息并兼容旧版表名数组', () => {
    expect(normalizeSqlMetadata({
      database: { path: '/tmp/logs.db' },
      tables: [{
        table_name: 'users',
        row_count: 2,
        columns: [{ name: 'id', data_type: 'INTEGER', nullable: false, primary_key: true }]
      }]
    })).toEqual({
      databasePath: '/tmp/logs.db',
      tables: [{
        table_name: 'users',
        row_count: 2,
        columns: [{ name: 'id', data_type: 'INTEGER', nullable: false, primary_key: true }]
      }]
    })
    expect(normalizeSqlMetadata({ tables: ['users'] }).tables[0].table_name).toBe('users')
  })

  it('避免表格单元格显示为 [object Object]', () => {
    expect(formatSqlCell({ role: 'admin' })).toBe('{"role":"admin"}')
    expect(formatSqlCell(null)).toBe('-')
  })
})
