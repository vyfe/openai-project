import { minimaxBlob, minimaxGet, minimaxPost, minimaxUpload } from '@/services/minimaxApi'

export type Voice = {
  voice_id: string
  voice_type: 'system' | 'voice_cloning' | 'voice_generation'
  alias: string
  description: string
  created_time: string
  status: 'active' | 'pending' | 'unknown'
}
export type VoiceAudio = {
  has_audio?: boolean
  id: string; title: string; voice_id: string; model: string; speed: number
  volume: number; pitch: number; duration_seconds: number | null
  usage_characters: number | null; usage_voice_count: number; created_at: string; size: number
  status: 'generating' | 'unknown' | 'failed' | 'remote_ready' | 'ready'
  audio_url: string | null; url_expires_at: string | null; url_expired: boolean; error_message: string | null
}
export type VoiceState = {
  config: { ready: boolean; region: string; key_kind: string; model: string; base_url: string
    timeout_seconds: number; config_path: string; storage_dir: string
    clone_ready: boolean; clone_region: string; clone_base_url: string; clone_dedicated: boolean }
  models: string[]; voices: Voice[]; history: VoiceAudio[]
  default_voice_id: string; last_sync: string | null
}
export type SynthesisInput = {
  voice_id: string; title: string; text: string; model: string
  speed: number; volume: number; pitch: number; emotion: string
}
export type KeepaliveVoice = {
  voice_id: string; deadline: string | null; days_left: number | null
  disabled: boolean; activated_at: string | null; keepalive_count: number
}
export type KeepaliveState = {
  enabled: boolean; hour: number; minute: number; voices: KeepaliveVoice[]
}
export type KeepaliveInput = { enabled: boolean; hour: number; minute: number; disabled_voices: string[] }

const base = '/never_guess_my_usage/voice'

export const voiceAPI = {
  state: () => minimaxGet<VoiceState>(`${base}/state`),
  sync: () => minimaxPost<{ count: number }>(`${base}/sync`),
  clone: (data: FormData) => minimaxUpload<{ voice_id: string }>(`${base}/clone`, data),
  preference: (data: { voice_id: string; alias?: string; make_default?: boolean }) =>
    minimaxPost<null>(`${base}/preference`, data),
  delete: (voice_id: string, confirmation: string) =>
    minimaxPost<null>(`${base}/delete`, { voice_id, confirmation }),
  synthesize: (data: SynthesisInput) => minimaxPost<VoiceAudio>(`${base}/synthesize`, data),
  reading: (id: string) => minimaxGet<VoiceAudio & { text: string }>(`${base}/reading/${encodeURIComponent(id)}`),
  profile: () => minimaxGet<Record<string, unknown>>(`${base}/profile`),
  keepalive: () => minimaxGet<KeepaliveState>(`${base}/keepalive`),
  saveKeepalive: (data: KeepaliveInput) => minimaxPost<null>(`${base}/keepalive`, data),
  runKeepalive: () => minimaxPost<{ attempted: number; results: { voice_id: string; ok: boolean; error?: string }[] }>(`${base}/keepalive/run`),
  audio: (id: string, ext: 'mp3' | 'txt') => minimaxBlob(`${base}/audio/${encodeURIComponent(id)}/${ext}`)
}
