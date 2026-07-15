// ---------------------------------------------------------------------------
// codeImageGen — generate REAL images for the Code module via ComfyUI/FLUX.
// Replaces legacy remote placeholder fallbacks when ComfyUI is reachable. Returns
// data URLs ready to embed in <img src="..."> so the saved project never 404s.
// Also exposes a multi-image helper to populate hero + gallery + showcase
// slots for premium archetypes (apple_product, ecommerce, portfolio…).
// ---------------------------------------------------------------------------

import { createFluxWorkflow } from '../utils/fluxWorkflow'
import { parseImageIntent } from '../utils/imagePromptParser'
import {
  comfyuiQueuePrompt,
  comfyuiGetHistory,
  comfyuiGetImage,
  freeGpuBeforeFlux,
} from '../hooks/useTauri'
import {
  extractComfyPromptId,
  waitForComfyResult,
} from '../utils/comfyui'
import { getBridgeUrl, isTauriRuntime } from '../utils/runtime'
import type { CodeIntent } from './codeIntent'
import { detectDesignArchetype } from './codeDesignDirectives'

const COMFY_TIMEOUT_MS = 90_000
const COMFY_PROBE_TIMEOUT_MS = 2_500

export type GeneratedImage = {
  /** Embedded base64 data URL — safe to inline in HTML. */
  dataUrl: string
  /** "flux" when generated locally, otherwise the URL of the fallback source. */
  source: string
  /** Slot the image was generated for: hero / gallery / scenario / detail. */
  slot: string
  /** The prompt used to generate it (for debug + alt text fallback). */
  prompt: string
}

// ---------------------------------------------------------------------------
// ComfyUI availability probe — fast, doesn't block the pipeline if down.
// ---------------------------------------------------------------------------

let _comfyAvailableCache: { value: boolean; ts: number } | null = null
const COMFY_PROBE_CACHE_MS = 30_000

export async function probeComfyUI(): Promise<boolean> {
  if (_comfyAvailableCache && Date.now() - _comfyAvailableCache.ts < COMFY_PROBE_CACHE_MS) {
    return _comfyAvailableCache.value
  }
  try {
    const bridge = getBridgeUrl()
    const candidates: string[] = []
    if (bridge) candidates.push(`${bridge}/api/comfyui/status`)
    candidates.push('http://127.0.0.1:8188/system_stats')

    for (const url of candidates) {
      try {
        const resp = await fetch(url, { signal: AbortSignal.timeout(COMFY_PROBE_TIMEOUT_MS) })
        if (resp.ok) {
          _comfyAvailableCache = { value: true, ts: Date.now() }
          return true
        }
      } catch { /* try next */ }
    }
  } catch {
    // fall through
  }
  _comfyAvailableCache = { value: false, ts: Date.now() }
  return false
}

// ---------------------------------------------------------------------------
// Build ComfyUI image URL after generation completes
// ---------------------------------------------------------------------------

async function fetchComfyImageAsDataUrl(
  filename: string,
  subfolder: string,
): Promise<string | null> {
  try {
    const blob = await comfyuiGetImage(filename, subfolder)
    if (!blob || blob.size < 2000) return null
    return await new Promise<string | null>((resolve) => {
      const reader = new FileReader()
      reader.onload = () => resolve(typeof reader.result === 'string' ? reader.result : null)
      reader.onerror = () => resolve(null)
      reader.readAsDataURL(blob)
    })
  } catch {
    return null
  }
}

// ---------------------------------------------------------------------------
// Build per-slot prompts based on archetype + subject
// ---------------------------------------------------------------------------

type Slot = {
  id: string
  prompt: string
  width: number
  height: number
}

function buildSlotsForArchetype(intent: CodeIntent, prompt: string): Slot[] {
  const archetype = detectDesignArchetype(prompt, intent)
  const subject =
    intent.assetPlan?.subject?.canonical
    || intent.assetPlan?.objectMentions?.[0]
    || prompt.split(/\s+/).slice(0, 6).join(' ')

  const safe = subject.replace(/["\\]/g, '').slice(0, 80)

  // Common visual modifiers that map to "premium product page" output
  const studio = 'studio lighting, 4k, hyperdetailed, soft shadows, clean composition, neutral background, magazine-quality photography'
  const lifestyle = 'cinematic lighting, golden hour, real-world setting, depth of field, candid, premium lifestyle photography'

  switch (archetype) {
    case 'apple_product':
      return [
        { id: 'hero', prompt: `Premium hero shot of ${safe}, centered, ${studio}, on minimal seamless background, professional product photography, ultra-sharp focus`, width: 1280, height: 1280 },
        { id: 'detail', prompt: `Macro detail close-up of ${safe} surface texture and material finish, ${studio}, dramatic side lighting`, width: 1280, height: 720 },
        { id: 'lifestyle1', prompt: `${safe} in real-world use, person interacting with it, ${lifestyle}`, width: 1280, height: 720 },
        { id: 'lifestyle2', prompt: `Aerial flat-lay composition with ${safe} and complementary objects, premium editorial styling, soft daylight`, width: 1280, height: 720 },
      ]
    case 'ecommerce_premium':
      return [
        { id: 'hero', prompt: `Premium ecommerce hero of ${safe}, fashion-editorial composition, ${studio}, high contrast`, width: 1280, height: 1280 },
        { id: 'detail', prompt: `Detail shot of ${safe} with material focus, ${studio}`, width: 800, height: 1000 },
        { id: 'lifestyle1', prompt: `Model wearing/using ${safe}, ${lifestyle}, fashion editorial`, width: 800, height: 1000 },
        { id: 'lifestyle2', prompt: `${safe} flat-lay with complementary props, ${lifestyle}, fashion editorial`, width: 800, height: 1000 },
      ]
    case 'portfolio_immersive':
      return [
        { id: 'hero', prompt: `Abstract atmospheric hero image evoking the spirit of ${safe}, art-direction reference, color graded, cinematic`, width: 1600, height: 1000 },
        { id: 'work1', prompt: `Conceptual project visual related to ${safe}, modern design aesthetic, art direction`, width: 1280, height: 800 },
        { id: 'work2', prompt: `Editorial creative shot tied to ${safe} concept, ${lifestyle}`, width: 1280, height: 800 },
      ]
    case 'editorial_story':
      return [
        { id: 'hero', prompt: `Editorial cover image about ${safe}, photojournalism, narrative depth, real environment, ${lifestyle}`, width: 1600, height: 1000 },
        { id: 'figure1', prompt: `Documentary photograph supporting an article on ${safe}, ${lifestyle}`, width: 1280, height: 800 },
        { id: 'figure2', prompt: `Detail editorial photograph related to ${safe}, ${lifestyle}`, width: 1280, height: 800 },
      ]
    case 'narrative_landing':
    case 'saas_marketing':
      return [
        { id: 'hero', prompt: `Abstract premium tech hero composition representing ${safe}, dark background with gradient mesh, geometric shapes, modern editorial photography`, width: 1280, height: 800 },
        { id: 'feature1', prompt: `Conceptual visual representing the value of ${safe}, modern, futuristic, soft lighting`, width: 800, height: 800 },
        { id: 'feature2', prompt: `Conceptual visual representing scalability of ${safe}, modern, geometric`, width: 800, height: 800 },
      ]
    case 'scroll_3d_journey':
      return [
        { id: 'hero', prompt: `Cinematic atmospheric hero image evoking ${safe}, dramatic lighting, depth, movement, premium 3D-feel`, width: 1600, height: 1000 },
        { id: 'chapter1', prompt: `Cinematic chapter visual tied to ${safe}, dramatic atmosphere`, width: 1280, height: 800 },
        { id: 'chapter2', prompt: `Cinematic chapter visual tied to ${safe}, dramatic atmosphere`, width: 1280, height: 800 },
      ]
    case 'microsite_event':
      return [
        { id: 'hero', prompt: `Energetic event poster atmosphere about ${safe}, vibrant lighting, motion blur, festival mood`, width: 1280, height: 1280 },
        { id: 'venue', prompt: `Wide shot of an event venue evoking ${safe}, ${lifestyle}`, width: 1280, height: 720 },
      ]
    case 'dashboard_dataviz':
      return [
        { id: 'hero', prompt: `Clean abstract data visualization background for a SaaS dashboard about ${safe}, geometric, futuristic`, width: 1280, height: 720 },
      ]
    default:
      return [
        { id: 'hero', prompt: `Premium hero image about ${safe}, ${studio}`, width: 1280, height: 720 },
        { id: 'detail', prompt: `Editorial supporting image about ${safe}, ${lifestyle}`, width: 1280, height: 720 },
      ]
  }
}

// ---------------------------------------------------------------------------
// Single-image generation via FLUX
// ---------------------------------------------------------------------------

async function generateOneImageWithFlux(slot: Slot): Promise<GeneratedImage | null> {
  try {
    // v82bj : same parser application — slot prompts are templated
    // by buildSlotsForArchetype but might still contain user-supplied
    // brand text or descriptions with "without X" / "sans X". Strip
    // those before sending to FLUX so we don't render the un-wanted
    // concept literally.
    const slotIntent = parseImageIntent(slot.prompt)
    const workflow = createFluxWorkflow({
      prompt: slotIntent.cleanedPrompt,
      width: slot.width,
      height: slot.height,
      steps: 18,
      filenamePrefix: `code_${slot.id}`,
      style: 'none',
      seed: null,
      referenceImage: null,
    })

    // Free VRAM if possible — best effort
    try { await freeGpuBeforeFlux([]) } catch { /* ignore */ }

    const queueResult = await comfyuiQueuePrompt(workflow)
    const promptId = extractComfyPromptId(queueResult)
    if (!promptId) return null

    // waitForComfyResult already returns the extracted {filename, subfolder}
    // tuple from extractComfyImageOutput(entry); calling it again on the
    // resolved value would reject with "no image" since the value is no
    // longer a ComfyHistoryEntry. v82n3 — bug surfaced by tsc strict mode.
    const output = await waitForComfyResult(promptId, {
      getHistory: comfyuiGetHistory,
      timeoutMs: COMFY_TIMEOUT_MS,
    })
    if (!output?.filename) return null

    const dataUrl = await fetchComfyImageAsDataUrl(output.filename, output.subfolder || '')
    if (!dataUrl) return null

    return {
      dataUrl,
      source: 'flux',
      slot: slot.id,
      prompt: slot.prompt,
    }
  } catch (err) {
    console.warn(`[codeImageGen] FLUX gen failed for slot ${slot.id}:`, err)
    return null
  }
}

// ---------------------------------------------------------------------------
// Bridge fallback — calls /api/web/image for a single image
// ---------------------------------------------------------------------------

async function fetchOneImageViaBridge(slot: Slot): Promise<GeneratedImage | null> {
  try {
    const bridge = getBridgeUrl()
    const resp = await fetch(`${bridge}/api/web/image`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: slot.prompt.slice(0, 80), width: slot.width, height: slot.height }),
      signal: AbortSignal.timeout(20_000),
    })
    if (!resp.ok) return null
    const ct = resp.headers.get('content-type') || ''
    if (ct.includes('text/html')) return null // bridge returned HTML fallback (404)
    const data = await resp.json() as { ok?: boolean; dataUrl?: string; source?: string }
    if (!data?.ok || !data?.dataUrl) return null
    return { dataUrl: data.dataUrl, source: data.source || 'bridge', slot: slot.id, prompt: slot.prompt }
  } catch {
    return null
  }
}

// ---------------------------------------------------------------------------
// Public API — generate a list of images for the current archetype
// ---------------------------------------------------------------------------

export type GenerateImagesOptions = {
  /** Cap on number of images to actually run (UX vs. compute trade-off). */
  maxImages?: number
  /** When true, never fall back to bridge — only attempt FLUX. */
  fluxOnly?: boolean
}

/**
 * Generate the set of images the current archetype expects.
 *
 *  1. Probe ComfyUI. If reachable, run FLUX for each slot.
 *  2. For every FLUX failure, fall back to the bridge `/api/web/image`
 *     unless `fluxOnly` is set.
 *  3. Return only the images that actually came back as data URLs — so the
 *     orchestrator can decide whether the page should still try to embed them.
 */
export async function generateImagesForArchetype(
  prompt: string,
  intent: CodeIntent,
  opts: GenerateImagesOptions = {},
): Promise<GeneratedImage[]> {
  const slots = buildSlotsForArchetype(intent, prompt).slice(0, opts.maxImages ?? 4)
  const fluxAvailable = await probeComfyUI()

  const out: GeneratedImage[] = []
  for (const slot of slots) {
    let img: GeneratedImage | null = null
    if (fluxAvailable) {
      img = await generateOneImageWithFlux(slot)
    }
    if (!img && !opts.fluxOnly) {
      img = await fetchOneImageViaBridge(slot)
    }
    if (img) out.push(img)
  }
  return out
}

/**
 * Format the generated image set as a system-prompt block injectable into the
 * Codeur context. Each image is paired with a unique placeholder marker
 * (PLACEHOLDER_IMG_HERO, PLACEHOLDER_IMG_DETAIL…) the orchestrator swaps with
 * the actual data URL after generation.
 */
export function serializeGeneratedImagesBlock(images: GeneratedImage[]): {
  block: string
  placeholders: Record<string, string>
} {
  if (images.length === 0) return { block: '', placeholders: {} }

  const placeholders: Record<string, string> = {}
  const lines: string[] = [
    '## IMAGES PRE-GENEREES POUR TOI (utilise-les directement)',
    '- Plusieurs images premium ont ete generees en amont via FLUX (ou source web). Tu DOIS les utiliser dans ta page plutot que d en chercher d autres.',
    '- Pour chaque image, je te donne un placeholder. Tu utilises EXACTEMENT le placeholder dans le HTML, ex: `<img src="PLACEHOLDER_IMG_HERO" alt="...">`. L orchestrateur remplacera le placeholder par la data URL reelle au moment de la livraison.',
    '- Tu peux reutiliser le meme placeholder dans plusieurs sections (hero, showcase, footer) si pertinent.',
    '',
    'Liste des placeholders disponibles:',
  ]

  for (const img of images) {
    const ph = `PLACEHOLDER_IMG_${img.slot.toUpperCase()}`
    placeholders[ph] = img.dataUrl
    lines.push(`- \`${ph}\` — ${img.prompt.slice(0, 140)} (source: ${img.source}).`)
  }

  return {
    block: lines.join('\n'),
    placeholders,
  }
}

/**
 * Apply placeholder substitution to the streamed Codeur output.
 * Idempotent — running it twice is a no-op.
 */
export function applyImagePlaceholders(content: string, placeholders: Record<string, string>): string {
  if (!content || Object.keys(placeholders).length === 0) return content
  let next = content
  for (const [ph, dataUrl] of Object.entries(placeholders)) {
    if (!next.includes(ph)) continue
    next = next.split(ph).join(dataUrl)
  }
  return next
}

// Re-export the runtime helper so other modules can detect Tauri without
// pulling the heavy useTauri module directly.
export { isTauriRuntime }
