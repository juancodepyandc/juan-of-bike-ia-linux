import { ollamaGenerate } from '../hooks/useTauri'
import type { PromptNature, RealityAnalysis } from '../types/app'
import { AUXILIARY_ANALYSIS_MODEL } from '../config/models'

const CACHE_MAX_SIZE = 64
const CACHE_TTL_MS = 20 * 60 * 1000 // 20 minutes

type CacheEntry = { value: RealityAnalysis; expiresAt: number }
const analysisCache = new Map<string, CacheEntry>()

type RealityModule = 'general' | 'conversation' | 'image' | 'drawing' | 'video' | '3d' | 'code' | 'learning'

function hashPrompt(prompt: string): string {
  let hash = 0
  for (let index = 0; index < prompt.length; index += 1) {
    hash = ((hash << 5) - hash + prompt.charCodeAt(index)) | 0
  }
  return `reality_${hash}`
}

function buildModuleRules(module: RealityModule) {
  switch (module) {
    case 'image':
      return [
        'preserve reference identity and composition unless explicitly changed',
        'edit only the elements the user asked to change',
        'single dominant subject',
        'clean composition',
        'clear focal hierarchy',
        'coherent materials and lighting',
        'no watermark, no random text, no parasite objects',
      ]
    case 'drawing':
      return [
        'preserve the existing subject structure unless explicitly changed',
        'edit only the requested regions or attributes',
        'respect the sketch intent',
        'single readable subject',
        'clean silhouette and controlled background',
        'no watermark, no random text, no duplicated elements',
      ]
    case 'video':
      return [
        'preserve identity, outfit, subject count and framing unless explicitly changed',
        'modify only the requested action, motion or environment changes',
        'stable subject identity across the whole shot',
        'clear camera intention and readable motion',
        'no random cuts, no chaotic effects, no subject drift',
        'coherent lighting and scene continuity',
      ]
    case '3d':
      return [
        'preserve the uploaded object identity and major proportions unless explicitly changed',
        'isolated object with clean silhouette',
        'neutral readable background',
        'stable perspective and geometry',
        'no floating accessories or background clutter',
      ]
    case 'code':
      return [
        'strictly answer the requested task',
        'no invented files or features',
        'produce complete executable content',
        'state assumptions only in a dedicated notes section',
      ]
    case 'conversation':
      return [
        'do not claim unsupported facts',
        'say clearly what is known and what is missing',
        'prefer precision over speed',
      ]
    case 'learning':
      return [
        'stay pedagogical and exact',
        'prefer verifiable information over catchy wording',
        'do not flatten difficulty progression',
        'examples must remain coherent with the requested level',
      ]
    default:
      return [
        'stay faithful to the central request',
        'avoid drift and extra invented details',
        'keep the result clean and directly usable',
      ]
  }
}

function buildValidationChecks(module: RealityModule) {
  switch (module) {
    case 'image':
    case 'drawing':
      return [
        'subject must be readable at first glance',
        'background must support the subject instead of stealing focus',
        'finish must look intentional and polished',
      ]
    case 'video':
      return [
        'motion must stay readable from start to end',
        'camera behavior must remain coherent',
        'main subject must stay identifiable',
      ]
    case '3d':
      return [
        'reconstruction must focus on one object',
        'shape must remain interpretable from multiple angles',
        'reference image must stay clean and isolated',
      ]
    case 'code':
      return [
        'requested behavior must be covered',
        'output must be complete and structured',
        'no placeholder content must remain',
      ]
    case 'conversation':
      return [
        'every important user constraint is covered',
        'uncertainty is explicit when needed',
        'answer stays direct and actionable',
      ]
    case 'learning':
      return [
        'content must match the requested level',
        'examples must support understanding instead of adding noise',
        'progression must remain coherent from basics to application',
      ]
    default:
      return [
        'core request is fully covered',
        'extra noise is removed',
      ]
  }
}

function buildObjectiveLine(analysis: RealityAnalysis) {
  switch (analysis.nature) {
    case 'real_world':
      return 'maximum realism and factual coherence'
    case 'fictional':
      return 'strong internal coherence with believable execution'
    case 'technical':
      return 'precision, structure and zero ambiguity'
    case 'educational':
      return 'clarity, pedagogy and exactness'
    default:
      return 'high fidelity to the request with clean execution'
  }
}

function normalizePrompt(prompt: string) {
  return prompt.replace(/\s+/g, ' ').trim()
}

function buildVisualContract(
  prompt: string,
  analysis: RealityAnalysis,
  module: RealityModule,
) {
  const subjectLine = analysis.subject.length > 0 ? analysis.subject.join(', ') : 'central subject from the prompt'
  const rules = [
    ...analysis.consistencyRules,
    ...buildModuleRules(module),
  ]

  return [
    `main brief: ${normalizePrompt(prompt)}`,
    `primary subject: ${subjectLine}`,
    `target: ${buildObjectiveLine(analysis)}`,
    `non negotiable rules: ${rules.join('; ')}`,
    `validation: ${buildValidationChecks(module).join('; ')}`,
    'quality floor: clean composition, no parasite elements, no watermark, no random text, controlled background, polished finish',
  ].join('. ')
}

function buildStructuredContract(
  prompt: string,
  analysis: RealityAnalysis,
  module: RealityModule,
) {
  const subjectLine = analysis.subject.length > 0 ? analysis.subject.join(', ') : 'central request only'
  const rules = [
    ...analysis.consistencyRules,
    ...buildModuleRules(module),
  ]
  const checks = buildValidationChecks(module)

  return [
    `OBJECTIVE: ${normalizePrompt(prompt)}`,
    `NATURE: ${analysis.nature}`,
    `PRIMARY_SUBJECT: ${subjectLine}`,
    'NON_NEGOTIABLE_CONSTRAINTS:',
    ...rules.map((rule) => `- ${rule}`),
    'VALIDATION_CHECKLIST:',
    ...checks.map((check) => `- ${check}`),
    `FIDELITY_TARGET: ${analysis.fidelityTarget}/100`,
  ].join('\n')
}

export async function analyzePromptReality(
  prompt: string,
  module: string,
  model = AUXILIARY_ANALYSIS_MODEL
): Promise<RealityAnalysis> {
  const key = hashPrompt(prompt)
  const cached = analysisCache.get(key)
  if (cached && cached.expiresAt > Date.now()) return cached.value

  const metaPrompt = `/no_think
Analyze this prompt and classify it. Reply ONLY with valid JSON, no markdown:
{
  "nature": "real_world|fictional|technical|educational|creative_blend",
  "subject": ["key entities"],
  "isVerifiable": true/false,
  "complexityScore": 0-10,
  "requiresWebValidation": true/false,
  "consistencyRules": ["rules to follow"],
  "webSearchTerms": ["search terms if verifiable"]
}

Module: ${module}
Prompt: "${prompt}"`

  try {
    const response = await ollamaGenerate(model, metaPrompt)
    const text = response?.response || ''
    const cleaned = text.replace(/```(?:json)?\s*/g, '').replace(/```/g, '')
    const jsonMatch = cleaned.match(/\{[\s\S]*\}/)

    if (jsonMatch) {
      const parsed = JSON.parse(jsonMatch[0])
      const analysis: RealityAnalysis = {
        nature: (parsed.nature || 'creative_blend') as PromptNature,
        subject: parsed.subject || [],
        isVerifiable: parsed.isVerifiable ?? false,
        complexityScore: parsed.complexityScore ?? 5,
        requiresWebValidation: parsed.requiresWebValidation ?? false,
        consistencyRules: parsed.consistencyRules || [],
        fidelityTarget: 98,
        webSearchTerms: parsed.webSearchTerms || [],
      }
      if (analysisCache.size >= CACHE_MAX_SIZE) {
        const firstKey = analysisCache.keys().next().value
        if (firstKey !== undefined) analysisCache.delete(firstKey)
      }
      analysisCache.set(key, { value: analysis, expiresAt: Date.now() + CACHE_TTL_MS })
      return analysis
    }
  } catch (error) {
    console.warn('[RealityAnalyzer] Failed with model:', model, error)
  }

  const fallback: RealityAnalysis = {
    nature: 'creative_blend',
    subject: [prompt.slice(0, 60)],
    isVerifiable: false,
    complexityScore: 5,
    requiresWebValidation: false,
    consistencyRules: [],
    fidelityTarget: 98,
    webSearchTerms: [],
  }

  if (analysisCache.size >= CACHE_MAX_SIZE) {
    const firstKey = analysisCache.keys().next().value
    if (firstKey !== undefined) analysisCache.delete(firstKey)
  }
  analysisCache.set(key, { value: fallback, expiresAt: Date.now() + CACHE_TTL_MS })
  return fallback
}

export function buildRealityEnrichedPrompt(
  prompt: string,
  analysis: RealityAnalysis,
  module: RealityModule = 'general',
): string {
  if (module === 'code' || module === 'conversation') {
    return buildStructuredContract(prompt, analysis, module)
  }

  return buildVisualContract(prompt, analysis, module)
}

export function clearAnalysisCache() {
  analysisCache.clear()
}
