<script setup lang="ts">
import { onBeforeUnmount, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { checkAudioFile, readAudioDuration } from '@/utils/media'

defineProps<{ busy: boolean; ready: boolean }>()
const emit = defineEmits<{ create: [data: FormData] }>()
const form = reactive({ alias: '我的音色', voice_id: `MyVoice${Date.now()}`, consent: false,
  need_noise_reduction: false, need_volume_normalization: false, prompt_text: '' })
const sample = ref<File | null>(null)
const prompt = ref<File | null>(null)
const durations = reactive({ sample: 0, prompt: 0 })
const sampleUrl = ref('')
const loadingAudio = ref(false)
let generation = 0

async function selectFile(event: Event, kind: 'sample' | 'prompt') {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  const version = ++generation
  loadingAudio.value = true
  try {
    checkAudioFile(file, ['mp3', 'm4a', 'wav'], 'MP3、M4A 或 WAV')
    const duration = await readAudioDuration(file, 10000)
    if (!Number.isFinite(duration) || (kind === 'sample' ? duration < 10 || duration > 300 : duration <= 0 || duration >= 8)) {
      throw new Error(kind === 'sample' ? '复刻录音需为 10 秒至 5 分钟。' : '短示例音频必须小于 8 秒。')
    }
    if (version !== generation) return
    durations[kind] = duration
    if (kind === 'sample') {
      sample.value = file
      if (sampleUrl.value) URL.revokeObjectURL(sampleUrl.value)
      sampleUrl.value = URL.createObjectURL(file)
    } else prompt.value = file
  } catch (error) {
    ElMessage.error((error as Error).message)
    input.value = ''
    if (kind === 'sample') { sample.value = null; if (sampleUrl.value) URL.revokeObjectURL(sampleUrl.value); sampleUrl.value = '' }
    else prompt.value = null
  } finally {
    if (version === generation) loadingAudio.value = false
  }
}

function submit() {
  if (!sample.value || !form.consent || loadingAudio.value) return
  if (!form.alias.trim() || !/^[A-Za-z][A-Za-z0-9_-]{6,254}[A-Za-z0-9]$/.test(form.voice_id)) {
    ElMessage.error('请填写名称和有效音色 ID：8–256 位，以字母开头、字母或数字结尾。')
    return
  }
  if (prompt.value && !form.prompt_text.trim()) { ElMessage.error('请填写与短示例录音完全对应的文本。'); return }
  const data = new FormData()
  for (const [key, value] of Object.entries(form)) data.append(key, String(value))
  data.append('sample', sample.value)
  data.append('sample_duration', String(durations.sample))
  if (prompt.value) { data.append('prompt', prompt.value); data.append('prompt_duration', String(durations.prompt)) }
  emit('create', data)
}
onBeforeUnmount(() => { generation++; if (sampleUrl.value) URL.revokeObjectURL(sampleUrl.value) })
</script>

<template>
  <form class="studio-form studio-card" @submit.prevent="submit">
    <div class="studio-section-title"><div><h3>从录音复刻音色</h3><p>用平时说话的方式，留下一段熟悉的声音。</p></div><span class="studio-badge">录音 → 音色</span></div>
    <div class="studio-form-grid">
      <label>音色名称<input v-model="form.alias" required maxlength="80" placeholder="例如：我的朗读音色" /></label>
      <label>音色 ID<input v-model="form.voice_id" required minlength="8" maxlength="256" spellcheck="false" /><small>用于调用语音的唯一标识，创建后不能改名；名称可在本地修改。</small></label>
    </div>
    <label class="studio-file-zone">上传你的录音
      <input type="file" accept=".mp3,.m4a,.wav" :disabled="busy || loadingAudio" @change="selectFile($event, 'sample')" />
      <span>{{ sample ? `${sample.name} · ${durations.sample.toFixed(1)} 秒` : 'MP3 / M4A / WAV · 10 秒–5 分钟 · 最大 20 MB' }}</span>
      <small>建议录制 1–2 分钟，单人朗读、环境安静、无背景音乐。</small>
    </label>
    <audio v-if="sampleUrl" :src="sampleUrl" controls preload="metadata" class="studio-audio" aria-label="原始录音试听" />
    <details class="studio-details"><summary>增强相似度：添加短示例（可选）</summary>
      <label>短于 8 秒的示例音频<input type="file" accept=".mp3,.m4a,.wav" :disabled="busy || loadingAudio" @change="selectFile($event, 'prompt')" /></label>
      <label>对应的原文<textarea v-model="form.prompt_text" :required="!!prompt" maxlength="200" rows="2" placeholder="逐字填写短示例中的朗读内容，以标点结尾。" /></label>
    </details>
    <div class="studio-checks"><label><input v-model="form.need_noise_reduction" type="checkbox" /> 降噪</label><label><input v-model="form.need_volume_normalization" type="checkbox" /> 音量归一化</label></div>
    <label class="studio-consent"><input v-model="form.consent" type="checkbox" required /> 录音属于我本人，或我已取得声音本人的授权。</label>
    <p class="studio-note">点击后会将录音上传至 MiniMax。创建成功后，请在 7 天内生成一次朗读完成激活；生成费用按账户规则结算。</p>
    <button class="studio-button primary" :disabled="busy || !ready || !sample || !form.consent || loadingAudio" type="submit">{{ busy ? '正在处理，请等待…' : '上传并复刻音色' }}</button>
  </form>
</template>
