import { getBridgeUrl } from '../utils/runtime.ts'
import type { CodeFile } from './codeOrchestrator.ts'
import { detectSubject } from './codeIntentSubject.ts'
import { isCancellationMessage } from './codeInfrastructureFailure.ts'

/**
 * #7: construit un prompt IMAGE dedie au SUJET exact (produit) plutot que le
 * prompt PROJET. "AirPods Pro product shot, studio lighting" donne une vraie
 * image produit; "site landing page vitrine airpods..." donnait du hors-sujet.
 * Retourne undefined si aucun sujet resolu (l'appelant retombe sur le prompt).
 */
export function buildSubjectImagePrompt(prompt: string): string | undefined {
  const subject = detectSubject(prompt)
  if (!subject.canonical || subject.source === 'none') return undefined
  const base = subject.brandProfile?.imageQueries?.[0] ?? `${subject.canonical} product`
  return `${base}, studio lighting, clean neutral background, high detail, photorealistic, no text`
}

export const CODE_ASSET_BUNDLE_SCHEMA = 'aurora.code.asset-bundle/1'
export const CODE_ASSET_MANIFEST_PATH = 'assets/aurora-asset-bundle.json'

type FetchLike = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>

export type CodeAssetKind = 'image' | 'model3d' | 'voice'

export type CodeAssetRoute = {
  kind: CodeAssetKind | 'vision' | 'rag_reference'
  module: 'image' | '3d' | 'voice' | 'vision' | 'rag'
  endpoint: string
  fallbackEndpoints?: string[]
  required: boolean
}

export type CodeAssetVariant = {
  path: string
  storagePath?: string
  previewUrl?: string
  width: number
  height: number
  mimeType: string
  bytes: number
}

export type CodeGeneratedAsset = {
  id: string
  kind: CodeAssetKind
  role: string
  path: string
  storagePath?: string
  previewUrl?: string
  mimeType: string
  bytes: number
  sourceModule: string
  bridgeEndpoint: string
  requestedEndpoint?: string
  optimized: boolean
  srcset?: string
  projectSrcset?: string
  variants?: CodeAssetVariant[]
  metadata?: Record<string, unknown>
}

export type CodeAssetBundle = {
  schemaVersion: typeof CODE_ASSET_BUNDLE_SCHEMA
  createdAt: number
  runId: string
  prompt: string
  archetype: string
  outDir: string
  requiredKinds: CodeAssetKind[]
  missingRequired: CodeAssetKind[]
  assets: CodeGeneratedAsset[]
  routes: Array<Record<string, unknown>>
  rag?: {
    searchEndpoint?: string
    extractEndpoint?: string
    embedding?: string
    reranker?: string
    results?: Array<{ title?: string; url?: string; snippet?: string; score?: number }>
    fetchedPages?: number
    error?: string
  }
  deferred?: Array<{ kind: string; reason: string }>
}

export type GenerateAssetsForArchetypeRequest = {
  prompt: string
  /** #7: prompt IMAGE dedie au sujet exact (produit) au lieu du prompt projet. */
  imagePrompt?: string
  archetype?: string
  requestedKinds?: CodeAssetKind[]
  runId?: string
  bridgeUrl?: string
  fetchImpl?: FetchLike
  signal?: AbortSignal
  timeoutSec?: number
  fresh3d?: boolean
  allowExisting3d?: boolean
  sourceImageRunId?: string
  source3dRunId?: string
  sourceVoiceRunId?: string
  threeDTimeoutSec?: number
  seed?: number
}

export type CodeAssetSelectionInput = {
  prompt: string
  projectType: string
  wantsImages?: boolean
  wants3D?: boolean
  wantsPremiumLook?: boolean
}

export type InterModuleAssetPhaseRequest = CodeAssetSelectionInput & {
  enrichedPrompt: string
  imagePrompt?: string
  existingFiles: CodeFile[]
  setPhase: (detail: string, progress: number) => void
  bridgeUrl?: string
  fetchImpl?: FetchLike
  signal?: AbortSignal
}

export type InterModuleAssetPhaseResult = {
  bundle: CodeAssetBundle | null
  files: CodeFile[]
}

const VISUAL_PROJECT_TYPES = new Set([
  'static_web', 'game_web', 'spa_react', 'spa_vue', 'spa_svelte', 'spa_angular',
  'ssr_next', 'ssr_nuxt', 'ssr_sveltekit', 'mobile_android', 'mobile_ios',
  'mobile_flutter', 'mobile_react_native', 'native_electron', 'native_tauri',
  'engine_3d', 'game_native',
])

const VOICE_REQUEST = /\b(voix|voice|tts|narration|narrateur|audio guide|audioguide|lecture audio|synthese vocale)\b/i

export function selectInterModuleAssetKinds(input: CodeAssetSelectionInput): CodeAssetKind[] {
  const selected: CodeAssetKind[] = []
  if (input.wantsImages || VISUAL_PROJECT_TYPES.has(input.projectType)) selected.push('image')
  if (input.wants3D || input.projectType === 'engine_3d') selected.push('model3d')
  if (VOICE_REQUEST.test(input.prompt)) selected.push('voice')
  return Array.from(new Set(selected))
}

export async function runInterModuleAssetPhase({
  enrichedPrompt,
  imagePrompt,
  existingFiles,
  setPhase,
  bridgeUrl,
  fetchImpl,
  signal,
  ...selection
}: InterModuleAssetPhaseRequest): Promise<InterModuleAssetPhaseResult> {
  const requestedKinds = selectInterModuleAssetKinds(selection)
  if (requestedKinds.length === 0) return { bundle: null, files: existingFiles }

  try {
    setPhase(`Assets inter-modules: ${requestedKinds.join(', ')}...`, 30)
    const bundle = await generateAssetsForArchetype({
      prompt: enrichedPrompt,
      // #7: image commandee sur le SUJET exact (produit) et non le prompt projet.
      imagePrompt: imagePrompt ?? buildSubjectImagePrompt(selection.prompt),
      archetype: selection.projectType,
      requestedKinds,
      fresh3d: requestedKinds.includes('model3d'),
      allowExisting3d: false,
      bridgeUrl,
      fetchImpl,
      signal,
    })
    setPhase(`Assets integres: ${summarizeAssetBundle(bundle)}.`, 32)
    return { bundle, files: upsertAssetManifestFile(existingFiles, bundle, bridgeUrl) }
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    // Un arret demande par l utilisateur n est pas une degradation a absorber:
    // ce `catch` avalait TOUT, donc appuyer sur Stop pendant la phase d assets
    // laissait le pipeline repartir comme si de rien n etait. Une panne d asset
    // se degrade; une decision de l utilisateur se respecte.
    if (signal?.aborted || isCancellationMessage(message)) throw error
    console.warn('[CodeInterModuleAssets] Echec de la generation:', message)
    setPhase(`Assets inter-modules indisponibles (${message})...`, 32)
    return { bundle: null, files: existingFiles }
  }
}

export function buildInterModuleAssetRoutes(_archetype = 'default'): CodeAssetRoute[] {
  return [
    {
      kind: 'image',
      module: 'image',
      endpoint: '/api/comfyui/image',
      fallbackEndpoints: ['/api/web/image', '/api/web/images'],
      required: true,
    },
    { kind: 'model3d', module: '3d', endpoint: '/api/3d/run-pipeline', required: true },
    {
      kind: 'voice',
      module: 'voice',
      endpoint: '/api/voice/tts',
      fallbackEndpoints: ['/api/voice/synthesize'],
      required: true,
    },
    { kind: 'vision', module: 'vision', endpoint: '/api/code/visual-audit', required: false },
    {
      kind: 'rag_reference',
      module: 'rag',
      endpoint: '/api/web/search',
      fallbackEndpoints: ['/api/web/extract'],
      required: false,
    },
  ]
}

function isAsset(value: unknown): value is CodeGeneratedAsset {
  if (!value || typeof value !== 'object') return false
  const asset = value as Record<string, unknown>
  return typeof asset.id === 'string'
    && (asset.kind === 'image' || asset.kind === 'model3d' || asset.kind === 'voice')
    && typeof asset.path === 'string'
    && typeof asset.mimeType === 'string'
    && typeof asset.bytes === 'number'
    && typeof asset.sourceModule === 'string'
    && typeof asset.bridgeEndpoint === 'string'
    && typeof asset.optimized === 'boolean'
}

export function isCodeAssetBundle(value: unknown): value is CodeAssetBundle {
  if (!value || typeof value !== 'object') return false
  const bundle = value as Record<string, unknown>
  return bundle.schemaVersion === CODE_ASSET_BUNDLE_SCHEMA
    && typeof bundle.createdAt === 'number'
    && typeof bundle.runId === 'string'
    && typeof bundle.prompt === 'string'
    && typeof bundle.archetype === 'string'
    && typeof bundle.outDir === 'string'
    && Array.isArray(bundle.requiredKinds)
    && Array.isArray(bundle.missingRequired)
    && Array.isArray(bundle.assets)
    && bundle.assets.every(isAsset)
}

export function summarizeAssetBundle(bundle: CodeAssetBundle): string {
  const byKind = new Map<string, number>()
  for (const asset of bundle.assets) byKind.set(asset.kind, (byKind.get(asset.kind) ?? 0) + 1)
  const parts = Array.from(byKind.entries()).map(([kind, count]) => `${kind}:${count}`)
  const missing = bundle.missingRequired.length ? ` · manquants:${bundle.missingRequired.join(',')}` : ''
  const deferred = bundle.deferred?.length ? ` · differes:${bundle.deferred.length}` : ''
  return `${bundle.assets.length} asset(s) fichier(s) (${parts.join(', ') || 'aucun'})${missing}${deferred}`
}

function absoluteAssetUrl(bridgeUrl: string, value?: string): string | undefined {
  if (!value) return undefined
  if (/^https?:\/\//i.test(value)) return value
  return `${bridgeUrl.replace(/\/$/, '')}/${value.replace(/^\//, '')}`
}

export function buildAssetManifestFile(bundle: CodeAssetBundle, bridgeUrl = getBridgeUrl()): CodeFile {
  return {
    name: CODE_ASSET_MANIFEST_PATH,
    language: 'json',
    content: JSON.stringify({
      schemaVersion: bundle.schemaVersion,
      runId: bundle.runId,
      createdAt: bundle.createdAt,
      integration: {
        preview: 'Utiliser previewUrl et srcset pendant le rendu Aurora.',
        export: 'Utiliser path et projectSrcset dans le projet exporte.',
        inlineBase64: false,
      },
      assets: bundle.assets.map((asset) => ({
        id: asset.id,
        kind: asset.kind,
        role: asset.role,
        path: asset.path,
        previewUrl: absoluteAssetUrl(bridgeUrl, asset.previewUrl),
        mimeType: asset.mimeType,
        srcset: asset.srcset?.split(', ').map((part) => {
          const [url, width] = part.split(' ')
          return `${absoluteAssetUrl(bridgeUrl, url)} ${width}`
        }).join(', '),
        projectSrcset: asset.projectSrcset,
        sourceModule: asset.sourceModule,
        bridgeEndpoint: asset.bridgeEndpoint,
        optimized: asset.optimized,
        variants: asset.variants?.map((variant) => ({
          ...variant,
          previewUrl: absoluteAssetUrl(bridgeUrl, variant.previewUrl),
        })),
      })),
      rag: bundle.rag,
      deferred: bundle.deferred,
    }, null, 2),
  }
}

export function upsertAssetManifestFile(
  files: CodeFile[],
  bundle: CodeAssetBundle | null,
  bridgeUrl = getBridgeUrl(),
): CodeFile[] {
  if (!bundle) return files
  const manifest = buildAssetManifestFile(bundle, bridgeUrl)
  return [...files.filter((file) => file.name !== CODE_ASSET_MANIFEST_PATH), manifest]
}

function combineSignals(signal: AbortSignal | undefined, timeoutSec: number): AbortSignal {
  const timeoutSignal = AbortSignal.timeout(Math.max(5, timeoutSec) * 1000)
  if (!signal) return timeoutSignal
  return typeof AbortSignal.any === 'function' ? AbortSignal.any([signal, timeoutSignal]) : signal
}

export async function generateAssetsForArchetype({
  prompt,
  imagePrompt,
  archetype = 'default',
  requestedKinds = ['image'],
  runId,
  bridgeUrl = getBridgeUrl(),
  fetchImpl = globalThis.fetch.bind(globalThis),
  signal,
  timeoutSec = requestedKinds.includes('model3d') ? 14_400 : 300,
  fresh3d = false,
  allowExisting3d = true,
  sourceImageRunId,
  source3dRunId,
  sourceVoiceRunId,
  threeDTimeoutSec = 14_400,
  seed,
}: GenerateAssetsForArchetypeRequest): Promise<CodeAssetBundle> {
  if (!prompt.trim()) throw new Error('Prompt assets requis')
  const kinds = Array.from(new Set(requestedKinds))
  if (kinds.length === 0) throw new Error('Au moins une famille d assets est requise')
  const response = await fetchImpl(`${bridgeUrl}/api/code/assets/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      prompt,
      ...(imagePrompt ? { imagePrompt } : {}),
      archetype,
      requestedKinds: kinds,
      runId,
      timeoutSec,
      fresh3d,
      allowExisting3d,
      sourceImageRunId,
      source3dRunId,
      sourceVoiceRunId,
      threeDTimeoutSec,
      seed,
      expectedRoutes: buildInterModuleAssetRoutes(archetype),
    }),
    signal: combineSignals(signal, timeoutSec + 10),
  })
  const payload = await response.json().catch(() => null) as null | {
    ok?: boolean
    bundle?: unknown
    error?: string
  }
  if (!response.ok || !payload?.ok || !isCodeAssetBundle(payload.bundle)) {
    throw new Error(payload?.error || `Assets inter-modules HTTP ${response.status}`)
  }
  if (payload.bundle.missingRequired.length > 0) {
    throw new Error(`Assets requis manquants: ${payload.bundle.missingRequired.join(', ')}`)
  }
  return payload.bundle
}
