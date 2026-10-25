<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type { SynthesisInput, VoiceState } from '@/services/voiceApi'

const props = defineProps<{ state: VoiceState; selectedVoice: string; busy: boolean }>()
const emit = defineEmits<{ synthesize: [data: SynthesisInput]; select: [id: string] }>()
const sampleText = '傍晚的街道渐渐安静下来，风从窗缝里挤进来，吹动桌角那封还没拆的信。今天想听点什么，就从这里开始。'
const form = reactive<SynthesisInput>({ voice_id: props.selectedVoice, title: '音色试听', text: sampleText,
  model: props.state.config.model, speed: 0.9, volume: 1, pitch: 0, emotion: '' })
const count = computed(() => [...form.text].length)
const voiceStatus = computed(() => props.state.voices.find(v => v.voice_id === form.voice_id)?.status)
watch(() => props.selectedVoice, id => { form.voice_id = id })
watch(() => props.state.config.model, model => { form.model = model })
defineExpose({ loadStory: (title: string, text: string) => { form.title = title; form.text = text } })

async function pasteText() {
  try {
    const text = await navigator.clipboard.readText()
    if ([...text].length > 9999) throw new Error('正文需少于 10000 字符。')
    if (!text.trim()) throw new Error('剪贴板中没有文本。')
    form.text = text
  } catch (error) {
    ElMessage.info((error as Error).message.includes('字符') ? (error as Error).message : '请在正文框中使用系统粘贴快捷键。')
  }
}

async function importText(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  try {
    if (file.size > 100000) throw new Error('文本文件过大，请选择要朗读的正文文件。')
    const text = await file.text()
    if ([...text].length > 9999) throw new Error('每次朗读需少于 10000 字符。')
    form.text = text
    form.title = file.name.replace(/\.(txt|md)$/i, '').slice(0, 100)
  } catch (error) { ElMessage.error((error as Error).message) }
  finally { input.value = '' }
}
async function copyText() {
  try { await navigator.clipboard.writeText(form.text); ElMessage.success('正文已复制') }
  catch { ElMessage.info('请选中正文后使用系统复制快捷键。') }
}
function submit() {
  if (props.busy) return
  if (!form.voice_id.trim() || !form.text.trim() || count.value > 9999) {
    ElMessage.error('请填写音色 ID 和少于 10000 字符的朗读正文。')
    return
  }
  emit('synthesize', { ...form })
}
</script>

<template>
  <form class="studio-form studio-card" @submit.prevent="submit">
    <div class="studio-section-title"><div><h3>让内容有你的声音</h3><p>粘贴正文并提交，正文、音频链接和生成参数自动存入 SQLite。</p></div><span class="studio-badge">目标 3–4 分钟</span></div>
    <div class="studio-form-grid">
      <label>选择音色<select :value="form.voice_id" @change="form.voice_id = ($event.target as HTMLSelectElement).value; emit('select', form.voice_id)">
        <option value="">请选择音色</option><option v-for="voice in state.voices" :key="voice.voice_id" :value="voice.voice_id">{{ voice.alias }}{{ voice.status === 'pending' ? ' · 待激活' : '' }}</option>
      </select></label>
      <label>或填写已知音色 ID<input v-model="form.voice_id" maxlength="256" placeholder="支持填写尚未出现在云端列表中的音色 ID" spellcheck="false" @change="emit('select', form.voice_id)" /></label>
    </div>
    <div v-if="voiceStatus === 'pending' || voiceStatus === 'unknown'" class="studio-info">这次朗读会尝试激活音色。首次正式合成可能包含音色费用，请以 MiniMax 账单为准。</div>
    <label>文件名称<input v-model="form.title" maxlength="100" placeholder="例如：睡前故事 · 第一集" /></label>
    <label class="studio-editor-label"><span>朗读正文 <small>{{ count }} / 9999 字符</small></span><textarea v-model="form.text" rows="10" required placeholder="粘贴故事正文…" /></label>
    <div class="studio-editor-tools"><label class="studio-file-link">导入 TXT / Markdown<input type="file" accept=".txt,.md" @change="importText" /></label><div class="studio-actions"><button class="studio-link" type="button" @click="pasteText">粘贴剪贴板</button><button class="studio-link" type="button" :disabled="!form.text" @click="copyText">复制正文</button><button class="studio-link" type="button" @click="form.text = sampleText; form.title = '音色试听'">填入短试听文本</button></div></div>
    <details class="studio-details" open><summary>朗读设置</summary>
      <div class="studio-form-grid compact">
        <label>语音模型<select v-model="form.model"><option v-for="model in state.models" :key="model">{{ model }}</option></select></label>
        <label>语速<input v-model.number="form.speed" type="number" min="0.5" max="2" step="0.05" required /><small>0.5–2；低于 1 会读得更慢。</small></label>
        <label>音量<input v-model.number="form.volume" type="number" min="0.1" max="10" step="0.1" required /></label>
        <label>音调<input v-model.number="form.pitch" type="number" min="-12" max="12" step="1" required /><small>0 保留原音调。</small></label>
        <label>情绪<select v-model="form.emotion"><option value="">跟随正文</option><option value="calm">平静</option><option value="happy">开心</option><option value="sad">难过</option></select></label>
      </div>
    </details>
    <div class="studio-submit-row"><button class="studio-button primary" type="submit" :disabled="busy || !state.config.ready || !form.voice_id || !form.text.trim() || count > 9999">{{ busy ? '正在处理，请等待…' : '提交生成并保存' }}</button><span class="studio-note">消耗语音额度；成功后显示实际时长，并保存云端链接与本地 MP3。</span></div>
  </form>
</template>
