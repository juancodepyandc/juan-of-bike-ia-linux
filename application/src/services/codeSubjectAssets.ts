import { getBridgeUrl } from '../utils/runtime.ts'
import type { BrandProfile } from './codeIntent.ts'
import type { CodeFile } from './codeOrchestrator.ts'

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
