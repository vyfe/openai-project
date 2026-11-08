import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { useAuthStore } from '@/stores/auth'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { VoiceState } from '@/services/voiceApi'

const api = vi.hoisted(() => ({ state: vi.fn(), sync: vi.fn(), clone: vi.fn(), preference: vi.fn(), delete: vi.fn(),
  synthesize: vi.fn(), reading: vi.fn(), audio: vi.fn(), profile: vi.fn(), keepalive: vi.fn(), saveKeepalive: vi.fn(), runKeepalive: vi.fn() }))
vi.mock('@/services/voiceApi', () => ({ voiceAPI: api }))
import VoiceStudio from '@/components/studio/VoiceStudio.vue'

const initial: VoiceState = {
  config: { ready: true, region: 'cn', key_kind: 'token_plan', model: 'speech-2.8-hd', base_url: 'https://api.minimax.cn', timeout_seconds: 180, config_path: 'test.ini', storage_dir: '/tmp/voice', clone_ready: true, clone_region: 'cn', clone_base_url: 'https://api.minimax.cn', clone_dedicated: false },
  models: ['speech-2.8-hd'], default_voice_id: '', last_sync: null, history: [],
  voices: [{ voice_id: 'YuexiTest001', alias: '我的声音', voice_type: 'voice_cloning', description: '', status: 'pending', created_time: '' }]
}
const keepaliveState = { enabled: true, hour: 3, minute: 17, voices: [{ voice_id: 'YuexiTest001', deadline: null, days_left: 2, disabled: false, activated_at: null, keepalive_count: 0 }] }
const pinia = createPinia()
setActivePinia(pinia)
useAuthStore(pinia).login({ username: 'admin', roles: ['admin'], access_token: 'at', refresh_token: 'rt' })
const options = { global: { plugins: [pinia], stubs: { VoiceCloneForm: true, VoiceReader: true } } }
beforeEach(() => {
  vi.clearAllMocks()
  api.state.mockResolvedValue(structuredClone(initial))
  api.keepalive.mockResolvedValue(structuredClone(keepaliveState))
})
const button = (wrapper: ReturnType<typeof mount>, text: string) => wrapper.findAll('button').find(item => item.text() === text)!

describe('音色管理流程', () => {
  it('初次进入只读本地状态，不自动发起付费请求', async () => {
    const wrapper = mount(VoiceStudio, options)
    await flushPromises()
    expect(wrapper.text()).toContain('待首次合成')
    expect(api.sync).not.toHaveBeenCalled()
    expect(api.clone).not.toHaveBeenCalled()
    expect(api.synthesize).not.toHaveBeenCalled()
  })

  it('选择待激活音色进入朗读页', async () => {
    const wrapper = mount(VoiceStudio, options)
    await flushPromises()
    await button(wrapper, '试听 / 朗读').trigger('click')
    expect(wrapper.findComponent({ name: 'VoiceReader' }).props('selectedVoice')).toBe('YuexiTest001')
  })

  it('同步失败显示官方错误，不循环重试', async () => {
    api.sync.mockRejectedValue({ response: { data: { msg: 'MiniMax 1004：请核对语音权限' } } })
    const wrapper = mount(VoiceStudio, options)
    await flushPromises()
    await button(wrapper, '同步云端音色').trigger('click')
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain('1004')
    expect(api.sync).toHaveBeenCalledTimes(1)
  })

  it('有请求执行时再次提交不会重放付费生成', async () => {
    let finish: (result: unknown) => void = () => {}
    api.synthesize.mockImplementation(() => new Promise(resolve => { finish = resolve }))
    const wrapper = mount(VoiceStudio, options)
    await flushPromises()
    const reader = wrapper.findComponent({ name: 'VoiceReader' })
    reader.vm.$emit('synthesize', { text: '晚安', voice_id: 'YuexiTest001' })
    reader.vm.$emit('synthesize', { text: '晚安', voice_id: 'YuexiTest001' })
    expect(api.synthesize).toHaveBeenCalledTimes(1)
    finish(undefined)
    await flushPromises()
  })

  it('复刻走计费密钥、合成走语音密钥，界面分别标注', async () => {
    api.state.mockResolvedValue({ ...structuredClone(initial), config: { ...initial.config, clone_dedicated: true } })
    const wrapper = mount(VoiceStudio, options)
    await flushPromises()
    expect(wrapper.text()).toContain('复刻 计费密钥')
    wrapper.findAll('.studio-tabs button').find(button => button.text().includes('连接配置'))!.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('独立计费密钥（[minimax_music]）')
  })

  it('合成密钥未配置时提示合成不可用', async () => {
    api.state.mockResolvedValue({ ...structuredClone(initial), config: { ...initial.config, ready: false } })
    const wrapper = mount(VoiceStudio, options)
    await flushPromises()
    expect(wrapper.text()).toContain('语音合成密钥未配置')
  })

  it('音色卡片显示保活剩余天数', async () => {
    const wrapper = mount(VoiceStudio, options)
    await flushPromises()
    expect(wrapper.text()).toContain('保活还剩 2 天')
  })

  it('保存保活设置后调用后端接口', async () => {
    api.saveKeepalive.mockResolvedValue(null)
    const wrapper = mount(VoiceStudio, options)
    await flushPromises()
    const keepalivePanel = wrapper.findComponent({ name: 'VoiceKeepalive' })
    keepalivePanel.vm.$emit('save', { enabled: false, hour: 4, minute: 30, disabled_voices: [] })
    await flushPromises()
    expect(api.saveKeepalive).toHaveBeenCalledWith({ enabled: false, hour: 4, minute: 30, disabled_voices: [] })
  })

  it('立即执行保活时调用后端接口', async () => {
    api.runKeepalive.mockResolvedValue({ attempted: 1, results: [{ voice_id: 'YuexiTest001', ok: true }] })
    const wrapper = mount(VoiceStudio, options)
    await flushPromises()
    wrapper.findComponent({ name: 'VoiceKeepalive' }).vm.$emit('run')
    await flushPromises()
    expect(api.runKeepalive).toHaveBeenCalledTimes(1)
  })
})
