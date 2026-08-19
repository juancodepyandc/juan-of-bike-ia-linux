import { getBridgeUrl, isTauriRuntime } from '../utils/runtime.ts'

export type MusicRenderMode = 'instrumental' | 'song'
export type MusicQuality = 'preview' | 'studio'

export type MusicVoice = {
  slug: string
  name: string
  lang: string
  duration_s?: number
  quality_score?: number
}

export type MusicEngineStatus = {
  ok: boolean
  ready: boolean
  service?: string
  version?: string
  models: Array<{ name: string; is_default?: boolean; is_loaded?: boolean }>
  default_model?: string
  output_count?: number
  error?: string
}

export type MusicDraft = {
  title: string
  prompt: string
  lyrics: string
  mode: MusicRenderMode
  duration: number
  bpm?: number
  key?: string
  timeSignature?: string
  language: string
  voiceSlug?: string
  quality: MusicQuality
  seed?: number
}

export type MusicJob = {
  id: string
  status: 'queued' | 'running' | 'completed' | 'failed'
  queued_at?: number
  completed_at?: number
  queue_position?: number
  error?: string
  audio_url?: string
  filename?: string
  metadata?: Record<string, unknown>
}

function bridgeBase(): string {
  return isTauriRuntime() ? 'http://127.0.0.1:3001' : getBridgeUrl()
}

export function resolveMusicAsset(path: string): string {
  return /^https?:\/\//i.test(path) ? path : `${bridgeBase()}${path}`
}

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${bridgeBase()}${path}`, {
    ...init,
    headers: {
      ...(init?.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...(init?.headers ?? {}),
    },
  })
  const data = await response.json().catch(() => ({ error: `HTTP ${response.status}` })) as T & { error?: string }
  if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`)
  return data
}

export function musicStatus(): Promise<MusicEngineStatus> {
  return json<MusicEngineStatus>('/api/music/status')
}

export function listMusicVoices(): Promise<{ ok: boolean; voices: MusicVoice[] }> {
  return json('/api/music/voices')
}

export function listMusicExports(): Promise<{ ok: boolean; files: Array<{ filename: string; url: string; metadata?: Record<string, unknown>; modified?: number }> }> {
  return json('/api/music/exports')
}

export function createMusic(draft: MusicDraft): Promise<MusicJob> {
  return json<MusicJob>('/api/music/jobs', {
    method: 'POST',
    body: JSON.stringify(draft),
  })
}

export function readMusicJob(id: string): Promise<MusicJob> {
  return json<MusicJob>(`/api/music/jobs/${encodeURIComponent(id)}`)
}

export async function importMusicVoice(input: {
  file: File
  name: string
  language: string
  consent: boolean
}): Promise<{ ok: boolean; jobId?: string; slug?: string; error?: string }> {
  const body = new FormData()
  body.append('audio', input.file)
  body.append('name', input.name)
  body.append('language', input.language)
  body.append('consent', input.consent ? 'true' : 'false')
  return json('/api/music/voices', { method: 'POST', body })
}
