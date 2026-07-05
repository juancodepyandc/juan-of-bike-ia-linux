// Détection de BPM (tempo) depuis un signal audio mono échantillonné.
// Algo : énergie spectrale par fenêtre → onset detection → auto-corrélation
// dans la plage 50-200 BPM → score top.
//
// Pas Web Audio API direct — le caller fournit un Float32Array (amplitudes
// brutes, normalisées). Pas de FFT externe, on utilise détection d'onset
// par variations d'énergie.

export type BpmDetection = {
  /** BPM trouvé. */
  bpm: number
  /** Confidence [0..1] basée sur la hauteur du pic d'autocorrélation. */
  confidence: number
  /** Tempo classification. */
  category: 'larghissimo' | 'lento' | 'andante' | 'moderato' | 'allegro' | 'presto' | 'prestissimo'
  /** Indices des onsets détectés (en frames). */
  onsets: number[]
}

const MIN_BPM = 50
const MAX_BPM = 200

/**
 * Détecte le tempo principal.
 *   sampleRate : Hz (typique 44100 / 48000)
 *   windowSize : taille de fenêtre pour le calcul d'énergie (default 1024)
 */
export function detectBpm(
  samples: Float32Array | number[],
  sampleRate: number,
  windowSize = 1024,
): BpmDetection {
  if (samples.length < sampleRate) {
    return { bpm: 0, confidence: 0, category: 'moderato', onsets: [] }
  }
  // 1. Calcule l'énergie par fenêtre.
  const energies: number[] = []
  for (let i = 0; i + windowSize <= samples.length; i += windowSize) {
    let e = 0
    for (let j = 0; j < windowSize; j += 1) e += samples[i + j] * samples[i + j]
    energies.push(e)
  }
  if (energies.length < 10) {
    return { bpm: 0, confidence: 0, category: 'moderato', onsets: [] }
  }

  // 2. Onset detection : pic d'énergie locale.
  const onsets: number[] = []
  // Moyenne glissante locale (52 fenêtres ≈ 1.2s à 44kHz / 1024).
  const localWindow = Math.min(43, Math.floor(energies.length / 4))
  for (let i = localWindow; i < energies.length - localWindow; i += 1) {
    let mean = 0
    for (let k = i - localWindow; k < i + localWindow; k += 1) mean += energies[k]
    mean /= 2 * localWindow
    if (energies[i] > mean * 1.3 && energies[i] > energies[i - 1]) {
      onsets.push(i)
    }
  }
  if (onsets.length < 4) {
    return { bpm: 0, confidence: 0.1, category: 'moderato', onsets }
  }

  // 3. Inter-onset intervals → histogramme → max bin.
  const framesPerSecond = sampleRate / windowSize
  const intervalsFrames: number[] = []
  for (let i = 1; i < onsets.length; i += 1) intervalsFrames.push(onsets[i] - onsets[i - 1])

  // Convertit chaque interval en BPM candidate.
  const bpmCandidates = intervalsFrames
    .map((f) => 60 * framesPerSecond / f)
    .filter((b) => b >= MIN_BPM && b <= MAX_BPM)

  if (bpmCandidates.length === 0) {
    // Tente moitié/double de BPM hors range.
    const expanded = intervalsFrames.map((f) => 60 * framesPerSecond / f)
    for (const b of expanded) {
      if (b * 2 >= MIN_BPM && b * 2 <= MAX_BPM) bpmCandidates.push(b * 2)
      if (b / 2 >= MIN_BPM && b / 2 <= MAX_BPM) bpmCandidates.push(b / 2)
    }
  }
  if (bpmCandidates.length === 0) {
    return { bpm: 0, confidence: 0.1, category: 'moderato', onsets }
  }

  // Histogramme par bin 2 BPM (entre MIN et MAX).
  const bins = new Array(Math.floor((MAX_BPM - MIN_BPM) / 2) + 1).fill(0)
  for (const b of bpmCandidates) {
    const idx = Math.floor((b - MIN_BPM) / 2)
    if (idx >= 0 && idx < bins.length) bins[idx] += 1
  }
  let maxBin = 0
  let maxCount = 0
  for (let i = 0; i < bins.length; i += 1) {
    if (bins[i] > maxCount) {
      maxCount = bins[i]
      maxBin = i
    }
  }
  const bpm = MIN_BPM + maxBin * 2 + 1 // milieu du bin
  const confidence = Math.min(1, maxCount / bpmCandidates.length * 2)

  return {
    bpm,
    confidence,
    category: classifyTempo(bpm),
    onsets,
  }
}

export function classifyTempo(bpm: number): BpmDetection['category'] {
  if (bpm < 60) return 'larghissimo'
  if (bpm < 80) return 'lento'
  if (bpm < 108) return 'andante'
  if (bpm < 120) return 'moderato'
  if (bpm < 156) return 'allegro'
  if (bpm < 184) return 'presto'
  return 'prestissimo'
}

/**
 * Recommande un BPM cible pour matcher un tone vidéo (pour générer une
 * piste audio cohérente avec le rythme du voice-over).
 */
export function recommendBpmForTone(tone: 'tutoriel' | 'storytelling' | 'pub' | 'recap' | 'hype'): number {
  const map: Record<string, number> = {
    tutoriel: 100,
    storytelling: 80,
    pub: 130,
    recap: 110,
    hype: 150,
  }
  return map[tone] ?? 110
}

/**
 * Génère un signal de test : sinusoïdes superposées à BPM connu pour valider
 * detectBpm sans dépendre d'un vrai fichier audio.
 */
export function syntheticBeatSignal(bpm: number, durationSec: number, sampleRate: number): Float32Array {
  const totalSamples = Math.floor(durationSec * sampleRate)
  const out = new Float32Array(totalSamples)
  const beatIntervalSamples = (60 / bpm) * sampleRate
  // Chaque beat = 50 ms de kick (40-100 Hz).
  const kickDurationSamples = Math.floor(0.05 * sampleRate)
  for (let beat = 0; beat * beatIntervalSamples < totalSamples; beat += 1) {
    const startIdx = Math.floor(beat * beatIntervalSamples)
    for (let i = 0; i < kickDurationSamples && startIdx + i < totalSamples; i += 1) {
      const t = i / sampleRate
      const envelope = Math.exp(-t * 30)
      out[startIdx + i] += Math.sin(2 * Math.PI * 60 * t) * envelope
    }
  }
  return out
}
