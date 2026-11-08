import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { createI18n } from 'vue-i18n'
import messages from '@/locales'

const adminApi = vi.hoisted(() => ({
  list: vi.fn(),
  get: vi.fn(),
  create: vi.fn(),
  update: vi.fn(),
  delete: vi.fn()
}))
vi.mock('@/services/adminApi', () => ({ userAPI: adminApi }))

import UserTable from '@/components/admin/UserTable.vue'

const i18n = createI18n({ legacy: false, locale: 'zh', messages: messages as any })

const stubs = {
  'el-table': { template: '<div><slot /></div>' },
  'el-table-column': { template: '<div><slot :row="{}" /></div>' },
  'el-input': {
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template: '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />'
  },
  'el-button': { template: '<button @click="$emit(\'click\')"><slot /></button>' },
  'el-icon': { template: '<i><slot /></i>' },
  'el-tag': { template: '<span><slot /></span>' },
  'el-select': { template: '<div><slot /></div>' },
  'el-option': { template: '<div><slot /></div>' },
  'el-switch': {
    props: ['modelValue'],
    emits: ['update:modelValue', 'change'],
    template: '<input type="checkbox" :checked="modelValue" @change="$emit(\'update:modelValue\', $event.target.checked); $emit(\'change\', $event.target.checked)" />'
  },
  'el-checkbox-group': {
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template: '<div><slot /></div>'
  },
  'el-checkbox': { template: '<label><slot /></label>' },
  'el-form': { template: '<form><slot /></form>' },
  'el-form-item': { template: '<div><slot /></div>' },
  'el-dialog': { template: '<div><slot /><slot name="footer" /></div>' },
  'el-pagination': { template: '<div />' }
}

function mountTable() {
  return mount(UserTable, { global: { plugins: [createPinia(), i18n], stubs } })
}

beforeEach(() => {
  localStorage.clear()
  vi.clearAllMocks()
  setActivePinia(createPinia())
  adminApi.list.mockResolvedValue({
    success: true,
    data: {
      items: [
        {
          id: 1,
          username: 'combo_user',
          api_key_masked: 'sk-****abcd',
          role: 'user',
          roles: ['chat', 'quant'],
          is_active: true,
          created_at: '',
          updated_at: ''
        },
        {
          id: 2,
          username: 'sound_only',
          api_key_masked: '-',
          role: 'user',
          roles: ['sound'],
          is_active: false,
          created_at: '',
          updated_at: ''
        }
      ],
      pagination: { page: 1, page_size: 20, total: 2, pages: 1 }
    }
  })
  adminApi.get.mockResolvedValue({
    success: true,
    data: {
      id: 2,
      username: 'sound_only',
      api_key: '',
      role: 'user',
      roles: ['sound'],
      is_active: false
    }
  })
  adminApi.create.mockResolvedValue({ success: true, data: { id: 3, roles: ['quant'] } })
  adminApi.update.mockResolvedValue({ success: true, data: { id: 2, roles: ['chat', 'sound'] } })
  adminApi.delete.mockResolvedValue({ success: true })
})

describe('用户列表角色展示', () => {
  it('列表显示多个角色标签', async () => {
    const wrapper = mountTable()
    await flushPromises()
    expect(wrapper.text()).toContain('智能对话')
    expect(wrapper.text()).toContain('量化研究')
    expect(wrapper.text()).toContain('声音创作')
  })

  it('按角色筛选走成员关系', async () => {
    const wrapper = mountTable()
    await flushPromises()
    adminApi.list.mockClear()
    const vm: any = wrapper.vm
    vm.roleFilter = 'quant'
    await vm.onRoleFilterChange()
    expect(adminApi.list).toHaveBeenCalledWith(expect.objectContaining({ role: 'quant' }))
  })
})

describe('角色编辑', () => {
  it('编辑仅量化账号时正确回显', async () => {
    const wrapper = mountTable()
    await flushPromises()
    adminApi.get.mockResolvedValue({
      success: true,
      data: { id: 5, username: 'quant_only', api_key: '', role: 'user', roles: ['quant'], is_active: true }
    })
    const vm: any = wrapper.vm
    await vm.openEditDialog({ id: 5, username: 'quant_only' })
    await flushPromises()
    expect(vm.formData.roles).toEqual(['quant'])
    expect(vm.formData.isAdmin).toBe(false)
  })

  it('保存时提交 roles 数组', async () => {
    const wrapper = mountTable()
    await flushPromises()
    const vm: any = wrapper.vm
    adminApi.get.mockResolvedValue({
      success: true,
      data: { id: 7, username: 'combo_user', api_key: '', role: 'user', roles: ['chat', 'quant'], is_active: true }
    })
    await vm.openEditDialog({ id: 7, username: 'combo_user' })
    await flushPromises()
    vm.formData.roles = ['chat', 'quant']
    await vm.saveUser()
    await flushPromises()
    expect(adminApi.update).toHaveBeenCalledWith(
      expect.objectContaining({ id: 7, roles: ['chat', 'quant'] })
    )
  })

  it('管理员开启时提交 ["admin"]', async () => {
    const wrapper = mountTable()
    await flushPromises()
    const vm: any = wrapper.vm
    adminApi.get.mockResolvedValue({
      success: true,
      data: { id: 7, username: 'combo_user', api_key: '', role: 'user', roles: ['chat'], is_active: true }
    })
    await vm.openEditDialog({ id: 7, username: 'combo_user' })
    await flushPromises()
    vm.formData.isAdmin = true
    await vm.saveUser()
    await flushPromises()
    expect(adminApi.update).toHaveBeenCalledWith(expect.objectContaining({ roles: ['admin'] }))
  })

  it('未选择任何角色时拒绝保存', async () => {
    const wrapper = mountTable()
    await flushPromises()
    const vm: any = wrapper.vm
    adminApi.get.mockResolvedValue({
      success: true,
      data: { id: 7, username: 'combo_user', api_key: '', role: 'user', roles: ['chat'], is_active: true }
    })
    await vm.openEditDialog({ id: 7, username: 'combo_user' })
    await flushPromises()
    vm.formData.roles = []
    await vm.saveUser()
    await flushPromises()
    expect(adminApi.update).not.toHaveBeenCalled()
  })
})
