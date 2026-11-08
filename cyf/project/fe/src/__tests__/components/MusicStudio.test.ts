import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { useAuthStore } from '@/stores/auth'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { MusicState } from '@/services/musicApi'

const api = vi.hoisted(() => ({ state: vi.fn(), generate: vi.fn(), coverPreprocess: vi.fn(), coverGenerate: vi.fn(),
  track: vi.fn(), delete: vi.fn(), audio: vi.fn() }))
vi.mock('@/services/musicApi', () => ({ musicAPI: api }))
import MusicStudio from '@/components/studio/MusicStudio.vue'

const pinia = createPinia()
setActivePinia(pinia)
useAuthStore(pinia).login({ username: 'admin', roles: ['admin'], access_token: 'at', refresh_token: 'rt' })
const mountOptions = { global: { plugins: [pinia] } }

const initial: MusicState = {
  config: { ready: true, region: 'cn', key_kind: 'token_plan', model: 'music-3.0', cover_model: 'music-cover', dedicated_key: false, base_url: 'https://api.minimax.cn', timeout_seconds: 180, config_path: 'test.ini', storage_dir: '/tmp/voice' },
  models: ['music-3.0', 'music-2.6'], tracks: []
}
beforeEach(() => { vi.clearAllMocks(); api.state.mockResolvedValue(structuredClone(initial)) })

describe('音乐创作管理流程', () => {
  it('初次进入只读本地状态，不自动发起付费生成', async () => {
    const wrapper = mount(MusicStudio, mountOptions)
    await flushPromises()
    expect(wrapper.text()).toContain('还没有作品')
    expect(api.generate).not.toHaveBeenCalled()
    expect(api.coverGenerate).not.toHaveBeenCalled()
  })

  it('生成失败显示官方错误，不循环重试', async () => {
    api.generate.mockRejectedValue({ response: { data: { msg: 'MiniMax 1008：账号余额不足' } } })
    const wrapper = mount(MusicStudio, mountOptions)
    await flushPromises()
    wrapper.findComponent({ name: 'MusicComposer' }).vm.$emit('generate', { title: '作品', prompt: '风格', lyrics: '歌词', model: 'music-3.0', instrumental: false, lyrics_optimizer: false })
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain('1008')
    expect(api.generate).toHaveBeenCalledTimes(1)
  })

  it('有请求执行时再次提交不会重放付费生成', async () => {
    let finish: (result: unknown) => void = () => {}
    api.generate.mockImplementation(() => new Promise(resolve => { finish = resolve }))
    const wrapper = mount(MusicStudio, mountOptions)
    await flushPromises()
    const composer = wrapper.findComponent({ name: 'MusicComposer' })
    composer.vm.$emit('generate', { title: '作品', prompt: '风格', lyrics: '歌词', model: 'music-3.0', instrumental: false, lyrics_optimizer: false })
    composer.vm.$emit('generate', { title: '作品', prompt: '风格', lyrics: '歌词', model: 'music-3.0', instrumental: false, lyrics_optimizer: false })
    expect(api.generate).toHaveBeenCalledTimes(1)
    finish(undefined)
    await flushPromises()
  })

  it('参考音频提取歌词后回填到编辑器', async () => {
    api.coverPreprocess.mockResolvedValue({ id: '20261022-160914-18d3cf5a', lyrics: '[Verse]\n街角的路灯亮了', reference_duration: 42.5 })
    const wrapper = mount(MusicStudio, mountOptions)
    await flushPromises()
    wrapper.findComponent({ name: 'MusicComposer' }).vm.$emit('cover-preprocess', { file: new File(['x'], 'song.mp3'), duration: 42.5, title: '翻唱一版' })
    await flushPromises()
    expect(api.coverPreprocess).toHaveBeenCalledTimes(1)
    const form = api.coverPreprocess.mock.calls[0][0] as FormData
    expect(form.get('audio_duration')).toBe('42.5')
    expect((form.get('audio') as File).name).toBe('song.mp3')
    const texts = wrapper.findAll('textarea')
    expect((texts[1].element as HTMLTextAreaElement).value).toBe('[Verse]\n街角的路灯亮了')
    expect(wrapper.text()).toContain('参考音频已上传')
    expect(wrapper.text()).toContain('并提取歌词')
  })

  it('未配置独立密钥时说明沿用语音密钥', async () => {
    const wrapper = mount(MusicStudio, mountOptions)
    await flushPromises()
    expect(wrapper.text()).toContain('沿用语音密钥')
  })

  it('配置独立密钥时说明密钥来源并给出配置段', async () => {
    api.state.mockResolvedValue({ ...structuredClone(initial), config: { ...initial.config, dedicated_key: true } })
    const wrapper = mount(MusicStudio, mountOptions)
    await flushPromises()
    expect(wrapper.text()).toContain('独立音乐密钥')
    wrapper.findAll('.studio-tabs button').find(button => button.text().includes('连接配置'))!.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('[minimax_music]')
  })
})
