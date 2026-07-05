// Export des sous-titres de la Timeline vers les 3 formats standards :
//   - SRT (SubRip) : simple, universel
//   - VTT (WebVTT) : streaming HTML5 <track>
//   - ASS (Advanced SubStation) : style avancé (font, color, position)
//
// Module pur. Utilise les SubtitleCue produits par videoCompositionPlanner.

import type { SubtitleCue, Timeline } from './videoCompositionPlanner.ts'

function msToSrtTime(ms: number): string {
  const totalSec = Math.floor(ms / 1000)
  const hh = Math.floor(totalSec / 3600)
  const mm = Math.floor((totalSec % 3600) / 60)
  const ss = totalSec % 60
  const msPart = ms % 1000
  return `${String(hh).padStart(2, '0')}:${String(mm).padStart(2, '0')}:${String(ss).padStart(2, '0')},${String(msPart).padStart(3, '0')}`
}

function msToVttTime(ms: number): string {
  return msToSrtTime(ms).replace(',', '.')
}

function msToAssTime(ms: number): string {
  const totalCs = Math.floor(ms / 10)
  const cs = totalCs % 100
  const totalSec = Math.floor(totalCs / 100)
  const ss = totalSec % 60
  const mm = Math.floor(totalSec / 60) % 60
  const hh = Math.floor(totalSec / 3600)
  return `${hh}:${String(mm).padStart(2, '0')}:${String(ss).padStart(2, '0')}.${String(cs).padStart(2, '0')}`
}

/**
 * SRT format (le plus universel). Compatibilité : VLC, mpv, YouTube,
 * Twitch, OBS, Premiere…
 */
export function exportSrt(cues: SubtitleCue[]): string {
  return cues
    .map((cue, i) => {
      return `${i + 1}\n${msToSrtTime(cue.startMs)} --> ${msToSrtTime(cue.endMs)}\n${cue.text.trim()}\n`
    })
    .join('\n')
}

/**
 * WebVTT format pour HTML5 <video> + <track>. RFC à la W3C.
 */
export function exportVtt(cues: SubtitleCue[]): string {
  const header = 'WEBVTT\n\n'
  const body = cues
    .map((cue, i) => {
      return `${i + 1}\n${msToVttTime(cue.startMs)} --> ${msToVttTime(cue.endMs)}\n${cue.text.trim()}\n`
    })
    .join('\n')
  return header + body
}

export type AssStyle = {
  name: string
  fontName: string
  fontSize: number
  primaryColor: string // "&H00FFFFFF" format ASS BGR
  outlineColor: string
  shadowColor: string
  bold: boolean
  italic: boolean
  /** 1=bottom-left, 2=bottom-center, 3=bottom-right, etc. (Numpad). */
  alignment: 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9
}

export const ASS_STYLE_AURORA: AssStyle = {
  name: 'Aurora',
  fontName: 'Inter',
  fontSize: 48,
  primaryColor: '&H00FFFFFF',
  outlineColor: '&H00000000',
  shadowColor: '&H80000000',
  bold: true,
  italic: false,
  alignment: 2,
}

/**
 * ASS / SSA v4+ : format avec styles riches. Ouvrable par mpv, OBS, Aegisub.
 */
export function exportAss(cues: SubtitleCue[], style: AssStyle = ASS_STYLE_AURORA, resolution: { width: number; height: number } = { width: 1920, height: 1080 }): string {
  const header = `[Script Info]
ScriptType: v4.00+
PlayResX: ${resolution.width}
PlayResY: ${resolution.height}
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: ${style.name},${style.fontName},${style.fontSize},${style.primaryColor},&H000000FF,${style.outlineColor},${style.shadowColor},${style.bold ? -1 : 0},${style.italic ? -1 : 0},0,0,100,100,0,0,1,2,2,${style.alignment},20,20,40,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
`
  const body = cues
    .map((cue) => {
      const text = cue.text.replace(/\n/g, '\\N').trim()
      return `Dialogue: 0,${msToAssTime(cue.startMs)},${msToAssTime(cue.endMs)},${style.name},,0,0,0,,${text}`
    })
    .join('\n')
  return header + body + '\n'
}

/**
 * Découpe automatiquement un texte long en cues de N secondes max + M
 * caractères max par cue. Pour générer des subs depuis une transcription
 * Whisper sans timecodes par cue.
 */
export type AutoSplitOptions = {
  maxDurationMs?: number
  maxChars?: number
  wordsPerSecond?: number
}

export function autoSplitSubtitles(
  fullText: string,
  startMs: number,
  totalDurationMs: number,
  opts: AutoSplitOptions = {},
): SubtitleCue[] {
  const maxDur = opts.maxDurationMs ?? 4500
  const maxChars = opts.maxChars ?? 80
  const wpsExplicit = opts.wordsPerSecond ?? 2.5

  // Découpe en phrases (sur . ? !) puis en sous-cues si trop long.
  const sentences = fullText.split(/(?<=[.!?])\s+/).filter(Boolean)
  const cues: SubtitleCue[] = []
  let cursor = startMs

  for (const sentence of sentences) {
    // Si la phrase est plus longue que maxChars, split par groupes de N mots.
    const chunks: string[] = []
    if (sentence.length <= maxChars) {
      chunks.push(sentence)
    } else {
      const words = sentence.split(/\s+/)
      let current = ''
      for (const w of words) {
        if ((current + ' ' + w).trim().length > maxChars) {
          chunks.push(current.trim())
          current = w
        } else {
          current = current ? current + ' ' + w : w
        }
      }
      if (current) chunks.push(current.trim())
    }

    for (const chunk of chunks) {
      const wordCount = chunk.split(/\s+/).length
      let dur = (wordCount / wpsExplicit) * 1000
      dur = Math.min(maxDur, Math.max(800, dur))
      cues.push({ startMs: cursor, endMs: cursor + dur, text: chunk })
      cursor += dur
    }
  }

  // Si on dépasse totalDurationMs, on raccourcit le dernier cue.
  if (cues.length > 0 && cursor > startMs + totalDurationMs) {
    const overshoot = cursor - (startMs + totalDurationMs)
    const lastCue = cues[cues.length - 1]
    lastCue.endMs = Math.max(lastCue.startMs + 500, lastCue.endMs - overshoot)
  }
  return cues
}

/**
 * Export complet : SRT + VTT + ASS d'une Timeline.
 */
export function exportAllSubtitles(timeline: Timeline, style?: AssStyle): { srt: string; vtt: string; ass: string } {
  return {
    srt: exportSrt(timeline.subtitles),
    vtt: exportVtt(timeline.subtitles),
    ass: exportAss(timeline.subtitles, style),
  }
}
