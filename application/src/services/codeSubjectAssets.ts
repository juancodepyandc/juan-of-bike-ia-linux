import { getBridgeUrl } from '../utils/runtime.ts'
import type { BrandProfile, CodeIntent } from './codeIntent.ts'
import type { CodeFile } from './codeOrchestrator.ts'
import { searchReferenceImages, probeExtension } from './auroraExtensionBridge.ts'
import { buildAuroraInlineSvgDataUri } from './codeVisualFallbacks.ts'

type SubjectImage = { dataUrl: string; source?: string; query?: string }

/**
 * Build up to 4 image search queries for the subject. Brand pages reuse the
 * canonical brand image queries (logo, product, lifestyle); generic subjects
 * fall back to the canonical name + variants.
 */
function buildSubjectImageQueries(intent: CodeIntent): string[] {
  const subject = intent.assetPlan?.subject
  const objectMentions = intent.assetPlan?.objectMentions || []

  const queries: string[] = []

  if (subject?.source === 'brand' && subject.brandProfile?.imageQueries?.length) {
    // Brand path - use the curated queries (logo / product / lifestyle / detail).
    queries.push(...subject.brandProfile.imageQueries.slice(0, 4))
  } else if (subject?.canonical) {
    queries.push(subject.canonical)
    queries.push(`${subject.canonical} photo`)
    queries.push(`${subject.canonical} produit`)
  } else if (objectMentions.length > 0) {
    queries.push(objectMentions[0])
    if (objectMentions[1]) queries.push(objectMentions[1])
  }

  // Deduplicate while preserving order.
  return Array.from(new Set(queries.map((q) => q.trim()).filter(Boolean))).slice(0, 4)
}

/**
 * v71 multi-image fetch.
 *
 * Strategy:
 *   1) Probe the Aurora-Connect extension. When connected, ask it to perform
 *      `searchReferenceImages` with each query - those URLs come from a real
 *      browser tab (Google Images / DuckDuckGo) so they are fresher than what
 *      the Python bridge can search. We then download each URL to a data URL
 *      so the result survives any later save-as.
 *   2) For each remaining query (or all of them if the extension is absent),
 *      POST `/api/web/image` to the local Python bridge - same path as before.
 *   3) Fallback to deterministic inline SVG only if the previous two failed
 *      for a given query.
 *
 * Returns the resolved images in priority order. Empty array on full failure.
 */
export async function fetchSubjectImages(intent: CodeIntent): Promise<SubjectImage[]> {
  const queries = buildSubjectImageQueries(intent)
  if (queries.length === 0) return []

  const out: SubjectImage[] = []
  const seen = new Set<string>()

  // Step 1 - try the extension when reachable.
  let extensionReachable = false
  try {
    const ext = await probeExtension(AbortSignal.timeout(3000))
    extensionReachable = ext !== null
  } catch {
    extensionReachable = false
  }

  if (extensionReachable) {
    for (const query of queries) {
      try {
        const result = await searchReferenceImages(query, { limit: 3, signal: AbortSignal.timeout(15_000) })
        if (!result.ok || result.data.length === 0) continue
        // Keep the first image we manage to download for each query.
        for (const candidate of result.data) {
          if (!candidate.url || seen.has(candidate.url)) continue
          seen.add(candidate.url)
          const dataUrl = await downloadAsDataUrl(candidate.url)
          if (dataUrl) {
            out.push({ dataUrl, source: candidate.url, query })
            break
          }
        }
      } catch {
        // try next query
      }
    }
  }

  // Step 2 - for any query that didn't yield an image yet, ask the Python bridge.
  const yieldedQueries = new Set(out.map((img) => img.query))
  const bridge = getBridgeUrl()
  for (const query of queries) {
    if (yieldedQueries.has(query)) continue
    try {
      const resp = await fetch(`${bridge}/api/web/image`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, width: 1600, height: 900 }),
        signal: AbortSignal.timeout(22_000),
      })
      if (resp.ok) {
        const ct = resp.headers.get('content-type') || ''
        if (!ct.includes('text/html')) {
          const data = await resp.json() as { ok?: boolean; dataUrl?: string; source?: string }
          if (data?.ok && data?.dataUrl && !out.some((img) => img.dataUrl === data.dataUrl)) {
            out.push({ dataUrl: data.dataUrl, source: data.source ?? `bridge:${query}`, query })
            yieldedQueries.add(query)
          }
        }
      }
    } catch {
      // try next query
    }
  }

  // Step 3 - deterministic local fallback for any remaining slot.
  const stillMissing = queries.filter((q) => !yieldedQueries.has(q))
  for (const query of stillMissing) {
    out.push({
      dataUrl: buildAuroraInlineSvgDataUri(query, { width: 1600, height: 900 }),
      source: `inline-svg:${query}`,
      query,
    })
  }

  // Deduplicate by dataUrl prefix in case two queries hit the same image.
  const finalOut: SubjectImage[] = []
  const dataUrlSeen = new Set<string>()
  for (const img of out) {
    const fingerprint = img.dataUrl.slice(0, 256)
    if (dataUrlSeen.has(fingerprint)) continue
    dataUrlSeen.add(fingerprint)
    finalOut.push(img)
    if (finalOut.length >= 4) break
  }
  return finalOut
}

// Enrich brand profile via bridge: Wikipedia summary + Ollama JSON extraction.
// Returns profile (colors, keywords, design vibe) or null for fallback generic page.
export async function fetchBrandProfileFromBridge(brandName: string): Promise<BrandProfile | null> {
  const bridge = getBridgeUrl()
  try {
    const resp = await fetch(`${bridge}/api/brand/enrich`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ brand: brandName }),
      signal: AbortSignal.timeout(50_000),
    })
    if (!resp.ok) return null
    const data = await resp.json() as {
      ok?: boolean
      profile?: {
        primaryColor?: string
        secondaryColor?: string
        tertiaryColor?: string
        productKeywords?: unknown
        designVibe?: string
        typoVibe?: string
        imageQueries?: unknown
        productShape?: string
      }
    }
    if (!data?.ok || !data.profile) return null
    const p = data.profile
    if (!p.primaryColor || !p.designVibe) return null
    if (!Array.isArray(p.productKeywords) || !Array.isArray(p.imageQueries)) return null

    // Sanitise - keep only string entries, cap to reasonable lengths.
    const productKeywords = (p.productKeywords as unknown[])
      .filter((s): s is string => typeof s === 'string' && s.trim().length > 0)
      .slice(0, 6)
    const imageQueries = (p.imageQueries as unknown[])
      .filter((s): s is string => typeof s === 'string' && s.trim().length > 0)
      .slice(0, 4)

    if (productKeywords.length === 0 || imageQueries.length === 0) return null

    const VALID_SHAPES = new Set([
      'can', 'bottle', 'phone', 'tablet', 'laptop',
      'shoe', 'car', 'watch', 'bag', 'headphones',
      'controller', 'console', 'card', 'cup', 'logo', 'building',
    ])
    const productShape = (typeof p.productShape === 'string' && VALID_SHAPES.has(p.productShape))
      ? p.productShape as BrandProfile['productShape']
      : 'logo'

    return {
      primaryColor: p.primaryColor,
      secondaryColor: typeof p.secondaryColor === 'string' && /^#[0-9a-fA-F]{6}$/.test(p.secondaryColor)
        ? p.secondaryColor : undefined,
      tertiaryColor: typeof p.tertiaryColor === 'string' && /^#[0-9a-fA-F]{6}$/.test(p.tertiaryColor)
        ? p.tertiaryColor : undefined,
      productKeywords,
      designVibe: p.designVibe,
      typoVibe: typeof p.typoVibe === 'string' && p.typoVibe.length > 0 ? p.typoVibe : 'sans-serif modern',
      imageQueries,
      productShape,
    }
  } catch {
    return null
  }
}

async function downloadAsDataUrl(url: string): Promise<string | null> {
  try {
    const resp = await fetch(url, { redirect: 'follow', signal: AbortSignal.timeout(15_000) })
    if (!resp.ok) return null
    const blob = await resp.blob()
    if (blob.size < 1024) return null
    return await blobToDataUrl(blob)
  } catch {
    return null
  }
}

function blobToDataUrl(blob: Blob): Promise<string | null> {
  return new Promise((resolve) => {
    const reader = new FileReader()
    reader.onload = () => resolve(typeof reader.result === 'string' ? reader.result : null)
    reader.onerror = () => resolve(null)
    reader.readAsDataURL(blob)
  })
}

/**
 * After the Codeur has produced the full content, swap each literal marker
 * (`PLACEHOLDER_SUBJECT_IMG`, `PLACEHOLDER_SUBJECT_IMG_1`...`_N`) with its
 * real data URL so `<img>` tags load immediately.
 *
 * The first image is bound to both `PLACEHOLDER_SUBJECT_IMG` (legacy single
 * marker, used by older prompts) and `PLACEHOLDER_SUBJECT_IMG_1`. Markers
 * 2..N map to images[1..N-1]. Markers without a matching image are stripped
 * to a transparent 1x1 GIF data URL so the page never shows a broken icon.
 */
export function applySubjectImagePlaceholder(content: string, intent: CodeIntent): string {
  const stash = intent as unknown as { __subjectImageDataUrls?: string[]; __subjectImageDataUrl?: string }
  const images = stash.__subjectImageDataUrls && stash.__subjectImageDataUrls.length > 0
    ? stash.__subjectImageDataUrls
    : (stash.__subjectImageDataUrl ? [stash.__subjectImageDataUrl] : [])

  // Build a fallback URL pyramid even when the bridge yielded zero images.
  // Order : local brand-keyword SVG -> local subject-canonical SVG
  // -> transparent 1x1 GIF (last resort, never broken icon).
  // intent.brand n'existe pas sur CodeIntent - la marque vit dans assetPlan.subject
  // (subject.canonical = "Pepsi", "iphone 15", etc.). On garde une chaine unique.
  const subjectKw =
    intent.assetPlan?.subject?.canonical ||
    'modern product'
  const brandKw = subjectKw
  const TRANSPARENT_GIF =
    'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7'
  const fallbackPool: string[] = images.length > 0
    ? images
    : [
        buildAuroraInlineSvgDataUri(subjectKw, { width: 1600, height: 900 }),
        buildAuroraInlineSvgDataUri(brandKw, { width: 1200, height: 800 }),
        TRANSPARENT_GIF,
      ]

  let next = content

  // Substitute numbered markers first (greedy: _6 before _1 to avoid prefix overlap).
  for (let idx = 6; idx >= 1; idx--) {
    const marker = `PLACEHOLDER_SUBJECT_IMG_${idx}`
    if (!next.includes(marker)) continue
    const url = fallbackPool[(idx - 1) % fallbackPool.length] ?? fallbackPool[0]
    next = next.split(marker).join(url)
  }

  // Then the legacy unnumbered marker - bind to the first url.
  if (next.includes('PLACEHOLDER_SUBJECT_IMG')) {
    next = next.split('PLACEHOLDER_SUBJECT_IMG').join(fallbackPool[0])
  }

  return next
}

/**
 * Follow-up merge: keep every existing file unless the model re-emitted it.
 * Compares by normalised path so "./src/app.js" and "src/app.js" match.
 */
export function mergeExistingWithUpdates(existing: CodeFile[], updates: CodeFile[]): CodeFile[] {
  const norm = (p: string) => p.replace(/^\.\//, '').replace(/\\/g, '/').trim().toLowerCase()
  const updatedNames = new Set(updates.map((f) => norm(f.name)))
  const kept = existing.filter((f) => !updatedNames.has(norm(f.name)))
  return [...kept, ...updates]
}
