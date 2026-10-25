<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type { KeepaliveState } from '@/services/voiceApi'

const props = defineProps<{ status: KeepaliveState | null; busy: boolean }>()
const emit = defineEmits<{ save: [data: { enabled: boolean; hour: number; minute: number; disabled_voices: string[] }]; run: [] }>()

const form = reactive({ enabled: true, hour: 3, minute: 17, disabled_voices: [] as string[] })
watch(() => props.status, status => {
  if (!status) return
  form.enabled = status.enabled
  form.hour = status.hour
  form.minute = status.minute
  form.disabled_voices = status.voices.filter(voice => voice.disabled).map(voice => voice.voice_id)
}, { immediate: true })

const pending = computed(() => (props.status?.voices || []).filter(voice => !voice.disabled))
const nextVoice = computed(() => pending.value.slice().sort((a, b) => (a.days_left ?? 99) - (b.days_left ?? 99))[0])
const nextRunText = computed(() => {
  if (!props.status) return '—'
  return `${String(props.status.hour).padStart(2, '0')}:${String(props.status.minute).padStart(2, '0')}`
})

function save() {
  if (props.busy) return
  if (form.hour < 0 || form.hour > 23 || form.minute < 0 || form.minute > 59) {
    ElMessage.error('执行时间需在 00:00–23:59 之间。')
    return
  }
  emit('save', { ...form })
}
</script>

<template>
  <div class="studio-keepalive">
    <div class="studio-keepalive-main">
      <label class="studio-keepalive-switch"><input v-model="form.enabled" type="checkbox" /> 每日自动激活到期音色</label>
      <label class="studio-keepalive-time">每天 <input v-model.number="form.hour" type="number" min="0" max="23" step="1" aria-label="执行小时" /> 时 <input v-model.number="form.minute" type="number" min="0" max="59" step="1" aria-label="执行分钟" /> 分</label>
      <div class="studio-actions">
        <button class="studio-button" :disabled="busy" @click="save">保存设置</button>
        <button class="studio-button" :disabled="busy || !status?.enabled" @click="emit('run')">立即执行一次</button>
      </div>
    </div>
    <p class="studio-note">复刻音色 7 天内没有正式调用会被 MiniMax 删除。到期前 1 天，服务端会自动用该音色合成一句日期播报（如“现在是 2026 年 10 月 22 日 20 时 45 分”）续期，只生成链接、不保存本地音频，消耗少量额度。</p>
    <p class="studio-note">每日执行时间：{{ nextRunText }}<template v-if="nextVoice"> · 下一个待保活：{{ nextVoice.voice_id }}<template v-if="nextVoice.days_left !== null">（还剩 {{ nextVoice.days_left }} 天）</template></template><template v-else> · 当前没有待保活的音色</template></p>
  </div>
</template>
