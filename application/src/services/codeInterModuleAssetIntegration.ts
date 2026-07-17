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

function collectImageAssetUrls(bundle: CodeAssetBundle, bridgeUrl: string): string[] {
  const urls: string[] = []
  for (const asset of bundle.assets) {
    if (asset.kind !== 'image') continue
    const main = absoluteAssetUrl(bridgeUrl, asset.previewUrl)
    if (main) urls.push(main)
    for (const variant of asset.variants ?? []) {
      const v = absoluteAssetUrl(bridgeUrl, variant.previewUrl)
      if (v && !urls.includes(v)) urls.push(v)
    }
  }
  return urls
}

/**
 * Filet DETERMINISTE (independant du modele). Le modele hotlink souvent des
 * images externes (images.unsplash.com etc.) — souvent HORS-SUJET (iPhone au
 * lieu d'AirPods) — au lieu d'utiliser l'asset REEL genere pour le sujet. On
 * reecrit donc tout <img src="http externe"> et url(http externe) vers l'asset
 * local du bundle: la vraie image du sujet apparait MEME si le modele a ignore
 * le contrat PLACEHOLDER. Les data:/chemins locaux/markers deja materialises ne
 * sont pas touches. Plusieurs assets -> on alterne pour varier.
 */
function rewriteExternalImagesToBundle(content: string, imageUrls: string[]): string {
  if (imageUrls.length === 0) return content
  let i = 0
  const nextUrl = () => imageUrls[(i++) % imageUrls.length]
  let next = content.replace(
    /(<img\b[^>]*?\bsrc\s*=\s*["'])(https?:\/\/[^"']+)(["'])/gi,
    (_m, pre: string, _url: string, post: string) => `${pre}${nextUrl()}${post}`,
  )
  next = next.replace(
    /url\(\s*(["']?)(https?:\/\/[^"')]+\.(?:jpg|jpeg|png|webp|avif|gif))\1\s*\)/gi,
    (_m, q: string) => `url(${q}${nextUrl()}${q})`,
  )
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
  const imageUrls = collectImageAssetUrls(bundle, bridgeUrl)
  const imageUrl = imageUrls[0] ?? absoluteAssetUrl(bridgeUrl, first('image')?.previewUrl)
  const modelUrl = absoluteAssetUrl(bridgeUrl, first('model3d')?.previewUrl)
  const voiceUrl = absoluteAssetUrl(bridgeUrl, first('voice')?.previewUrl)
  if (imageUrl) next = replaceAll(next, IMAGE_MARKERS, imageUrl)
  if (modelUrl) next = replaceAll(next, ['PLACEHOLDER_MODEL_3D', 'PLACEHOLDER_ASSET_GLB'], modelUrl)
  if (voiceUrl) next = replaceAll(next, ['PLACEHOLDER_VOICE_NARRATION', 'PLACEHOLDER_ASSET_VOICE'], voiceUrl)
  // Filet: apres les markers, forcer l'usage de l'asset local sur tout hotlink restant.
  if (imageUrls.length > 0) next = rewriteExternalImagesToBundle(next, imageUrls)
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
