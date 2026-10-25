<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessageBox } from 'element-plus'
import { useStudioPage } from '@/composables/useStudioPage'
import { formatDuration } from '@/utils/media'
import { musicAPI, type CoverInput, type MusicInput, type MusicState, type MusicTrack } from '@/services/musicApi'
import MusicComposer from './music/MusicComposer.vue'

const state = ref<MusicState | null>(null)
const tab = ref('composer')
const composer = ref<InstanceType<typeof MusicComposer>>()
const player = ref<HTMLAudioElement>()
const tabs = [{ id: 'composer', name: '音乐创作' }, { id: 'history', name: '创作记录' }, { id: 'settings', name: '连接配置' }]
const keyKind = computed(() => ({ token_plan: 'Token Plan', m_plan: 'M Plan', pay_as_you_go: '按量计费' }[state.value?.config.key_kind || ''] || '未标记'))
const credentialSource = computed(() => state.value?.config.dedicated_key ? '独立音乐密钥' : '沿用语音密钥')

const page = useStudioPage({
  errorText: '音乐操作失败',
  load,
  fetchAudio: (id, ext) => musicAPI.audio(id, ext),
  getPlayer: () => player.value
})
const { busy, failure, playing, playerUrl, action, prepareAudio, download, copyLink, date } = page

async function load() {
  state.value = await musicAPI.state()
  if (playing.value && !state.value.tracks.some(row => row.id === playing.value?.id)) page.clearPlayer()
}
async function generate(data: MusicInput) {
  const row = await action('generate', () => musicAPI.generate(data), true, '音乐已生成，链接和创作参数已保存')
  if (row) {
    tab.value = 'history'
    if (row.has_audio) await action('audio', () => prepareAudio(row, true))
  }
}
async function coverPreprocess(payload: { file: File; duration: number; title: string }) {
  const data = new FormData()
  data.append('audio', payload.file)
  data.append('audio_duration', String(payload.duration))
  data.append('title', payload.title)
  const row = await action('cover', () => musicAPI.coverPreprocess(data), true, '参考音频已上传，歌词已提取')
  if (row) composer.value?.loadCover(row.id, row.lyrics, row.reference_duration)
}
async function coverGenerate(payload: CoverInput) {
  const row = await action('cover', () => musicAPI.coverGenerate(payload), true, '翻唱已生成，链接和创作参数已保存')
  if (row) {
    tab.value = 'history'
    if (row.has_audio) await action('audio', () => prepareAudio(row, true))
  }
}
async function reuse(row: MusicTrack) {
  const detail = await action('detail', () => musicAPI.track(row.id))
  if (!detail) return
  tab.value = 'composer'
  if (row.model === state.value?.config.cover_model) composer.value?.loadCoverEdit(detail.id, detail.title, detail.prompt, detail.lyrics, detail.reference_duration)
  else composer.value?.loadTrack(detail.title, detail.prompt, detail.lyrics)
}
async function remove(row: MusicTrack) {
  try {
    await ElMessageBox.confirm(`删除后无法恢复：${row.title}`, '删除音乐记录', { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' })
    await action('delete', () => musicAPI.delete(row.id), true, '音乐记录已删除')
  } catch { /* 用户关闭对话框。 */ }
}
onMounted(() => action('load', load))
</script>

<template>
  <section class="studio-panel studio-music" :aria-busy="!!busy">
    <header class="studio-heading">
      <div class="studio-identity">
        <svg viewBox="0 0 72 72" class="studio-emblem" aria-hidden="true"><rect x="1" y="1" width="70" height="70" rx="20" fill="currentColor" opacity=".08" /><path d="M44 12v30.5a9.5 9.5 0 1 1-5-8.35V21l18-4.5v21.5a9.5 9.5 0 1 1-5-8.35V14z" fill="currentColor" opacity=".85" /></svg>
        <div><span class="studio-eyebrow">MiniMax · 音乐创作</span><h2>音乐工坊</h2><p>写下风格与歌词，生成属于你的作品。</p></div>
      </div>
      <div class="studio-connection"><span :class="['studio-dot', { ready: state?.config.ready }]" />{{ state?.config.ready ? `${keyKind} · ${credentialSource}` : '等待配置密钥' }}</div>
    </header>
    <nav class="studio-tabs" aria-label="音乐工坊功能"><button v-for="item in tabs" :key="item.id" :class="{ active: tab === item.id }" :aria-current="tab === item.id ? 'page' : undefined" @click="tab = item.id">{{ item.name }}<span v-if="item.id === 'history' && state?.tracks.length">{{ state.tracks.length }}</span></button></nav>
    <div v-if="failure" class="studio-error" role="alert">{{ failure }}</div>
    <div v-if="busy" class="studio-progress" role="status">{{ busy === 'generate' ? '正在生成音乐，请等待完成；请勿重复提交…' : '正在处理…' }}</div>
    <template v-if="state">
      <div v-if="!state.config.ready" class="studio-info">先在后端配置 MiniMax 音乐密钥，再开始创作。可在“连接配置”查看独立配置段；留空则沿用音色管理的语音密钥。</div>
      <MusicComposer ref="composer" v-show="tab === 'composer'" :state="state" :busy="!!busy" @generate="generate" @cover-preprocess="coverPreprocess" @cover-generate="coverGenerate" />
      <section v-show="tab === 'history'" class="studio-card">
        <div class="studio-section-title"><div><h3>创作记录</h3><p>创作参数与音频链接存入 SQLite；临时链接有效期为 24 小时，本地备份可长期下载。</p></div><span class="studio-badge">最近 {{ state.tracks.length }} 条</span></div>
        <div v-if="!state.tracks.length" class="studio-empty"><span class="studio-empty-glyph" aria-hidden="true">♪</span><h4>还没有作品</h4><p>提交一次创作，这里会保存音频、时长和创作参数。</p><button class="studio-button" @click="tab = 'composer'">去创作</button></div>
        <article v-for="row in state.tracks" :key="row.id" class="studio-history-row"><div><h4>{{ row.title }}</h4><p>{{ date(row.created_at) }} · {{ row.model }}</p><small>{{ row.instrumental ? '纯音乐' : '带人声' }}{{ row.lyrics_optimizer ? ' · 自动写词' : '' }}<template v-if="row.duration_seconds !== null"> · {{ formatDuration(row.duration_seconds) }}</template></small><p v-if="row.audio_url" :class="{ 'studio-expired': row.url_expired }">链接{{ row.url_expired ? '已过期' : `有效至 ${date(row.url_expires_at)}` }} · {{ row.status === 'ready' ? '本地 MP3 已保存' : '本地备份待下载' }}</p><p v-if="row.error_message" class="studio-record-error">{{ row.error_message }}</p><small v-if="row.status === 'generating'">生成请求已提交；若服务重启前未返回，请先检查云端结果。</small><small v-if="row.status === 'cover_ready'">参考音频已上传，翻唱特征 24 小时内有效。</small></div><strong>{{ formatDuration(row.duration_seconds) }}</strong><div class="studio-actions"><button v-if="row.has_audio" class="studio-button" :disabled="!!busy || (row.url_expired && row.status !== 'ready')" @click="action('audio', () => prepareAudio(row, true), true)">播放</button><button v-if="row.has_audio" class="studio-link" :disabled="!!busy || (row.url_expired && row.status !== 'ready')" @click="download(row, 'mp3')">MP3 ↓</button><button class="studio-link" :disabled="!!busy" @click="download(row, 'txt')">参数 ↓</button><button v-if="row.status !== 'cover_ready'" class="studio-link" :disabled="!!busy" @click="reuse(row)">载入编辑</button><button v-if="row.audio_url" class="studio-link" :disabled="!!busy" @click="copyLink(row)">复制音频链接</button><button class="studio-link danger" :disabled="!!busy" @click="remove(row)">删除</button></div></article>
      </section>
      <section v-show="tab === 'settings'" class="studio-card studio-settings">
        <div class="studio-section-title"><div><h3>连接 MiniMax 音乐</h3><p>音乐生成可单独配一套计费密钥，与音色管理的语音凭据互不影响。</p></div></div>
        <dl><dt>当前配置文件</dt><dd><code>{{ state.config.config_path || '由测试环境提供' }}</code></dd><dt>密钥来源</dt><dd>{{ credentialSource }}</dd><dt>密钥类型标记</dt><dd>{{ keyKind }}（仅作记录，实际权限由 MiniMax 返回）</dd><dt>服务区域</dt><dd>{{ state.config.region === 'cn' ? '中国站' : '国际站' }} · {{ state.config.base_url }}</dd><dt>音乐模型</dt><dd>{{ state.config.model }} · 翻唱 {{ state.config.cover_model }}</dd><dt>请求超时</dt><dd>{{ state.config.timeout_seconds }} 秒</dd><dt>本地音频目录</dt><dd><code>{{ state.config.storage_dir }}</code></dd></dl>
        <h4>在当前配置文件末尾加入（独立计费密钥）</h4><pre>[minimax_music]
api_key=&lt;填入音乐专用的 MiniMax API Key&gt;
region=cn
key_kind=token_plan
model=music-3.0
timeout_seconds=180</pre>
        <p>保存后重启项目后端。留空 <code>api_key</code> 时沿用 <code>[minimax]</code> 的语音密钥；也支持环境变量 <code>MINIMAX_MUSIC_API_KEY</code>，其优先级高于配置文件。</p>
        <div class="studio-info">使用独立密钥时，音乐记录与本地音频按该密钥单独隔离；换回原密钥才能看到用旧密钥生成的作品。官方已停止向新用户提供音乐接口，历史付费账号才可调用。</div>
        <div class="studio-source-links"><a href="https://platform.minimax.cn/docs/api-reference/music-generation" target="_blank" rel="noreferrer">音乐生成接口 ↗</a><a href="https://platform.minimax.cn/docs/api-reference/music-cover-preprocess" target="_blank" rel="noreferrer">翻唱前处理 ↗</a></div>
      </section>
      <section v-if="playing && playerUrl" class="studio-player" aria-label="音乐播放器"><div class="studio-player-info"><span class="studio-eyebrow">已保存在本机</span><h4>{{ playing.title }}</h4><p>{{ formatDuration(playing.duration_seconds) }}</p></div><audio ref="player" :src="playerUrl" controls preload="metadata" /><button class="studio-button" :disabled="!!busy" @click="download(playing, 'mp3')">下载 MP3</button></section>
    </template>
    <div v-else-if="!busy" class="studio-empty"><p>页面未能载入，请检查后端和管理员登录状态。</p><button class="studio-button" @click="action('load', load)">重新载入</button></div>
  </section>
</template>

