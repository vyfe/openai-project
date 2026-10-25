<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useStudioPage } from '@/composables/useStudioPage'
import { voiceAPI, type KeepaliveInput, type KeepaliveState, type Voice, type VoiceAudio, type VoiceState, type SynthesisInput } from '@/services/voiceApi'
import { downloadBlob, formatDuration } from '@/utils/media'
import VoiceCloneForm from './voice/VoiceCloneForm.vue'
import VoiceKeepalive from './voice/VoiceKeepalive.vue'
import VoiceReader from './voice/VoiceReader.vue'

const state = ref<VoiceState | null>(null)
const keepalive = ref<KeepaliveState | null>(null)
const tab = ref('library')
const keyword = ref('')
const filter = ref('custom')
const selectedVoice = ref('')
const reader = ref<InstanceType<typeof VoiceReader>>()
const player = ref<HTMLAudioElement>()
const types = { system: '系统音色', voice_cloning: '录音复刻', voice_generation: '文字设计' }
const statusLabels = { active: '可使用', pending: '待首次合成', unknown: '创建结果待确认' }
const tabs = [{ id: 'library', name: '音色库' }, { id: 'clone', name: '复刻我的音色' }, { id: 'reader', name: '语音合成' }, { id: 'history', name: '合成记录' }, { id: 'settings', name: '连接配置' }]
const visibleVoices = computed(() => {
  const search = keyword.value.toLocaleLowerCase().trim()
  return (state.value?.voices || []).filter(v =>
    (filter.value === 'all' || (filter.value === 'custom' ? v.voice_type !== 'system' : v.voice_type === filter.value)) &&
    (!search || `${v.alias} ${v.voice_id} ${v.description}`.toLocaleLowerCase().includes(search)))
})
const customCount = computed(() => state.value?.voices.filter(v => v.voice_type !== 'system').length || 0)
const keyKind = computed(() => ({ token_plan: 'Token Plan', m_plan: 'M Plan', pay_as_you_go: '按量计费' }[state.value?.config.key_kind || ''] || '未标记'))
const keepaliveMap = computed(() => new Map((keepalive.value?.voices || []).map(voice => [voice.voice_id, voice])))

function keepaliveText(voiceId: string) {
  const info = keepaliveMap.value.get(voiceId)
  if (!info) return ''
  if (info.disabled) return '已关闭保活'
  if (info.days_left === null) return '保活时间待确认'
  if (info.days_left <= 0) return '已到期，将自动激活'
  return `保活还剩 ${info.days_left} 天`
}

const page = useStudioPage({
  errorText: '音色操作失败',
  load,
  fetchAudio: (id, ext) => voiceAPI.audio(id, ext),
  getPlayer: () => player.value
})
const { busy, failure, playing, playerUrl, action, prepareAudio, download, copyLink, date } = page

async function load() {
  const previousRegion = state.value?.config.region
  state.value = await voiceAPI.state()
  keepalive.value = await voiceAPI.keepalive()
  if (playing.value && !state.value.history.some(row => row.id === playing.value?.id)) page.clearPlayer()
  if (!selectedVoice.value || previousRegion !== state.value.config.region || !state.value.voices.some(v => v.voice_id === selectedVoice.value)) {
    selectedVoice.value = state.value.default_voice_id || state.value.voices.find(v => v.voice_type !== 'system')?.voice_id || ''
  }
}
async function sync() {
  const result = await action('sync', () => voiceAPI.sync(), true)
  if (result) ElMessage.success(`连接成功，同步了 ${result.count} 个云端音色`)
}
async function saveKeepalive(data: KeepaliveInput) {
  const result = await action('keepalive', () => voiceAPI.saveKeepalive(data), true, '保活设置已保存')
  if (result !== undefined) keepalive.value = await voiceAPI.keepalive()
}
async function runKeepalive() {
  const result = await action('keepalive', () => voiceAPI.runKeepalive(), true, '保活执行完成')
  if (result) {
    const failed = result.results.filter(row => !row.ok)
    if (failed.length) ElMessage.warning(`${result.attempted} 个待保活音色中 ${failed.length} 个失败：${failed[0].error || '未知错误'}`)
    else if (result.attempted) ElMessage.success(`已激活 ${result.attempted} 个到期音色`)
    keepalive.value = await voiceAPI.keepalive()
  }
}
async function create(data: FormData) {
  const result = await action('clone', () => voiceAPI.clone(data), true, '复刻成功，请生成一次朗读完成激活')
  if (result) { selectedVoice.value = result.voice_id; tab.value = 'reader' }
}
function useVoice(voice: Voice) { selectedVoice.value = voice.voice_id; tab.value = 'reader' }
async function rename(voice: Voice) {
  try {
    const { value } = await ElMessageBox.prompt('名称保存在本地，云端音色 ID 保持原值。', '修改音色名称',
      { inputValue: voice.alias, inputValidator: value => !!value?.trim() && value.trim().length <= 80, inputErrorMessage: '请输入 1–80 个字符', confirmButtonText: '保存名称', cancelButtonText: '取消' })
    await action('preference', () => voiceAPI.preference({ voice_id: voice.voice_id, alias: value.trim() }), true, '名称已保存')
  } catch { /* 用户关闭对话框。 */ }
}
async function remove(voice: Voice) {
  try {
    const { value } = await ElMessageBox.prompt(`删除后，该云端音色 ID 无法再次使用。请输入完整 ID：${voice.voice_id}`, '删除云端音色',
      { inputValidator: value => value === voice.voice_id, inputErrorMessage: '音色 ID 不匹配', confirmButtonText: '删除音色', cancelButtonText: '取消', type: 'warning' })
    await action('delete', () => voiceAPI.delete(voice.voice_id, value), true, '云端音色已删除')
  } catch { /* 用户关闭对话框。 */ }
}
async function makeDefault(voice: Voice) {
  await action('preference', () => voiceAPI.preference({ voice_id: voice.voice_id, make_default: true }), true, '已设为默认音色')
}
async function synthesize(data: SynthesisInput) {
  const row = await action('synthesize', () => voiceAPI.synthesize(data), true, '朗读链接和正文已保存到 SQLite')
  if (row?.status === 'ready') await action('audio', () => prepareAudio(row))
  else if (row) { tab.value = 'history'; ElMessage.warning('云端音频已保存到记录，本地备份未完成，可从记录重试下载') }
}
async function exportProfile() {
  await action('profile', async () => downloadBlob(new Blob([JSON.stringify(await voiceAPI.profile(), null, 2)], { type: 'application/json' }), 'minimax-voice-profile.json'))
}
async function reuseText(row: VoiceAudio) {
  const detail = await action('text', () => voiceAPI.reading(row.id))
  if (detail) { tab.value = 'reader'; reader.value?.loadStory(detail.title, detail.text); selectedVoice.value = row.voice_id }
}
onMounted(() => action('load', load))
</script>

<template>
  <section class="studio-panel" :aria-busy="!!busy">
    <header class="studio-heading">
      <div class="studio-identity">
        <svg viewBox="0 0 72 72" class="studio-emblem" aria-hidden="true"><rect x="1" y="1" width="70" height="70" rx="20" fill="currentColor" opacity=".08" /><path d="M45 14a17 17 0 1 0 13 28A19 19 0 0 1 45 14Z" fill="currentColor" opacity=".85" /><path d="M12 49c9-7 18 7 28 0s16-5 20-2M13 57c9-7 18 7 28 0s16-5 20-2" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" /></svg>
        <div><span class="studio-eyebrow">MiniMax · 声音工坊</span><h2>声音工坊</h2><p>收藏熟悉的声音，让每一段内容都有温度。</p></div>
      </div>
      <div class="studio-connection"><span :class="['studio-dot', { ready: state?.config.clone_ready }]" />{{ state?.config.clone_ready ? `复刻 ${state.config.clone_dedicated ? '计费密钥' : '同密钥'} · 合成 ${keyKind}` : '等待配置密钥' }}</div>
    </header>
    <nav class="studio-tabs" aria-label="声音工坊功能"><button v-for="item in tabs" :key="item.id" :class="{ active: tab === item.id }" :aria-current="tab === item.id ? 'page' : undefined" @click="tab = item.id">{{ item.name }}<span v-if="item.id === 'library' && customCount">{{ customCount }}</span></button></nav>
    <div v-if="failure" class="studio-error" role="alert">{{ failure }}</div>
    <div v-if="busy" class="studio-progress" role="status">{{ busy === 'clone' ? '正在上传并复刻录音，请保持页面打开…' : busy === 'synthesize' ? '正在生成语音，请等待完成；请勿重复提交…' : '正在处理…' }}</div>
    <template v-if="state">
      <div v-if="!state.config.clone_ready && tab !== 'settings'" class="studio-info">先在后端配置 MiniMax 密钥，再开始管理音色。<button class="studio-link" @click="tab = 'settings'">查看配置方法 →</button></div>
      <div v-if="state.config.clone_ready && !state.config.ready && tab !== 'settings'" class="studio-info">复刻凭据已就绪，但语音合成密钥未配置，合成功能暂不可用。<button class="studio-link" @click="tab = 'settings'">查看配置方法 →</button></div>
      <section v-show="tab === 'library'" class="studio-card">
        <div class="studio-section-title"><div><h3>我的音色库</h3><p>录音复刻与文字设计的音色集中保存在这里。</p></div><div class="studio-actions"><button class="studio-button" :disabled="!!busy || !state.config.clone_ready" @click="sync">同步云端音色</button><button class="studio-button primary" @click="tab = 'clone'">＋ 复刻我的音色</button></div></div>
        <VoiceKeepalive :status="keepalive" :busy="!!busy" @save="saveKeepalive" @run="runKeepalive" />
        <div class="studio-filters"><input v-model="keyword" type="search" aria-label="搜索音色" placeholder="搜索名称、ID 或声音描述" /><select v-model="filter" aria-label="音色类型"><option value="custom">我的自定义音色</option><option value="system">系统音色</option><option value="all">全部音色</option></select><span class="studio-note">{{ visibleVoices.length }} 个音色</span></div>
        <div v-if="!visibleVoices.length" class="studio-empty"><span class="studio-empty-glyph" aria-hidden="true">∿</span><h4>{{ keyword ? '没有匹配的音色' : '在这里，留下你的声音' }}</h4><p>{{ keyword ? '换个关键词，或切换音色类型。' : '上传一段录音创建音色；已有音色可通过“同步云端音色”载入。' }}</p><button v-if="!keyword" class="studio-button" @click="tab = 'clone'">创建第一个音色</button></div>
        <div v-else class="studio-grid"><article v-for="voice in visibleVoices" :key="voice.voice_id" class="studio-tile" :class="{ 'is-default': voice.voice_id === state.default_voice_id }">
          <div class="studio-tile-top"><span class="studio-wave" aria-hidden="true">▂ ▅ ▇ ▃ ▆ ▂</span><span class="studio-badge">{{ types[voice.voice_type] }}</span></div>
          <h4>{{ voice.alias }}</h4><code>{{ voice.voice_id }}</code><p class="studio-tile-description">{{ voice.description || '已保存在你的 MiniMax 账户中' }}</p>
          <div class="studio-tile-status"><span :class="['studio-status', { pending: voice.status !== 'active' }]">{{ statusLabels[voice.status] }}</span><span v-if="voice.voice_id === state.default_voice_id" class="studio-default">默认音色</span><span v-if="keepaliveText(voice.voice_id)" :class="['studio-keepalive-badge', { urgent: (keepaliveMap.get(voice.voice_id)?.days_left ?? 99) <= 1 }]">{{ keepaliveText(voice.voice_id) }}</span></div>
          <p v-if="voice.status === 'pending'" class="studio-note">创建于 {{ date(voice.created_time) }}；请在 7 天内合成一次。</p>
          <div class="studio-tile-actions"><button class="studio-button" :disabled="!!busy" @click="useVoice(voice)">试听 / 朗读</button><button class="studio-link" :disabled="!!busy || voice.voice_id === state.default_voice_id" @click="makeDefault(voice)">设为默认</button><button class="studio-link" :disabled="!!busy" @click="rename(voice)">改名</button><button v-if="voice.voice_type !== 'system'" class="studio-link danger" :disabled="!!busy" @click="remove(voice)">删除</button></div>
        </article></div>
        <footer class="studio-card-footer"><span>最近同步：{{ date(state.last_sync) }}</span><button class="studio-link" :disabled="!!busy || !state.default_voice_id" @click="exportProfile">导出默认音色配置 ↗</button></footer>
      </section>
      <VoiceCloneForm v-show="tab === 'clone'" :busy="!!busy" :ready="state.config.clone_ready" @create="create" />
      <VoiceReader ref="reader" v-show="tab === 'reader'" :state="state" :selected-voice="selectedVoice" :busy="!!busy" @select="selectedVoice = $event" @synthesize="synthesize" />
      <section v-show="tab === 'history'" class="studio-card">
        <div class="studio-section-title"><div><h3>合成记录</h3><p>正文与音频链接存入 SQLite；临时链接有效期为 24 小时，本地备份可长期下载。</p></div><span class="studio-badge">最近 {{ state.history.length }} 条</span></div>
        <div v-if="!state.history.length" class="studio-empty"><h4>还没有合成记录</h4><p>提交合成后，这里会保存音频、时长和所用音色。</p><button class="studio-button" @click="tab = 'reader'">去生成语音</button></div>
        <article v-for="row in state.history" :key="row.id" class="studio-history-row"><div><h4>{{ row.title }}</h4><p>{{ date(row.created_at) }} · {{ row.voice_id }}</p><small>{{ row.model }} · {{ row.speed }} 倍速 · 计费字符 {{ row.usage_characters ?? '未返回' }}</small><p v-if="row.audio_url" :class="{ 'studio-expired': row.url_expired }">链接{{ row.url_expired ? '已过期' : `有效至 ${date(row.url_expires_at)}` }} · {{ row.status === 'ready' ? '本地 MP3 已保存' : '本地备份待下载' }}</p><p v-if="row.error_message" class="studio-record-error">{{ row.error_message }}</p><small v-if="row.status === 'generating'">生成请求已提交；若服务重启前未返回，请先检查云端结果。</small></div><strong>{{ formatDuration(row.duration_seconds) }}</strong><div class="studio-actions"><button v-if="row.audio_url" class="studio-button" :disabled="!!busy || (row.url_expired && row.status !== 'ready')" @click="action('audio', () => prepareAudio(row, true), true)">播放</button><button v-if="row.audio_url" class="studio-link" :disabled="!!busy || (row.url_expired && row.status !== 'ready')" @click="download(row, 'mp3')">MP3 ↓</button><button class="studio-link" :disabled="!!busy" @click="download(row, 'txt')">正文 ↓</button><button class="studio-link" :disabled="!!busy" @click="reuseText(row)">载入正文</button><button v-if="row.audio_url" class="studio-link" :disabled="!!busy" @click="copyLink(row)">复制音频链接</button></div></article>
      </section>
      <section v-show="tab === 'settings'" class="studio-card studio-settings">
        <div class="studio-section-title"><div><h3>连接 MiniMax</h3><p>复刻与合成可能用两把不同的密钥；密钥只由后端读取，页面不会返回或保存密钥。</p></div><button class="studio-button" :disabled="!!busy || !state.config.clone_ready" @click="sync">检测连接并同步</button></div>
        <dl><dt>当前配置文件</dt><dd><code>{{ state.config.config_path || '由测试环境提供' }}</code></dd><dt>复刻凭据</dt><dd>{{ state.config.clone_dedicated ? '独立计费密钥（[minimax_music]）' : '与合成共用同一密钥' }} · {{ state.config.clone_region === 'cn' ? '中国站' : '国际站' }} · {{ state.config.clone_base_url }} · {{ state.config.clone_ready ? '已配置' : '未配置' }}</dd><dt>合成凭据</dt><dd>{{ state.config.region === 'cn' ? '中国站' : '国际站' }} · {{ state.config.base_url }} · {{ state.config.ready ? '已配置' : '未配置' }}</dd><dt>密钥类型标记</dt><dd>{{ keyKind }}（仅作记录，实际权限由 MiniMax 返回）</dd><dt>本地音频目录</dt><dd><code>{{ state.config.storage_dir }}</code></dd></dl>
        <h4>在当前配置文件末尾加入</h4><pre>[minimax]
api_key=&lt;填入你的 MiniMax API Key&gt;
region=cn
key_kind=token_plan
model=speech-2.8-hd
timeout_seconds=180
storage_dir=voice_data

[minimax_music]
# 复刻音色需要计费密钥：Token Plan 密钥只能合成，不能创建音色。
api_key=&lt;填入音乐专用的计费 API Key&gt;
region=cn
key_kind=token_plan
model=music-3.0
timeout_seconds=180</pre>
        <p>保存后重启项目后端，再点击“检测连接并同步”。也支持环境变量 <code>MINIMAX_API_KEY</code> 与 <code>MINIMAX_MUSIC_API_KEY</code>，其优先级高于配置文件。</p>
        <div class="studio-info">Token Plan、M Plan 与按量计费的权益不同。检测会显示当前密钥的实际权限；程序不会自动改用其他密钥或切换计费方式。音色查询通过后，复刻和合成仍分别受账户权限、认证及额度约束。</div>
        <div class="studio-info">复刻、查询音色和删除音色都走复刻凭据，语音合成走合成凭据；复刻出来的音色需要在合成凭据所属账号下可见才能用于合成。音乐创作是独立能力，在“声音工作台 → 音乐创作 → 连接配置”里有自己的配置说明。</div>
        <div class="studio-info">复刻音色**首次使用**会一次性收取音色费用，这笔费用只走账户余额，不走订阅额度。刚复刻的音色首次合成会自动改用计费凭据，激活后即可用订阅凭据正常合成；若订阅凭据余额不足会返回官方 1008，程序会自动换计费凭据重试一次。</div>
        <div class="studio-source-links"><a href="https://platform.minimax.cn/docs/guides/speech-voice-clone" target="_blank" rel="noreferrer">复刻录音要求 ↗</a><a href="https://platform.minimax.cn/docs/m-plan/faq" target="_blank" rel="noreferrer">订阅密钥与额度说明 ↗</a></div>
      </section>
      <section v-if="playing && playerUrl" class="studio-player" aria-label="语音播放器"><div class="studio-player-info"><span class="studio-eyebrow">已保存在本机</span><h4>{{ playing.title }}</h4><p>{{ formatDuration(playing.duration_seconds) }}<span v-if="playing.duration_seconds !== null"> · {{ playing.duration_seconds >= 180 && playing.duration_seconds <= 240 ? '符合 3–4 分钟目标' : '可根据实际时长调整篇幅或语速' }}</span></p></div><audio ref="player" :src="playerUrl" controls preload="metadata" /><button class="studio-button" :disabled="!!busy" @click="download(playing, 'mp3')">下载 MP3</button></section>
    </template>
    <div v-else-if="!busy" class="studio-empty"><p>页面未能载入，请检查后端和管理员登录状态。</p><button class="studio-button" @click="action('load', load)">重新载入</button></div>
  </section>
</template>
