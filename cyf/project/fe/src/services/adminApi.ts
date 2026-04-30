import { createApiClient } from '@/services/httpClient'

const adminApi = createApiClient({
  requireAuthByDefault: true
})

export const modelMetaAPI = {
  list: (params?: { recommend?: boolean; status_valid?: boolean; page?: number; page_size?: number; keyword?: string }) =>
    adminApi.get('/never_guess_my_usage/model_meta/list', { params }),
  get: (id: number) => adminApi.get(`/never_guess_my_usage/model_meta/get/${id}`),
  create: (data: any) => adminApi.post('/never_guess_my_usage/model_meta/create', data),
  update: (data: any) => adminApi.post('/never_guess_my_usage/model_meta/update', data),
  delete: (id: number) => adminApi.post('/never_guess_my_usage/model_meta/delete', { id }),
  batchUpdate: (data: { ids: number[]; recommend?: boolean; allow_net?: boolean; status_valid?: boolean; model_grp?: string }) =>
    adminApi.post('/never_guess_my_usage/model_meta/batch_update', data)
}

export const systemPromptAPI = {
  list: (params?: { role_group?: string; status_valid?: boolean; page?: number; page_size?: number; keyword?: string }) =>
    adminApi.get('/never_guess_my_usage/system_prompt/list', { params }),
  get: (id: number) => adminApi.get(`/never_guess_my_usage/system_prompt/get/${id}`),
  create: (data: any) => adminApi.post('/never_guess_my_usage/system_prompt/create', data),
  update: (data: any) => adminApi.post('/never_guess_my_usage/system_prompt/update', data),
  delete: (id: number) => adminApi.post('/never_guess_my_usage/system_prompt/delete', { id })
}

export const userAPI = {
  list: (params?: { page?: number; page_size?: number; keyword?: string; role?: string; is_active?: boolean }) =>
    adminApi.get('/never_guess_my_usage/user/list', { params }),
  get: (id: number) => adminApi.get(`/never_guess_my_usage/user/get/${id}`),
  create: (data: any) => adminApi.post('/never_guess_my_usage/user/create', data),
  update: (data: any) => adminApi.post('/never_guess_my_usage/user/update', data),
  delete: (id: number, hardDelete?: boolean) =>
    adminApi.post('/never_guess_my_usage/user/delete', { id, hard_delete: hardDelete })
}

export const notificationAPI = {
  list: (params?: { status?: string; page?: number; page_size?: number; keyword?: string }) =>
    adminApi.get('/never_guess_my_usage/notification/list', { params }),
  get: (id: number) => adminApi.get(`/never_guess_my_usage/notification/get/${id}`),
  create: (data: any) => adminApi.post('/never_guess_my_usage/notification/create', data),
  update: (data: any) => adminApi.post('/never_guess_my_usage/notification/update', data),
  delete: (id: number) => adminApi.post('/never_guess_my_usage/notification/delete', { id })
}

export const testLimitAPI = {
  list: (params?: { page?: number; page_size?: number; keyword?: string }) =>
    adminApi.get('/never_guess_my_usage/test_limit/list', { params }),
  get: (id: number) => adminApi.get(`/never_guess_my_usage/test_limit/get/${id}`),
  create: (data: any) => adminApi.post('/never_guess_my_usage/test_limit/create', data),
  update: (data: any) => adminApi.post('/never_guess_my_usage/test_limit/update', data),
  delete: (id: number) => adminApi.post('/never_guess_my_usage/test_limit/delete', { id }),
  reset: (data: { id?: number; user_ip?: string; reset_all?: boolean }) =>
    adminApi.post('/never_guess_my_usage/test_limit/reset', data)
}

export const sqlAPI = {
  execute: (sql: string, params?: any[]) =>
    adminApi.post('/never_guess_my_usage/sql_execute', { sql, params }),
  meta: () => adminApi.get('/never_guess_my_usage/sql/meta')
}

export const runtimeAPI = {
  overview: () => adminApi.get('/never_guess_my_usage/runtime/overview')
}
