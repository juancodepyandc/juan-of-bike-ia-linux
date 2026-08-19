import { isTauriRuntime, getBridgeUrl } from '../utils/runtime.ts'

function bridgeBase(): string {
  if (isTauriRuntime()) return 'http://127.0.0.1:3001'
  return getBridgeUrl()
}

async function bridgeFetch(path: string, init?: RequestInit): Promise<Response> {
  return fetch(`${bridgeBase()}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
  })
}

async function bridgeJson<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await bridgeFetch(path, init)
  const ct = resp.headers.get('content-type') || ''
  if (!ct.includes('json')) {
    const text = await resp.text().catch(() => '')
    throw new Error(`Bridge ${path} réponse non-JSON (HTTP ${resp.status}): ${text.slice(0, 200)}`)
  }
  const data = await resp.json() as T
  if (!resp.ok) {
    const err = (data as unknown as { error?: string }).error || `HTTP ${resp.status}`
    throw new Error(`${path}: ${err}`)
  }
  return data
}

export type VoiceSampleQuality = {
  ok: boolean
  sample_rate?: number
  channels?: number
  duration_s?: number
  clipping_ratio?: number
  silence_ratio?: number
  estimated_snr_db?: number
  quality_score?: number
  failures?: string[]
  warnings?: string[]
}

export type VoiceSampleUploadResponse = {
  ok: boolean
  sampleId: string
  samplePath: string
  audioUrl: string
  duration_s: number
  quality: VoiceSampleQuality
  error?: string
}

export type VoiceReplicateParams = {
  sampleId?: string
  samplePath?: string
  profileSlug?: string
  text: string
  name?: string
  savePermanent?: boolean
  lang?: 'fr' | 'en' | string
  promptText?: string
  instruction?: string
}

export type VoiceReplicateResponse = {
  ok: boolean
  name?: string
  slug?: string
  is_permanent?: boolean
  wav?: string
  meta?: string
  audioUrl?: string
  duration_s?: number
  engine?: string
  quality?: VoiceSampleQuality
  text?: string
  error?: string
}

export type VoiceStudioProfile = {
  slug: string
  name: string
  path: string
  reference: string
  audioUrl: string
  lang: string
  duration_s: number
  quality_score: number
  transcript?: string
  extracted_at?: number
  is_permanent: boolean
}

export type VoiceStudioGeneration = {
  name: string
  path: string
  size_bytes: number
  modified: number
  date: string
  text: string
  voice_name: string
  duration_s: number
  engine: string
  emotion?: string
}

export type VoiceStudioSong = {
  name: string
  path: string
  size_bytes: number
  modified: number
  date: string
  text: string
  voice_name: string
  duration_s: number
  backing_track?: string
  style?: string
}

export type InstrumentalTrack = {
  id: string
  name: string
  path: string
  filename: string
  style: string
  bpm: number
  key: string
  duration_s: number
  audioUrl: string
  size_bytes: number
}

export type EmotionAdvice = {
  ok: boolean
  emotion: string
  intensity: string
  instruction: string
  score: number
}

export type VoiceSingingParams = {
  sampleId?: string
  samplePath?: string
  profileSlug?: string
  lyrics?: string
  guideAudio?: string
  backingMusicId?: string
  style?: string
  bpm?: number
  name?: string
  savePermanent?: boolean
  lang?: string
  vocalVolume?: number
  musicVolume?: number
}

export type VoiceStudioTree = {
  ok: boolean
  root: string
  directories: {
    echantillons: string
    profils: string
    generations: string
    chansons?: string
    musiques?: string
    sessions: string
  }
  counts: {
    echantillons: number
    profils: number
    generations: number
    chansons?: number
    musiques?: number
    sessions: number
  }
  echantillons: Array<{ name: string; path: string; size_bytes: number; modified: number; date: string }>
  profils: VoiceStudioProfile[]
  generations: VoiceStudioGeneration[]
  chansons?: VoiceStudioSong[]
  sessions: Array<{ name: string; path: string; size_bytes: number; modified: number; date: string }>
}

export function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onloadend = () => {
      const res = reader.result as string
      resolve(res)
    }
    reader.onerror = (err) => reject(err)
    reader.readAsDataURL(blob)
  })
}

export async function uploadVoiceSampleBlob(blob: Blob, filename = 'recording.wav'): Promise<VoiceSampleUploadResponse> {
  try {
    const b64 = await blobToBase64(blob)
    return await uploadVoiceSampleBase64(b64)
  } catch {
    // Fallback multipart si FileReader indisponible
    const formData = new FormData()
    formData.append('audio', blob, filename)
    const resp = await fetch(`${bridgeBase()}/api/voice/studio/sample`, {
      method: 'POST',
      body: formData,
    })
    const data = await resp.json().catch(() => ({}))
    if (!resp.ok || !data.ok) {
      throw new Error(data.error || `HTTP ${resp.status}`)
    }
    return data
  }
}

export async function uploadVoiceSampleBase64(wavBase64: string): Promise<VoiceSampleUploadResponse> {
  return bridgeJson<VoiceSampleUploadResponse>('/api/voice/studio/sample', {
    method: 'POST',
    body: JSON.stringify({ wavBase64 }),
  })
}

export async function replicateVoice(params: VoiceReplicateParams): Promise<VoiceReplicateResponse> {
  return bridgeJson<VoiceReplicateResponse>('/api/voice/studio/replicate', {
    method: 'POST',
    body: JSON.stringify(params),
  })
}

export async function replicateSingingVoice(params: VoiceSingingParams): Promise<VoiceReplicateResponse & { backing_track?: string; lyrics?: string }> {
  return bridgeJson<VoiceReplicateResponse & { backing_track?: string; lyrics?: string }>('/api/voice/studio/sing', {
    method: 'POST',
    body: JSON.stringify(params),
  })
}

export async function detectVoiceEmotion(text: string): Promise<EmotionAdvice> {
  return bridgeJson<EmotionAdvice>('/api/voice/studio/emotion/detect', {
    method: 'POST',
    body: JSON.stringify({ text }),
  })
}

export async function searchInstrumentalTracks(query = '', limit = 12): Promise<InstrumentalTrack[]> {
  const q = encodeURIComponent(query.trim())
  const res = await bridgeJson<{ ok: boolean; tracks: InstrumentalTrack[] }>(`/api/voice/studio/music/search?q=${q}&limit=${limit}`)
  return res.tracks || []
}

export async function calibrateVoiceProfile(slug?: string): Promise<{ ok: boolean; transcript?: string; calibrated?: Record<string, unknown> }> {
  return bridgeJson<{ ok: boolean; transcript?: string; calibrated?: Record<string, unknown> }>('/api/voice/studio/calibrate', {
    method: 'POST',
    body: JSON.stringify({ slug: slug || '' }),
  })
}

export async function getVoiceStudioTree(): Promise<VoiceStudioTree> {
  return bridgeJson<VoiceStudioTree>('/api/voice/studio/tree')
}

export async function getVoiceStudioProfiles(): Promise<VoiceStudioProfile[]> {
  const res = await bridgeJson<{ ok: boolean; profils: VoiceStudioProfile[] }>('/api/voice/studio/profiles')
  return res.profils || []
}

export async function deleteVoiceStudioProfile(slug: string): Promise<{ ok: boolean; slug: string }> {
  return bridgeJson<{ ok: boolean; slug: string }>(`/api/voice/studio/profile/${encodeURIComponent(slug)}`, {
    method: 'DELETE',
  })
}

export async function cleanLegacyOutputs(): Promise<{ ok: boolean; cleaned: string[] }> {
  return bridgeJson<{ ok: boolean; cleaned: string[] }>('/api/voice/studio/clean-legacy', {
    method: 'POST',
    body: '{}',
  })
}

export function resolveVoiceAudioUrl(pathOrUrl: string): string {
  const val = (pathOrUrl || '').trim()
  if (!val) return ''
  if (/^https?:\/\//i.test(val)) return val
  if (val.startsWith('/api/')) return `${bridgeBase()}${val}`
  return `${bridgeBase()}/api/asset/${encodeURIComponent(val)}`
}
