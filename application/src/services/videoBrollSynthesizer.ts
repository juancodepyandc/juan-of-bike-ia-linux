// B-roll prompt synthesizer — pour chaque marker B-roll de la timeline,
// produit un prompt SDXL/FLUX pertinent en analysant le segment de script
// qui le précède.
//
// Demande handoff : "talking-head + B-roll auto : pendant que la voix off
// parle, le module switch sur des scènes 3D ou images générées".
//
// Stratégie :
//   1. Repérer le segment de script aligné temporellement sur le marker.
//   2. Extraire le sujet principal (NP) + adjectifs descriptifs.
//   3. Composer un prompt court : sujet + style cohérent (tone vidéo) + cadrage.

import { buildPrompt, type ImageStyle, type ImageBrief } from './imagePromptBuilder.ts'
import type { Timeline } from './videoCompositionPlanner.ts'

export type BrollPromptRequest = {
  timeline: Timeline
  script: string
  /** wordsPerMinute du voice-over — pour aligner segments. */
  wordsPerMinute: number
  /** Tone vidéo : guide le style image. */
  tone: 'tutoriel' | 'storytelling' | 'pub' | 'recap'
  /** Style préféré de l'auteur (sinon dérivé du tone). */
  preferredStyle?: ImageStyle
}

export type BrollPromptResult = {
  markerIndex: number
  /** Position en ms dans la timeline. */
  atMs: number
  /** Cue d'origine ("Segment 2", "Hook"…). */
  cue: string
  /** Bout du script aligné avec le marker. */
  scriptExcerpt: string
  /** Prompt SDXL/FLUX complet (avec qualifiers). */
  prompt: string
  /** Negative prompt. */
  negative: string
  /** Width/Height pour l'asset cible. */
  width: number
  height: number
  /** Aspect ratio dérivé du format vidéo. */
  aspectRatio: '16:9' | '9:16' | '1:1'
}

const TONE_TO_STYLE: Record<BrollPromptRequest['tone'], ImageStyle> = {
  tutoriel: 'flat-illustration',
  storytelling: 'cinematic',
  pub: 'studio-product',
  recap: 'cinematic',
}

/** Découpe le script en N segments de durées équivalentes. */
function scriptSegments(script: string, count: number): string[] {
  const words = script.trim().split(/\s+/).filter(Boolean)
  if (count <= 0 || words.length === 0) return []
  const out: string[] = []
  const per = Math.max(1, Math.floor(words.length / count))
  for (let i = 0; i < count; i += 1) {
    const start = i * per
    const end = i === count - 1 ? words.length : Math.min(words.length, (i + 1) * per)
    out.push(words.slice(start, end).join(' '))
  }
  return out
}

/** Extrait un "sujet" condensé : retire les mots-outils, garde 6-12 tokens. */
const STOPWORDS_BROLL = new Set([
  'le', 'la', 'les', 'un', 'une', 'des', 'de', 'du', 'au', 'aux', 'à', 'a',
  'et', 'ou', 'pour', 'par', 'sur', 'sous', 'avec', 'sans', 'dans', 'en',
  'je', 'tu', 'il', 'elle', 'on', 'nous', 'vous', 'ils', 'elles',
  'que', 'qui', 'quoi', 'est', 'sont', 'ce', 'cette', 'ces', 'son', 'sa',
  'mais', 'donc', 'car', 'ne', 'pas', 'plus', 'moins', 'puis', 'comment',
])

export function extractSubject(text: string, maxTokens = 10): string {
  const tokens = text
    .replace(/[.,;:!?()«»"']/g, ' ')
    .split(/\s+/)
    .filter(Boolean)
    .filter((t) => !STOPWORDS_BROLL.has(t.toLowerCase()))
    .slice(0, maxTokens)
  return tokens.join(' ')
}

/**
 * Synthétise les prompts B-roll pour tous les markers de la timeline.
 *
 * Aligne chaque marker temporellement sur le script (proportionnel) pour
 * éviter d'illustrer une partie qui n'est pas en train d'être prononcée.
 */
export function synthesizeBrollPrompts(req: BrollPromptRequest): BrollPromptResult[] {
  const { timeline, script, tone } = req
  const style = req.preferredStyle ?? TONE_TO_STYLE[tone]
  const markers = timeline.brollMarkers
  if (markers.length === 0) return []

  // Estime quand chaque mot est prononcé : mot k → temps k × (60000 / wpm).
  const words = script.trim().split(/\s+/).filter(Boolean)
  const wpm = Math.max(60, req.wordsPerMinute)
  const msPerWord = 60_000 / wpm

  const aspectRatio: '16:9' | '9:16' | '1:1' = timeline.format === '9:16' ? '9:16' : timeline.format === '1:1' ? '1:1' : '16:9'

  // VO start dans la timeline : fenêtre [voStart, voStart + voDuration].
  const vo = timeline.audioTracks.find((a) => a.kind === 'voice-over')
  const voStart = vo?.startMs ?? 0

  return markers.map((marker, idx) => {
    // Mot prononcé au moment du marker, sous une marge.
    const relMs = marker.atMs - voStart
    const wordIndex = Math.max(0, Math.min(words.length - 1, Math.floor(relMs / msPerWord)))
    const window = words.slice(Math.max(0, wordIndex - 4), Math.min(words.length, wordIndex + 6)).join(' ')
    const subject = extractSubject(window, 10) || marker.cue
    const brief: ImageBrief = {
      subject,
      style,
      composition: 'rule-of-thirds',
      aspectRatio,
    }
    const built = buildPrompt(brief)
    return {
      markerIndex: idx,
      atMs: marker.atMs,
      cue: marker.cue,
      scriptExcerpt: window,
      prompt: built.positive,
      negative: built.negative,
      width: built.width,
      height: built.height,
      aspectRatio,
    }
  })
}
