// Cinema / Voice API helpers — talks to bridge_server.py /api/cinema/* and /api/voice/*.
// Works in Tauri natif, browser local, et tunnel Cloudflare:
//   - Tauri / browser local : appel direct http://127.0.0.1:3001
//   - Tunnel / cloud        : URL relative passee par le proxy Vite
// Le bridge tourne toujours en local sur le PC du user, meme en mode Tauri.

import { isTauriRuntime } from '../utils/runtime.ts'
import { getBridgeUrl } from '../utils/runtime.ts'

// In Tauri prod the webview lives on tauri:// — relative '/api/...' would not resolve.
// CSP allows http://127.0.0.1:* (cf. tauri.conf.json connect-src) so we just hit the
// bridge directly. In tunnel mode we want the relative path so the Vite/Cloudflare
// proxy forwards it; getBridgeUrl() already returns '' in that case.
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
    throw new Error(`Bridge ${path} reponse non-JSON (HTTP ${resp.status}): ${text.slice(0, 200)}`)
  }
  const data = await resp.json() as T
  if (!resp.ok) {
    const err = (data as unknown as { error?: string }).error || `HTTP ${resp.status}`
    throw new Error(`${path}: ${err}`)
  }
  return data
}

// ---------------------------------------------------------------------------
// Storyboard
// ---------------------------------------------------------------------------

export type CinemaCharacter = {
  name: string
  voice_slug: string
  voice_lang: 'fr' | 'en' | string
  voice_preset?: string
  voice_policy?: 'registered' | 'style' | string
  public_figure?: boolean
  description: string
}

export type CinemaShot = {
  id: number
  scene: string
  // v90 : identifiant stable du décor — le pipeline ancre les plans d'un même
  // lieu sur la dernière frame vue à cet endroit (continuité longue durée).
  location?: string
  speaker: string | null
  dialogue: string
  duration_s: number
  // v90 : durée réelle du clip livré, renseignée par le pipeline (peut différer
  // de duration_s : parole plus longue, cap du moteur vidéo).
  actual_duration_s?: number
  camera: 'wide' | 'medium' | 'close-up' | string
  needs_lipsync: boolean
  action_contract?: string
}

export type Storyboard = {
  title: string
  summary: string
  style: string
  aspect: '16:9' | '9:16' | '1:1' | '4:3' | string
  resolution: '720p' | '1080p' | '1440p' | string
  characters: CinemaCharacter[]
  shots: CinemaShot[]
  music?: { enabled: boolean; prompt?: string }
  subtitles?: { enabled: boolean }
  quality_mode?: 'auto' | 'balanced' | 'premium'
}

export type StoryboardResponse = {
  ok: boolean
  storyboard?: Storyboard
  clarification?: string
  error?: string
  raw?: unknown
}

export async function cinemaGenerateStoryboard(
  prompt: string,
  hints: Partial<{ aspect: string; resolution: string; lengthHint: string; style: string; cinematography: string }> = {},
  model?: string,
): Promise<StoryboardResponse> {
  // Pas de defaut hardcode : si non fourni, le bridge tombe sur sa propre liste
  // de fallbacks (qwen3:14b -> qwen2.5:7b -> premier modele installe).
  return bridgeJson<StoryboardResponse>('/api/cinema/storyboard', {
    method: 'POST',
    body: JSON.stringify({ prompt, hints, ...(model ? { model } : {}) }),
  })
}

// ---------------------------------------------------------------------------
// Generate (async job)
// ---------------------------------------------------------------------------

export type CinemaJobSpawn = { ok: true; jobId: string; outputPath: string }

export async function cinemaGenerateRun(storyboard: Storyboard): Promise<CinemaJobSpawn> {
  return bridgeJson<CinemaJobSpawn>('/api/cinema/generate', {
    method: 'POST',
    body: JSON.stringify({ storyboard }),
  })
}

// Preview character keyframes before Wan2.2 rendering.
export type CinemaPreviewKeyframesResponse = {
  ok: boolean
  char_quality?: Record<string, {
    score: number
    reason: string
    ok: boolean
    keyframe_url: string
  }>
  previewId?: string
  error?: string
}

export async function cinemaPreviewKeyframes(storyboard: Storyboard): Promise<CinemaPreviewKeyframesResponse> {
  return bridgeJson<CinemaPreviewKeyframesResponse>('/api/cinema/preview-keyframes', {
    method: 'POST',
    body: JSON.stringify({ storyboard }),
  })
}

// Self-test pipeline before Wan2.2 rendering.
export type CinemaSelftestStage = {
  ok: boolean
  ms: number
  error?: string
  [key: string]: unknown
}

export type CinemaSelftestResponse = {
  ok: boolean
  stages: Record<string, CinemaSelftestStage>
  overall_ok: boolean
  summary: string
}

export async function cinemaSelftest(): Promise<CinemaSelftestResponse> {
  return bridgeJson<CinemaSelftestResponse>('/api/cinema/selftest', {
    method: 'POST',
    body: '{}',
  })
}

// Per-shot regenerate: re-render single shot with new seed.
export type CinemaRegenerateShotResponse = {
  ok: boolean
  jobId?: string
  shotId?: number
  seed?: number
  outputPath?: string
  error?: string
}

export async function cinemaRegenerateShot(
  jobId: string,
  shotId: number,
  alterSeed?: number,
  modifiedScene?: string,
): Promise<CinemaRegenerateShotResponse> {
  return bridgeJson<CinemaRegenerateShotResponse>('/api/cinema/regenerate-shot', {
    method: 'POST',
    body: JSON.stringify({ jobId, shotId, alterSeed, modifiedScene }),
  })
}

// Sample render: 1 shot at 720p (~5-7 min) before full commit.
export type CinemaSampleRenderResponse = {
  ok: boolean
  jobId?: string
  mode?: string
  error?: string
}

export async function cinemaSampleRender(storyboard: Storyboard): Promise<CinemaSampleRenderResponse> {
  return bridgeJson<CinemaSampleRenderResponse>('/api/cinema/sample-render', {
    method: 'POST',
    body: JSON.stringify({ storyboard }),
  })
}

export type CinemaEta = {
  elapsed_s: number
  done: number
  total: number
  remaining_s: number
  stage: string
}

export type CinemaIntegrity = {
  ok: boolean
  duration_s: number
  has_video: boolean
  has_audio: boolean
  video_codec: string | null
  audio_codec: string | null
  size_bytes: number
  errors: string[]
}

export type CinemaCharacterQuality = {
  score: number
  reason: string
  ok: boolean
  keyframe_path: string
}

export type CinemaShotQuality = {
  shot_id: number
  scene_excerpt: string
  score: number | null
  reason: string
  ok: boolean
  // Physics and identity scores (multi-frame).
  physics_score?: number | null
  identity_score?: number | null
  issues?: string[]
}

// Audio silence detection per shot.
export type CinemaAudioQuality = {
  shot_id: number
  ok: boolean
  has_audio: boolean
  total_silence_s?: number
  silence_ratio?: number
  silences?: { start: number; end: number }[]
  expected_dialogue?: boolean
  error?: string
}

export type CinemaDialogueQuality = {
  shot: number
  speaker?: string
  voice_ok: boolean
  voice_engine?: string
  voice_preset?: string
  lipsync_required: boolean
  lipsync_ok: boolean | null
  error?: string
}

// Temporal coherence quality: detect scene cuts inside a shot.
export type CinemaTemporalQuality = {
  shot_id: number
  ok: boolean
  cuts_count: number
  cuts?: { t: number }[]
  duration_s?: number
  error?: string
}

// Aggregate quality grade (A/B/C/D) with breakdown per metric.
export type CinemaQualityGrade = {
  grade: 'A' | 'B' | 'C' | 'D'
  overall_pct: number
  breakdown: {
    shot_pct: number
    char_pct: number
    audio_pct: number
    temporal_pct: number
    integrity_pct: number
  }
  weak_shots: { shot_id: number; avg_score: number }[]
  exportable: boolean
}

export type CinemaJobStatus = {
  jobId: string
  status: 'queued' | 'running' | 'done' | 'unknown'
  output?: string
  error?: string
  exitCode?: number
  eta?: CinemaEta
  result?: {
    ok?: boolean
    video?: string
    shots?: number
    actual_time_s?: number
    error?: string
    integrity?: CinemaIntegrity  // ffprobe report
    char_quality?: Record<string, CinemaCharacterQuality>  // per-character vision scores
    shot_quality?: CinemaShotQuality[]  // per-shot vision scores
    audio_quality?: CinemaAudioQuality[]  // per-shot audio silence detection
    dialogue_quality?: CinemaDialogueQuality[]  // per-shot voice/lipsync contract
    temporal_quality?: CinemaTemporalQuality[]  // per-shot scene-cut detection
    quality_grade?: CinemaQualityGrade  // aggregate quality grade (A/B/C/D)
  }
  outputPath?: string
}

export async function cinemaJobStatus(jobId: string): Promise<CinemaJobStatus> {
  const resp = await bridgeFetch(`/api/cinema/job/${encodeURIComponent(jobId)}`)
  if (!resp.ok && resp.status !== 404) {
    throw new Error(`/api/cinema/job/${jobId}: HTTP ${resp.status}`)
  }
  return resp.json() as Promise<CinemaJobStatus>
}

// ---------------------------------------------------------------------------
// Voice library
// ---------------------------------------------------------------------------

export type VoiceLibraryEntry = {
  slug: string
  character: string
  lang: string
  source: string | null
  duration_s: number | null
  quality_score: number | null
  extracted_at: number | null
}

export async function voiceLibraryList(): Promise<VoiceLibraryEntry[]> {
  const data = await bridgeJson<{ ok: boolean; voices: VoiceLibraryEntry[]; count: number }>('/api/voice/library')
  return data.voices || []
}

export async function voiceLibraryDelete(slug: string): Promise<void> {
  const resp = await bridgeFetch(`/api/voice/library/${encodeURIComponent(slug)}`, { method: 'DELETE' })
  if (!resp.ok) {
    const text = await resp.text().catch(() => '')
    throw new Error(`Suppression voix ${slug} echouee: HTTP ${resp.status} ${text.slice(0, 160)}`)
  }
}

export async function voiceLibraryClear(): Promise<number> {
  const data = await bridgeJson<{ ok: boolean; deleted: number }>('/api/voice/library/clear', { method: 'POST' })
  return data.deleted ?? 0
}

export async function voiceRegister(args: {
  character: string
  lang?: string
  source?: string
  filePath?: string
  wavBase64?: string
}): Promise<{ ok: boolean; slug: string; path?: string; error?: string }> {
  return bridgeJson('/api/voice/register', {
    method: 'POST',
    body: JSON.stringify(args),
  })
}

// ---------------------------------------------------------------------------
// Voice extract (async)
// ---------------------------------------------------------------------------

export type VoiceExtractSpawn = { ok: true; jobId: string; outputPath: string; slug: string }

export async function voiceExtractRun(args: {
  character: string
  query?: string
  inputPath?: string
  lang?: string
  targetDuration?: number
  minConfidence?: number
  maxVideos?: number
}): Promise<VoiceExtractSpawn> {
  return bridgeJson<VoiceExtractSpawn>('/api/voice/extract', {
    method: 'POST',
    body: JSON.stringify(args),
  })
}

// ---------------------------------------------------------------------------
// Voice synthesize preview (async ou sync)
// ---------------------------------------------------------------------------

export async function voiceSynthesize(args: {
  character: string
  text: string
  lang?: string
  sync?: boolean
}): Promise<{ ok: boolean; jobId?: string; wavPath?: string; outputPath?: string; error?: string }> {
  return bridgeJson('/api/voice/synthesize', {
    method: 'POST',
    body: JSON.stringify(args),
  })
}

// ---------------------------------------------------------------------------
// Helpers UI: convertir un chemin local en URL lisible par <video>/<audio>
// ---------------------------------------------------------------------------

export function localFileToBridgeUrl(absolutePath: string): string {
  // Bridge sert les assets sous /api/asset/<path-relative-to-workspace>
  // En Tauri on peut utiliser convertFileSrc, mais via le bridge ca fonctionne
  // partout (Tauri/browser/tunnel) sans probleme de scheme asset://
  const cleaned = absolutePath.replace(/\\/g, '/')
  // Trim known prefixes — server already mounts the workspace root
  const idx = cleaned.lastIndexOf('/application/')
  const subpath = idx >= 0 ? cleaned.slice(idx + '/application/'.length) : cleaned
  const encoded = subpath.split('/').map(encodeURIComponent).join('/')
  return `${bridgeBase()}/api/asset/${encoded}`
}
