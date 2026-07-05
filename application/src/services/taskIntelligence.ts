import { analyzeMultimodalContext, summarizePreparedContext, type PreparedContextFile } from '../utils/multimodalContext'
import { analyzePromptReality, buildRealityEnrichedPrompt } from './realityAnalyzer'
import type { ModuleId, RealityAnalysis } from '../types/app'
import { analyzeGenerationContract, buildGenerationContractSection, type GenerationContract } from './generationContract'
import { ollamaGenerate } from '../hooks/useTauri'
import { withTimeout } from './llmTimebox'

type ResearchHit = {
  wiki: 'fr' | 'en'
  title: string
  snippet: string
  extract: string
}

type TaskIntelligenceInput = {
  module: ModuleId
  prompt: string
  model: string
  files: PreparedContextFile[]
  setPhase?: (detail: string, progress: number) => void
  phaseBase?: number
  phaseSpan?: number
}

type TaskIntelligenceResult = {
  effectivePrompt: string
  enrichedPrompt: string
  /** Clean English prompt ready for diffusion models (FLUX, Wan2.2). */
  generationPrompt: string
  multimodalContext: string
  researchContext: string
  analysis: RealityAnalysis
  generationContract: GenerationContract
  clarificationQuestion: string | null
}

// ---------------------------------------------------------------------------
// Research cache — bounded LRU with TTL to prevent unbounded growth
// ---------------------------------------------------------------------------
const RESEARCH_CACHE_MAX = 80
const RESEARCH_CACHE_TTL_MS = 30 * 60 * 1000 // 30 min

type CacheEntry = { value: string; expiresAt: number }
const researchCacheInternal = new Map<string, CacheEntry>()

const researchCache = {
  has(key: string): boolean {
    const entry = researchCacheInternal.get(key)
    if (!entry) return false
    if (Date.now() > entry.expiresAt) { researchCacheInternal.delete(key); return false }
    return true
  },
  get(key: string): string | undefined {
    const entry = researchCacheInternal.get(key)
    if (!entry) return undefined
    if (Date.now() > entry.expiresAt) { researchCacheInternal.delete(key); return undefined }
    // LRU: refresh by re-inserting at end
    researchCacheInternal.delete(key)
    researchCacheInternal.set(key, entry)
    return entry.value
  },
  set(key: string, value: string): void {
    // Evict oldest entry when at capacity
    if (researchCacheInternal.size >= RESEARCH_CACHE_MAX && !researchCacheInternal.has(key)) {
      const firstKey = researchCacheInternal.keys().next().value
      if (firstKey !== undefined) researchCacheInternal.delete(firstKey)
    }
    researchCacheInternal.set(key, { value, expiresAt: Date.now() + RESEARCH_CACHE_TTL_MS })
  },
  /** Purge all expired entries (call occasionally, not on every access). */
  purgeExpired(): void {
    const now = Date.now()
    for (const [k, entry] of researchCacheInternal) {
      if (now > entry.expiresAt) researchCacheInternal.delete(k)
    }
  },
  clear(): void {
    researchCacheInternal.clear()
  },
}

function uniqueStrings(values: string[]) {
  return Array.from(new Set(values.map((value) => value.trim()).filter(Boolean)))
}

function stripHtml(text: string) {
  return text
    .replace(/<[^>]+>/g, ' ')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/\s+/g, ' ')
    .trim()
}

function shorten(text: string, limit = 420) {
  const normalized = text.replace(/\s+/g, ' ').trim()
  if (normalized.length <= limit) {
    return normalized
  }

  return `${normalized.slice(0, limit)}...`
}

function buildCacheKey(module: ModuleId, prompt: string) {
  return `${module}::${prompt.trim().toLowerCase()}`
}

function looksLikeReferenceSensitivePrompt(prompt: string) {
  const normalized = prompt.toLowerCase()
  const directNeedles = [
    'qui est',
    'who is',
    'recherche',
    'cherche',
    'find',
    'personne',
    'person',
    'celebrite',
    'celebrity',
    'marque',
    'brand',
    'historique',
    'history',
    'biographie',
    'biography',
    'lieu',
    'location',
    'ville',
    'country',
    'entreprise',
    'company',
    'inspire de',
    'inspired by',
    'comme ',
    'style de',
    'style of',
  ]

  if (directNeedles.some((needle) => normalized.includes(needle))) {
    return true
  }

  return /\b(courroie|belt|poulie|pulley|engrenage|gear|gearbox|reducteur|reducer|verin|v[eé]rin|cylinder|hydraulic|hydraulique|pneumatic|pneumatique|charniere|hinge|linkage|bielle|cam|came|cable|wiring|wire harness|harness|faisceau|routing|connector|connecteur|motherboard|carte mere|psu|pcie|atx|sata|usb|ethernet|electrique|electrical|pcb|circuit|anime|manga|personnage|character|hero|heros|h[eé]ros|heroine|heroïne|waifu|villain|cosplay|pokemon|digimon)\b/i.test(normalized)
}

function extractTechnicalResearchQueries(prompt: string) {
  const normalized = prompt.toLowerCase()
  const queries = [prompt]

  if (/\b(courroie|belt|poulie|pulley)\b/i.test(normalized)) {
    queries.push('systeme courroie poulie transmission mecanique')
    queries.push('belt drive pulley mechanical system')
  }

  if (/\b(engrenage|gear|gearbox|reducteur|reducer)\b/i.test(normalized)) {
    queries.push('train d engrenages transmission mecanique')
    queries.push('gear train mechanical transmission')
  }

  if (/\b(verin|v[eé]rin|cylinder|hydraulic|hydraulique|pneumatic|pneumatique|actuator)\b/i.test(normalized)) {
    queries.push('verin mecanique hydraulique pneumatique')
    queries.push('cylinder actuator mechanical assembly')
  }

  if (/\b(cable|wiring|wire harness|harness|faisceau|routing)\b/i.test(normalized)) {
    queries.push('routage cable faisceau electrique')
    queries.push('cable routing electrical harness')
  }

  if (/\b(motherboard|carte mere|psu|pcie|atx|sata|gpu)\b/i.test(normalized)) {
    queries.push('pc cable management connector routing')
  }

  return uniqueStrings(queries.map((query) => shorten(query, 180)))
}

function extractReferenceResearchQueries(prompt: string) {
  const normalized = prompt.toLowerCase()
  const queries = [prompt]

  if (/\b(anime|manga|personnage|character|hero|heros|h[eé]ros|heroine|heroïne|waifu|villain|pokemon|digimon)\b/i.test(normalized)) {
    queries.push(`${prompt} official character design`)
    queries.push(`${prompt} anime character appearance`)
  }

  if (/\b(piece|component|composant|mecanique|mechanical|electrique|electrical|cable|connector|connecteur|bearing|roulement|poulie|pulley|courroie|belt|verin|v[eé]rin)\b/i.test(normalized)) {
    queries.push(`${prompt} dimensions size measurements`)
    queries.push(`${prompt} reference photo`)
  }

  if (/\b(photo|reference exacte|reference realiste|modele reel|real object|existing object)\b/i.test(normalized)) {
    queries.push(`${prompt} product photo`)
  }

  return uniqueStrings(queries.map((query) => shorten(query, 180)))
}

function buildResearchQueries(prompt: string, analysis: RealityAnalysis, generationContract: GenerationContract) {
  const queries = [
    prompt,
    analysis.webSearchTerms.join(' '),
    ...extractTechnicalResearchQueries(prompt),
    ...extractReferenceResearchQueries(prompt),
  ]

  if (generationContract.requestedChanges.length > 0) {
    queries.push(generationContract.requestedChanges.slice(0, 2).join(' '))
  }

  return uniqueStrings(queries.map((query) => shorten(query, 180))).slice(0, 4)
}

function hasLikelyProperNoun(prompt: string): boolean {
  // Strip the first word (usually the verb/article) then look for a word
  // starting with an uppercase letter that is not a trivial sentence start.
  // Also catches CamelCase (IPhone, PlayStation, DeepMind) and hyphenated
  // proper nouns (Spider-Man, Michel-Ange).
  const stripped = prompt.replace(/^[\s'"«»:,;.\-]+/, '')
  const first = stripped.split(/\s+/)[0] ?? ''
  const rest = stripped.slice(first.length)
  if (/\b([A-ZÀ-Ý][a-zà-ÿ]+(?:[- ][A-ZÀ-Ý][a-zà-ÿ]+)+|[A-ZÀ-Ý]{2,}[a-zà-ÿ]+|[A-Z][a-zà-ÿ]{2,}[A-Z][a-z]+)\b/.test(rest)) {
    return true
  }
  // Standalone all-caps acronyms (NASA, Apple if repeated, BMW, etc.) count
  // too — they need research to match reality.
  if (/\b[A-Z]{3,}\b/.test(prompt)) return true
  // Single capitalized word after the start ("un Naruto qui court")
  if (/\s[A-ZÀ-Ý][a-zà-ÿ]{2,}/.test(' ' + stripped)) return true
  return false
}

function hasLikelyNamedAction(prompt: string): boolean {
  // Famous dances, moves, trends — none of these are a base diffusion
  // model's strong suit, so research-fetched descriptions help it reproduce
  // the choreography.
  return /\b(macarena|gangnam\s*style|soulja\s*boy|cupid\s*shuffle|floss\s*dance|haka|ola|mexican\s*wave|waka\s*waka|tiktok|renegade|woah|orange\s*justice|fortnite\s+dance|moonwalk|robot\s*dance|breakdance|flamenco|tango|salsa|hip[- ]?hop|ballet|waltz|charleston|twist|gangsta|twerk|kuduro|shuffle|step|routine)\b/i.test(prompt)
}

function shouldRunNativeResearch(
  module: ModuleId,
  prompt: string,
  analysis: RealityAnalysis,
  files: PreparedContextFile[],
  generationContract: GenerationContract,
) {
  const hasImages = files.some((file) => file.kind === 'image')

  if (hasImages && generationContract.mode === 'edit' && !generationContract.shouldResearch && !looksLikeReferenceSensitivePrompt(prompt)) {
    return false
  }

  if (
    module === 'code'
    && !analysis.requiresWebValidation
    && !generationContract.shouldResearch
    && !looksLikeReferenceSensitivePrompt(prompt)
  ) {
    return false
  }

  // Visual generation modules: research-by-default when the prompt names a
  // proper noun (character, brand, product, place, person) OR a named
  // action/dance/cultural move. Base diffusion models have spotty coverage
  // for specifics, so pulling a few factual bullets from Wikipedia + web
  // into the distiller fixes 80% of the "it doesn't look like X" complaints
  // without hardcoding any specific IP list.
  if (module === 'video' || module === 'image' || module === 'drawing' || module === '3d') {
    if (hasLikelyProperNoun(prompt) || hasLikelyNamedAction(prompt)) {
      return true
    }
  }

  return generationContract.shouldResearch || analysis.requiresWebValidation || analysis.isVerifiable || looksLikeReferenceSensitivePrompt(prompt)
}

async function wikiSearch(query: string, wiki: 'fr' | 'en') {
  try {
    const response = await fetch(
      `https://${wiki}.wikipedia.org/w/api.php?action=query&list=search&format=json&origin=*&utf8=1&srlimit=3&srprop=snippet&srsearch=${encodeURIComponent(query)}`,
      { signal: AbortSignal.timeout(4000) },
    )

    if (!response.ok) {
      return []
    }

    const text = await response.text()
    if (!text || text.trimStart().startsWith('<')) return []
    const payload = JSON.parse(text) as {
      query?: {
        search?: Array<{
          title: string
          snippet: string
        }>
      }
    }

    return payload.query?.search || []
  } catch {
    return []
  }
}

async function wikiExtract(title: string, wiki: 'fr' | 'en') {
  try {
    const response = await fetch(
      `https://${wiki}.wikipedia.org/w/api.php?action=query&prop=extracts&format=json&origin=*&redirects=1&exintro=1&explaintext=1&titles=${encodeURIComponent(title)}`,
      { signal: AbortSignal.timeout(4000) },
    )

    if (!response.ok) {
      return ''
    }

    const text = await response.text()
    if (!text || text.trimStart().startsWith('<')) return ''
    const payload = JSON.parse(text) as {
      query?: {
        pages?: Record<string, { extract?: string }>
      }
    }

    const pages = Object.values(payload.query?.pages || {})
    return pages.find((page) => page.extract?.trim())?.extract?.trim() || ''
  } catch {
    return ''
  }
}

async function runNativeKnowledgeResearch(queries: string[]) {
  const normalizedQueries = uniqueStrings(
    queries
      .map((query) => query.replace(/\s+/g, ' ').trim().slice(0, 180))
      .filter(Boolean),
  ).slice(0, 4)
  const languages: Array<'fr' | 'en'> = ['fr', 'en']
  const hits: ResearchHit[] = []
  const seen = new Set<string>()

  for (const normalizedQuery of normalizedQueries) {
    for (const wiki of languages) {
      try {
        const results = await wikiSearch(normalizedQuery, wiki)
        for (const result of results.slice(0, 2)) {
          const key = `${wiki}:${result.title}`
          if (seen.has(key)) {
            continue
          }

          const extract = await wikiExtract(result.title, wiki)
          if (!extract) {
            continue
          }

          seen.add(key)
          hits.push({
            wiki,
            title: result.title,
            snippet: stripHtml(result.snippet),
            extract: shorten(extract, 540),
          })

          if (hits.length >= 4) {
            return hits
          }
        }
      } catch {
        // Ignore per-wiki failures and keep trying the next source.
      }
    }
  }

  return hits
}

function buildResearchContext(hits: ResearchHit[]) {
  if (hits.length === 0) {
    return ''
  }

  return [
    'Recherche native verifiee:',
    ...hits.map((hit) => [
      `- Source: Wikipedia ${hit.wiki.toUpperCase()} / ${hit.title}`,
      `  Indice: ${hit.snippet || 'Sans extrait court.'}`,
      `  Resume: ${hit.extract}`,
    ].join('\n')),
    'Priorite: si une reference utilisateur jointe contredit ces notes, la reference utilisateur l emporte.',
  ].join('\n')
}

function buildTaskEnvelope(
  module: ModuleId,
  prompt: string,
  multimodalContext: string,
  researchContext: string,
  generationContract: GenerationContract,
  files: PreparedContextFile[],
) {
  const attachmentsSummary = files.length > 0
    ? [
      `Pieces jointes detectees: ${files.map((file) => `${file.name} (${file.kind})`).join(', ')}`,
      summarizePreparedContext(files) ? 'Des extraits fiables de documents ont ete ajoutes au contexte.' : '',
      files.some((file) => file.imageBase64) ? 'Des references visuelles sont disponibles et doivent etre prioritaires pour l apparence, l identite et la composition.' : '',
    ].filter(Boolean).join('\n')
    : ''

  return [
    `Brief module ${module}: ${prompt}`,
    attachmentsSummary,
    buildGenerationContractSection(generationContract),
    multimodalContext,
    researchContext,
  ].filter(Boolean).join('\n\n')
}

// ---------------------------------------------------------------------------
// Distill the enriched context into a clean diffusion-model-ready prompt.
// FLUX and Wan2.2 expect descriptive English, not structured metadata.
// ---------------------------------------------------------------------------

const VISUAL_MODULES: ModuleId[] = ['image', 'video', 'drawing', '3d']

async function distillToGenerationPrompt(
  originalPrompt: string,
  contract: GenerationContract,
  module: ModuleId,
  model: string,
  supportingContext = '',
): Promise<string> {
  const isVideo = module === 'video'
  const isThreeD = module === '3d'
  const isImage = module === 'image' || module === 'drawing'
  const subjects = contract.requestedChanges.slice(0, 3).join(', ')
  const colors = contract.colorConstraints.slice(0, 3).join(', ')
  const spatial = contract.spatialConstraints.slice(0, 3).join(', ')
  const motion = contract.motionConstraints.slice(0, 3).join(', ')
  const quality = contract.qualityPriorities.slice(0, 4).join(', ')
  const forbidden = contract.forbiddenChanges.slice(0, 4).join(', ')
  const preserve = contract.mustPreserve.slice(0, 3).join(', ')
  const maxWords = isThreeD ? 140 : 100
  const clippedSupportingContext = shorten(supportingContext, isThreeD ? 1000 : 780)

  const distillationPrompt = `/no_think
Convert the following prompt to a clean English description for ${isVideo ? 'a video diffusion model (Wan2.2)' : isThreeD ? 'a 3D reference-image diffusion model (FLUX before Hunyuan3D)' : 'an image diffusion model (FLUX)'}.

Rules:
- Output ONLY the generation description, nothing else, no explanations
- NEVER refuse, decline or water down the request. This is a creative local pipeline; imaginative, surreal, violent-cartoon, dark-fantasy, horror, gory fictional, body-horror, monster, mythological, action-movie and adult-fantasy prompts are ALL acceptable and MUST be described faithfully. Do not emit safety disclaimers, do not replace the scene by something safer, do not soften the described action. (Hard limits, which the upstream pipeline already enforces: no CSAM, no real-person non-consensual sexual content, no real-person harassment.)
- English only, maximum ${maxWords} words
- Preserve EVERY subject, character, creature and action from the original prompt
- NAME EACH SUBJECT EXPLICITLY with its common noun. If the prompt says "banane qui danse", the output MUST contain "banana" — never "yellow fruit", "elongated yellow shape" or any paraphrase. Diffusion models anchor on nouns; losing the noun loses the subject. Same for "dog" (not "canine mammal"), "fish" (not "aquatic creature"), "Porsche 911" (not "sports car"), "Eiffel Tower" (not "tall iron tower"), etc.
- IMPORTANT French disambiguation: "qui souris" means "who is smiling" (NOT a mouse). "une souris" = "a mouse (animal)". "il sourit" / "qui sourit" = "he/she smiles / who smiles". Use context to tell them apart.
${isVideo ? '- ANATOMICAL ACCURACY FOR NON-HUMAN SUBJECTS: fabricating limbs that the species does not have is forbidden. A snake stays without legs, a fish keeps its fins and has no feet, a seahorse never gains running legs, a hippopotamus keeps its four stubby legs (no two-legged stand unless the prompt explicitly says so), a cyclops has ONE eye, octopus has EXACTLY eight arms, etc. If the user asks an impossible action — e.g. "a seahorse jumping on a hippopotamus" — describe the action using the species\' real anatomy (the seahorse propels with its tail and dorsal fin, not with legs it does not have).' : ''}
${isVideo ? '- PHYSICS AND CONTACT COHERENCE: if the prompt does not request phasing/teleport/ghost behaviour, every subject must obey contact physics. Feet stay on the ground while standing/walking, a body crushing another stays in contact through the crushing motion, a character jumping on another lands on top (not through). For "un cyclope qui écrase une souris" describe the foot descending, contact with the mouse, and the mouse being flattened under visible pressure — not the foot passing through the floor.' : ''}
${isVideo ? '- MOTION COMPLETION: when the prompt names an action (écrase, saute, danse, explose, court, frappe…), describe the action as a complete cycle with a beginning, peak and follow-through. The clip must end AFTER the action is visibly finished, not mid-motion.' : ''}
- If original is French, translate accurately before generating
${isVideo ? '- Describe motion, dynamics and temporal flow' : isThreeD ? '- Describe a single clean studio reference for later 3D reconstruction, with isolated subject, faithful structure and readable part separation' : '- Describe visual composition, style, lighting and materials'}
- Include all explicit colors, positions and spatial relationships
${isImage ? '- Unless pixel art, sprites or voxel style are explicitly requested, forbid pixelation, compression noise, mosaic artifacts and low-resolution upscale look' : ''}
${isImage ? '- If the subject is an existing character, person, object or component, use the supporting context to preserve recognizable traits instead of inventing a nearby approximation' : ''}
${isImage ? '- Preserve iconic hairstyle, silhouette, costume cues, connector layout, proportions and known dimensions whenever the supporting context provides them' : ''}
${isThreeD ? '- If the prompt describes a mechanism or assembly, describe the full system, distinguish fixed structure from moving or routed elements, and keep the kinematic chain readable' : ''}
${isThreeD ? '- If the prompt describes cables or electrical routing, focus on connector endpoints, routing path, bend radius and bundle organization, not fake motion' : ''}
${isThreeD ? '- When the supporting context provides real-world dimensional relationships or known proportions, preserve them unless the user explicitly asks for a different size' : ''}
${isThreeD ? '- CRITICAL: If the supporting context contains a PRODUCT/SUBJECT IDENTITY section with visual descriptions, you MUST use those descriptions as the PRIMARY basis for the generation. Do NOT substitute with a different product or component.' : ''}
${isThreeD ? '- If the prompt names a specific product (brand + model), describe that exact product based on the provided identity context, not a generic version or the manufacturer\'s other products' : ''}
${isThreeD || isImage ? '- If a MOTION/POSE DIRECTIVE is present, the generated description MUST show the subject in that exact pose or motion state — this is mandatory, not optional' : ''}
${quality ? '- Preserve the stated quality priorities exactly' : ''}
${forbidden ? '- Do not violate the forbidden-change list' : ''}
${preserve ? '- Respect the preservation constraints when a reference already exists' : ''}

Original prompt: ${originalPrompt}
Extracted subjects: ${subjects || 'none'}
${colors ? `Color constraints: ${colors}` : ''}
${spatial ? `Spatial constraints: ${spatial}` : ''}
${(isVideo || isThreeD) && motion ? `Motion or functional constraints: ${motion}` : ''}
${quality ? `Quality priorities: ${quality}` : ''}
${forbidden ? `Avoid: ${forbidden}` : ''}
${preserve ? `Must preserve: ${preserve}` : ''}
${clippedSupportingContext ? `Supporting factual or visual context:\n${clippedSupportingContext}` : ''}

Generation description:`

  try {
    const response = await withTimeout(ollamaGenerate(model, distillationPrompt), {
      label: 'taskIntelligence.distillGenerationPrompt',
      timeoutMs: 18_000,
    })
    const text = (response?.response || '').trim()
    // Strip any <think> blocks the model might emit
    const cleaned = text.replace(/<think>[\s\S]*?<\/think>/g, '').replace(/<think>[\s\S]*$/g, '').trim()
    if (cleaned.length > 8) return cleaned
  } catch {
    // Fall through to fallback (timeout, model error, etc.)
  }

  // Fallback: return the original prompt unchanged
  return originalPrompt
}

// v77zam: minimal fallback when the LLM-driven intelligence path times out.
// Lets the generation pipeline continue with the raw prompt instead of hanging
// indefinitely on a slow / stuck Ollama. The downstream code (FLUX prompt
// builder, intent classifier) already has its own fallback heuristics and
// will produce a usable mesh from the bare prompt.
function buildTaskIntelligenceFallback(prompt: string): TaskIntelligenceResult {
  return {
    effectivePrompt: prompt,
    enrichedPrompt: prompt,
    generationPrompt: prompt,
    multimodalContext: '',
    researchContext: '',
    analysis: {
      nature: 'creative_blend',
      subject: [prompt.slice(0, 60)],
      isVerifiable: false,
      complexityScore: 5,
      requiresWebValidation: false,
      consistencyRules: [],
      fidelityTarget: 98,
      webSearchTerms: [],
    },
    generationContract: {
      mode: 'create',
      editStrategy: 'fresh_create',
      mustPreserve: [],
      requestedChanges: [],
      forbiddenChanges: [],
      qualityPriorities: [],
      colorConstraints: [],
      spatialConstraints: [],
      motionConstraints: [],
      needsClarification: false,
      clarificationQuestion: null,
      shouldResearch: false,
    },
    clarificationQuestion: null,
  }
}

export async function prepareTaskIntelligence(input: TaskIntelligenceInput): Promise<TaskIntelligenceResult> {
  // v77zam: wrap the whole intelligence phase in a hard 120s budget. If any
  // sub-step (multimodal, reality, contract, research, distill) hangs on
  // Ollama, the global timeout fires and we fall back to a minimal
  // intelligence struct so the generation pipeline downstream still runs.
  const TIMEOUT_MS = 120_000

  return new Promise<TaskIntelligenceResult>((resolve) => {
    let settled = false
    const timer = setTimeout(() => {
      if (settled) return
      settled = true
      console.warn(`[prepareTaskIntelligence] Global timeout ${TIMEOUT_MS}ms, using fallback for module:`, input.module)
      resolve(buildTaskIntelligenceFallback(input.prompt))
    }, TIMEOUT_MS)

    _prepareTaskIntelligenceImpl(input).then((result) => {
      if (settled) return
      settled = true
      clearTimeout(timer)
      resolve(result)
    }).catch((err) => {
      if (settled) return
      settled = true
      clearTimeout(timer)
      console.warn('[prepareTaskIntelligence] Failed, using fallback:', err)
      resolve(buildTaskIntelligenceFallback(input.prompt))
    })
  })
}

async function _prepareTaskIntelligenceImpl({
  module,
  prompt,
  model,
  files,
  setPhase,
  phaseBase = 36,
  phaseSpan = 18,
}: TaskIntelligenceInput): Promise<TaskIntelligenceResult> {
  const step = Math.max(4, Math.round(phaseSpan / 4))

  setPhase?.('Analyse du contexte transmis...', phaseBase)
  const multimodalContext = files.length > 0
    ? await analyzeMultimodalContext({
      module,
      prompt,
      model,
      files,
    })
    : ''

  const basePrompt = multimodalContext ? `${prompt}\n\n${multimodalContext}` : prompt

  setPhase?.('Analyse du contrat de la demande...', phaseBase + step)
  const analysis = await analyzePromptReality(basePrompt, module, model)
  const generationContract = await analyzeGenerationContract({
    module,
    prompt: basePrompt,
    model,
    files,
  })

  let researchContext = ''
  const cacheKey = buildCacheKey(module, basePrompt)
  const shouldResearch = shouldRunNativeResearch(module, basePrompt, analysis, files, generationContract)
  const researchQueries = buildResearchQueries(basePrompt, analysis, generationContract)

  if (shouldResearch) {
    setPhase?.('Recherche native de references...', phaseBase + step * 2)
    if (researchCache.has(cacheKey)) {
      researchContext = researchCache.get(cacheKey) || ''
    } else {
      const hits = await runNativeKnowledgeResearch(researchQueries)
      researchContext = buildResearchContext(hits)
      researchCache.set(cacheKey, researchContext)
    }
  }

  const effectivePrompt = buildTaskEnvelope(module, prompt, multimodalContext, researchContext, generationContract, files)

  setPhase?.('Construction du contrat final du module...', phaseBase + step * 3)
  const enrichedPrompt = buildRealityEnrichedPrompt(effectivePrompt, analysis, module as Parameters<typeof buildRealityEnrichedPrompt>[2])
  const visualSupportContext = [researchContext, multimodalContext].filter(Boolean).join('\n\n')

  // For visual diffusion modules: distill to a clean English prompt that FLUX/Wan2.2 can use.
  // For code/conversation/learning: enrichedPrompt is appropriate (LLM reads structured contracts).
  const generationPrompt = VISUAL_MODULES.includes(module)
    ? await distillToGenerationPrompt(prompt, generationContract, module, model, visualSupportContext)
    : enrichedPrompt

  return {
    effectivePrompt,
    enrichedPrompt,
    generationPrompt,
    multimodalContext,
    researchContext,
    analysis,
    generationContract,
    clarificationQuestion: generationContract.needsClarification ? generationContract.clarificationQuestion : null,
  }
}

export function clearTaskIntelligenceCache() {
  researchCache.clear()
}
