<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { checkAudioFile, readAudioDuration } from '@/utils/media'
import type { CoverInput, MusicInput, MusicState } from '@/services/musicApi'

const props = defineProps<{ state: MusicState; busy: boolean }>()
const emit = defineEmits<{
  generate: [data: MusicInput]
  'cover-preprocess': [data: { file: File; duration: number; title: string }]
  'cover-generate': [data: CoverInput]
}>()

const samplePrompt = '轻快的独立民谣，木吉他伴奏，节奏舒缓，混响干净，适合清晨散步时听。'
const sampleLyrics = '[Verse]\n街角的路灯亮了\n风把影子拉得很长\n我把今天折进口袋\n慢慢走向明天\n[Chorus]\n唱一句没有名字的歌\n让旋律替我先开口'
const coverSampleStyle = '流行摇滚，女声演唱，副歌有强力和弦，节奏明快'
const mode = ref<'text' | 'cover'>('text')
const form = reactive<MusicInput>({ title: '', prompt: '', lyrics: '', model: props.state.config.model,
  instrumental: false, lyrics_optimizer: false })
const cover = reactive({ title: '', style: '', lyrics: '', id: '', duration: 0 })
const coverFile = ref<File | null>(null)
const coverDuration = ref(0)
const readingAudio = ref(false)
let generation = 0

const promptCount = computed(() => [...form.prompt].length)
const lyricsCount = computed(() => [...form.lyrics].length)
const coverStyleCount = computed(() => [...cover.style].length)
const coverLyricsCount = computed(() => [...cover.lyrics].length)

defineExpose({
  loadTrack: (title: string, prompt: string, lyrics: string) => {
    form.title = title
    form.prompt = prompt
    form.lyrics = lyrics
  },
  loadCover: (id: string, lyrics: string, duration: number | null) => {
    mode.value = 'cover'
    cover.id = id
    cover.lyrics = lyrics
    cover.duration = duration || 0
  },
  loadCoverEdit: (id: string, title: string, style: string, lyrics: string, duration: number | null) => {
    mode.value = 'cover'
    cover.id = id
    cover.title = title
    cover.style = style
    cover.lyrics = lyrics
    cover.duration = duration || 0
  }
})

function fillSample() {
  form.prompt = samplePrompt
  form.lyrics = sampleLyrics
  form.title = '示例作品'
  form.instrumental = false
  form.lyrics_optimizer = false
}

async function selectReference(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  const version = ++generation
  readingAudio.value = true
  try {
    checkAudioFile(file, ['mp3', 'wav', 'flac', 'm4a', 'aac', 'ogg'], 'MP3、WAV、FLAC、M4A、AAC 或 OGG')
    const duration = await readAudioDuration(file)
    if (!Number.isFinite(duration) || duration < 6 || duration > 360) {
      throw new Error('参考音频需为 6 秒至 6 分钟。')
    }
    if (version !== generation) return
    coverFile.value = file
    coverDuration.value = duration
    cover.id = ''
  } catch (error) {
    ElMessage.error((error as Error).message)
    input.value = ''
    coverFile.value = null
    coverDuration.value = 0
    cover.id = ''
  } finally {
    if (version === generation) readingAudio.value = false
  }
}

function submitText() {
  if (props.busy) return
  if (form.instrumental && !form.prompt.trim()) {
    ElMessage.error('纯音乐也需要填写风格描述。')
    return
  }
  if (!form.instrumental && !form.lyrics.trim() && !form.lyrics_optimizer) {
    ElMessage.error('带人声的作品需要填写歌词，或开启自动写词。')
    return
  }
  if (promptCount.value > 2000 || lyricsCount.value > 3500) {
    ElMessage.error('风格描述不超过 2000 字符，歌词不超过 3500 字符。')
    return
  }
  emit('generate', { ...form, title: form.title.trim() })
}

function submitCoverPreprocess() {
  if (props.busy) return
  if (!coverFile.value) {
    ElMessage.error('请先选择参考音频。')
    return
  }
  emit('cover-preprocess', { file: coverFile.value, duration: coverDuration.value, title: cover.title.trim() })
}

function submitCover() {
  if (props.busy) return
  if (!cover.id) {
    ElMessage.error('请先上传参考音频并提取歌词。')
    return
  }
  if (cover.style.trim().length < 10 || cover.style.trim().length > 300) {
    ElMessage.error('目标曲风描述需 10–300 个字符。')
    return
  }
  if (cover.lyrics.trim() && (cover.lyrics.trim().length < 10 || cover.lyrics.trim().length > 1000)) {
    ElMessage.error('歌词需 10–1000 个字符。')
    return
  }
  emit('cover-generate', { id: cover.id, prompt: cover.style.trim(), lyrics: cover.lyrics.trim(), title: cover.title.trim() })
}

onBeforeUnmount(() => { generation++ })
</script>

<template>
  <form class="studio-form studio-card" @submit.prevent="mode === 'cover' ? submitCover() : submitText()">
    <div class="studio-section-title"><div><h3>写下你的旋律</h3><p>风格描述与歌词提交后入库，音频链接和生成参数自动存入 SQLite。</p></div><span class="studio-badge">MiniMax 音乐生成</span></div>
    <div class="studio-checks">
      <label><input v-model="mode" type="radio" value="text" /> 文本生音乐</label>
      <label><input v-model="mode" type="radio" value="cover" /> 参考音频翻唱</label>
    </div>

    <template v-if="mode === 'text'">
      <div class="studio-form-grid">
        <label>作品名称<input v-model="form.title" maxlength="100" placeholder="留空时取风格描述开头" /></label>
        <label>音乐模型<select v-model="form.model"><option v-for="model in state.models" :key="model">{{ model }}</option></select></label>
      </div>
      <div class="studio-checks">
        <label><input v-model="form.instrumental" type="checkbox" /> 纯音乐（无人声）</label>
        <label><input v-model="form.lyrics_optimizer" type="checkbox" /> 由风格描述自动写词</label>
      </div>
      <label class="studio-editor-label"><span>风格描述 <small>{{ promptCount }} / 2000 字符</small></span><textarea v-model="form.prompt" rows="3" placeholder="曲风、情绪、场景、乐器，例如：轻快的独立民谣，木吉他伴奏，适合清晨散步时听。" /></label>
      <label v-if="!form.instrumental" class="studio-editor-label"><span>歌词 <small>{{ lyricsCount }} / 3500 字符</small></span><textarea v-model="form.lyrics" rows="8" placeholder="每行一句，可用 [Verse]、[Chorus]、[Bridge] 等段落标记。" /></label>
      <div v-if="form.lyrics_optimizer && !form.lyrics.trim()" class="studio-info">已开启自动写词，歌词留空时由 MiniMax 根据风格描述生成；填写的歌词会优先使用。</div>
      <div class="studio-editor-tools"><span class="studio-note">歌词可留空并开启自动写词；纯音乐只需风格描述。</span><div class="studio-actions"><button class="studio-link" type="button" @click="fillSample">填入示例</button></div></div>
      <div class="studio-submit-row"><button class="studio-button primary" type="submit" :disabled="busy || !state.config.ready">{{ busy ? '正在处理，请等待…' : '提交生成并保存' }}</button><span class="studio-note">消耗音乐额度；成功后显示实际时长，并保存云端链接与本地 MP3。</span></div>
    </template>

    <template v-else>
      <div class="studio-form-grid">
        <label>作品名称<input v-model="cover.title" maxlength="100" placeholder="留空时记为「参考翻唱」" /></label>
        <label>翻唱模型<input :value="state.config.cover_model" readonly spellcheck="false" /><small>翻唱使用官方 music-cover 模型。</small></label>
      </div>
      <label class="studio-file-zone">上传参考音频
        <input type="file" accept=".mp3,.wav,.flac,.m4a,.aac,.ogg" :disabled="busy || readingAudio" @change="selectReference" />
        <span>{{ coverFile ? `${coverFile.name} · ${coverDuration.toFixed(1)} 秒` : 'MP3 / WAV / FLAC / M4A / AAC / OGG · 6 秒–6 分钟 · 最大 20 MB' }}</span>
        <small>上传后由 MiniMax 提取歌词；可修改后再生成翻唱。</small>
      </label>
      <label class="studio-editor-label"><span>目标曲风 <small>{{ coverStyleCount }} / 300 字符</small></span><textarea v-model="cover.style" rows="2" placeholder="想要翻唱成的曲风，例如：流行摇滚，女声演唱，副歌有强力和弦。" /></label>
      <label class="studio-editor-label"><span>歌词 <small>{{ coverLyricsCount }} / 1000 字符</small></span><textarea v-model="cover.lyrics" rows="8" placeholder="上传参考音频后自动提取；也可以直接填写或修改。" /></label>
      <div v-if="cover.id" class="studio-info">参考音频已上传{{ cover.duration ? `（${cover.duration.toFixed(1)} 秒）` : '' }}并提取歌词，可修改后提交生成。</div>
      <div class="studio-editor-tools"><span class="studio-note">参考音频的翻唱特征有效期 24 小时，超时需重新上传。</span><div class="studio-actions"><button class="studio-link" type="button" @click="cover.style = coverSampleStyle">填入示例曲风</button></div></div>
      <div class="studio-submit-row">
        <button class="studio-button" type="button" :disabled="busy || !state.config.ready || !coverFile || readingAudio" @click="submitCoverPreprocess">{{ busy ? '正在处理，请等待…' : '上传参考音频并提取歌词' }}</button>
        <button class="studio-button primary" type="submit" :disabled="busy || !state.config.ready || !cover.id">{{ busy ? '正在处理，请等待…' : '提交生成翻唱' }}</button>
      </div>
    </template>
  </form>
</template>
