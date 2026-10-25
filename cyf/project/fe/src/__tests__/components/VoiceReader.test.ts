import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import VoiceReader from '@/components/studio/voice/VoiceReader.vue'
import type { VoiceState } from '@/services/voiceApi'

const state: VoiceState = {
  config: { ready: true, region: 'cn', key_kind: 'token_plan', model: 'speech-2.8-hd', base_url: 'https://api.minimax.cn', timeout_seconds: 180, config_path: 'test.ini', storage_dir: '/tmp/voice', clone_ready: true, clone_region: 'cn', clone_base_url: 'https://api.minimax.cn', clone_dedicated: false },
  models: ['speech-2.8-hd'], default_voice_id: 'YuexiTest001', last_sync: null, history: [],
  voices: [{ voice_id: 'YuexiTest001', alias: '我的声音', voice_type: 'voice_cloning', description: '', status: 'pending', created_time: '' }]
}

describe('故事朗读提交', () => {
  it('粘贴正文后提交所选音色和参数，不改写正文', async () => {
    const wrapper = mount(VoiceReader, { props: { state, selectedVoice: 'YuexiTest001', busy: false } })
    await wrapper.get('textarea').setValue('阿禾沿着月溪，轻轻走回了家。\n晚安。')
    await wrapper.get('form').trigger('submit')
    const payload = wrapper.emitted('synthesize')?.[0][0] as any
    expect(payload.text).toBe('阿禾沿着月溪，轻轻走回了家。\n晚安。')
    expect(payload.voice_id).toBe('YuexiTest001')
    expect(payload.speed).toBe(0.9)
    expect(wrapper.text()).toContain('首次正式合成可能包含音色费用')
  })

  it('已有生成请求进行时禁止再次提交', async () => {
    const wrapper = mount(VoiceReader, { props: { state, selectedVoice: 'YuexiTest001', busy: true } })
    await wrapper.get('form').trigger('submit')
    expect(wrapper.emitted('synthesize')).toBeUndefined()
    expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeDefined()
  })

  it('从历史载入正文可以再编辑', async () => {
    const wrapper = mount(VoiceReader, { props: { state, selectedVoice: 'YuexiTest001', busy: false } })
    wrapper.vm.loadStory('第十一集', '保存过的故事')
    await wrapper.vm.$nextTick()
    expect((wrapper.get('textarea').element as HTMLTextAreaElement).value).toBe('保存过的故事')
    await wrapper.get('textarea').setValue('重新编辑的故事')
    await wrapper.get('form').trigger('submit')
    expect((wrapper.emitted('synthesize')?.[0][0] as any).title).toBe('第十一集')
    expect((wrapper.emitted('synthesize')?.[0][0] as any).text).toBe('重新编辑的故事')
  })
})
