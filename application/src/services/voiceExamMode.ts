import { getBridgeUrl } from '../utils/runtime.ts'

export type VoiceExamFormat = 'presentation' | 'questions' | 'mixed'

/** Persona menée par l'examinateur — change le ton et l'objectif de l'oral. */
export type VoiceExamInterviewer = 'coach' | 'jury' | 'recruteur'

/** Niveau de pression / d'exigence des relances. */
export type VoiceExamIntensity = 'doux' | 'standard' | 'exigeant'

export interface VoiceExamDocument {
  name: string
  text: string
}

export interface VoiceExamConfig {
  subject: string
  durationSec: number
  format: VoiceExamFormat
  planText: string
  questionsText: string
  documents: VoiceExamDocument[]
  /** Persona de l'examinateur. Défaut 'jury'. */
  interviewer?: VoiceExamInterviewer
  /** Exigence des relances. Défaut 'standard'. */
  intensity?: VoiceExamIntensity
}

export interface VoiceExamValidation {
  ok: boolean
  errors: string[]
}

export interface VoiceExamCriterion {
  label: string
  weight: number
}

export interface VoiceExamReportInput {
  config: VoiceExamConfig
  transcript: Array<{ role: 'user' | 'assistant'; text: string }>
  startedAt: number
  endedAt: number
}

/** Note d'un critère unique produit par la correction LLM. */
export interface VoiceExamCriterionScore {
  label: string
  score: number
  max: number
  note: string
}

/** Correction structurée d'un oral — produite par le LLM (ou heuristique en fallback). */
export interface VoiceExamGrade {
  score20: number
  verdict: string
  strengths: string[]
  weaknesses: string[]
  mistakes: string[]
  advice: string[]
  criteria: VoiceExamCriterionScore[]
  /** True quand on n'a pas pu joindre le LLM et qu'on retombe sur l'heuristique. */
  fallback?: boolean
}

// ---------------------------------------------------------------------------
//  Durée : parsing + formatage
// ---------------------------------------------------------------------------

export function parseVoiceExamDuration(input: string): number {
  const raw = input.trim().toLowerCase().replace(',', '.')
  if (!raw) return 0
  const compact = raw.replace(/\s+/g, '')
  if (/^\d+(?:\.\d+)?$/.test(compact)) return Math.round(Number(compact) * 60)

  const hourMinute = compact.match(/^(\d+(?:\.\d+)?)h(\d{1,2})$/)
  if (hourMinute) return Math.round(Number(hourMinute[1]) * 3600 + Number(hourMinute[2]) * 60)

  let total = 0
  const tokenRe = /(\d+(?:\.\d+)?)(h|heure|heures|hr|hrs|min|m|minute|minutes|s|sec|secs|seconde|secondes)/g
  let match: RegExpExecArray | null
  while ((match = tokenRe.exec(compact))) {
    const value = Number(match[1])
    const unit = match[2]
    if (!Number.isFinite(value)) continue
    if (unit === 'h' || unit === 'heure' || unit === 'heures' || unit === 'hr' || unit === 'hrs') {
      total += value * 3600
    } else if (unit === 'min' || unit === 'm' || unit === 'minute' || unit === 'minutes') {
      total += value * 60
    } else {
      total += value
    }
  }

  if (total > 0) return Math.round(total)

  const clock = compact.match(/^(\d{1,2}):(\d{2})(?::(\d{2}))?$/)
  if (clock) {
    const a = Number(clock[1])
    const b = Number(clock[2])
    const c = clock[3] ? Number(clock[3]) : 0
    return clock[3] ? a * 3600 + b * 60 + c : a * 60 + b
  }
  return 0
}

export function formatVoiceExamDuration(seconds: number): string {
  const sec = Math.max(0, Math.round(seconds))
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  const s = sec % 60
  const parts: string[] = []
  if (h) parts.push(`${h}h`)
  if (m) parts.push(`${m}min`)
  if (s || parts.length === 0) parts.push(`${s}s`)
  return parts.join(' ')
}

export function formatVoiceExamClock(seconds: number): string {
  const sec = Math.max(0, Math.round(seconds))
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  const s = sec % 60
  if (h > 0) return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
}

// ---------------------------------------------------------------------------
//  Banque de questions
// ---------------------------------------------------------------------------

export function extractVoiceExamQuestionPool(text: string): string[] {
  return text
    .split(/\r?\n|[;•]/)
    .map((line) => line.replace(/^\s*(?:[-*]|\d+[.)]|question\s*\d+\s*[:.-]?)\s*/i, '').trim())
    .filter((line) => line.length >= 3)
}

export function pickVoiceExamQuestion(text: string, random = Math.random): string {
  const pool = extractVoiceExamQuestionPool(text)
  if (pool.length === 0) return text.trim()
  const index = Math.max(0, Math.min(pool.length - 1, Math.floor(random() * pool.length)))
  return pool[index]
}

// ---------------------------------------------------------------------------
//  Mode interactif vs continu
// ---------------------------------------------------------------------------

/**
 * 'questions' et 'mixed' = entretien INTERACTIF (Aurora pose une question,
 * écoute, réagit, relance, enchaîne). 'presentation' = oral CONTINU (l'élève
 * parle sans interruption pendant toute la durée, le jury reste silencieux).
 */
export function isInteractiveExam(format: VoiceExamFormat): boolean {
  return format === 'questions' || format === 'mixed'
}

/**
 * Détecte un VRAI signal de fin de présentation ("j'ai terminé", "voilà j'ai
 * fini", "merci de votre attention") pour basculer vers les questions.
 *
 * Doit IGNORER les formes futures / introductives où la conclusion fait encore
 * partie de l'exposé : "je vais terminer avec ma conclusion", "pour conclure…",
 * "en conclusion…", "je termine dans une minute". On biaise vers la précision :
 * en cas de doute on ne coupe pas (le bouton "passer aux questions" reste là).
 */
export function isPresentationEndSignal(text: string): boolean {
  // Normalise : minuscule, sans accents, apostrophes unifiées.
  const t = text
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/['’`]/g, "'")
    .trim()
  if (t.length < 2) return false

  // 1) REJET : annonce FUTURE / introduction de conclusion (pas une fin).
  if (/\b(je vais|on va|j'irai|tout de suite|bientot|presque|en train de|sur le point de|je m'apprete a)\b.{0,20}(termin|finir|fini|conclu)/.test(t)) return false
  if (/\b(pour|avant de)\s+(termin|finir|conclu)/.test(t)) return false
  if (/\b(en conclusion|pour conclure|pour terminer|pour finir|je vais conclure|je conclus|je termine|je vais finir|je finis par)\b/.test(t)) return false

  // 2) ACCEPT : complétion ACCOMPLIE / clôture explicite.
  const done = [
    /\bj'ai (bien |donc )?(fini|termine|acheve)\b/,
    /\bj'en ai (fini|termine)\b/,
    /\bc'est (fini|termine|tout|bon)\b/,
    /\bma (presentation|presentation|expose|partie) est (finie|termine|terminee|achevee)\b/,
    /\bvoila[\s,!.]*(c'est tout|j'ai (fini|termine)|pour (ma|la) (presentation|conclusion|partie)|ce sera tout|fin de (ma|la) presentation)\b/,
    /\bvoila ce sera tout\b/,
    /\bmerci (de|pour) votre attention\b/,
    /\bje vous remercie (de|pour) votre attention\b/,
    // Anglais
    /\bi'?m (done|finished)\b/,
    /\bi (have|'ve) (finished|completed|concluded)\b/,
    /\bthat's (it|all|everything)\b/,
    /\bthank you for (your attention|listening)\b/,
  ]
  return done.some((re) => re.test(t))
}

// ---------------------------------------------------------------------------
//  Validation
// ---------------------------------------------------------------------------

export function validateVoiceExamConfig(config: VoiceExamConfig): VoiceExamValidation {
  const errors: string[] = []
  const hasDocuments = config.documents.some((doc) => doc.text.trim().length > 0)
  const hasPlan = config.planText.trim().length > 0
  const hasQuestions = config.questionsText.trim().length > 0
  const hasSubject = config.subject.trim().length > 0

  if (!Number.isFinite(config.durationSec) || config.durationSec < 1) {
    errors.push('Indique une duree d examen valide avec unite, par exemple 5min, 10min ou 1h30.')
  }
  // En interactif, un sujet OU des questions OU un support suffisent : Aurora
  // sait improviser les relances. En continu, il faut au moins un sujet/plan.
  if (!hasDocuments && !hasPlan && !hasQuestions && !hasSubject) {
    errors.push('Donne au moins un sujet (ou une fiche, ou des questions) pour qu Aurora sache sur quoi t interroger.')
  }
  if (!isInteractiveExam(config.format) && !hasPlan && !hasQuestions && !hasSubject) {
    errors.push('Pour un oral continu, ecris au moins le sujet ou un plan a presenter.')
  }
  return { ok: errors.length === 0, errors }
}

// ---------------------------------------------------------------------------
//  Grille de critères par défaut
// ---------------------------------------------------------------------------

const LANGUAGE_PATTERNS: Array<[RegExp, string]> = [
  [/\b(anglais|english|lv1\s*anglais|etlv)\b/i, 'anglais'],
  [/\b(espagnol|spanish|castellano)\b/i, 'espagnol'],
  [/\b(allemand|german|deutsch)\b/i, 'allemand'],
  [/\b(italien|italian|italiano)\b/i, 'italien'],
  [/\b(portugais|portuguese)\b/i, 'portugais'],
  [/\b(russe|russian)\b/i, 'russe'],
  [/\b(arabe|arabic)\b/i, 'arabe'],
  [/\b(japonais|japanese)\b/i, 'japonais'],
  [/\b(chinois|mandarin|chinese)\b/i, 'chinois'],
  [/\b(latin)\b/i, 'latin'],
]

/** Détecte la langue cible d'un oral de langue (null si matière en français). */
export function detectVoiceExamLanguage(subject: string): string | null {
  for (const [re, label] of LANGUAGE_PATTERNS) {
    if (re.test(subject)) return label
  }
  if (/\blangue|lv2\b/i.test(subject)) return 'la langue cible'
  return null
}

/** Détecte un Grand Oral du baccalauréat (grille officielle dédiée). */
export function isGrandOral(subject: string): boolean {
  return /\bgrand[\s-]?oral\b/i.test(subject)
}

export function defaultVoiceExamCriteria(subject: string, format: VoiceExamFormat): VoiceExamCriterion[] {
  // Grille officielle Grand Oral (BAC) : 5 dimensions, prioritaire sur le reste.
  if (isGrandOral(subject)) {
    return [
      { label: 'Qualite orale : voix, debit, conviction', weight: 4 },
      { label: 'Qualite de la prise de parole en continu', weight: 4 },
      { label: 'Solidite et pertinence des connaissances', weight: 4 },
      { label: 'Construction et solidite de l argumentation', weight: 4 },
      { label: 'Qualite de l echange avec le jury (relances)', weight: 4 },
    ]
  }
  const isLanguage = detectVoiceExamLanguage(subject) !== null
  const base: VoiceExamCriterion[] = [
    { label: 'Comprehension du sujet et respect de la consigne', weight: 4 },
    { label: 'Structure claire avec introduction, progression et conclusion', weight: 4 },
    { label: 'Precision des connaissances et exemples mobilises', weight: 4 },
    { label: 'Qualite de l expression orale et fluidite', weight: 4 },
  ]
  if (isLanguage) {
    return [
      { label: 'Comprehension et reponse exacte a la consigne', weight: 4 },
      { label: 'Richesse du vocabulaire et structures grammaticales', weight: 4 },
      { label: 'Prononciation, fluidite et autonomie orale', weight: 4 },
      { label: 'Organisation du propos et connecteurs', weight: 4 },
      { label: 'Reponses aux questions ou relances', weight: 4 },
    ]
  }
  if (format === 'questions') {
    return [
      { label: 'Exactitude des reponses', weight: 5 },
      { label: 'Justification et exemples', weight: 5 },
      { label: 'Capacite a reformuler et corriger', weight: 4 },
      { label: 'Expression orale claire', weight: 3 },
      { label: 'Gestion du temps', weight: 3 },
    ]
  }
  return [
    ...base,
    { label: 'Gestion du temps et reaction aux relances', weight: 4 },
  ]
}

// ---------------------------------------------------------------------------
//  Profils examinateur / intensité
// ---------------------------------------------------------------------------

interface InterviewerProfile {
  label: string
  hint: string
  persona: string
}

export const VOICE_EXAM_INTERVIEWERS: Record<VoiceExamInterviewer, InterviewerProfile> = {
  coach: {
    label: 'Coach',
    hint: 'Bienveillant mais lucide — te met en confiance et te pousse a progresser.',
    persona:
      'Tu es un coach d oral bienveillant mais lucide. Tu mets l eleve a l aise, tu valides les bons reflexes a voix haute, mais tu pousses toujours a aller plus loin. Tu n es jamais complaisant : si c est creux, tu le fais creuser.',
  },
  jury: {
    label: 'Jury examen',
    hint: 'Neutre et exigeant, comme un vrai jury de BAC / Grand Oral.',
    persona:
      'Tu es un membre de jury d examen officiel (type Grand Oral, BAC, concours). Tu es neutre, courtois et exigeant. Tu n encourages pas, tu evalues sans complaisance, tu reformules les imprecisions et tu attends des reponses precises et structurees.',
  },
  recruteur: {
    label: 'Recruteur',
    hint: 'Mene un vrai entretien : posture, clarte, capacite a convaincre sous pression.',
    persona:
      'Tu es un recruteur experimente qui mene un vrai entretien. Tu testes la posture, la clarte du discours, la capacite a convaincre et a gerer la pression. Tu rebondis sur les contradictions, tu demandes des exemples concrets et des resultats chiffres.',
  },
}

const INTENSITY_PROFILES: Record<VoiceExamIntensity, { label: string; hint: string; rule: string }> = {
  doux: {
    label: 'Doux',
    hint: 'Relances douces, du temps, pas de piege.',
    rule: 'Relances douces, une seule a la fois. Tu laisses du temps, tu ne piege pas, tu securises avant de challenger.',
  },
  standard: {
    label: 'Standard',
    hint: 'Tu creuses les points faibles, tu demandes des exemples.',
    rule: 'Relances normales : tu creuses les points faibles, tu demandes des exemples et des justifications, tu challenges gentiment les imprecisions.',
  },
  exigeant: {
    label: 'Exigeant',
    hint: 'Pression realiste de vrai oral, chaque imprecision relevee.',
    rule: 'Relances exigeantes : tu pousses dans les retranchements, tu releves chaque imprecision, tu demandes des justifications solides et tu mets la pression realiste d un vrai oral d examen.',
  },
}

export const VOICE_EXAM_INTENSITIES = INTENSITY_PROFILES

function resolveInterviewer(config: VoiceExamConfig): InterviewerProfile {
  return VOICE_EXAM_INTERVIEWERS[config.interviewer ?? 'jury']
}

function resolveIntensity(config: VoiceExamConfig): { label: string; rule: string } {
  return INTENSITY_PROFILES[config.intensity ?? 'standard']
}

// ---------------------------------------------------------------------------
//  System prompt examinateur
// ---------------------------------------------------------------------------

export function buildVoiceExamPromptBlock(config: VoiceExamConfig): string {
  const criteria = defaultVoiceExamCriteria(config.subject, config.format)
  const interviewer = resolveInterviewer(config)
  const intensity = resolveIntensity(config)
  const interactive = isInteractiveExam(config.format)
  const targetLanguage = detectVoiceExamLanguage(config.subject)
  const docs = config.documents
    .filter((doc) => doc.text.trim())
    .map((doc) => `--- ${doc.name} ---\n${doc.text.trim().slice(0, 5000)}`)
    .join('\n\n')
  const formatLabel = {
    presentation: 'presentation orale continue (monologue, jury silencieux)',
    questions: 'entretien interactif par questions (tu poses, tu ecoutes, tu relances)',
    mixed: 'presentation puis entretien de relance interactif',
  }[config.format]

  const behaviour = interactive
    ? [
        '## TON COMPORTEMENT D EXAMINATEUR (ENTRETIEN INTERACTIF)',
        `- ${interviewer.persona}`,
        `- ${intensity.rule}`,
        '- Tu mènes un vrai entretien oral EN DIRECT. Tu parles UNIQUEMENT comme l examinateur, jamais a la place de l eleve.',
        '- UNE seule question a la fois. Ne liste JAMAIS plusieurs questions dans la meme prise de parole.',
        '- Apres chaque reponse : une mini-reaction naturelle d une phrase (accuse reception, rebondis sur ce qu il a REELLEMENT dit), PUIS soit tu relances pour creuser CETTE reponse, soit tu passes au theme suivant.',
        '- Tes relances s appuient sur le contenu exact de la derniere reponse (cite ou reformule un mot/idee de l eleve). Pas de question generique deconnectee.',
        '- Adapte la difficulte au niveau reel de l eleve : s il assure, tu montes d un cran ; s il bloque, tu reformules plus simplement sans donner la reponse.',
        '- Couvre progressivement les themes / la banque de questions sans te repeter. Garde le fil de ce qui a deja ete demande.',
        '- Tu ne fais JAMAIS le cours, tu ne donnes JAMAIS la reponse attendue, tu n evalues pas a voix haute pendant l oral. Tu interroges, c est tout.',
        '- Reste bref et parlable : 1 a 2 phrases courtes, pas de liste, pas de markdown, pas de symboles.',
        '- Gere le temps : quand il reste peu de temps, annonce "derniere question" puis conclus sobrement. Ne donne PAS la note pendant l oral (le bilan vient apres).',
      ]
    : [
        '## TON COMPORTEMENT D EXAMINATEUR (ORAL CONTINU)',
        `- ${interviewer.persona}`,
        '- L eleve fait une presentation orale continue. Tu RESTES SILENCIEUX pendant qu il parle, tu ne l interromps pas.',
        '- Tu n interviens que si on te sollicite explicitement, et seulement par une relance courte.',
        '- Ne donne pas la note avant la fin. Le bilan detaille est genere apres l oral.',
      ]

  if (targetLanguage && targetLanguage !== 'la langue cible') {
    behaviour.push(
      `- C est un oral de langue : conduis l entretien EN ${targetLanguage.toUpperCase()} (questions, relances, reactions). Ne corrige pas la langue a voix haute pendant l oral, garde ca pour le bilan.`,
    )
  } else if (targetLanguage) {
    behaviour.push(
      '- C est un oral de langue : conduis l entretien dans la langue cible de l eleve. Garde les corrections de langue pour le bilan final.',
    )
  }

  return [
    '',
    '## MODE EXAMEN ORAL ACTIF',
    `- Sujet/matiere : ${config.subject || 'non precise'}`,
    `- Format : ${formatLabel}`,
    `- Duree : ${formatVoiceExamDuration(config.durationSec)}`,
    `- Examinateur : ${interviewer.label} · intensite ${intensity.label}`,
    '- Contexte technique : cette passation tourne dans un navigateur web standard via le front Aurora/Cloudflare. Ne suppose pas de capacites locales Tauri pendant l oral.',
    '- Niveau attendu : analyse expert. Repere la qualite du raisonnement, les criteres de grille, les oublis, les contresens, le niveau de langue, la precision et la gestion du temps.',
    '- Si la grille fournie contient des criteres, utilise-les en priorite. Sinon applique la grille par defaut ci-dessous.',
    '',
    ...behaviour,
    '',
    'Grille par defaut si aucune grille explicite :',
    ...criteria.map((criterion) => `- ${criterion.label} (${criterion.weight} pts)`),
    config.planText.trim() ? `\nPlan fourni par l eleve :\n${config.planText.trim().slice(0, 2500)}` : '',
    config.questionsText.trim() ? `\nQuestions/sujet fournis (banque a couvrir) :\n${config.questionsText.trim().slice(0, 2500)}` : '',
    docs ? `\nFiches ou grilles fournies :\n${docs}` : '',
  ].filter(Boolean).join('\n')
}

/**
 * Première prise de parole d'Aurora au lancement d'un entretien interactif :
 * accueil + invitation à présenter (mixed) ou première question (questions).
 * Pure : sert à être parlée par le TTS au démarrage de l'oral.
 */
export function buildVoiceExamOpener(config: VoiceExamConfig, lang: 'fr' | 'en' = 'fr', random = Math.random): string {
  const minutes = Math.max(1, Math.round(config.durationSec / 60))
  const minutesLabel = config.durationSec < 60
    ? formatVoiceExamDuration(config.durationSec)
    : `${minutes} minute${minutes > 1 ? 's' : ''}`
  const subject = config.subject.trim()
  const pool = extractVoiceExamQuestionPool(config.questionsText)

  if (lang === 'en') {
    if (config.format === 'mixed') {
      return `Hello, make yourself comfortable. ${subject ? `Today we focus on ${subject}. ` : ''}Take about ${minutesLabel} to present your topic. I am listening. When you are done, just say "I'm finished" and I will ask you some questions.`
    }
    const first = pool.length ? pickVoiceExamQuestion(config.questionsText, random) : ''
    return first
      ? `Hello, let's begin. First question: ${first}`
      : `Hello, let's begin.${subject ? ` We will talk about ${subject}.` : ''} Introduce yourself briefly, then I will start my questions.`
  }

  if (config.format === 'mixed') {
    return `Bonjour, installe-toi. ${subject ? `Aujourd hui on travaille sur ${subject}. ` : ''}Prends environ ${minutesLabel} pour presenter ton sujet, je t ecoute. Quand tu as fini, dis simplement "j ai termine" et je te poserai mes questions.`
  }
  const first = pool.length ? pickVoiceExamQuestion(config.questionsText, random) : ''
  return first
    ? `Bonjour, on commence. Premiere question : ${first}`
    : `Bonjour, on commence.${subject ? ` On va parler de ${subject}.` : ''} Presente-toi en une phrase, puis je lance mes questions.`
}

// ---------------------------------------------------------------------------
//  Correction LLM réelle
// ---------------------------------------------------------------------------

function chatEndpoint(): string {
  const base = (() => { try { return getBridgeUrl() } catch { return '' } })()
  return base ? `${base}/proxy/ollama/api/chat` : '/api/ollama/chat'
}

/**
 * Cherche en ligne le BARÈME / la grille d'évaluation OFFICIELLE de l'oral, via
 * le bridge web search. Sert à ancrer la correction sur les vrais critères
 * (Grand Oral, oral de langue BAC…) quand l'élève n'a pas fourni de grille.
 * Ne jette jamais : renvoie '' si rien / bridge absent.
 */
export async function searchOfficialBareme(
  subject: string,
  format: VoiceExamFormat,
  options: { signal?: AbortSignal; timeoutMs?: number } = {},
): Promise<string> {
  const { signal, timeoutMs = 20_000 } = options
  const base = (() => { try { return getBridgeUrl() } catch { return '' } })()
  if (!base) return ''
  const lang = detectVoiceExamLanguage(subject)
  const query = isGrandOral(subject)
    ? 'grille evaluation officielle Grand Oral baccalaureat criteres bareme eduscol'
    : lang && lang !== 'la langue cible'
      ? `grille evaluation officielle oral ${lang} baccalaureat criteres bareme`
      : `bareme grille evaluation officielle oral ${subject || 'examen'} criteres notation`

  const ctrl = new AbortController()
  let timer: ReturnType<typeof setTimeout> | null = null
  if (timeoutMs > 0) timer = setTimeout(() => ctrl.abort(), timeoutMs)
  if (signal) {
    if (signal.aborted) ctrl.abort()
    else signal.addEventListener('abort', () => ctrl.abort(), { once: true })
  }
  try {
    const r = await fetch(`${base}/api/web/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, limit: 5 }),
      signal: ctrl.signal,
    })
    if (timer) clearTimeout(timer)
    if (!r.ok) return ''
    const data = (await r.json()) as {
      results?: string
      sources?: Array<{ title?: string; url?: string; snippet?: string }>
    }
    const fromSources = Array.isArray(data.sources)
      ? data.sources
          .slice(0, 5)
          .map((s, i) => `[${i + 1}] ${s.title || ''}${s.snippet ? ': ' + s.snippet.slice(0, 220) : ''}`)
          .join('\n')
      : ''
    return (data.results || fromSources || '').slice(0, 1800)
  } catch {
    if (timer) clearTimeout(timer)
    return ''
  }
}

function clampScore20(value: unknown): number {
  const n = typeof value === 'number' ? value : Number(value)
  if (!Number.isFinite(n)) return 0
  return Math.max(0, Math.min(20, Math.round(n * 10) / 10))
}

function asStringArray(value: unknown, max = 5): string[] {
  if (!Array.isArray(value)) return []
  return value
    .map((v) => (typeof v === 'string' ? v.trim() : ''))
    .filter(Boolean)
    .slice(0, max)
}

/**
 * Bilan heuristique (sans LLM) — utilisé en fallback. Reprend l'analyse
 * structure/exemples/longueur de l'ancien rapport.
 */
export function heuristicVoiceExamGrade(input: VoiceExamReportInput): VoiceExamGrade {
  const { config, transcript } = input
  const criteria = defaultVoiceExamCriteria(config.subject, config.format)
  const userTurns = transcript.filter((e) => e.role === 'user').map((e) => e.text.trim()).filter(Boolean)
  const assistantTurns = transcript.filter((e) => e.role === 'assistant').map((e) => e.text.trim()).filter(Boolean)
  const answerText = userTurns.join('\n\n')
  const wordCount = answerText.split(/\s+/).filter(Boolean).length
  const hasStructure = /\b(introduction|intro|premiere|premierement|deuxieme|ensuite|conclusion|pour conclure)\b/i.test(answerText)
  const hasExamples = /\b(exemple|par exemple|ainsi|cas|document|citation|preuve)\b/i.test(answerText)
  const expectedWords = Math.max(10, Math.round((config.durationSec / 60) * 35))
  const likelyTooShort = wordCount < expectedWords

  const strengths = [
    !likelyTooShort ? 'Volume de parole suffisant pour la duree.' : '',
    hasStructure ? 'Plan ou progression reperable.' : '',
    hasExamples ? 'Presence d exemples ou de justifications.' : '',
  ].filter(Boolean)
  const weaknesses = [
    likelyTooShort ? 'Reponse probablement trop courte pour la duree indiquee.' : '',
    !hasStructure ? 'Structure peu explicite : annonce mieux les parties et la conclusion.' : '',
    !hasExamples ? 'Peu d exemples ou de preuves clairement cites.' : '',
    assistantTurns.length > 4 ? 'Beaucoup de relances ont ete necessaires : anticipe davantage.' : '',
  ].filter(Boolean)

  const score = clampScore20(11 + (hasStructure ? 2 : -1) + (hasExamples ? 2 : -1) + (!likelyTooShort ? 2 : -2))
  return {
    score20: score,
    verdict: strengths[0]
      ? `Base exploitable : ${strengths[0].toLowerCase()}`
      : 'Reponse presente, base de travail a consolider.',
    strengths: strengths.length ? strengths : ['Reponse presente, base de travail exploitable.'],
    weaknesses: weaknesses.length ? weaknesses : ['Rien de bloquant detecte par l analyse de base.'],
    mistakes: [],
    advice: [
      'Prepare une ouverture en une phrase.',
      'Annonce explicitement deux ou trois axes.',
      'Ajoute un exemple precis par axe.',
      'Termine par une conclusion courte et assumee.',
    ],
    criteria: criteria.map((c) => ({ label: c.label, score: 0, max: c.weight, note: 'Non note automatiquement (mode hors-ligne).' })),
    fallback: true,
  }
}

const GRADING_SYSTEM_PROMPT = `Tu es un examinateur expert qui corrige un ORAL apres la passation.
Tu lis la transcription complete (examinateur + eleve) et tu rends un bilan FRANC, precis et actionnable.
Tu notes sur 20 selon la grille fournie. Tu n inventes rien : tu juges uniquement ce qui a ete dit.

Tu retournes UNIQUEMENT un JSON valide pur (pas de markdown, pas de \`\`\`), de la forme exacte :
{"score20": <number 0-20>, "verdict": "<1-2 phrases franches>", "strengths": ["..."], "weaknesses": ["..."], "mistakes": ["erreurs factuelles ou contresens, [] si aucun"], "advice": ["conseils actionnables"], "criteria": [{"label": "<critere>", "score": <int>, "max": <int>, "note": "<1 phrase>"}]}

Regles :
- Sois honnete : si c est faible, dis-le ; si c est bon, dis-le. Pas de flatterie reflexe, pas de langue de bois.
- "mistakes" = erreurs factuelles, contresens, oublis majeurs. Tableau vide si rien de grave.
- "advice" = 3 a 5 conseils concrets pour progresser au prochain oral.
- "criteria" reprend EXACTEMENT les libelles et le bareme (max) fournis ; "score" entre 0 et max.
- La somme des "score" de criteria doit etre coherente avec score20.
- Si l eleve a a peine parle, note bas et explique pourquoi.`

/**
 * Corrige l'oral via le LLM (note réelle + bilan structuré). Retombe sur
 * l'heuristique si le LLM est injoignable ou répond mal. Ne jette jamais.
 */
export async function gradeVoiceExam(
  model: string,
  input: VoiceExamReportInput,
  options: { signal?: AbortSignal; timeoutMs?: number; officialCriteria?: string } = {},
): Promise<VoiceExamGrade> {
  const { signal, timeoutMs = 90_000, officialCriteria } = options
  const { config, transcript } = input
  const criteria = defaultVoiceExamCriteria(config.subject, config.format)
  const userText = transcript.filter((e) => e.role === 'user').map((e) => e.text).join(' ').trim()
  // Pas assez de matiere pour une vraie correction → heuristique directe.
  if (userText.length < 5) {
    return heuristicVoiceExamGrade(input)
  }

  const transcriptText = transcript
    .map((e) => `${e.role === 'user' ? 'ELEVE' : 'EXAMINATEUR'} : ${e.text.trim()}`)
    .join('\n')
    .slice(0, 8000)

  const officialBlock = (officialCriteria || '').trim()
  const userMsg = [
    `Sujet / matiere : ${config.subject || 'non precise'}`,
    `Format : ${config.format}`,
    `Duree prevue : ${formatVoiceExamDuration(config.durationSec)}`,
    'Grille (label : bareme) :',
    ...criteria.map((c) => `- ${c.label} : ${c.weight}`),
    officialBlock
      ? `\nBAREME OFFICIEL TROUVE EN LIGNE (a utiliser en PRIORITE pour calibrer la note, sans citer les sites a voix haute) :\n${officialBlock.slice(0, 1600)}`
      : '',
    '',
    'TRANSCRIPTION DE L ORAL :',
    '<<<',
    transcriptText,
    '>>>',
    '',
    'Corrige maintenant en JSON strict.',
  ].join('\n')

  const ctrl = new AbortController()
  let timer: ReturnType<typeof setTimeout> | null = null
  if (timeoutMs > 0) timer = setTimeout(() => ctrl.abort(), timeoutMs)
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
          { role: 'system', content: GRADING_SYSTEM_PROMPT },
          { role: 'user', content: userMsg },
        ],
        stream: false,
        options: { temperature: 0.25, num_ctx: 8192, num_predict: 700 },
      }),
      signal: ctrl.signal,
    })
    const data = (await resp.json()) as { message?: { content?: string }; response?: string }
    const text = data?.message?.content ?? data?.response ?? ''
    if (timer) clearTimeout(timer)
    const parsed = parseVoiceExamGrade(text, criteria)
    return parsed ?? heuristicVoiceExamGrade(input)
  } catch {
    if (timer) clearTimeout(timer)
    return heuristicVoiceExamGrade(input)
  }
}

export function parseVoiceExamGrade(raw: string, criteria: VoiceExamCriterion[]): VoiceExamGrade | null {
  const fenced = raw.match(/```(?:json)?\s*([\s\S]*?)```/)
  const candidate = fenced ? fenced[1] : raw
  const first = candidate.indexOf('{')
  const last = candidate.lastIndexOf('}')
  if (first === -1 || last <= first) return null
  try {
    const obj = JSON.parse(candidate.slice(first, last + 1)) as Record<string, unknown>
    const rawCriteria = Array.isArray(obj.criteria) ? obj.criteria : []
    const mappedCriteria: VoiceExamCriterionScore[] = rawCriteria
      .map((c) => {
        const o = (c ?? {}) as Record<string, unknown>
        const label = typeof o.label === 'string' ? o.label.trim() : ''
        if (!label) return null
        const max = Number.isFinite(Number(o.max)) ? Math.max(1, Math.round(Number(o.max))) : 4
        const score = Math.max(0, Math.min(max, Math.round(Number(o.score) || 0)))
        const note = typeof o.note === 'string' ? o.note.trim().slice(0, 200) : ''
        return { label, score, max, note }
      })
      .filter(Boolean) as VoiceExamCriterionScore[]
    return {
      score20: clampScore20(obj.score20),
      verdict: typeof obj.verdict === 'string' ? obj.verdict.trim().slice(0, 400) : '',
      strengths: asStringArray(obj.strengths),
      weaknesses: asStringArray(obj.weaknesses),
      mistakes: asStringArray(obj.mistakes),
      advice: asStringArray(obj.advice, 6),
      criteria: mappedCriteria.length
        ? mappedCriteria
        : criteria.map((c) => ({ label: c.label, score: 0, max: c.weight, note: '' })),
    }
  } catch {
    return null
  }
}

// ---------------------------------------------------------------------------
//  Rapport
// ---------------------------------------------------------------------------

export function buildVoiceExamReport(
  input: VoiceExamReportInput,
  grade?: VoiceExamGrade,
): { markdown: string; spokenSummary: string } {
  const { config, transcript, startedAt, endedAt } = input
  const resolvedGrade = grade ?? heuristicVoiceExamGrade(input)
  const criteria = defaultVoiceExamCriteria(config.subject, config.format)
  const userTurns = transcript.filter((entry) => entry.role === 'user').map((entry) => entry.text.trim()).filter(Boolean)
  const wordCount = userTurns.join('\n\n').split(/\s+/).filter(Boolean).length
  const elapsedSec = Math.max(1, Math.round((endedAt - startedAt) / 1000))
  const score = resolvedGrade.score20

  const firstStrength = resolvedGrade.strengths[0] || 'tu as produit une base exploitable'
  const firstFix = resolvedGrade.mistakes[0] || resolvedGrade.weaknesses[0] || 'rends tes criteres de reussite plus visibles'
  const spokenSummary = [
    `Bilan : note indicative ${score} sur 20.`,
    `Point fort : ${firstStrength}.`,
    `A corriger en priorite : ${firstFix}.`,
  ].join(' ')

  const criteriaLines = resolvedGrade.criteria.length
    ? resolvedGrade.criteria.map((c) => `- ${c.label} : ${c.score}/${c.max}${c.note ? ` — ${c.note}` : ''}`)
    : criteria.map((c) => `- ${c.label} (${c.weight} pts)`)

  const markdown = [
    '# Rapport examen oral Aurora',
    '',
    `Date : ${new Date(endedAt).toLocaleString('fr-FR')}`,
    `Sujet : ${config.subject || 'non precise'}`,
    `Format : ${config.format}`,
    `Examinateur : ${resolveInterviewer(config).label} · intensite ${resolveIntensity(config).label}`,
    `Duree prevue : ${formatVoiceExamDuration(config.durationSec)}`,
    `Duree effective : ${formatVoiceExamDuration(elapsedSec)}`,
    `Volume eleve : ${wordCount} mots environ`,
    resolvedGrade.fallback ? '_(correction hors-ligne : note approximative)_' : '',
    '',
    '## Note indicative',
    `${score}/20`,
    '',
    ...(resolvedGrade.verdict ? ['## Verdict', resolvedGrade.verdict, ''] : []),
    '## Detail par critere',
    ...criteriaLines,
    '',
    '## Points forts',
    ...(resolvedGrade.strengths.length ? resolvedGrade.strengths.map((s) => `- ${s}`) : ['- Reponse presente, base de travail exploitable.']),
    '',
    '## Ce qui ne va pas encore',
    ...(resolvedGrade.weaknesses.length ? resolvedGrade.weaknesses.map((s) => `- ${s}`) : ['- Rien de bloquant detecte.']),
    '',
    ...(resolvedGrade.mistakes.length ? ['## Erreurs / contresens', ...resolvedGrade.mistakes.map((s) => `- ${s}`), ''] : []),
    '## Conseils de reprise',
    ...(resolvedGrade.advice.length ? resolvedGrade.advice.map((s) => `- ${s}`) : ['- Structure ton propos en intro, deux axes, conclusion.']),
    '',
    '## Transcription',
    ...transcript.map((entry) => `**${entry.role === 'user' ? 'Eleve' : 'Aurora'}** : ${entry.text}`),
    '',
  ].join('\n')

  return { markdown, spokenSummary }
}
