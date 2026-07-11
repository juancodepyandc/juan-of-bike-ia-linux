/**
 * iter34.A — LLM-based oral classifier (no hardcoded regex / hardcoded subject).
 *
 * Replaces iter32/33 hardcoded heuristic that triggered "oral mode" on
 *   - subject === 'langues' (always oral)
 *   - regex /\b(oral|presentation orale|etlv)\b/
 *   - regex /\b(anglais|espagnol|...)\b/ for language
 *
 * User explicit clarification (iter34) :
 *   « Le français peut être ECRIT ou ORAL. Il existe d'autres langues
 *     (russe, arabe, japonais, chinois, latin...) que je ne peux pas toutes
 *     citer. Faut que l'IA comprenne du multilangue. Si je dis 'oral en
 *     anglais 10 min, 1ère partie présentation 2ème questions', c'est mixed. »
 *
 * The classifier asks gemma3:12b to read the user prompt + a 2k-char sample
 * of the uploaded lesson and produce a JSON :
 *   {is_oral, language, format, duration_min, inverse_language, reasoning}
 *
 * Fallback (LLM down) : {is_oral:false, language:'français', format:'written',
 * duration_min:0, inverse_language:false}.
 *
 * Routing : `/proxy/ollama/api/chat` via bridge (Cloudflare-friendly with
 * SSE keepalive). Default 30s timeout — classifier is short JSON, no need
 * for the parcours-bac 240s budget.
 */

import { getBridgeUrl } from '../utils/runtime.ts'
import { LEARNING_EVAL_MODEL } from '../config/models.ts'

export type OralFormat = 'full' | 'mixed' | 'questions_only' | 'written'

export type OralClassification = {
  is_oral: boolean
  /**
   * Natural French label for the target oral language ("anglais", "espagnol",
   * "russe", "japonais", "français"…). Default 'français' when unknown.
   */
  language: string
  format: OralFormat
  /** Total exam duration in minutes (0 if written). */
  duration_min: number
  /**
   * True when the user explicitly asks to invert the dominant language of
   * the source — e.g. EN source + "donne-moi la trad française" → inverse.
   */
  inverse_language: boolean
  /** 1-sentence rationale, useful for debug + prompt injection. */
  reasoning: string
  /** True when we fell back without a real LLM call. */
  fallback?: boolean
}

export type OralClassifierInput = {
  userPrompt: string
  /** First ~2000 chars of extracted PDFs / lessonText. */
  uploadedTextSample: string
  /** Subject hint from the picker, NOT authoritative. */
  subject?: string
}

const SYSTEM_PROMPT = `Tu es un classifieur pédagogique BAC. À partir d'un
prompt utilisateur et d'un extrait de leçon, tu identifies le format
d'évaluation que l'élève prépare.

Tu retournes UNIQUEMENT un JSON valide pur (pas de markdown, pas de \`\`\`),
de la forme exacte :

{"is_oral": <bool>, "language": "<nom_fr>", "format": "<full|mixed|questions_only|written>", "duration_min": <int>, "inverse_language": <bool>, "reasoning": "<1 phrase>"}

Règles strictes pour chaque champ :

1. is_oral : TRUE seulement si le user veut préparer un ORAL.
   Indices PROBANTS : "oral", "présentation", "interrogation orale",
   "passage oral", "exposé", "passage devant le jury", "ETLV",
   "expression orale", "DALF/DELF oral", "Grand Oral".
   N'INFÈRE PAS oral juste parce que la matière est une langue. Le
   français a aussi des écrits. L'anglais a aussi des écrits.
   Si rien ne mentionne explicitement l'oral → is_oral=false.

2. language : la LANGUE PARLÉE/ÉCRITE de l'évaluation, PAS la matière.
   - "philo", "histoire", "physique", "SVT", "maths", "économie" → ce
     sont des MATIÈRES, pas des langues. Pour ces matières en France,
     la langue est "français" par défaut.
   - "anglais LV1", "espagnol LV2", "ETLV anglais" → la langue est
     respectivement "anglais", "espagnol", "anglais".
   - Inférée de la combinaison prompt + dominante du texte uploadé.
   - Multi-lingue géré : anglais, espagnol, allemand, italien, portugais,
     russe, arabe, japonais, chinois (mandarin), coréen, latin, grec,
     hébreu, langues régionales (catalan, basque, breton, occitan…).
   - IMPORTANT : tu retournes le NOM EN FRANÇAIS minuscules ("anglais",
     "russe", "japonais", "latin"…), JAMAIS un code ISO ("en", "es", "ja"),
     JAMAIS le nom d'une matière ("philosophie", "histoire", "physique").
   - Si l'utilisateur écrit "english" → tu réponds "anglais".
   - Default "français" si rien d'évident.

3. format :
   - "full"            : présentation orale continue (juste l'élève parle)
   - "mixed"           : présentation + questions de relance après
                         (ex: "1ère partie oral, 2ème question")
   - "questions_only"  : juste interrogation orale par questions
   - "written"         : pas d'oral du tout (synonyme de is_oral=false)

4. duration_min : durée TOTALE demandée par user (extrait "10 min",
   "15min", "1h", "1h30"). 0 si écrit ou non précisé.

5. inverse_language : TRUE si user demande d'INVERSER la langue cible
   (ex: "donne-moi la trad française du texte anglais" → inverse).
   Sinon false.

6. reasoning : 1 phrase courte qui justifie ta classification.

Exemples :
- prompt="oral en anglais 10 min, 1ère partie présentation 2ème questions"
  → {"is_oral":true,"language":"anglais","format":"mixed","duration_min":10,"inverse_language":false,"reasoning":"oral mixte explicite en anglais 10min"}
- prompt="je veux réviser la mitose pour le bac" + texte FR sur biologie
  → {"is_oral":false,"language":"français","format":"written","duration_min":0,"inverse_language":false,"reasoning":"révision écrite SVT en français"}
- prompt="grand oral philo 20 min" + texte FR de cours
  → {"is_oral":true,"language":"français","format":"full","duration_min":20,"inverse_language":false,"reasoning":"grand oral philo en français 20min"}
- prompt="oral russe 8 min juste questions" + texte russe
  → {"is_oral":true,"language":"russe","format":"questions_only","duration_min":8,"inverse_language":false,"reasoning":"interrogation orale russe 8min"}
- prompt="traduis-moi ce texte japonais en français" + texte JP
  → {"is_oral":false,"language":"japonais","format":"written","duration_min":0,"inverse_language":true,"reasoning":"version japonais→français écrite"}`

function chatEndpoint(): string {
  const base = (() => { try { return getBridgeUrl() } catch { return '' } })()
  return base ? `${base}/proxy/ollama/api/chat` : '/api/ollama/chat'
}

function defaultFallback(reason: string): OralClassification {
  return {
    is_oral: false,
    language: 'français',
    format: 'written',
    duration_min: 0,
    inverse_language: false,
    reasoning: reason,
    fallback: true,
  }
}

/**
 * Normalize the language label to a canonical French name. The LLM
 * sometimes returns ISO codes ("en", "es", "ja") despite the prompt asking
 * for French labels — we tolerate both and map back to FR. We DON'T
 * hardcode the list of allowed languages — anything not in the map flows
 * through as-is (the user clarified : multi-langue géré, on ne peut pas
 * tout citer).
 */
function clampLang(s: unknown): string {
  if (typeof s !== 'string') return 'français'
  const raw = s.trim().toLowerCase()
  if (!raw) return 'français'
  // ISO 2-letter / 3-letter common codes → FR canonical.
  const isoMap: Record<string, string> = {
    en: 'anglais', eng: 'anglais', english: 'anglais',
    es: 'espagnol', spa: 'espagnol', spanish: 'espagnol',
    de: 'allemand', deu: 'allemand', german: 'allemand', deutsch: 'allemand',
    it: 'italien', ita: 'italien', italian: 'italien', italiano: 'italien',
    pt: 'portugais', por: 'portugais', portuguese: 'portugais',
    ru: 'russe', rus: 'russe', russian: 'russe',
    ja: 'japonais', jpn: 'japonais', japanese: 'japonais',
    zh: 'chinois', chi: 'chinois', mandarin: 'chinois', chinese: 'chinois',
    ar: 'arabe', ara: 'arabe', arabic: 'arabe',
    ko: 'coréen', kor: 'coréen', korean: 'coréen',
    la: 'latin', lat: 'latin',
    el: 'grec', ell: 'grec', greek: 'grec',
    he: 'hébreu', heb: 'hébreu', hebrew: 'hébreu',
    fr: 'français', fra: 'français', french: 'français', francais: 'français', fle: 'français',
    nl: 'néerlandais', tr: 'turc', pl: 'polonais', sv: 'suédois',
    no: 'norvégien', da: 'danois', fi: 'finnois', cs: 'tchèque',
    hi: 'hindi', th: 'thaï', vi: 'vietnamien', sw: 'swahili',
  }
  if (isoMap[raw]) return isoMap[raw]
  // Defensive : si le LLM a confondu langue avec matière, on rabaisse à
  // "français" (matière française = oral en français par défaut). Liste
  // courte des matières BAC les plus communes — pas de hardcode lang ici,
  // c'est juste une garde anti-confusion.
  const subjectFalsePositives = new Set([
    'philosophie', 'philo', 'histoire', 'géographie', 'geographie', 'histoire-géo',
    'physique', 'chimie', 'svt', 'biologie', 'mathématiques', 'mathematiques', 'maths',
    'économie', 'economie', 'ses', 'informatique', 'nsi', 'ses-éco',
    'lettres', 'art', 'musique', 'théâtre', 'theatre', 'cinéma', 'cinema',
  ])
  if (subjectFalsePositives.has(raw)) return 'français'
  // Otherwise, sanitize and pass through (covers langues régionales,
  // langues exotiques, n'importe quoi que le LLM nomme en français).
  return raw.replace(/[^a-zà-öø-ÿœæ\s\-]/gi, '').slice(0, 30) || 'français'
}

function clampFormat(s: unknown): OralFormat {
  const v = typeof s === 'string' ? s.trim().toLowerCase() : ''
  if (v === 'full' || v === 'mixed' || v === 'questions_only' || v === 'written') return v
  return 'written'
}

function parseLLMJson(raw: string): OralClassification | null {
  // Strip code fences if present.
  const fenced = raw.match(/```(?:json)?\s*([\s\S]*?)```/)
  const candidate = fenced ? fenced[1] : raw
  const first = candidate.indexOf('{')
  const last = candidate.lastIndexOf('}')
  if (first === -1 || last <= first) return null
  try {
    const obj = JSON.parse(candidate.slice(first, last + 1)) as Record<string, unknown>
    const isOral = obj.is_oral === true
    const language = clampLang(obj.language)
    const format = clampFormat(obj.format)
    const dur = typeof obj.duration_min === 'number'
      ? Math.max(0, Math.min(180, Math.round(obj.duration_min)))
      : 0
    const inverse = obj.inverse_language === true
    const reasoning = typeof obj.reasoning === 'string'
      ? obj.reasoning.slice(0, 300)
      : ''
    // Coherence patches : if format !== 'written' but is_oral=false, trust is_oral.
    // If is_oral=true but format='written', upgrade to 'full'.
    let finalFormat = format
    let finalIsOral = isOral
    if (finalIsOral && finalFormat === 'written') finalFormat = 'full'
    if (!finalIsOral && finalFormat !== 'written') finalIsOral = true
    return {
      is_oral: finalIsOral,
      language,
      format: finalFormat,
      duration_min: dur,
      inverse_language: inverse,
      reasoning,
    }
  } catch {
    return null
  }
}

/**
 * Run the LLM classifier. Returns a classification regardless of failure
 * (fallback to "written" / "français" if Ollama down or parse fails).
 *
 * Default model : gemma3:12b (loaded with MAX_LOADED=1, fast cold-start).
 * Default timeout : 30s.
 */
export async function classifyOralMode(
  input: OralClassifierInput,
  options: { signal?: AbortSignal; timeoutMs?: number; model?: string } = {},
): Promise<OralClassification> {
  const { signal, timeoutMs = 30_000, model = LEARNING_EVAL_MODEL } = options
  const userPrompt = (input.userPrompt || '').trim()
  const sample = (input.uploadedTextSample || '').slice(0, 2000)
  const subject = (input.subject || '').trim()

  // Quick-path : nothing at all to classify.
  if (!userPrompt && !sample) {
    return defaultFallback('aucun prompt ni leçon — fallback écrit')
  }

  const userMsg = [
    subject ? `Matière indicative (NON autoritative) : ${subject}` : '',
    `Prompt utilisateur : ${userPrompt || '(vide)'}`,
    sample
      ? `Extrait leçon (premiers 2000 chars) :\n---\n${sample}\n---`
      : 'Aucun support uploadé.',
    'Classifie maintenant en JSON strict.',
  ].filter(Boolean).join('\n\n')

  const ctrl = new AbortController()
  let timer: ReturnType<typeof setTimeout> | null = null
  if (timeoutMs > 0) {
    timer = setTimeout(() => ctrl.abort(), timeoutMs)
  }
  if (signal) {
    if (signal.aborted) ctrl.abort()
    else signal.addEventListener('abort', () => ctrl.abort(), { once: true })
  }

  try {
    const resp = await fetch(chatEndpoint(), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model,
        messages: [
          { role: 'system', content: SYSTEM_PROMPT },
          { role: 'user', content: userMsg },
        ],
        stream: false,
        options: { temperature: 0.2, num_ctx: 4096, num_predict: 300 },
      }),
      signal: ctrl.signal,
    })
    const data = await resp.json() as { message?: { content?: string }; response?: string }
    const text = data?.message?.content ?? data?.response ?? ''
    if (timer) clearTimeout(timer)
    const parsed = parseLLMJson(text)
    if (parsed) return parsed
    return defaultFallback(`LLM JSON parse fail (raw len=${text.length})`)
  } catch (e) {
    if (timer) clearTimeout(timer)
    const msg = e instanceof Error ? e.message : String(e)
    return defaultFallback(`LLM injoignable (${msg.slice(0, 80)})`)
  }
}

/**
 * Pure helper to format the classification as a system-prompt prefix block.
 * Used by useAcademyViewLogic.buildSystemPrompt() to inject the classifier
 * verdict into the parcours-bac generation prompt (replaces hardcoded oralBlock).
 */
export function classificationToPromptBlock(cls: OralClassification): string {
  if (!cls.is_oral) {
    return `\n\n=== ANALYSE PRÉALABLE ===\nFormat évaluation : écrit\nLangue : ${cls.language}\nMode : ÉCRIT — comportement standard.\n=== FIN ANALYSE ===`
  }
  const langUp = cls.language.toUpperCase()
  const mixedHint = cls.format === 'mixed'
    ? `\n- AJOUTE en racine du JSON un array "questions_relance" (5-8 questions de relance que le jury poserait après la présentation, en ${cls.language}). Chaque entrée = chaîne ${cls.language}.`
    : ''
  return `\n\n=== ANALYSE PRÉALABLE (auto-classifier LLM) ===
- Format évaluation : ${cls.format}
- Langue cible : ${cls.language}
- Durée totale : ${cls.duration_min} min
- is_oral : true
- inverse_language : ${cls.inverse_language}
- Justification : ${cls.reasoning}

MODE ORAL ACTIVÉ (langue cible : ${cls.language}). Adapte TOUT le parcours :

- Synthèse et fiches : VOCABULARY thématique + PHRASES-TYPES prononçables
  + STRUCTURES grammaticales + CONNECTEURS oraux, EN ${langUp} avec
  traduction française entre parenthèses. 5-8 phrases-types par fiche,
  exemples concrets prêts à dire.

- "fiches" : "developpement_court" en ${langUp} (100-180 mots) + IPA
  optionnelle dans "schema_ascii_ou_data" pour mots difficiles.

- "exos_apprentissage" :
  * flashcards vocab (front=mot ${langUp}, back=trad FR + exemple en contexte)
  * QCM grammaire / structures (4 choix, 1+ bonnes réponses)
  * mini-exos type "raconte en ${langUp} ce que tu sais sur X" — pour
    ces mini-exos AJOUTE le champ "speak": true (l'UI rendra un bouton
    micro pour répondre à voix haute au lieu d'une textarea écrite).

- "controle" devient la PASSATION ORALE :
  * "duration_min" = ${cls.duration_min || 10}
  * "questions" = 3 à 5 questions de RELANCE OUVERTES en ${langUp},
    chacune vaut 1 point dans la grille.
  * "developpement.consigne" = sujet de PRÉSENTATION ORALE en ${langUp}
    à dire à voix haute pendant ${cls.duration_min || 10} minutes.
  * "developpement.criteres_attendus" = grille notation : compréhension,
    structure intro/parties/conclusion, vocabulary, pronunciation/fluidité,
    réponse aux relances.

- AJOUTE en racine du JSON :
  "is_oral": true, "language": "${cls.language}", "oral_format": "${cls.format}", "duration_min": ${cls.duration_min || 10}${mixedHint}

Tu écris le contenu pédagogique en ${langUp} quand c'est attendu (vocab,
phrases-types, sujet de présentation, questions de relance), tout le reste
(consignes méta, fiches FR de soutien) en français.
=== FIN ANALYSE ===`
}
