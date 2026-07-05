// ---------------------------------------------------------------------------
// Learning Research — multi-source retrieval for quiz / courses / paths / fiches
// Ensures the Academie module grounds its outputs on verifiable snippets
// (Wikipedia FR/EN, DuckDuckGo fallback) to reduce hallucinations.
// ---------------------------------------------------------------------------

import { isTauriRuntime, getBridgeUrl } from '../utils/runtime.ts'

export type LearningSource = {
  origin: 'wikipedia-fr' | 'wikipedia-en' | 'duckduckgo' | 'llm-synthesis' | 'exam-bank'
  title: string
  url?: string
  extract: string
  /** 'concept' = definition/theorie · 'exam' = annales / attendus / exercices types · 'general' = synthese */
  kind?: 'concept' | 'exam' | 'general'
}

export type LearningDownloadedResource = {
  url: string
  path: string
  filename: string
  bytes?: number
  contentType?: string
  downloadUrl?: string
}

export type AcademicLevel =
  | 'primaire'
  | 'college'
  | 'brevet'
  | 'seconde'
  | 'premiere'
  | 'terminale'
  | 'bac'
  | 'prepa'
  | 'licence'
  | 'master'
  | 'doctorat'
  | 'concours'
  | 'certification'
  | 'pro'
  | 'general'

export type AcademicIntent = {
  level: AcademicLevel
  isExamFocus: boolean
  examKeywords: string[]
  /** Indicateur d intensite attendue (base / approfondi / expert) pour calibrer le prompt. */
  depth: 'base' | 'approfondi' | 'expert'
}

export type LearningResearchResult = {
  sources: LearningSource[]
  contextBlock: string
  hasExternalSources: boolean
  academicIntent: AcademicIntent
  examContextBlock: string
  downloadableResources: LearningDownloadedResource[]
}

// ---------------------------------------------------------------------------
// Detection du niveau academique et de l intention "examens"
// ---------------------------------------------------------------------------

const LEVEL_PATTERNS: Array<{ level: AcademicLevel; pattern: RegExp; depth: AcademicIntent['depth'] }> = [
  { level: 'doctorat', pattern: /\b(doctorat|phd|these|these universitaire|agregation)\b/i, depth: 'expert' },
  { level: 'master', pattern: /\b(master|m1|m2|maitrise)\b/i, depth: 'expert' },
  { level: 'prepa', pattern: /\b(prepa|classe\s+prepa|mp\b|mpsi|mp2i|pcsi|pc\b|psi|mp|bl\b|ecg\b|ecs\b|ece\b|ens\b)\b/i, depth: 'expert' },
  { level: 'licence', pattern: /\b(licence|l1|l2|l3|bachelor|bac\s*\+\s*3|dut|but|bts)\b/i, depth: 'approfondi' },
  { level: 'concours', pattern: /\b(concours|capes|crpe|capeps|agreg|caplp|tnq|ecricome|polytechnique|mines|centrale|iep|sciences\s*po|oral)\b/i, depth: 'expert' },
  { level: 'certification', pattern: /\b(toeic|toefl|ielts|delf|dalf|cambridge|pix|voltaire|google|aws|azure|cisco|comptia|ocp|oca|ccna|pmp|itil|prince2)\b/i, depth: 'approfondi' },
  { level: 'terminale', pattern: /\b(terminale|tle|bac\s*(?:s|es|l|sti|stmg|st2s|stl|std2a|sti2d)?)\b/i, depth: 'approfondi' },
  { level: 'premiere', pattern: /\b(premi[eè]re|1[èe]re)\b/i, depth: 'approfondi' },
  { level: 'seconde', pattern: /\b(seconde|2nde)\b/i, depth: 'base' },
  { level: 'bac', pattern: /\b(baccalaureat|bac|epreuve\s+du\s+bac)\b/i, depth: 'approfondi' },
  { level: 'brevet', pattern: /\b(brevet|dnb|3eme|troisi[eè]me)\b/i, depth: 'base' },
  { level: 'college', pattern: /\b(coll[eè]ge|6eme|5eme|4eme|3eme|sixi[eè]me|cinqui[eè]me|quatri[eè]me)\b/i, depth: 'base' },
  { level: 'primaire', pattern: /\b(primaire|cp|ce1|ce2|cm1|cm2|ecole\s+elementaire)\b/i, depth: 'base' },
  { level: 'pro', pattern: /\b(pro\b|cap\b|bep\b|entreprise|formation\s+pro|recyclage)\b/i, depth: 'base' },
]

const EXAM_INTENT_PATTERNS = /\b(examen|exam|preparer|preparation|reviser|revisions?|exercices?|exercice|entrainer|entrainement|annale|annales|corrige|sujet\s+type|epreuve|epreuves|bareme|attendus?|competences?|notions?|programme\s+officiel|passer\s+(le|un)\s+(bac|brevet|concours)|passer\s+le\s+permis|prepa\s+(du|au|aux))\b/i

const DEPTH_BOOST: RegExp[] = [
  /\bapprofondi\b/i, /\bavance\b/i, /\bexpert\b/i, /\bd[eé]taill[eé]\b/i,
  /\bpour\s+comprendre\b/i, /\bniveau\s+(expert|avance|superieur)\b/i,
]

/** Normalise le texte: minuscules + suppression des accents pour matcher les regex unitaires. */
function normalizeText(input: string): string {
  return input
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
}

export function detectAcademicIntent(topic: string, extras?: string): AcademicIntent {
  const corpus = normalizeText(`${topic} ${extras ?? ''}`)
  const isExamFocus = EXAM_INTENT_PATTERNS.test(corpus)

  let level: AcademicLevel = 'general'
  let depth: AcademicIntent['depth'] = 'base'
  for (const { level: lvl, pattern, depth: d } of LEVEL_PATTERNS) {
    if (pattern.test(corpus)) {
      level = lvl
      depth = d
      break
    }
  }

  if (depth !== 'expert' && DEPTH_BOOST.some((p) => p.test(corpus))) {
    depth = depth === 'base' ? 'approfondi' : 'expert'
  }

  const examKeywords: string[] = []
  if (isExamFocus) {
    if (/\bannale/i.test(corpus)) examKeywords.push('annales')
    if (/\bepreuve/i.test(corpus)) examKeywords.push('epreuve type')
    if (/\bbareme/i.test(corpus)) examKeywords.push('bareme')
    if (/\battendu/i.test(corpus)) examKeywords.push('attendus')
    if (/\bexercice/i.test(corpus)) examKeywords.push('exercices corriges')
    if (/\boral/i.test(corpus)) examKeywords.push('oral')
  }

  return { level, isExamFocus, examKeywords, depth }
}

function buildLevelQueryHint(intent: AcademicIntent): string {
  switch (intent.level) {
    case 'primaire': return 'primaire cycle 3 CM1 CM2'
    case 'college': return 'college programme cycle 4'
    case 'brevet': return 'brevet DNB troisieme'
    case 'seconde': return 'seconde lycee programme officiel'
    case 'premiere': return 'premiere lycee programme officiel'
    case 'terminale':
    case 'bac':
      return 'terminale baccalaureat epreuve ecrite corrige'
    case 'prepa': return 'classes preparatoires programme officiel'
    case 'licence': return 'licence universite programme'
    case 'master': return 'master universite programme'
    case 'doctorat': return 'these doctorat recherche'
    case 'concours': return 'concours annales corriges'
    case 'certification': return 'certification examen officiel'
    default: return ''
  }
}

const CACHE = new Map<string, LearningResearchResult>()
const CACHE_MAX = 32

function cacheKey(topic: string, extras?: string) {
  return `${topic.trim().toLowerCase()}::${(extras ?? '').trim().toLowerCase()}`
}

function stripHtml(text: string): string {
  return text
    .replace(/<[^>]+>/g, ' ')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&#x27;/g, "'")
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/\s+/g, ' ')
    .trim()
}

function shorten(text: string, limit = 520): string {
  const normalized = text.replace(/\s+/g, ' ').trim()
  if (normalized.length <= limit) return normalized
  return `${normalized.slice(0, limit - 1).trim()}…`
}

async function wikiSearch(query: string, wiki: 'fr' | 'en') {
  try {
    const url = `https://${wiki}.wikipedia.org/w/api.php?action=query&list=search&format=json&origin=*&utf8=1&srlimit=3&srprop=snippet&srsearch=${encodeURIComponent(query)}`
    const response = await fetch(url, { signal: AbortSignal.timeout(4000) })
    if (!response.ok) return []
    const text = await response.text()
    if (!text || text.trimStart().startsWith('<')) return []
    const payload = JSON.parse(text) as {
      query?: { search?: Array<{ title: string; snippet: string }> }
    }
    return payload.query?.search ?? []
  } catch {
    return []
  }
}

async function wikiExtract(title: string, wiki: 'fr' | 'en') {
  try {
    const url = `https://${wiki}.wikipedia.org/w/api.php?action=query&prop=extracts&format=json&origin=*&redirects=1&exintro=1&explaintext=1&titles=${encodeURIComponent(title)}`
    const response = await fetch(url, { signal: AbortSignal.timeout(4000) })
    if (!response.ok) return ''
    const text = await response.text()
    if (!text || text.trimStart().startsWith('<')) return ''
    const payload = JSON.parse(text) as {
      query?: { pages?: Record<string, { extract?: string }> }
    }
    const pages = Object.values(payload.query?.pages ?? {})
    return pages.find((page) => page.extract?.trim())?.extract?.trim() ?? ''
  } catch {
    return ''
  }
}

async function duckSnippets(query: string): Promise<string[]> {
  const results = await webSearchResults(query)
  if (results.length > 0) {
    return results
      .map((r) => [r.title, r.snippet, r.url ? `(${r.url})` : ''].filter(Boolean).join(': '))
      .filter((line) => line.length > 40)
      .slice(0, 5)
  }
  return duckSnippetsFallback(query)
}

type WebSearchResult = { title: string; url?: string; snippet?: string }

async function webSearchResults(query: string): Promise<WebSearchResult[]> {
  try {
    if (isTauriRuntime()) {
      return []
    }

    // BUGFIX: getBridgeUrl() returns '' in cloud/tunnel — which is valid
    // (relative path via Vite proxy). The old `if (bridge)` guard skipped
    // the bridge entirely in that mode. Always try the bridge path first.
    const bridge = getBridgeUrl()
    try {
      const response = await fetch(`${bridge}/api/web/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, limit: 5 }),
        signal: AbortSignal.timeout(8000),
      })
      if (response.ok) {
        const raw = await response.text()
        if (raw && !raw.trimStart().startsWith('<')) {
          const parsed = JSON.parse(raw) as { results?: string; resultsList?: WebSearchResult[] }
          if (Array.isArray(parsed.resultsList) && parsed.resultsList.length > 0) {
            return parsed.resultsList
              .filter((r) => r && typeof r.title === 'string')
              .map((r) => ({
                title: shorten(r.title || r.url || 'Source', 120),
                url: typeof r.url === 'string' ? r.url : undefined,
                snippet: typeof r.snippet === 'string' ? shorten(r.snippet, 420) : undefined,
              }))
          }
          if (parsed.results) {
            return parsed.results.split('\n')
              .map((line) => line.trim())
              .filter((line) => line.length > 40)
              .map((line) => ({ title: shorten(line, 120), snippet: shorten(line, 420) }))
          }
        }
      }
    } catch {
      // Bridge path failed — fall through to direct DuckDuckGo fetch below.
    }

    return []
  } catch {
    return []
  }
}

async function duckSnippetsFallback(query: string): Promise<string[]> {
  try {
    const response = await fetch(`https://html.duckduckgo.com/html/?q=${encodeURIComponent(query)}`, {
      headers: { 'User-Agent': 'Mozilla/5.0 (compatible; AuroraIA/2.0)' },
      signal: AbortSignal.timeout(8000),
    })
    if (!response.ok) return []
    const html = await response.text()
    const snippetRegex = /class="result__snippet"[^>]*>([\s\S]*?)<\/a>/gi
    const snippets: string[] = []
    let match: RegExpExecArray | null
    while ((match = snippetRegex.exec(html)) !== null && snippets.length < 5) {
      const text = stripHtml(match[1])
      if (text.length > 40) snippets.push(text)
    }
    return snippets
  } catch {
    return []
  }
}

function dedupeSources(sources: LearningSource[]): LearningSource[] {
  const seen = new Set<string>()
  const out: LearningSource[] = []
  for (const source of sources) {
    const key = `${source.origin}|${source.title.toLowerCase()}`
    if (seen.has(key)) continue
    seen.add(key)
    out.push(source)
  }
  return out
}

function looksDownloadableAcademicUrl(url: string): boolean {
  return /\.(pdf|docx?|odt|rtf|xlsx?|pptx?|zip)(?:[?#].*)?$/i.test(url)
    || /(?:annale|corrige|sujet|fiche|cours|download|telecharg|télécharg|resource|document)/i.test(url)
}

async function downloadAcademicResources(results: WebSearchResult[], topic: string): Promise<LearningDownloadedResource[]> {
  if (isTauriRuntime()) return []
  const bridge = getBridgeUrl()
  const candidates = results
    .filter((r) => r.url && looksDownloadableAcademicUrl(r.url))
    .slice(0, 4)
  const downloaded: LearningDownloadedResource[] = []
  for (const candidate of candidates) {
    try {
      const response = await fetch(`${bridge}/api/web/download`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url: candidate.url,
          category: 'academic',
          filename: candidate.title,
          maxBytes: 80 * 1024 * 1024,
        }),
        signal: AbortSignal.timeout(35_000),
      })
      if (!response.ok) continue
      const data = await response.json() as LearningDownloadedResource & { ok?: boolean }
      if (data.ok && data.path && data.filename && data.url) {
        downloaded.push({
          url: data.url,
          path: data.path,
          filename: data.filename,
          bytes: data.bytes,
          contentType: data.contentType,
          downloadUrl: data.downloadUrl,
        })
      }
    } catch {
      // Best effort: source snippets remain usable even if a host blocks file download.
    }
  }
  return downloaded.map((r) => ({ ...r, filename: r.filename || topic }))
}

/**
 * Multi-source research pass aimed at the Academie module. Always best-effort:
 * if no external source is reachable (e.g. offline Tauri), callers can still
 * rely on the LLM's native knowledge.
 *
 * Quand un niveau academique et/ou une intention "examen" sont detectes,
 * la recherche est enrichie de requetes ciblees (annales, attendus, exercices
 * corriges, programme officiel) pour ancrer la generation sur ce que l epreuve
 * demande vraiment.
 */
export async function researchLearningTopic(topic: string, extras?: string): Promise<LearningResearchResult> {
  const clean = topic.trim()
  if (!clean) {
    return {
      sources: [], contextBlock: '', hasExternalSources: false,
      academicIntent: { level: 'general', isExamFocus: false, examKeywords: [], depth: 'base' },
      examContextBlock: '',
      downloadableResources: [],
    }
  }

  const academicIntent = detectAcademicIntent(clean, extras)
  const key = cacheKey(clean, `${extras ?? ''}|${academicIntent.level}|${academicIntent.isExamFocus ? 'exam' : 'std'}`)
  const cached = CACHE.get(key)
  if (cached) return cached

  const levelHint = buildLevelQueryHint(academicIntent)
  const conceptQueries = Array.from(
    new Set(
      [clean, extras ? `${clean} ${extras}` : '', `${clean} explication`, levelHint ? `${clean} ${levelHint}` : '']
        .map((q) => q.trim())
        .filter(Boolean),
    ),
  ).slice(0, 3)

  const examQueries = academicIntent.isExamFocus
    ? Array.from(
        new Set(
          [
            `${clean} annales corrigees ${levelHint}`,
            `${clean} exercices types corriges ${levelHint}`,
            `${clean} attendus epreuve ${levelHint}`,
            `${clean} notions cles programme ${levelHint}`,
            `${clean} erreurs a eviter ${levelHint}`,
          ].map((q) => q.replace(/\s+/g, ' ').trim()).filter(Boolean),
        ),
      ).slice(0, 4)
    : []

  const conceptSources: LearningSource[] = []

  for (const query of conceptQueries) {
    for (const wiki of ['fr', 'en'] as const) {
      const results = await wikiSearch(query, wiki)
      for (const result of results.slice(0, 2)) {
        const extract = await wikiExtract(result.title, wiki)
        if (!extract) continue
        conceptSources.push({
          origin: wiki === 'fr' ? 'wikipedia-fr' : 'wikipedia-en',
          title: result.title,
          url: `https://${wiki}.wikipedia.org/wiki/${encodeURIComponent(result.title.replace(/\s+/g, '_'))}`,
          extract: shorten(extract, 560),
          kind: 'concept',
        })
        if (conceptSources.length >= 4) break
      }
      if (conceptSources.length >= 4) break
    }
    if (conceptSources.length >= 4) break
  }

  if (conceptSources.length < 2) {
    const duck = await duckSnippets(clean)
    for (const snippet of duck.slice(0, 3)) {
      conceptSources.push({
        origin: 'duckduckgo',
        title: shorten(snippet, 70),
        extract: shorten(snippet, 420),
        kind: 'concept',
      })
    }
  }

  const examSources: LearningSource[] = []
  const examWebResults: WebSearchResult[] = []
  if (academicIntent.isExamFocus) {
    for (const query of examQueries) {
      const webResults = await webSearchResults(query)
      examWebResults.push(...webResults)
      const snippets = webResults.length > 0
        ? webResults.map((r) => [r.title, r.snippet, r.url ? `(${r.url})` : ''].filter(Boolean).join(': '))
        : await duckSnippetsFallback(query)
      for (const snippet of snippets.slice(0, 2)) {
        examSources.push({
          origin: 'exam-bank',
          title: shorten(query, 70),
          extract: shorten(snippet, 420),
          kind: 'exam',
        })
        if (examSources.length >= 6) break
      }
      if (examSources.length >= 6) break
    }
  }

  const merged = dedupeSources([...conceptSources, ...examSources])
  const downloadableResources = academicIntent.isExamFocus
    ? await downloadAcademicResources(examWebResults, clean)
    : []
  const contextBlock = buildContextBlock(merged.filter((s) => s.kind !== 'exam'))
  const examContextBlock = [
    examSources.length > 0 ? buildExamContextBlock(examSources, academicIntent) : '',
    downloadableResources.length > 0 ? buildDownloadedResourcesBlock(downloadableResources) : '',
  ].filter(Boolean).join('\n\n')

  const result: LearningResearchResult = {
    sources: merged,
    contextBlock,
    hasExternalSources: merged.length > 0,
    academicIntent,
    examContextBlock,
    downloadableResources,
  }

  if (CACHE.size >= CACHE_MAX) {
    const firstKey = CACHE.keys().next().value
    if (firstKey) CACHE.delete(firstKey)
  }
  CACHE.set(key, result)

  return result
}

function buildExamContextBlock(sources: LearningSource[], intent: AcademicIntent): string {
  if (sources.length === 0) return ''
  const header = [
    'ATTENDUS DE L EPREUVE — indices collectes en ligne (a croiser avec ta connaissance du programme):',
    `Niveau detecte: ${intent.level.toUpperCase()} · profondeur attendue: ${intent.depth}.`,
    intent.examKeywords.length > 0 ? `Mots-cles releves: ${intent.examKeywords.join(', ')}.` : '',
  ].filter(Boolean)
  const body = sources.map((source, index) => `- [E${index + 1}] ${source.title} — ${source.extract}`)
  return [...header, '', ...body].join('\n')
}

function buildDownloadedResourcesBlock(resources: LearningDownloadedResource[]): string {
  if (resources.length === 0) return ''
  const lines = ['RESSOURCES TELECHARGEES POUR REPRODUIRE LE STYLE / SUPPORT:']
  for (const [index, resource] of resources.entries()) {
    const size = typeof resource.bytes === 'number' ? ` (${Math.round(resource.bytes / 1024)} Ko)` : ''
    lines.push(`- [D${index + 1}] ${resource.filename}${size}`)
    lines.push(`  Source: ${resource.url}`)
    lines.push(`  Fichier local: ${resource.path}`)
  }
  lines.push('Utilise ces fichiers comme reference de structure: niveau, formulation, format des questions, corriges et baremes.')
  return lines.join('\n')
}

export function buildAcademicLevelInstructions(intent: AcademicIntent): string {
  const base: Record<AcademicLevel, string> = {
    primaire: 'Explique en phrases courtes, mots simples, exemples concrets du quotidien. Vocabulaire d un enfant de 9-11 ans.',
    college: 'Niveau college cycle 4 (11-15 ans). Va jusqu a la classe de 3eme (brevet). Vocabulaire clair, formules simples.',
    brevet: 'Aligne-toi sur le Brevet (DNB): competences attendues, notions clairement balisees, exercices types courts.',
    seconde: 'Programme de Seconde generale. Introduit les notions sans encore entrer dans le niveau bac.',
    premiere: 'Programme de Premiere. Inclus les notions qui seront evaluees dans les epreuves anticipees du bac.',
    terminale: 'Terminale generale, preparation directe au baccalaureat: exigences d argumentation, calculs rigoureux, exemples valorises par les correcteurs.',
    bac: 'Preparation au Baccalaureat: barème, structure d epreuve, attendus des correcteurs, pieges recurrents.',
    prepa: 'Classes preparatoires (MP/MPSI/PC/PCSI/PSI/BL/ECG/ECS/ECE/B-L). Densite maximale, rigueur, demonstrations completes, astuces.',
    licence: 'Niveau Licence universitaire: rigueur scientifique, vocabulaire specialise, demonstrations, references aux cours magistraux.',
    master: 'Niveau Master: pointe theorique, articles de recherche cites quand pertinent, formalismes.',
    doctorat: 'Niveau doctorat/recherche: precision, sources academiques, etat de l art, limites epistemologiques.',
    concours: 'Concours (CAPES, agregation, grandes ecoles, etc.): attendus specifiques, jury, oraux, ecrit. Montre la methode.',
    certification: 'Certification professionnelle officielle: referentiel officiel, objectifs d apprentissage numerotes, annales types.',
    pro: 'Public professionnel: applications terrain, cas d usage, checklist operationnelle.',
    general: 'Public grand public curieux: style clair, exemples varies, eviter le jargon inutile.',
  }
  const extras: string[] = []
  if (intent.isExamFocus) {
    extras.push(
      'FOCUS EXAMENS: chaque section doit aider a REUSSIR une epreuve — notions cibles, erreurs a eviter, exemples types, formulation attendue par les correcteurs.',
    )
  }
  if (intent.depth === 'expert') {
    extras.push('PROFONDEUR EXPERT: n hesite pas a entrer dans les details techniques, demonstrations, exceptions, cas limites.')
  } else if (intent.depth === 'approfondi') {
    extras.push('PROFONDEUR APPROFONDIE: solide sans etre lourd. Des exemples, des justifications, des nuances.')
  }
  return [base[intent.level] ?? base.general, ...extras].join(' ')
}

export function buildContextBlock(sources: LearningSource[]): string {
  if (sources.length === 0) return ''
  const lines = [
    'Sources factuelles verifiees (a privilegier pour toute affirmation):',
  ]
  sources.forEach((source, index) => {
    const originLabel =
      source.origin === 'wikipedia-fr'
        ? 'Wikipedia FR'
        : source.origin === 'wikipedia-en'
          ? 'Wikipedia EN'
          : source.origin === 'duckduckgo'
            ? 'DuckDuckGo'
            : 'Synthese LLM'
    lines.push(`- [S${index + 1}] ${originLabel} — ${source.title}`)
    if (source.url) lines.push(`  URL: ${source.url}`)
    lines.push(`  Extrait: ${source.extract}`)
  })
  lines.push('Regle: si aucune source ne couvre un point, preciser "information generale" ou s abstenir.')
  return lines.join('\n')
}

export function summarizeSourcesForUI(sources: LearningSource[]): string {
  if (sources.length === 0) return 'Aucune source externe verifiee.'
  const parts = sources.slice(0, 3).map((source) => {
    const originLabel =
      source.origin === 'wikipedia-fr'
        ? 'Wikipedia FR'
        : source.origin === 'wikipedia-en'
          ? 'Wikipedia EN'
          : source.origin === 'duckduckgo'
            ? 'DuckDuckGo'
            : 'Synthese'
    return `${originLabel}: ${source.title}`
  })
  if (sources.length > 3) parts.push(`… +${sources.length - 3} autres`)
  return parts.join(' · ')
}
