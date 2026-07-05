// Intent router — détermine quel module Aurora doit prendre la main.
//
// Le handoff demande "détection d'intent par embedding plutôt que keywords".
// On ne charge pas un modèle d'embeddings côté navigateur (poids ~50MB+ pour
// du multilingue qualité). Compromis : feature vectors fabriqués main par
// module (sets de patterns FR + EN + bigrammes pondérés), avec scoring TF-IDF
// pondéré + bonus structuraux (mots-clés forts, intents explicites).
//
// Pour Juan : tape "code une todo app React" → route 'code' avec confidence
// 0.91, raison "starter framework 'react'". Tape "fais moi un schéma de
// pendule" → 'simulator' ou 'drawing' selon le mode.
//
// 0 dépendance, déterministe, testable. ~5 ms par classification.

import { tokenize } from './conversationMemory.ts'

export type ModuleId =
  | 'conversation'
  | 'code'
  | 'image'
  | 'voice'
  | 'video'
  | 'drawing'
  | '3d'
  | 'learning'
  | 'cyber'
  | 'simulator'
  | 'cowork'

export type IntentSignal = {
  /** Token, bigram or short n-gram to detect (normalised lowercase, no accents). */
  pattern: string
  /** Weight added to the module score when matched. */
  weight: number
  /** If true, match anywhere in the string; otherwise require word boundary. */
  loose?: boolean
}

export type ModuleProfile = {
  id: ModuleId
  label: string
  /** Strong patterns (weight ≥ 2). */
  signals: IntentSignal[]
  /** Anti-patterns — penalise if the term sneaks in. */
  antiSignals?: IntentSignal[]
  /** Boost factor (some modules outrank others when tied). */
  priority: number
}

// --- Profiles --------------------------------------------------------------
const PROFILES: readonly ModuleProfile[] = [
  {
    id: 'code',
    label: 'Code',
    priority: 1.0,
    signals: [
      { pattern: 'code', weight: 3 },
      { pattern: 'fonction', weight: 2 },
      { pattern: 'function', weight: 2 },
      { pattern: 'classe', weight: 2 },
      { pattern: 'class', weight: 2 },
      { pattern: 'react', weight: 3 },
      { pattern: 'vue', weight: 2 },
      { pattern: 'svelte', weight: 2 },
      { pattern: 'angular', weight: 2 },
      { pattern: 'python', weight: 3 },
      { pattern: 'typescript', weight: 3 },
      { pattern: 'javascript', weight: 3 },
      { pattern: 'rust', weight: 2 },
      { pattern: 'tauri', weight: 2 },
      { pattern: 'vite', weight: 2 },
      { pattern: 'npm', weight: 2 },
      { pattern: 'pip', weight: 2 },
      { pattern: 'api', weight: 2 },
      { pattern: 'endpoint', weight: 2 },
      { pattern: 'debug', weight: 2 },
      { pattern: 'bug', weight: 2 },
      { pattern: 'erreur', weight: 1.5 },
      { pattern: 'refactor', weight: 2 },
      { pattern: 'todo app', weight: 4, loose: true },
      { pattern: 'site web', weight: 3, loose: true },
      { pattern: 'page web', weight: 3, loose: true },
      { pattern: 'application', weight: 1.5 },
      { pattern: 'compiler', weight: 2 },
      { pattern: 'tsc', weight: 3 },
      { pattern: 'tests', weight: 1.5 },
    ],
  },
  {
    id: 'image',
    label: 'Image',
    priority: 0.95,
    signals: [
      { pattern: 'image', weight: 3 },
      { pattern: 'photo', weight: 2 },
      { pattern: 'illustration', weight: 3 },
      { pattern: 'paysage', weight: 2 },
      { pattern: 'portrait', weight: 2 },
      { pattern: 'wallpaper', weight: 3 },
      { pattern: 'fond ecran', weight: 4, loose: true },
      { pattern: 'sdxl', weight: 4 },
      { pattern: 'flux', weight: 3 },
      { pattern: 'controlnet', weight: 4 },
      { pattern: 'realiste', weight: 2 },
      { pattern: 'anime', weight: 2 },
      { pattern: 'manga', weight: 2 },
      { pattern: 'aquarelle', weight: 2 },
      { pattern: 'genere une image', weight: 5, loose: true },
      { pattern: 'fais moi une image', weight: 5, loose: true },
      { pattern: 'dessine moi', weight: 4, loose: true },
    ],
    antiSignals: [
      { pattern: 'svg', weight: 2 },
      { pattern: 'schema', weight: 2 },
      { pattern: 'croquis', weight: 1.5 },
    ],
  },
  {
    id: 'drawing',
    label: 'Dessin / SVG',
    priority: 0.9,
    signals: [
      { pattern: 'dessine', weight: 2 },
      { pattern: 'croquis', weight: 3 },
      { pattern: 'schema', weight: 4 },
      { pattern: 'diagramme', weight: 4 },
      { pattern: 'svg', weight: 4 },
      { pattern: 'vectoriel', weight: 3 },
      { pattern: 'flowchart', weight: 4 },
      { pattern: 'organigramme', weight: 4 },
      { pattern: 'plan electrique', weight: 4, loose: true },
      { pattern: 'circuit imprime', weight: 3, loose: true },
    ],
  },
  {
    id: '3d',
    label: '3D',
    priority: 0.95,
    signals: [
      { pattern: '3d', weight: 4 },
      { pattern: 'modele 3d', weight: 5, loose: true },
      { pattern: 'mesh', weight: 3 },
      { pattern: 'blender', weight: 3 },
      { pattern: 'glb', weight: 4 },
      { pattern: 'fbx', weight: 4 },
      { pattern: 'obj', weight: 2 },
      { pattern: 'hunyuan', weight: 5 },
      { pattern: 'gltf', weight: 4 },
      { pattern: 'sculpte', weight: 3 },
      { pattern: 'personnage 3d', weight: 5, loose: true },
      { pattern: 'creature', weight: 2 },
      { pattern: 'voxel', weight: 3 },
      { pattern: 'low poly', weight: 4, loose: true },
      { pattern: 'pbr', weight: 4 },
      { pattern: 'animation 3d', weight: 5, loose: true },
      { pattern: 'rig', weight: 3 },
    ],
  },
  {
    id: 'voice',
    label: 'Voix',
    priority: 0.9,
    signals: [
      { pattern: 'parle', weight: 2 },
      { pattern: 'voix', weight: 3 },
      { pattern: 'tts', weight: 4 },
      { pattern: 'lis a haute voix', weight: 5, loose: true },
      { pattern: 'audio', weight: 2 },
      { pattern: 'piper', weight: 4 },
      { pattern: 'whisper', weight: 4 },
      { pattern: 'enregistre ma voix', weight: 5, loose: true },
      { pattern: 'micro', weight: 2 },
    ],
  },
  {
    id: 'video',
    label: 'Vidéo',
    priority: 0.9,
    signals: [
      { pattern: 'video', weight: 4 },
      { pattern: 'court metrage', weight: 5, loose: true },
      { pattern: 'montage', weight: 4 },
      { pattern: 'tiktok', weight: 4 },
      { pattern: 'youtube short', weight: 5, loose: true },
      { pattern: 'reels', weight: 3 },
      { pattern: 'editing', weight: 2 },
      { pattern: 'cut', weight: 1 },
      { pattern: 'sous titre', weight: 3 },
    ],
  },
  {
    id: 'learning',
    label: 'Apprentissage',
    priority: 1.0,
    signals: [
      { pattern: 'cours', weight: 3 },
      { pattern: 'lecon', weight: 3 },
      { pattern: 'apprend', weight: 3 },
      { pattern: 'apprendre', weight: 3 },
      { pattern: 'quiz', weight: 4 },
      { pattern: 'exercice', weight: 4 },
      { pattern: 'qcm', weight: 4 },
      { pattern: 'bac', weight: 4 },
      { pattern: 'sti2d', weight: 5 },
      { pattern: 'sin', weight: 4 },
      { pattern: 'epreuve', weight: 3 },
      { pattern: 'revise', weight: 4 },
      { pattern: 'fiche de revision', weight: 5, loose: true },
      { pattern: 'controle', weight: 2 },
      { pattern: 'annale', weight: 4 },
    ],
  },
  {
    id: 'cyber',
    label: 'Cybersécurité',
    priority: 0.95,
    signals: [
      { pattern: 'cyber', weight: 4 },
      { pattern: 'securite', weight: 3 },
      { pattern: 'hack', weight: 3 },
      { pattern: 'ctf', weight: 5 },
      { pattern: 'argon2', weight: 5 },
      { pattern: 'bcrypt', weight: 5 },
      { pattern: 'mot de passe', weight: 4, loose: true },
      { pattern: 'password', weight: 3 },
      { pattern: 'hash', weight: 4 },
      { pattern: 'sha256', weight: 4 },
      { pattern: 'md5', weight: 4 },
      { pattern: 'crypto', weight: 3 },
      { pattern: 'chiffrement', weight: 4 },
      { pattern: 'tls', weight: 4 },
      { pattern: 'osint', weight: 5 },
    ],
  },
  {
    id: 'simulator',
    label: 'Simulateur',
    priority: 1.0,
    signals: [
      { pattern: 'simule', weight: 4 },
      { pattern: 'simulation', weight: 4 },
      { pattern: 'pendule', weight: 5 },
      { pattern: 'projectile', weight: 4 },
      { pattern: 'ressort', weight: 4 },
      { pattern: 'rlc', weight: 5 },
      { pattern: 'newton', weight: 3 },
      { pattern: 'gravite', weight: 3 },
      { pattern: 'collision', weight: 3 },
      { pattern: 'mecanique', weight: 4 },
      { pattern: 'physique', weight: 3 },
      { pattern: 'fluide', weight: 4 },
      { pattern: 'optique', weight: 3 },
      { pattern: 'verlet', weight: 4 },
      { pattern: 'rk4', weight: 4 },
    ],
  },
  {
    id: 'cowork',
    label: 'Cowork (orchestration)',
    priority: 1.0,
    signals: [
      { pattern: 'cowork', weight: 5 },
      { pattern: 'orchestre', weight: 4 },
      { pattern: 'fais ca pour moi', weight: 5, loose: true },
      { pattern: 'execute', weight: 3 },
      { pattern: 'lance le build', weight: 5, loose: true },
      { pattern: 'deploy', weight: 4 },
      { pattern: 'commit et push', weight: 5, loose: true },
      { pattern: 'github', weight: 2 },
      { pattern: 'vercel', weight: 3 },
      { pattern: 'pipeline', weight: 3 },
    ],
  },
  {
    id: 'conversation',
    label: 'Discussion',
    priority: 0.6, // fallback — picks if nothing else matches well
    signals: [
      { pattern: 'discute', weight: 2 },
      { pattern: 'parle moi', weight: 3, loose: true },
      { pattern: 'ton avis', weight: 3, loose: true },
      { pattern: 'tu penses quoi', weight: 4, loose: true },
      { pattern: 'salut', weight: 2 },
      { pattern: 'bonjour', weight: 2 },
      { pattern: 'merci', weight: 1 },
      { pattern: 'comment ca va', weight: 3, loose: true },
    ],
  },
]

const SLUG_RE = /^[a-z0-9]+$/

export type IntentResult = {
  moduleId: ModuleId
  confidence: number
  scores: Array<{ moduleId: ModuleId; score: number }>
  /** Top 3 signals that drove the decision. */
  matchedSignals: Array<{ moduleId: ModuleId; pattern: string; weight: number }>
  /** True if the second-best score is within 15% of the first. */
  ambiguous: boolean
  /** Suggestion FR for the UI ("Aurora va router vers le module Code"). */
  hint: string
}

function normalise(input: string): string {
  return input
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
}

/**
 * Classify a user query → which module should handle it.
 *
 * `userMessage`  — the raw input from the chat box.
 * `conversationContext` — optional last N messages, used to bias if the user
 *                  was already in a module (sticky intent).
 */
export function routeIntent(userMessage: string, conversationContext: string[] = []): IntentResult {
  const norm = normalise(userMessage)
  const tokens = new Set(tokenize(userMessage))
  const scores = new Map<ModuleId, number>()
  const matched: IntentResult['matchedSignals'] = []

  for (const profile of PROFILES) {
    let score = 0
    for (const sig of profile.signals) {
      if (matchSignal(norm, tokens, sig)) {
        score += sig.weight
        matched.push({ moduleId: profile.id, pattern: sig.pattern, weight: sig.weight })
      }
    }
    if (profile.antiSignals) {
      for (const sig of profile.antiSignals) {
        if (matchSignal(norm, tokens, sig)) score -= sig.weight
      }
    }
    if (score > 0) score *= profile.priority
    scores.set(profile.id, score)
  }

  // Sticky bonus : if the current module shows up in context, +1 score.
  for (const ctx of conversationContext) {
    const m = /\[module:([a-z0-9-]+)\]/.exec(ctx)
    if (m && SLUG_RE.test(m[1])) {
      const id = m[1] as ModuleId
      scores.set(id, (scores.get(id) ?? 0) + 0.5)
    }
  }

  const sorted = [...scores.entries()]
    .map(([moduleId, score]) => ({ moduleId, score }))
    .sort((a, b) => b.score - a.score)

  // Confidence = score top / (sum of positive scores), clamped to [0..1].
  const positiveSum = sorted.reduce((acc, e) => acc + Math.max(0, e.score), 0)
  const topScore = sorted[0]?.score ?? 0
  let confidence = topScore <= 0 ? 0.1 : Math.min(1, topScore / Math.max(1, positiveSum))
  let moduleId = sorted[0]?.moduleId ?? 'conversation'

  // No signal matched → fall back to conversation with low confidence.
  if (topScore <= 0) {
    moduleId = 'conversation'
    confidence = 0.2
  }

  const second = sorted[1]?.score ?? 0
  const ambiguous = topScore > 0 && second > 0 && second / topScore >= 0.85

  // Top 3 matches across modules, sorted by weight desc.
  const topMatches = matched
    .filter((m) => m.moduleId === moduleId)
    .sort((a, b) => b.weight - a.weight)
    .slice(0, 3)

  const profile = PROFILES.find((p) => p.id === moduleId)
  const hint = topMatches.length > 0
    ? `Aurora route vers ${profile?.label ?? moduleId} (mot-clé "${topMatches[0].pattern}")${ambiguous ? ' — ambigu, autre option : ' + (PROFILES.find((p) => p.id === sorted[1]?.moduleId)?.label ?? '') : ''}`
    : `Aurora reste en discussion libre (rien de spécifique détecté).`

  return {
    moduleId,
    confidence,
    scores: sorted,
    matchedSignals: topMatches,
    ambiguous,
    hint,
  }
}

function matchSignal(norm: string, tokens: Set<string>, sig: IntentSignal): boolean {
  const p = normalise(sig.pattern)
  if (sig.loose) return norm.includes(p)
  if (p.includes(' ')) {
    // multi-word phrase — fall back to includes with word boundaries.
    return new RegExp(`(?:^|\\W)${escapeRe(p)}(?:\\W|$)`).test(norm)
  }
  return tokens.has(p)
}

function escapeRe(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

/** Export profiles so the UI can list available modules. */
export function listModules(): readonly { id: ModuleId; label: string }[] {
  return PROFILES.map((p) => ({ id: p.id, label: p.label }))
}
