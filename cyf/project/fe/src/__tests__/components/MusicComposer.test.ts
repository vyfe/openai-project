import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import MusicComposer from '@/components/studio/music/MusicComposer.vue'
import type { MusicState } from '@/services/musicApi'

const state: MusicState = {
  config: { ready: true, region: 'cn', key_kind: 'token_plan', model: 'music-3.0', cover_model: 'music-cover', dedicated_key: false, base_url: 'https://api.minimax.cn', timeout_seconds: 180, config_path: 'test.ini', storage_dir: '/tmp/voice' },
  models: ['music-3.0', 'music-2.6'], tracks: []
}

describe('音乐创作提交', () => {
  it('带人声缺少歌词时不提交', async () => {
    const wrapper = mount(MusicComposer, { props: { state, busy: false } })
    await wrapper.find('textarea').setValue('轻快的独立民谣')
    await wrapper.get('form').trigger('submit')
    expect(wrapper.emitted('generate')).toBeUndefined()
  })

  it('开启自动写词后带人声可提交', async () => {
    const wrapper = mount(MusicComposer, { props: { state, busy: false } })
    await wrapper.findAll('input[type="checkbox"]')[1].setValue(true)
    await wrapper.find('textarea').setValue('轻快的独立民谣')
    await wrapper.get('form').trigger('submit')
    const payload = wrapper.emitted('generate')?.[0][0] as any
    expect(payload.lyrics_optimizer).toBe(true)
    expect(payload.model).toBe('music-3.0')
  })

  it('纯音乐只需风格描述，歌词输入框不出现', async () => {
    const wrapper = mount(MusicComposer, { props: { state, busy: false } })
    await wrapper.findAll('input[type="checkbox"]')[0].setValue(true)
    await wrapper.find('textarea').setValue('轻快的独立民谣')
    await wrapper.get('form').trigger('submit')
    const payload = wrapper.emitted('generate')?.[0][0] as any
    expect(payload.instrumental).toBe(true)
    expect(payload.prompt).toBe('轻快的独立民谣')
    expect(wrapper.findAll('textarea')).toHaveLength(1)
  })

  it('载入历史作品后可以再编辑', async () => {
    const wrapper = mount(MusicComposer, { props: { state, busy: false } })
    wrapper.vm.loadTrack('旧作品', '旧风格', '旧歌词')
    await wrapper.vm.$nextTick()
    const texts = wrapper.findAll('textarea')
    expect((texts[0].element as HTMLTextAreaElement).value).toBe('旧风格')
    expect((texts[1].element as HTMLTextAreaElement).value).toBe('旧歌词')
  })

  it('翻唱模式未提取歌词时不提交', async () => {
    const wrapper = mount(MusicComposer, { props: { state, busy: false } })
    await wrapper.findAll('input[type="radio"]')[1].setValue(true)
    await wrapper.get('form').trigger('submit')
    expect(wrapper.emitted('cover-generate')).toBeUndefined()
    expect(wrapper.emitted('cover-preprocess')).toBeUndefined()
  })

  it('提取歌词后可提交翻唱', async () => {
    const wrapper = mount(MusicComposer, { props: { state, busy: false } })
    await wrapper.findAll('input[type="radio"]')[1].setValue(true)
    wrapper.vm.loadCover('20261022-160914-18d3cf5a', '[Verse]\n街角的路灯亮了', 42.5)
    await wrapper.vm.$nextTick()
    const texts = wrapper.findAll('textarea')
    expect((texts[1].element as HTMLTextAreaElement).value).toBe('[Verse]\n街角的路灯亮了')
    await texts[0].setValue('流行摇滚，女声演唱，副歌有强力和弦')
    await wrapper.get('form').trigger('submit')
    const payload = wrapper.emitted('cover-generate')?.[0][0] as any
    expect(payload.id).toBe('20261022-160914-18d3cf5a')
    expect(payload.prompt).toBe('流行摇滚，女声演唱，副歌有强力和弦')
    expect(payload.lyrics).toBe('[Verse]\n街角的路灯亮了')
  })
})
