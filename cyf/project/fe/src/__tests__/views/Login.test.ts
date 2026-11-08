import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { createI18n } from 'vue-i18n'
import messages from '@/locales'

const api = vi.hoisted(() => ({
  login: vi.fn(),
  register: vi.fn(),
  me: vi.fn()
}))
vi.mock('@/services/api', () => ({ authAPI: api }))

const syncMock = vi.hoisted(() => vi.fn(async () => null))
vi.mock('@/auth/sync', () => ({ syncCurrentRoles: syncMock }))

const routerMock = vi.hoisted(() => ({
  push: vi.fn(async () => undefined),
  replace: vi.fn(async () => undefined),
  currentRoute: { value: { query: {} as Record<string, string> } }
}))
vi.mock('vue-router', () => ({
  useRoute: () => routerMock.currentRoute.value,
  useRouter: () => routerMock
}))

import Login from '@/views/Login.vue'

const i18n = createI18n({ legacy: false, locale: 'zh', messages: messages as any })

const stubs = {
  'el-form': {
    template: '<form><slot /></form>',
    methods: { validate: () => Promise.resolve(true) }
  },
  'el-form-item': { template: '<div><slot /></div>' },
  'el-input': {
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template:
      '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />'
  },
  'el-button': { template: '<button @click="$emit(\'click\')"><slot /></button>' },
  'el-icon': { template: '<i><slot /></i>' },
  'el-tag': { template: '<span><slot /></span>' },
  'el-checkbox-group': { template: '<div><slot /></div>' },
  'el-checkbox': { template: '<label><slot /></label>' }
}

function mountLogin(query: Record<string, string> = {}) {
  routerMock.currentRoute = { value: { query } } as any
  return mount(Login, { global: { plugins: [createPinia(), i18n], stubs } })
}

const radioInputs = (wrapper: ReturnType<typeof mountLogin>) => wrapper.findAll('input[type="radio"]')
const textInputs = (wrapper: ReturnType<typeof mountLogin>) => wrapper.findAll('input:not([type="radio"])')

async function fillLoginForm(wrapper: ReturnType<typeof mountLogin>, username: string, password: string) {
  const inputs = textInputs(wrapper)
  await inputs[0].setValue(username)
  await inputs[1].setValue(password)
}

beforeEach(() => {
  localStorage.clear()
  vi.clearAllMocks()
  setActivePinia(createPinia())
  api.login.mockResolvedValue({
    success: true,
    msg: '登录成功',
    data: {
      username: 'tester',
      user_id: 7,
      roles: ['chat'],
      role: 'user',
      access_token: 'at',
      access_token_expires_at: 9999999999,
      refresh_token: 'rt',
      refresh_token_expires_at: 9999999999
    }
  })
  api.register.mockResolvedValue({
    success: true,
    msg: '注册成功',
    data: { username: 'newbie', roles: ['chat'] }
  })
  api.me.mockResolvedValue({
    success: true,
    data: { username: 'tester', user_id: 7, roles: ['chat'], role: 'user' }
  })
  syncMock.mockResolvedValue(null)
})

describe('登录页功能选择', () => {
  it('默认选中智能对话，并展示三张功能卡', () => {
    const wrapper = mountLogin()
    const radios = radioInputs(wrapper)
    expect(radios).toHaveLength(3)
    expect((radios[0].element as HTMLInputElement).value).toBe('chat')
    expect((radios[0].element as HTMLInputElement).checked).toBe(true)
  })

  it('切换功能卡会更新按钮文案', async () => {
    const wrapper = mountLogin()
    await radioInputs(wrapper)[1].setValue('quant')
    expect(wrapper.text()).toContain('量化研究')
    expect(wrapper.text()).toContain('登录并进入量化研究')
  })

  it('量化与声音带「需授权」标签', () => {
    const wrapper = mountLogin()
    expect(wrapper.text()).toContain('需授权')
    expect(wrapper.text()).toContain('注册即开通')
  })

  it('管理员入口复用同一表单', async () => {
    const wrapper = mountLogin()
    const adminEntry = wrapper.findAll('button').find((item) => item.text().includes('管理员入口'))
    await adminEntry?.trigger('click')
    expect(wrapper.text()).toContain('登录并进入管理后台')
  })
})

describe('登录流程', () => {
  it('登录成功后按当前选择进入目标模块', async () => {
    api.login.mockResolvedValue({
      success: true,
      msg: '登录成功',
      data: {
        username: 'researcher',
        user_id: 11,
        roles: ['chat', 'quant'],
        role: 'user',
        access_token: 'at',
        refresh_token: 'rt'
      }
    })
    const wrapper = mountLogin()
    await radioInputs(wrapper)[1].setValue('quant')
    await fillLoginForm(wrapper, 'tester', 'test123')
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(api.login).toHaveBeenCalledWith('tester', 'test123')
    expect(routerMock.push).toHaveBeenCalledWith('/quant/overview')
  })

  it('登录失败时不跳转', async () => {
    api.login.mockResolvedValue({ success: false, msg: '密码错误' })
    const wrapper = mountLogin()
    await fillLoginForm(wrapper, 'tester', 'wrong')
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(routerMock.push).not.toHaveBeenCalled()
  })

  it('目标未开通时保留登录态并展示权限引导', async () => {
    api.login.mockResolvedValue({
      success: true,
      msg: '登录成功',
      data: {
        username: 'chat_only',
        user_id: 9,
        roles: ['chat'],
        role: 'user',
        access_token: 'at',
        refresh_token: 'rt'
      }
    })
    const wrapper = mountLogin()
    await radioInputs(wrapper)[1].setValue('quant')
    await fillLoginForm(wrapper, 'chat_only', 'test123')
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(routerMock.push).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('该功能暂未开通')
  })
})

describe('注册流程', () => {
  const openRegister = async (wrapper: ReturnType<typeof mountLogin>) => {
    const registerButton = wrapper.findAll('button').find((item) => item.text().includes('还没有账户'))
    await registerButton?.trigger('click')
  }

  it('注册表单展示只读初始权限', async () => {
    const wrapper = mountLogin()
    await openRegister(wrapper)
    expect(wrapper.text()).toContain('聊天已开通')
    expect(wrapper.text()).toContain('量化需管理员开通')
    expect(wrapper.text()).toContain('声音需管理员开通')
  })

  it('注册成功后回到登录表单并预填用户名', async () => {
    const wrapper = mountLogin()
    await openRegister(wrapper)
    expect(wrapper.text()).toContain('新账号默认开通聊天。')
    const inputs = textInputs(wrapper)
    await inputs[0].setValue('newbie')
    await inputs[1].setValue('test123')
    await inputs[2].setValue('test123')
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(api.register).toHaveBeenCalledWith('newbie', 'test123', undefined)
    // 回到登录表单：目标设为聊天，用户名预填、密码清空
    expect(wrapper.text()).toContain('还没有账户？立即注册')
    expect(wrapper.text()).toContain('登录并进入智能对话')
    const loginInputs = textInputs(wrapper)
    expect((loginInputs[0].element as HTMLInputElement).value).toBe('newbie')
    expect((loginInputs[1].element as HTMLInputElement).value).toBe('')
  })
})
