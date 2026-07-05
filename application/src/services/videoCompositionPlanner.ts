// Video composition planner — fabrique un timeline de montage à partir d'un
// brief structuré. Aligné sur la spec handoff :
//
//   - intro hook 3s, rythme cuts toutes les 8s, outro CTA
//   - talking-head + B-roll auto (assets 3D ou images générées)
//   - sous-titres FR auto + correction LLM (cibles : timing keyframes ici)
//   - lower-thirds : nom du locuteur, source, timecode si pertinent
//   - branding consistent : jingles, fonts, couleurs Aurora
//   - export multi-format 16:9 cours, 9:16 shorts TikTok/Reels
//   - music ducking sous voix (-18 dB side-chain)
//
// Module pur — produit des structures que l'exporteur FFmpeg côté
// python-services/video appliquera.

export type AspectFormat = '16:9' | '9:16' | '1:1' | '4:5'

export type ClipKind =
  | 'talking-head'
  | 'b-roll-image'
  | 'b-roll-3d'
  | 'b-roll-screen'
  | 'lower-third'
  | 'jingle'
  | 'silence'
  | 'transition'

export type Clip = {
  id: string
  kind: ClipKind
  startMs: number
  durationMs: number
  /** Ref vers asset (chemin GLB, image, mp4...). */
  assetRef?: string
  /** Texte affiché (sous-titre, lower-third, CTA). */
  text?: string
  /** Animation in/out par défaut. */
  inTransition?: 'cut' | 'fade' | 'whip' | 'slide'
  outTransition?: 'cut' | 'fade' | 'whip' | 'slide'
}

export type SubtitleCue = {
  startMs: number
  endMs: number
  text: string
}

export type AudioTrack = {
  id: string
  kind: 'voice-over' | 'music' | 'sfx' | 'jingle'
  startMs: number
  durationMs: number
  /** Volume initial dB (0 = full). */
  baseDb: number
  /** Side-chain target : muter ce track quand voice-over joue (auto-duck). */
  duckOnVoiceOver?: boolean
  /** Profondeur du duck (dB). */
  duckDb?: number
}

export type Timeline = {
  format: AspectFormat
  totalDurationMs: number
  clips: Clip[]
  subtitles: SubtitleCue[]
  audioTracks: AudioTrack[]
  /** Marqueurs B-roll candidats — l'exporteur picke un asset par marqueur. */
  brollMarkers: Array<{ atMs: number; cue: string }>
}

export type VideoBrief = {
  /** Texte narration source (sera utilisé pour timer + sous-titres). */
  script: string
  /** Format primaire de sortie. */
  format: AspectFormat
  /** Style narratif. */
  tone: 'tutoriel' | 'storytelling' | 'pub' | 'recap'
  /** Mots/minute du voice-over (Piper sortie). */
  wordsPerMinute?: number
  /** Hook personnalisé (sinon généré). */
  hook?: string
  /** CTA final. */
  cta?: string
  /** Cible plateforme — module les transitions et durées. */
  platform: 'youtube-long' | 'youtube-short' | 'tiktok' | 'reels' | 'classroom'
  /** Auteur affiché en lower-third. */
  speakerName?: string
}

const PLATFORM_DEFAULTS: Record<VideoBrief['platform'], { format: AspectFormat; cutEveryMs: number; minDurationMs: number; maxDurationMs: number }> = {
  'youtube-long': { format: '16:9', cutEveryMs: 8000, minDurationMs: 60_000, maxDurationMs: 600_000 },
  'youtube-short': { format: '9:16', cutEveryMs: 3000, minDurationMs: 15_000, maxDurationMs: 60_000 },
  'tiktok': { format: '9:16', cutEveryMs: 2500, minDurationMs: 8000, maxDurationMs: 60_000 },
  'reels': { format: '9:16', cutEveryMs: 2800, minDurationMs: 10_000, maxDurationMs: 90_000 },
  'classroom': { format: '16:9', cutEveryMs: 14_000, minDurationMs: 60_000, maxDurationMs: 900_000 },
}

const HOOK_TEMPLATES: Record<VideoBrief['tone'], string[]> = {
  'tutoriel': ['Tu veux apprendre {sujet} en 2 minutes ?', 'Voilà la méthode que personne ne t\'a expliquée pour {sujet}.'],
  'storytelling': ['Il y a quelques années, {sujet} était impossible.', 'Imagine : {sujet} et personne ne sait comment.'],
  'pub': ['{sujet}, en mieux. Voilà comment.', 'On a refait {sujet}. Regarde.'],
  'recap': ['Cette semaine, {sujet}. Le résumé.', '{sujet} : ce que tu as manqué.'],
}

const CTA_TEMPLATES: Record<VideoBrief['tone'], string[]> = {
  'tutoriel': ['Abonne-toi pour le tuto suivant.', 'Quelle question tu te poses encore ? Dis-le en commentaire.'],
  'storytelling': ['La suite la semaine prochaine.', 'Si ça t\'a parlé, partage.'],
  'pub': ['Lien en description.', 'Essaie maintenant.'],
  'recap': ['Détail complet dans la description.', 'On se retrouve la semaine prochaine.'],
}

/**
 * Build a complete timeline from a brief. Estimates VO duration from script
 * (chars/min), spreads B-roll cuts at PLATFORM_DEFAULTS rhythm, inserts hook
 * + CTA + lower-third + jingle, adds side-chain ducking on music.
 */
export function planTimeline(brief: VideoBrief): Timeline {
  const platform = PLATFORM_DEFAULTS[brief.platform]
  const format = brief.format ?? platform.format
  const wpm = brief.wordsPerMinute ?? 160

  // Estimate VO duration : word count × (60_000 / wpm).
  const words = brief.script.trim().split(/\s+/).filter(Boolean).length
  const voDurationMs = Math.max(2000, Math.round(words * (60_000 / wpm)))

  const hookText = (brief.hook ?? pickTemplate(HOOK_TEMPLATES[brief.tone]))
    .replace('{sujet}', extractSubject(brief.script))
  const ctaText = brief.cta ?? pickTemplate(CTA_TEMPLATES[brief.tone])

  const HOOK_MS = 3000
  const OUTRO_MS = 4500
  const JINGLE_MS = 900

  let cursor = 0
  const clips: Clip[] = []
  const brollMarkers: Array<{ atMs: number; cue: string }> = []

  // Hook
  clips.push({
    id: 'hook',
    kind: 'b-roll-image',
    startMs: cursor,
    durationMs: HOOK_MS,
    text: hookText,
    assetRef: 'aurora://hook-image',
    inTransition: 'cut',
    outTransition: 'whip',
  })
  cursor += HOOK_MS

  // Jingle
  clips.push({
    id: 'jingle-in',
    kind: 'jingle',
    startMs: cursor,
    durationMs: JINGLE_MS,
    assetRef: 'aurora://jingle/short',
    inTransition: 'whip',
    outTransition: 'cut',
  })
  cursor += JINGLE_MS

  // Body : alternate talking-head + b-roll based on platform cadence.
  const bodyDuration = voDurationMs
  const bodyStart = cursor
  const cutEvery = platform.cutEveryMs
  const cutCount = Math.max(2, Math.floor(bodyDuration / cutEvery))
  const segDuration = Math.floor(bodyDuration / cutCount)
  for (let i = 0; i < cutCount; i += 1) {
    const seg: Clip = {
      id: `body-${i}`,
      kind: i % 2 === 0 ? 'talking-head' : 'b-roll-3d',
      startMs: cursor,
      durationMs: i === cutCount - 1 ? bodyDuration - segDuration * i : segDuration,
      assetRef: i % 2 === 0 ? 'aurora://talking-head' : `aurora://broll/${i}`,
      inTransition: i === 0 ? 'cut' : 'fade',
      outTransition: 'cut',
    }
    clips.push(seg)
    if (seg.kind === 'b-roll-3d') {
      brollMarkers.push({ atMs: seg.startMs, cue: `Segment ${i + 1}` })
    }
    cursor += seg.durationMs
  }

  // Lower-third (intro, 4s)
  if (brief.speakerName) {
    clips.push({
      id: 'lower-third',
      kind: 'lower-third',
      startMs: bodyStart + 500,
      durationMs: 3500,
      text: brief.speakerName,
    })
  }

  // CTA / outro
  clips.push({
    id: 'cta',
    kind: 'b-roll-image',
    startMs: cursor,
    durationMs: OUTRO_MS,
    text: ctaText,
    assetRef: 'aurora://outro',
    inTransition: 'fade',
    outTransition: 'fade',
  })
  cursor += OUTRO_MS

  const total = cursor

  // Subtitles : split script into ~6-word chunks, distribute over VO duration.
  const subtitles = makeSubtitles(brief.script, bodyStart, voDurationMs)

  // Audio tracks
  const audioTracks: AudioTrack[] = [
    {
      id: 'voice-over',
      kind: 'voice-over',
      startMs: bodyStart,
      durationMs: voDurationMs,
      baseDb: -3,
    },
    {
      id: 'background-music',
      kind: 'music',
      startMs: 0,
      durationMs: total,
      baseDb: -12,
      duckOnVoiceOver: true,
      duckDb: -18,
    },
  ]

  return {
    format,
    totalDurationMs: total,
    clips,
    subtitles,
    audioTracks,
    brollMarkers,
  }
}

function pickTemplate(arr: string[]): string {
  return arr[0] ?? ''
}

function extractSubject(script: string): string {
  const first = script.trim().split(/[.!?]/)[0] ?? script
  return first.length > 40 ? first.slice(0, 40) + '…' : first
}

function makeSubtitles(script: string, startMs: number, durationMs: number): SubtitleCue[] {
  const words = script.trim().split(/\s+/).filter(Boolean)
  if (words.length === 0) return []
  const chunkSize = 6
  const out: SubtitleCue[] = []
  const totalChunks = Math.max(1, Math.ceil(words.length / chunkSize))
  const chunkMs = durationMs / totalChunks
  for (let i = 0; i < totalChunks; i += 1) {
    const slice = words.slice(i * chunkSize, (i + 1) * chunkSize).join(' ')
    out.push({
      startMs: startMs + i * chunkMs,
      endMs: startMs + (i + 1) * chunkMs,
      text: slice,
    })
  }
  return out
}

// --- Multi-format export plan ----------------------------------------------
export type ExportPreset = {
  format: AspectFormat
  width: number
  height: number
  fps: number
  bitrateMbps: number
  containerExt: 'mp4' | 'webm' | 'mov'
  /** Codec vidéo recommandé. */
  videoCodec: 'h264' | 'h265' | 'vp9' | 'av1'
  audioCodec: 'aac' | 'opus'
  /** Suffixe pour le nom de sortie. */
  suffix: string
}

export function defaultExportPresets(timeline: Timeline): ExportPreset[] {
  const presets: ExportPreset[] = [
    { format: '16:9', width: 1920, height: 1080, fps: 30, bitrateMbps: 8, containerExt: 'mp4', videoCodec: 'h264', audioCodec: 'aac', suffix: '_1080p.mp4' },
    { format: '9:16', width: 1080, height: 1920, fps: 30, bitrateMbps: 6, containerExt: 'mp4', videoCodec: 'h264', audioCodec: 'aac', suffix: '_short.mp4' },
  ]
  // Only export the formats relevant to the planned timeline + the primary one.
  return presets.filter((p) => p.format === timeline.format || p.format === '16:9')
}
