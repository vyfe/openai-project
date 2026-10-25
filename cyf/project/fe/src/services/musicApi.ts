import { minimaxBlob, minimaxGet, minimaxPost, minimaxUpload } from '@/services/minimaxApi'

export type MusicTrack = {
  id: string; title: string; model: string; instrumental: boolean; lyrics_optimizer: boolean
  status: 'generating' | 'cover_ready' | 'unknown' | 'failed' | 'remote_ready' | 'ready'
  audio_url: string | null; url_expires_at: string | null; url_expired: boolean
  duration_seconds: number | null; size: number; error_message: string | null
  created_at: string; has_audio: boolean; cover_ready: boolean; reference_duration: number | null
}
export type MusicState = {
  config: { ready: boolean; region: string; key_kind: string; model: string; cover_model: string
    base_url: string; timeout_seconds: number; config_path: string; storage_dir: string
    dedicated_key: boolean }
  models: string[]; tracks: MusicTrack[]
}
export type MusicInput = {
  title: string; prompt: string; lyrics: string; model: string
  instrumental: boolean; lyrics_optimizer: boolean
}
export type CoverInput = { id: string; prompt: string; lyrics: string; title: string }

const base = '/never_guess_my_usage/music'

export const musicAPI = {
  state: () => minimaxGet<MusicState>(`${base}/state`),
  generate: (data: MusicInput) => minimaxPost<MusicTrack>(`${base}/generate`, data),
  coverPreprocess: (data: FormData) => minimaxUpload<MusicTrack & { prompt: string; lyrics: string }>(`${base}/cover/preprocess`, data),
  coverGenerate: (data: CoverInput) => minimaxPost<MusicTrack>(`${base}/cover/generate`, data),
  track: (id: string) => minimaxGet<MusicTrack & { prompt: string; lyrics: string }>(`${base}/track/${encodeURIComponent(id)}`),
  delete: (id: string) => minimaxPost<null>(`${base}/delete`, { id }),
  audio: (id: string, ext: 'mp3' | 'txt') => minimaxBlob(`${base}/audio/${encodeURIComponent(id)}/${ext}`)
}
