import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import VoiceKeepalive from '@/components/studio/voice/VoiceKeepalive.vue'
import type { KeepaliveState } from '@/services/voiceApi'

const status: KeepaliveState = {
  enabled: true, hour: 3, minute: 17,
  voices: [{ voice_id: 'MyVoice001', deadline: '2026-10-29T03:17:00+00:00', days_left: 2, disabled: false, activated_at: '2026-10-22T03:17:00+00:00', keepalive_count: 1 }]
}

describe('音色保活面板', () => {
  it('展示下一个待保活音色与剩余天数', () => {
    const wrapper = mount(VoiceKeepalive, { props: { status, busy: false } })
    expect(wrapper.text()).toContain('MyVoice001')
    expect(wrapper.text()).toContain('还剩 2 天')
    expect(wrapper.text()).toContain('03:17')
  })

  it('保存时提交开关、时间和禁用列表', async () => {
    const wrapper = mount(VoiceKeepalive, { props: { status, busy: false } })
    await wrapper.get('button').trigger('click')
    const payload = wrapper.emitted('save')?.[0][0] as any
    expect(payload.enabled).toBe(true)
    expect(payload.hour).toBe(3)
    expect(payload.minute).toBe(17)
    expect(payload.disabled_voices).toEqual([])
  })

  it('点击立即执行触发运行事件', async () => {
    const wrapper = mount(VoiceKeepalive, { props: { status, busy: false } })
    const buttons = wrapper.findAll('button')
    await buttons[buttons.length - 1].trigger('click')
    expect(wrapper.emitted('run')).toBeTruthy()
  })

  it('没有音色时不显示待保活提示', () => {
    const wrapper = mount(VoiceKeepalive, { props: { status: { ...status, voices: [] }, busy: false } })
    expect(wrapper.text()).toContain('当前没有待保活的音色')
  })
})
