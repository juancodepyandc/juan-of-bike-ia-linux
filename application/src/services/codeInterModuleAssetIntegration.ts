import { getBridgeUrl } from '../utils/runtime.ts'
import type { CodeFile } from './codeOrchestrator.ts'
import {
  CODE_ASSET_BUNDLE_SCHEMA,
  CODE_ASSET_MANIFEST_PATH,
  type CodeAssetBundle,
  type CodeGeneratedAsset,
} from './codeInterModuleAssets.ts'

export type CodeAssetExportEntry = {
  path: string
  url: string
  mimeType?: string
}

const IMAGE_MARKERS = [
  'PLACEHOLDER_SUBJECT_IMG_6', 'PLACEHOLDER_SUBJECT_IMG_5',
  'PLACEHOLDER_SUBJECT_IMG_4', 'PLACEHOLDER_SUBJECT_IMG_3',
  'PLACEHOLDER_SUBJECT_IMG_2', 'PLACEHOLDER_SUBJECT_IMG_1',
  'PLACEHOLDER_SUBJECT_IMG', 'PLACEHOLDER_IMG_LIFESTYLE2',
  'PLACEHOLDER_IMG_LIFESTYLE1', 'PLACEHOLDER_IMG_DETAIL', 'PLACEHOLDER_IMG_HERO',
]

function absoluteAssetUrl(bridgeUrl: string, value?: string): string | null {
  if (!value) return null
  if (/^https?:\/\//i.test(value)) return value
  return `${bridgeUrl.replace(/\/$/, '')}/${value.replace(/^\//, '')}`
}

function replaceAll(content: string, markers: string[], replacement: string): string {
  let next = content
  for (const marker of markers) next = next.split(marker).join(replacement)
  return next
}

export function applyInterModuleAssetPlaceholders(
  content: string,
  bundle: CodeAssetBundle | null,
  bridgeUrl = getBridgeUrl(),
): string {
  if (!bundle || !content) return content
  let next = content
  const first = (kind: CodeGeneratedAsset['kind']) => bundle.assets.find((asset) => asset.kind === kind)
  const imageUrl = absoluteAssetUrl(bridgeUrl, first('image')?.previewUrl)
  const modelUrl = absoluteAssetUrl(bridgeUrl, first('model3d')?.previewUrl)
  const voiceUrl = absoluteAssetUrl(bridgeUrl, first('voice')?.previewUrl)
  if (imageUrl) next = replaceAll(next, IMAGE_MARKERS, imageUrl)
  if (modelUrl) next = replaceAll(next, ['PLACEHOLDER_MODEL_3D', 'PLACEHOLDER_ASSET_GLB'], modelUrl)
  if (voiceUrl) next = replaceAll(next, ['PLACEHOLDER_VOICE_NARRATION', 'PLACEHOLDER_ASSET_VOICE'], voiceUrl)
  return next
}

export function materializeInterModuleAssetReferences(
  files: CodeFile[],
  bundle: CodeAssetBundle | null,
  bridgeUrl = getBridgeUrl(),
): CodeFile[] {
  if (!bundle) return files
  return files.map((file) => ({
    ...file,
    content: applyInterModuleAssetPlaceholders(file.content, bundle, bridgeUrl),
  }))
}

function isSafeProjectAssetPath(path: string): boolean {
  return path.startsWith('assets/generated/')
    && !path.startsWith('/')
    && !path.split('/').includes('..')
}

export function collectAssetExportEntries(files: CodeFile[]): CodeAssetExportEntry[] {
  const manifest = files.find((file) => file.name === CODE_ASSET_MANIFEST_PATH)
  if (!manifest) return []
  let parsed: unknown
  try { parsed = JSON.parse(manifest.content) } catch { return [] }
  if (!parsed || typeof parsed !== 'object') return []
  const payload = parsed as { schemaVersion?: unknown; assets?: unknown }
  if (payload.schemaVersion !== CODE_ASSET_BUNDLE_SCHEMA || !Array.isArray(payload.assets)) return []

  const entries = new Map<string, CodeAssetExportEntry>()
  const add = (candidate: unknown) => {
    if (!candidate || typeof candidate !== 'object') return
    const item = candidate as { path?: unknown; previewUrl?: unknown; mimeType?: unknown }
    if (typeof item.path !== 'string' || !isSafeProjectAssetPath(item.path)) return
    if (typeof item.previewUrl !== 'string' || !/^https?:\/\//i.test(item.previewUrl)) return
    entries.set(item.path, {
      path: item.path,
      url: item.previewUrl,
      mimeType: typeof item.mimeType === 'string' ? item.mimeType : undefined,
    })
  }
  for (const asset of payload.assets) {
    add(asset)
    if (asset && typeof asset === 'object' && Array.isArray((asset as { variants?: unknown }).variants)) {
      for (const variant of (asset as { variants: unknown[] }).variants) add(variant)
    }
  }
  return [...entries.values()]
}

export function rewriteAssetUrlsForExport(content: string, entries: CodeAssetExportEntry[]): string {
  let next = content
  for (const entry of entries) next = next.split(entry.url).join(entry.path)
  return next
}
