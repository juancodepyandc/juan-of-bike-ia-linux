/**
 * Lab-assistant service — shared between Academy and Cyber labs.
 *
 *   gradeAnswer   → the AI evaluates a user response against a specific
 *                   objective, returning score + missing concepts + targeted
 *                   feedback (non-binary "correct/incorrect").
 *   deepHint      → multi-level hint system. Level 1 nudges, level 2 shows
 *                   the method, level 3 walks the user halfway. Callers
 *                   track XP cost.
 *   diagnose      → the AI looks at what the user did (their HTML sandbox
 *                   state, console logs, last error) and explains.
 *
 * All calls return structured JSON. No markdown/disclaimers upstream.
 */
import { ollamaChat } from '../hooks/useTauri.ts'

const COACH_SYSTEM = [
  'Tu es un coach pédagogique universitaire, dense et rigoureux.',
  'Tu évalues le travail d\'un élève avec honnêteté : ni flatterie, ni brutalité gratuite.',
  'Tu identifies précisément CE QUI MANQUE dans une réponse : concept oublié, étape sautée, formule mal appliquée, hypothèse manquante.',
  'Tu donnes un indice qui pousse l\'élève à trouver sans lui donner la réponse — sauf si le niveau d\'indice demandé est maximum.',
  'Tu ne dis JAMAIS "bonne tentative" ni "c\'est intéressant" si c\'est faux. Tu dis ce qui est faux et pourquoi.',
  'Langue : français. Tu réponds UNIQUEMENT par le JSON demandé, dans un bloc ```json, rien autour.',
].join('\n')

export type Verdict = 'correct' | 'partial' | 'incorrect' | 'off_topic'

export interface GradeResult {
  verdict: Verdict
  /** 0..100 score of completeness/correctness */
  score: number
  /** One-sentence summary to display as a banner */
  summary: string
  /** Concrete things the student got right (at least 1, even when incorrect — "you did start by X") */
  strengths: string[]
  /** What is missing/wrong. Each item actionable. */
  gaps: string[]
  /** A concrete next step the student should try. */
  next_step: string
}

function parseJson<T>(raw: string): T | null {
  const fenced = raw.match(/```(?:json)?\s*([\s\S]+?)```/)
  const body = (fenced ? fenced[1] : raw).trim()
  const first = body.indexOf('{')
  const last = body.lastIndexOf('}')
  if (first === -1 || last === -1) return null
  try { return JSON.parse(body.slice(first, last + 1)) as T } catch { return null }
}

export interface GradeContext {
  subject?: string
  briefing?: string
  solutionHint?: string
  expectedFlag?: string
  /** v82er : notes/writeup personnel injecté dans le prompt comme
   *  contexte additionnel pour grader plus finement. */
  userNotes?: string
}

export async function gradeAnswer(
  model: string,
  objective: string,
  userAnswer: string,
  ctx: GradeContext = {},
): Promise<GradeResult> {
  const user = [
    `OBJECTIF DONNÉ À L'ÉLÈVE : ${objective}`,
    ctx.subject ? `SUJET / CONTEXTE : ${ctx.subject}` : null,
    ctx.briefing ? `BRIEFING : ${ctx.briefing.slice(0, 800)}` : null,
    ctx.solutionHint ? `RÉSUMÉ DE LA SOLUTION ATTENDUE (confidentiel) : ${ctx.solutionHint.slice(0, 600)}` : null,
    ctx.expectedFlag ? `FLAG ATTENDU (s'il y en a un) : ${ctx.expectedFlag}` : null,
    ctx.userNotes ? `NOTES / WRITEUP DE L'ÉLÈVE (contexte personnel) :\n${ctx.userNotes.slice(0, 1500)}` : null,
    '',
    `RÉPONSE DE L'ÉLÈVE :`,
    '<<<',
    userAnswer,
    '>>>',
    '',
    'Évalue :',
    '- verdict ∈ {"correct","partial","incorrect","off_topic"}',
    '- score 0..100 (100 = parfait, 70 = bon mais une étape manque, 40 = idée juste mais exécution erronée, 0 = hors-sujet)',
    '- summary : 1 phrase directe, factuelle',
    '- strengths : 1-3 items concrets (ce qui est juste)',
    '- gaps : 0-3 items concrets (ce qui manque / est faux)',
    '- next_step : 1 consigne actionnable',
    '',
    'Si l\'élève a trouvé le bon flag (exact match ou normalisation case/espaces raisonnable) → verdict="correct", score=100.',
    'Si l\'élève dit juste "je sais pas" ou équivalent → verdict="off_topic" avec next_step pointant vers le premier levier à explorer.',
    '',
    'Réponds UNIQUEMENT par ce JSON dans un bloc ```json :',
    '{',
    '  "verdict": "correct|partial|incorrect|off_topic",',
    '  "score": 0,',
    '  "summary": "...",',
    '  "strengths": ["..."],',
    '  "gaps": ["..."],',
    '  "next_step": "..."',
    '}',
  ].filter(Boolean).join('\n')

  const res = await ollamaChat(model, [
    { role: 'system', content: COACH_SYSTEM },
    { role: 'user',   content: user },
  ], 0.2)
  const raw = (res as { message?: { content?: string } })?.message?.content ?? ''
  const parsed = parseJson<GradeResult>(raw)
  if (!parsed) {
    // Fallback heuristic so the UI never crashes even if the model fumbles.
    const matchesFlag = !!ctx.expectedFlag && userAnswer.trim().toLowerCase() === ctx.expectedFlag.trim().toLowerCase()
    return matchesFlag
      ? { verdict: 'correct', score: 100, summary: 'Flag exact.', strengths: ['Réponse exacte'], gaps: [], next_step: 'Passe à l\'objectif suivant.' }
      : { verdict: 'partial', score: 40, summary: 'Réponse enregistrée mais l\'IA n\'a pas pu donner un diagnostic fiable.', strengths: ['Tu as tenté'], gaps: ['Diagnostic indisponible'], next_step: 'Reformule ou précise.' }
  }
  return {
    verdict: (['correct','partial','incorrect','off_topic'].includes(parsed.verdict) ? parsed.verdict : 'partial') as Verdict,
    score: Math.max(0, Math.min(100, Math.round(Number(parsed.score) || 0))),
    summary: String(parsed.summary || '').slice(0, 240),
    strengths: Array.isArray(parsed.strengths) ? parsed.strengths.map(String).slice(0, 3) : [],
    gaps: Array.isArray(parsed.gaps) ? parsed.gaps.map(String).slice(0, 3) : [],
    next_step: String(parsed.next_step || '').slice(0, 240),
  }
}

// ---------------------------------------------------------------------------
// Multi-level progressive hints
// ---------------------------------------------------------------------------

export type HintLevel = 1 | 2 | 3

export interface HintResult {
  level: HintLevel
  /** 1 = nudge, 2 = method, 3 = half-solution */
  body: string
  xp_cost: number
}

const HINT_PROFILES: Record<HintLevel, { system: string; xp: number }> = {
  1: {
    system: 'Donne un INDICE DISCRET (niveau 1/3) : 1 phrase courte qui oriente sans révéler la méthode. PAS de formule, PAS de commande précise. Juste un angle à explorer.',
    xp: 3,
  },
  2: {
    system: 'Donne un INDICE MÉTHODE (niveau 2/3) : 2-3 phrases qui décrivent la démarche générale / la famille de technique / l\'outil à utiliser, SANS donner la valeur exacte.',
    xp: 8,
  },
  3: {
    system: 'Donne un INDICE AVANCÉ (niveau 3/3) : montre concrètement les 60 premiers % de la solution (formule, commande, clé de lecture) mais laisse l\'élève finir lui-même.',
    xp: 18,
  },
}

export async function deepHint(
  model: string,
  objective: string,
  level: HintLevel,
  ctx: GradeContext = {},
): Promise<HintResult> {
  const profile = HINT_PROFILES[level]
  const user = [
    `OBJECTIF : ${objective}`,
    ctx.subject ? `SUJET : ${ctx.subject}` : null,
    ctx.briefing ? `CONTEXTE : ${ctx.briefing.slice(0, 600)}` : null,
    ctx.solutionHint ? `SOLUTION ATTENDUE (confidentielle) : ${ctx.solutionHint.slice(0, 500)}` : null,
    '',
    profile.system,
    '',
    'Réponds UNIQUEMENT par ce JSON dans un bloc ```json :',
    '{ "hint": "le texte de l\'indice" }',
  ].filter(Boolean).join('\n')

  const res = await ollamaChat(model, [
    { role: 'system', content: COACH_SYSTEM },
    { role: 'user',   content: user },
  ], 0.25)
  const raw = (res as { message?: { content?: string } })?.message?.content ?? ''
  const parsed = parseJson<{ hint: string }>(raw)
  const body = parsed?.hint?.slice(0, 500) || 'Réessaie en décomposant le problème en étapes plus petites.'
  return { level, body, xp_cost: profile.xp }
}
