import type { OllamaMessage } from '../types/app.ts'
import { classifyCodeAssetPlan } from './codeIntentAssets.ts'
import {
  BUNDLED_PREVIEW_PROJECTS,
  DEV_SERVER_PROJECTS,
  getBuildCommand,
  getDevCommand,
  getTestCommand,
} from './codeIntentCommands.ts'
import { estimateComplexity } from './codeIntentComplexity.ts'
import { estimateFileCount, isWholeProductRequest, minimumFileCountForIntent } from './codeIntentFileCount.ts'
import { classifyCodeIntent } from './codeIntentClassification.ts'
import { normalizeSignalText } from './codeIntentSignalUtils.ts'
import type { CodeIntent, CodeProjectType, PreviewType } from './codeIntentTypes.ts'

export const CODE_SEMANTIC_INTENT_SCHEMA_VERSION = 'aurora.code.semantic-intent/1'

export type CodeSemanticIntent = {
  schemaVersion: typeof CODE_SEMANTIC_INTENT_SCHEMA_VERSION
  projectType: CodeProjectType
  confidence: number
  languages: string[]
  frameworks: string[]
  features: string[]
  rationale: string
}

export type CodeSemanticIntentModelClient = (
  messages: OllamaMessage[],
  options?: { signal?: AbortSignal },
) => Promise<unknown>

const VALID_PROJECT_TYPES = new Set<CodeProjectType>([
  'static_web', 'spa_react', 'spa_vue', 'spa_angular', 'spa_svelte',
  'ssr_nextjs', 'ssr_nuxt', 'ssr_remix',
  'api_express', 'api_fastapi', 'api_django', 'api_flask', 'api_spring', 'api_gin', 'api_actix', 'api_dotnet',
  'fullstack_mern', 'fullstack_nextjs', 'fullstack_django', 'fullstack_rails',
  'cli_node', 'cli_python', 'cli_rust', 'cli_go', 'cli_cpp',
  'desktop_electron', 'desktop_tauri', 'desktop_app',
  'mobile_rn', 'mobile_flutter', 'mobile_ios', 'mobile_android',
  'library_npm', 'library_pypi', 'library_crate',
  'game_web', 'game_unity', 'engine_3d', 'ide',
  'embedded_esp32', 'embedded_arduino', 'compiler', 'os_kernel', 'distributed_system',
  'system_c', 'system_cpp', 'system_rust', 'data_python', 'devops_docker', 'script', 'unknown',
])

function extractContent(response: unknown) {
  if (typeof response === 'string') return response
  if (!response || typeof response !== 'object') return ''
  const record = response as Record<string, unknown>
  if (typeof record.response === 'string') return record.response
  const message = record.message && typeof record.message === 'object'
    ? record.message as Record<string, unknown>
    : null
  return typeof message?.content === 'string' ? message.content : ''
}

function parseJsonObject(raw: string) {
  const cleaned = raw.replace(/```(?:json)?/gi, '').replace(/```/g, '').trim()
  const start = cleaned.indexOf('{')
  const end = cleaned.lastIndexOf('}')
  if (start < 0 || end <= start) return null
  try { return JSON.parse(cleaned.slice(start, end + 1)) as Record<string, unknown> } catch { return null }
}

function stringArray(value: unknown) {
  return Array.isArray(value) ? value.filter((entry): entry is string => typeof entry === 'string') : []
}

export function buildSemanticIntentClassifierMessages(prompt: string): OllamaMessage[] {
  return [
    {
      role: 'system',
      content: [
        'Tu es le classifieur semantique du Module Code AuroraIA.',
        'Reponds uniquement en JSON strict, sans markdown.',
        `schemaVersion obligatoire: ${CODE_SEMANTIC_INTENT_SCHEMA_VERSION}`,
        'Champs obligatoires: schemaVersion, projectType, confidence, languages, frameworks, features, rationale.',
        'projectType doit etre une valeur connue du Module Code, par exemple compiler, os_kernel, distributed_system, mobile_ios, mobile_android, embedded_esp32, ide, engine_3d.',
      ].join('\n'),
    },
    { role: 'user', content: prompt },
  ]
}

export function parseSemanticIntentClassifierResponse(raw: string) {
  const parsed = parseJsonObject(raw)
  const errors: string[] = []
  if (!parsed) return { ok: false as const, errors: ['json_object_missing'] }
  if (parsed.schemaVersion !== CODE_SEMANTIC_INTENT_SCHEMA_VERSION) errors.push('schema_version_invalid')
  if (!VALID_PROJECT_TYPES.has(parsed.projectType as CodeProjectType)) errors.push('project_type_invalid')
  if (typeof parsed.confidence !== 'number' || parsed.confidence < 0 || parsed.confidence > 1) errors.push('confidence_invalid')
  if (errors.length > 0) return { ok: false as const, errors }
  return {
    ok: true as const,
    value: {
      schemaVersion: CODE_SEMANTIC_INTENT_SCHEMA_VERSION,
      projectType: parsed.projectType as CodeProjectType,
      confidence: parsed.confidence as number,
      languages: stringArray(parsed.languages),
      frameworks: stringArray(parsed.frameworks),
      features: stringArray(parsed.features),
      rationale: typeof parsed.rationale === 'string' ? parsed.rationale : '',
    },
  }
}

function previewTypeFor(projectType: CodeProjectType): PreviewType {
  if (DEV_SERVER_PROJECTS.has(projectType)) return 'dev_server'
  if (BUNDLED_PREVIEW_PROJECTS.has(projectType) || projectType.startsWith('spa_')) return 'iframe_bundled'
  if (projectType === 'static_web' || projectType === 'game_web') return 'iframe_static'
  if (
    projectType.startsWith('cli_')
    || projectType.startsWith('system_')
    || projectType.startsWith('embedded_')
    || projectType === 'compiler'
    || projectType === 'os_kernel'
    || projectType === 'distributed_system'
    || projectType === 'script'
    || projectType === 'data_python'
  ) return 'console'
  return 'none'
}

export function applySemanticIntentClassification(
  prompt: string,
  semantic: CodeSemanticIntent,
  fallback: CodeIntent = classifyCodeIntent(prompt),
): CodeIntent {
  const complexity = estimateComplexity(prompt)
  const features = [...new Set([...semantic.features, ...fallback.features])]
  const wholeProduct = isWholeProductRequest(normalizeSignalText(prompt))
  return {
    ...fallback,
    projectType: semantic.projectType,
    complexity,
    languages: [...new Set(semantic.languages.length ? semantic.languages : fallback.languages)],
    frameworks: [...new Set(semantic.frameworks.length ? semantic.frameworks : fallback.frameworks)],
    features,
    needsDevServer: DEV_SERVER_PROJECTS.has(semantic.projectType),
    needsBundling: BUNDLED_PREVIEW_PROJECTS.has(semantic.projectType) || semantic.projectType.startsWith('spa_'),
    previewType: previewTypeFor(semantic.projectType),
    devCommand: getDevCommand(semantic.projectType),
    buildCommand: getBuildCommand(semantic.projectType),
    testCommand: getTestCommand(semantic.projectType),
    primaryModelRole: 'planning',
    needsArchitecturePlanning: true,
    estimatedFileCount: Math.max(
      estimateFileCount(complexity, semantic.projectType),
      minimumFileCountForIntent(semantic.projectType, features, wholeProduct),
    ),
    assetPlan: classifyCodeAssetPlan(prompt),
  }
}

export async function classifyCodeIntentWithSemanticModel(args: {
  prompt: string
  modelClient?: CodeSemanticIntentModelClient
  signal?: AbortSignal
  minConfidence?: number
}) {
  const fallback = classifyCodeIntent(args.prompt)
  if (!args.modelClient) return { intent: fallback, source: 'fallback' as const, errors: ['model_client_missing'] }
  try {
    const response = await args.modelClient(buildSemanticIntentClassifierMessages(args.prompt), { signal: args.signal })
    const parsed = parseSemanticIntentClassifierResponse(extractContent(response))
    if (!parsed.ok) return { intent: fallback, source: 'fallback' as const, errors: parsed.errors }
    if (parsed.value.confidence < (args.minConfidence ?? 0.65)) {
      return { intent: fallback, source: 'fallback' as const, errors: ['confidence_below_threshold'] }
    }
    return { intent: applySemanticIntentClassification(args.prompt, parsed.value, fallback), source: 'semantic_model' as const, errors: [] }
  } catch (error) {
    return { intent: fallback, source: 'fallback' as const, errors: [error instanceof Error ? error.message : String(error)] }
  }
}
