/**
 * iter32.H — Semantic answer evaluation via gemma3:12b.
 *
 * Replaces the literal string-compare heuristic in QcmExo / MiniExo
 * with a real LLM-based evaluator that accepts synonyms, paraphrases,
 * partial answers, and equivalent formulations. Returns a 0-100 score
 * + a 1-2 sentence feedback the UI can show to the learner.
 *
 * The user explicitly asked: "ce qu'il attend comme réponse soit pas
 * en dure car sinon faudrait écrire lettre pour lettre et c'est pas
 * dans l'attente réelle faut avoir compris et donner une bonne réponse
 * qui veut dire la même chose."
 */

import { getBridgeUrl } from '../utils/runtime.ts'
import { LEARNING_EVAL_MODEL } from '../config/models.ts'

function chatEndpoint(): string {
  // iter32.H: route via bridge proxy so prod build works through Cloudflare tunnel.
  // The bridge exposes both `/proxy/ollama/api/chat` (with SSE keepalive) and the
  // legacy `/api/ollama/chat` alias. We prefer the proxy so cold-starts don't
  // get killed at 125s by Cloudflare.
  const base = (() => {
    try { return getBridgeUrl() } catch { return '' }
  })()
  return base ? `${base}/proxy/ollama/api/chat` : '/api/ollama/chat'
}

export type SemanticEvalInput = {
  question: string
  expected: string
  userAnswer: string
  /** Subject hint (geo, hist, math, ...) for tone/criteria. Optional. */
  subject?: string
  /** Optional indice from the source exo, included in the LLM context. */
  indice?: string
}

export type SemanticEvalResult = {
  ok: boolean
  /** 0-100. >=70 marks `ok` true. */
  score: number
  /** 1-2 sentences in French explaining what was right / wrong. */
  feedback: string
  /** List of concepts the answer missed (for adaptive regen). */
  weakConcepts: string[]
  /** Raw LLM response for debugging. Always present even on parse fail. */
  raw?: string
  /** Set when the LLM call itself fails (network, timeout, JSON parse). */
  error?: string
}

const SYSTEM_PROMPT = `Tu es correcteur d'évaluations BAC en France. Tu évalues
si la réponse d'un élève EXPRIME LA MÊME CHOSE que la réponse attendue.

Règles strictes :
- Synonymes, paraphrases, formulations différentes → ACCEPTÉS si le sens est conservé.
- Réponse partielle qui couvre l'essentiel → score >= 70.
- Réponse fausse, hors-sujet, ou qui contredit l'attendu → score < 50.
- Réponse à moitié bonne (concept correct mais flou ou incomplet) → 50-69.
- Réponse littéralement identique à l'attendu n'a PAS de bonus particulier — c'est juste 100.
- Pas de bonus pour la longueur. Pas de pénalité pour la concision si le sens est juste.

Tu réponds UNIQUEMENT par un JSON valide, sans markdown, sans préambule :
{"score": <0-100>, "feedback": "<1-2 phrases en français, ton bienveillant et précis>", "weak_concepts": ["<concept mal compris 1>", "..."]}

Si la réponse est vide ou ne contient rien d'utile : score 0, feedback explique ce qui était attendu.
Si la réponse est très bonne : score 90-100, feedback positif court.
Si la réponse a des manques précis : weak_concepts liste 1-3 termes que l'élève doit revoir.`

function buildUserMessage(input: SemanticEvalInput): string {
  const parts: string[] = []
  if (input.subject) parts.push(`Matière : ${input.subject}`)
  parts.push(`Question posée à l'élève :\n${input.question}`)
  if (input.indice) parts.push(`Indice fourni : ${input.indice}`)
  parts.push(`Réponse ATTENDUE par le correcteur :\n${input.expected}`)
  parts.push(`RÉPONSE de l'élève :\n${input.userAnswer || '(vide)'}`)
  parts.push(`Évalue la compréhension et renvoie le JSON.`)
  return parts.join('\n\n')
}

function parseLLMJson(raw: string): SemanticEvalResult | null {
  // Strip code fences if present.
  const fenced = raw.match(/```(?:json)?\s*([\s\S]*?)```/)
  const candidate = fenced ? fenced[1] : raw
  // Find first { ... last } to be tolerant.
  const first = candidate.indexOf('{')
  const last = candidate.lastIndexOf('}')
  if (first === -1 || last <= first) return null
  try {
    const obj = JSON.parse(candidate.slice(first, last + 1)) as {
      score?: unknown; feedback?: unknown; weak_concepts?: unknown
    }
    const score = typeof obj.score === 'number'
      ? Math.max(0, Math.min(100, Math.round(obj.score)))
      : 0
    const feedback = typeof obj.feedback === 'string'
      ? obj.feedback.slice(0, 400)
      : ''
    const weakConcepts = Array.isArray(obj.weak_concepts)
      ? obj.weak_concepts.filter((c): c is string => typeof c === 'string').slice(0, 5)
      : []
    return { ok: score >= 70, score, feedback, weakConcepts, raw }
  } catch {
    return null
  }
}

/**
 * Run the semantic eval. Times out at 30s. Falls back to a literal-match
 * heuristic if Ollama is unreachable so the UI never freezes.
 */
export async function evaluateAnswerSemantically(
  input: SemanticEvalInput,
  options: { signal?: AbortSignal; timeoutMs?: number } = {},
): Promise<SemanticEvalResult> {
  // iter34 : bump eval timeout 30s → 60s. gemma3:12b cold-start (premier
  // call après idle MAX_LOADED=1) peut tenir 35-50s avant TTFB sur tunnel
  // Cloudflare. 30s coupait régulièrement le student au moment où il
  // venait juste de soumettre une réponse mini-exo.
  const { signal, timeoutMs = 60_000 } = options
  // Quick-path: empty user answer → score 0.
  if (!input.userAnswer || !input.userAnswer.trim()) {
    return {
      ok: false,
      score: 0,
      feedback: `Réponse vide. Attendu : ${input.expected.slice(0, 120)}${input.expected.length > 120 ? '…' : ''}`,
      weakConcepts: [],
    }
  }
  // Quick-path: literal match → 100 (no need for LLM).
  const norm = (s: string) => s
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[^a-z0-9 ]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
  if (norm(input.userAnswer) === norm(input.expected)) {
    return {
      ok: true,
      score: 100,
      feedback: 'Réponse exacte.',
      weakConcepts: [],
    }
  }

  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort('timeout'), timeoutMs)
  if (signal) signal.addEventListener('abort', () => ctrl.abort('upstream-abort'))

  try {
    const resp = await fetch(chatEndpoint(), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: LEARNING_EVAL_MODEL,
        messages: [
          { role: 'system', content: SYSTEM_PROMPT },
          { role: 'user', content: buildUserMessage(input) },
        ],
        stream: false,
        options: { temperature: 0.2, num_ctx: 4096, num_predict: 400 },
      }),
      signal: ctrl.signal,
    })
    if (!resp.ok) {
      return fallbackHeuristic(input, `HTTP ${resp.status}`)
    }
    const data = await resp.json() as { message?: { content?: string }; response?: string }
    const text = data?.message?.content ?? data?.response ?? ''
    const parsed = parseLLMJson(text)
    if (parsed) return parsed
    return fallbackHeuristic(input, `parse-fail`)
  } catch (err) {
    return fallbackHeuristic(input, err instanceof Error ? err.message : String(err))
  } finally {
    clearTimeout(timer)
  }
}

function fallbackHeuristic(input: SemanticEvalInput, reason: string): SemanticEvalResult {
  const norm = (s: string) => s
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[^a-z0-9 ]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
  const userN = norm(input.userAnswer)
  const expN = norm(input.expected)
  // Bag-of-words overlap
  const userWords = new Set(userN.split(' ').filter((w) => w.length >= 3))
  const expWords = new Set(expN.split(' ').filter((w) => w.length >= 3))
  if (expWords.size === 0) {
    return { ok: false, score: 50, feedback: `(eval LLM indisponible: ${reason}) Note approximative.`, weakConcepts: [] }
  }
  let matches = 0
  for (const w of userWords) if (expWords.has(w)) matches++
  const overlap = matches / expWords.size
  const score = Math.round(overlap * 100)
  return {
    ok: score >= 70,
    score,
    feedback: `(eval LLM indisponible: ${reason}) ${score}% des mots-clés attendus retrouvés.`,
    weakConcepts: [],
    error: reason,
  }
}

/**
 * Regenerate a similar exo on weak concepts. Used by the "🔄 Refaire un
 * exo similaire" button. Returns the fresh exo or null on failure.
 */
export type RegenSimilarInput = {
  prevQuestion: string
  prevType: 'flashcard' | 'qcm' | 'mini-exo' | string
  weakConcepts: string[]
  subject?: string
}

export type RegenSimilarResult = {
  type: string
  question: string
  reponse: string
  indice?: string
  choix?: string[]
  bonnes_reponses?: number[]
  duree_sec?: number
  raw?: string
  error?: string
}

const REGEN_SYSTEM = `Tu génères UN exercice de révision BAC pour un élève qui
a manqué un concept. Tu réponds UNIQUEMENT par un JSON valide :
{"type": "<flashcard|qcm|mini-exo>", "question": "...", "reponse": "...", "indice": "...", "choix": [<4 options pour qcm uniquement>], "bonnes_reponses": [<index 0-based>], "duree_sec": <8-30>}

Règles :
- Le type DOIT être identique à celui demandé par l'utilisateur.
- La question DOIT être DIFFÉRENTE de celle déjà posée (varie l'angle, l'exemple, la formulation).
- Si type="qcm" : 4 choix avec exactement 1 ou plusieurs bonnes_reponses.
- Si type="flashcard" : pas de choix, juste question/reponse/indice.
- Si type="mini-exo" : question ouverte de rédaction, reponse = corrigé attendu en 2-4 phrases.
- Cible le concept faible mentionné par l'utilisateur.
- Pas de markdown. Que du JSON.`

export async function regenerateSimilarExo(
  input: RegenSimilarInput,
  options: { signal?: AbortSignal; timeoutMs?: number } = {},
): Promise<RegenSimilarResult | null> {
  // iter34 : bump regen-similar 45s → 90s. Génération exo + JSON parse
  // peut tenir 50-70s sur cold-start. 45s coupait au pire moment.
  const { signal, timeoutMs = 90_000 } = options
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort('timeout'), timeoutMs)
  if (signal) signal.addEventListener('abort', () => ctrl.abort('upstream-abort'))
  try {
    const resp = await fetch(chatEndpoint(), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: LEARNING_EVAL_MODEL,
        messages: [
          { role: 'system', content: REGEN_SYSTEM },
          { role: 'user', content: [
              `Matière : ${input.subject ?? 'général'}`,
              `Type d'exercice demandé : ${input.prevType}`,
              `Question DÉJÀ posée (à NE PAS répéter, varie totalement) :\n${input.prevQuestion}`,
              `Concept(s) que l'élève doit retravailler : ${input.weakConcepts.join(', ') || '(aucun précis)'}`,
              `Génère un nouvel exercice ciblé sur ces concepts.`,
            ].join('\n\n') },
        ],
        stream: false,
        options: { temperature: 0.7, num_ctx: 4096, num_predict: 600 },
      }),
      signal: ctrl.signal,
    })
    if (!resp.ok) return { type: input.prevType, question: '', reponse: '', error: `HTTP ${resp.status}` }
    const data = await resp.json() as { message?: { content?: string }; response?: string }
    const text = data?.message?.content ?? data?.response ?? ''
    const fenced = text.match(/```(?:json)?\s*([\s\S]*?)```/)
    const candidate = fenced ? fenced[1] : text
    const first = candidate.indexOf('{'); const last = candidate.lastIndexOf('}')
    if (first === -1 || last <= first) return { type: input.prevType, question: '', reponse: '', raw: text, error: 'no-json' }
    try {
      const obj = JSON.parse(candidate.slice(first, last + 1)) as RegenSimilarResult
      if (typeof obj.question !== 'string' || typeof obj.reponse !== 'string') {
        return { type: input.prevType, question: '', reponse: '', raw: text, error: 'missing-fields' }
      }
      return { ...obj, type: obj.type || input.prevType, raw: text }
    } catch (e) {
      return { type: input.prevType, question: '', reponse: '', raw: text, error: e instanceof Error ? e.message : 'parse-fail' }
    }
  } catch (err) {
    return { type: input.prevType, question: '', reponse: '', error: err instanceof Error ? err.message : String(err) }
  } finally {
    clearTimeout(timer)
  }
}
