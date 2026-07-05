import { ollamaChat } from '../hooks/useTauri'

export type ReferenceEntity = {
  label: string
  /** Normalized bounding box in [0, 1] coordinates */
  bbox: { x: number; y: number; w: number; h: number }
  confidence: number
  matchesPrompt: boolean
  /** Short one-line description — "a tall athletic character in green hoodie" */
  description: string
}

export type ReferencePaletteEntry = {
  hex: string
  /** Natural-language role: "body", "accent", "detail", "trim", "eyes", etc. */
  zone: string
  /** 0–1 — how much of the subject this colour occupies */
  prominence: number
}

export type ReferenceVisibleText = {
  text: string
  /** Natural description — "printed on the left fan", "stitched on the chest" */
  location: string
  family: 'logo' | 'label' | 'model-number' | 'brand' | 'caption' | 'other'
}

export type VisualReferenceAnalysis = {
  entities: ReferenceEntity[]
  palette: ReferencePaletteEntry[]
  visibleText: ReferenceVisibleText[]
  dominantEntityIndex: number
  subjectDescription: string
  notes: string
}

const HEX_RE = /^#([a-fA-F0-9]{6}|[a-fA-F0-9]{3})$/

function extractJsonObject<T>(raw: string): T | null {
  const match = raw.match(/\{[\s\S]*\}/)
  if (!match) return null
  try {
    return JSON.parse(match[0]) as T
  } catch {
    return null
  }
}

function clampUnit(value: unknown, fallback = 0): number {
  const n = typeof value === 'number' ? value : Number(value)
  if (!Number.isFinite(n)) return fallback
  if (n < 0) return 0
  if (n > 1) return 1
  return n
}

function sanitizeBbox(raw: unknown): ReferenceEntity['bbox'] {
  const obj = (raw || {}) as Record<string, unknown>
  // Accept both {x,y,w,h} and {x,y,width,height}
  const x = clampUnit(obj.x, 0)
  const y = clampUnit(obj.y, 0)
  const rawW = obj.w ?? obj.width
  const rawH = obj.h ?? obj.height
  let w = clampUnit(rawW, 1 - x)
  let h = clampUnit(rawH, 1 - y)
  if (w <= 0) w = Math.max(0.02, 1 - x)
  if (h <= 0) h = Math.max(0.02, 1 - y)
  if (x + w > 1) w = 1 - x
  if (y + h > 1) h = 1 - y
  return { x, y, w, h }
}

function sanitizeHex(raw: unknown): string | null {
  if (typeof raw !== 'string') return null
  const trimmed = raw.trim()
  const withHash = trimmed.startsWith('#') ? trimmed : `#${trimmed}`
  if (!HEX_RE.test(withHash)) return null
  if (withHash.length === 4) {
    const [, r, g, b] = withHash
    return `#${r}${r}${g}${g}${b}${b}`.toLowerCase()
  }
  return withHash.toLowerCase()
}

function sanitizePalette(raw: unknown): ReferencePaletteEntry[] {
  if (!Array.isArray(raw)) return []
  const entries: ReferencePaletteEntry[] = []
  for (const item of raw) {
    if (!item || typeof item !== 'object') continue
    const hex = sanitizeHex((item as Record<string, unknown>).hex)
    if (!hex) continue
    const zone = String((item as Record<string, unknown>).zone || 'body').slice(0, 40) || 'body'
    const prominence = clampUnit((item as Record<string, unknown>).prominence, 0.2)
    entries.push({ hex, zone, prominence })
    if (entries.length >= 8) break
  }
  // Sort by prominence descending so the main colours render first in the UI
  return entries.sort((a, b) => b.prominence - a.prominence)
}

function sanitizeTextList(raw: unknown): ReferenceVisibleText[] {
  if (!Array.isArray(raw)) return []
  const items: ReferenceVisibleText[] = []
  for (const item of raw) {
    if (!item || typeof item !== 'object') continue
    const obj = item as Record<string, unknown>
    const text = String(obj.text || '').trim()
    if (!text) continue
    const location = String(obj.location || '').slice(0, 120)
    const rawFamily = String(obj.family || 'other').toLowerCase()
    const family: ReferenceVisibleText['family'] =
      rawFamily === 'logo' || rawFamily === 'label' || rawFamily === 'model-number'
        || rawFamily === 'brand' || rawFamily === 'caption'
        ? rawFamily as ReferenceVisibleText['family']
        : 'other'
    items.push({ text: text.slice(0, 80), location, family })
    if (items.length >= 10) break
  }
  return items
}

function sanitizeEntities(raw: unknown, userRequestedSubject: string): ReferenceEntity[] {
  if (!Array.isArray(raw)) return []
  const wanted = userRequestedSubject.toLowerCase()
  const entities: ReferenceEntity[] = []
  for (const item of raw) {
    if (!item || typeof item !== 'object') continue
    const obj = item as Record<string, unknown>
    const label = String(obj.label || '').trim().slice(0, 60)
    if (!label) continue
    const confidence = Math.round(clampUnit(obj.confidence, 0.6) * 100)
    const description = String(obj.description || '').slice(0, 200)
    const bbox = sanitizeBbox(obj.bbox)
    let matchesPrompt: boolean
    if (typeof obj.matchesPrompt === 'boolean') {
      matchesPrompt = obj.matchesPrompt
    } else if (wanted) {
      matchesPrompt = label.toLowerCase().includes(wanted)
        || wanted.includes(label.toLowerCase())
        || description.toLowerCase().includes(wanted)
    } else {
      matchesPrompt = entities.length === 0
    }
    entities.push({ label, bbox, confidence: confidence / 100, matchesPrompt, description })
    if (entities.length >= 8) break
  }
  return entities
}

function pickDominantEntity(entities: ReferenceEntity[]): number {
  if (entities.length === 0) return -1
  let bestIndex = 0
  let bestScore = -1
  for (let i = 0; i < entities.length; i++) {
    const e = entities[i]
    const area = e.bbox.w * e.bbox.h
    const score = e.confidence * 0.5 + area * 0.3 + (e.matchesPrompt ? 0.4 : 0)
    if (score > bestScore) {
      bestScore = score
      bestIndex = i
    }
  }
  return bestIndex
}

function buildSystemPrompt() {
  return [
    '/no_think',
    'You are a vision analyst extracting structured data from a single reference image.',
    'The image will be used to reconstruct a faithful 3D model, so precision matters.',
    '',
    'Return ONLY a valid JSON object with this EXACT shape:',
    '{',
    '  "entities": [',
    '    {',
    '      "label": "short noun phrase (e.g. \'white dog\', \'GPU\', \'female character\')",',
    '      "description": "one short sentence describing the entity visually",',
    '      "bbox": { "x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0 },  // normalized 0-1, top-left origin',
    '      "confidence": 0.0-1.0,',
    '      "matchesPrompt": true|false  // does this entity match the user\'s request?',
    '    }',
    '  ],',
    '  "palette": [',
    '    { "hex": "#RRGGBB", "zone": "body|accent|detail|trim|eyes|hair|skin|background|...", "prominence": 0.0-1.0 }',
    '  ],',
    '  "visibleText": [',
    '    { "text": "exact characters you can read", "location": "natural description", "family": "logo|label|model-number|brand|caption|other" }',
    '  ],',
    '  "subjectDescription": "one paragraph richly describing the PRIMARY subject the user wants",',
    '  "notes": "any artifacts, occlusions, watermarks or confusing features worth knowing"',
    '}',
    '',
    'RULES:',
    '- List EVERY distinct physical entity visible (people, animals, products, vehicles, labels). Do NOT merge two dogs into one "dogs" entry.',
    '- bbox is in normalized coordinates with 0,0 top-left and 1,1 bottom-right.',
    '- palette: 3-6 HEX colours that actually appear on the PRIMARY subject. Order by visual prominence.',
    '- visibleText: transcribe EVERY text you can read verbatim (logos, model numbers, brand labels, stitched names). If nothing is readable, return [].',
    '- subjectDescription MUST focus on the entity the user asked for, not every entity.',
    '- matchesPrompt is true only if the entity is the one the user specifically requested.',
    '- If the user asks for "the dog" and the photo shows two dogs, set matchesPrompt=true only on the one that best fits (e.g. the larger one, the one in foreground, or the one matching any other qualifier in the prompt).',
    '- Output ONLY the JSON object. No surrounding text.',
  ].join('\n')
}

async function blobToBase64(blob: Blob): Promise<string> {
  const bytes = await blob.arrayBuffer()
  const chunks: string[] = []
  const view = new Uint8Array(bytes)
  const CHUNK = 0x8000
  for (let i = 0; i < view.length; i += CHUNK) {
    chunks.push(String.fromCharCode.apply(null, Array.from(view.subarray(i, i + CHUNK))))
  }
  return btoa(chunks.join(''))
}

export async function analyzeReferenceImage({
  blob,
  model,
  prompt,
  userRequestedSubject,
  maxAttempts = 2,
}: {
  blob: Blob
  model: string
  prompt: string
  userRequestedSubject?: string
  maxAttempts?: number
}): Promise<VisualReferenceAnalysis> {
  const wanted = (userRequestedSubject || prompt).trim()
  const base64 = await blobToBase64(blob)

  const userMessage = [
    `User prompt (what they want as a 3D model): ${prompt}`,
    wanted && wanted !== prompt ? `Specific subject they asked for: ${wanted}` : '',
    'Analyze the reference image and return the JSON object only.',
  ].filter(Boolean).join('\n')

  let lastRaw = ''
  let attempts = 0
  while (attempts < maxAttempts) {
    attempts++
    try {
      const response = await ollamaChat(model, [
        { role: 'system', content: buildSystemPrompt() },
        { role: 'user', content: userMessage, images: [base64] },
      ], 0.05)
      const raw = (response?.message?.content || '').trim()
      lastRaw = raw
      const cleaned = raw.replace(/<think>[\s\S]*?<\/think>/g, '').replace(/<think>[\s\S]*$/g, '').trim()
      const parsed = extractJsonObject<{
        entities?: unknown
        palette?: unknown
        visibleText?: unknown
        subjectDescription?: unknown
        notes?: unknown
      }>(cleaned)
      if (!parsed) continue

      const entities = sanitizeEntities(parsed.entities, wanted)
      const palette = sanitizePalette(parsed.palette)
      const visibleText = sanitizeTextList(parsed.visibleText)
      const dominantEntityIndex = pickDominantEntity(entities)
      const subjectDescription = String(parsed.subjectDescription || '').trim().slice(0, 1200)
      const notes = String(parsed.notes || '').trim().slice(0, 400)

      return {
        entities,
        palette,
        visibleText,
        dominantEntityIndex,
        subjectDescription,
        notes,
      }
    } catch (err) {
      lastRaw = err instanceof Error ? err.message : String(err)
    }
  }

  return {
    entities: [],
    palette: [],
    visibleText: [],
    dominantEntityIndex: -1,
    subjectDescription: '',
    notes: lastRaw ? `Vision analyzer indisponible: ${lastRaw.slice(0, 200)}` : 'Analyse visuelle non disponible.',
  }
}

const COLOR_NAME_MAP: Record<string, string> = {
  rouge: '#d0211a', red: '#d0211a', ecarlate: '#c8202a',
  bleu: '#1e66f5', blue: '#1e66f5', marine: '#0a2c66',
  vert: '#1f8a3b', green: '#1f8a3b', emeraude: '#0f7a50',
  jaune: '#f5c515', yellow: '#f5c515', doré: '#d4a017', dore: '#d4a017', gold: '#d4a017',
  orange: '#ef6c1a',
  violet: '#8840d8', purple: '#8840d8',
  rose: '#e85ca8', pink: '#e85ca8',
  noir: '#0d0d10', black: '#0d0d10',
  blanc: '#f6f6f8', white: '#f6f6f8',
  gris: '#6b6b70', grey: '#6b6b70', gray: '#6b6b70',
  argent: '#c0c0c8', silver: '#c0c0c8',
  marron: '#5e3a1e', brun: '#5e3a1e', brown: '#5e3a1e',
  turquoise: '#1fb9b4', cyan: '#1fb9b4',
  beige: '#d9c9a8',
}

const ZONE_SYNONYMS: Record<string, string[]> = {
  body: ['body', 'corps', 'main body', 'chassis', 'shell', 'coque'],
  accent: ['accent', 'detail', 'trim', 'finition', 'liseret'],
  eyes: ['eyes', 'yeux', 'iris'],
  hair: ['hair', 'cheveux', 'pelage', 'fur'],
  skin: ['skin', 'peau', 'complexion'],
  clothing: ['clothes', 'clothing', 'costume', 'vetement', 'veste', 'top', 'shirt'],
  pants: ['pants', 'trousers', 'pantalon'],
  blades: ['blade', 'blades', 'pale', 'pales', 'fan blades', 'vent'],
  casing: ['case', 'boitier', 'boîtier', 'housing', 'enclosure'],
  led: ['led', 'rgb', 'argb', 'lumineux', 'light'],
}

function normalizeZoneTerm(raw: string): string {
  const cleaned = raw.toLowerCase().trim()
  for (const [canonical, synonyms] of Object.entries(ZONE_SYNONYMS)) {
    if (synonyms.some((s) => cleaned.includes(s))) return canonical
  }
  return cleaned || 'accent'
}

export type ColorOverride = {
  zone: string
  hex: string
  source: 'prompt' | 'user'
}

/**
 * Parse natural-language colour instructions from the user prompt.
 * Examples:
 *   "les pales rouge, le boîtier noir"
 *   "body in navy blue with gold accents"
 *   "yeux violet, cheveux blond"
 * Returns overrides keyed by the canonical zone they target.
 */
export function parseColorOverridesFromPrompt(prompt: string): ColorOverride[] {
  if (!prompt) return []
  const overrides: ColorOverride[] = []

  // Pattern 1: "ZONE en COLOR" or "ZONE COLOR" separated by comma / conjunction
  const tokens = prompt
    .replace(/[\n;]/g, ',')
    .split(/[,]+/)
    .map((piece) => piece.trim())
    .filter(Boolean)

  for (const piece of tokens) {
    // Find a colour word anywhere in the piece
    const colorMatch = piece
      .toLowerCase()
      .match(new RegExp(`\\b(${Object.keys(COLOR_NAME_MAP).join('|')})\\b`))
    const hexMatch = piece.match(HEX_RE)
    if (!colorMatch && !hexMatch) continue

    const hex = hexMatch
      ? sanitizeHex(hexMatch[0]) || COLOR_NAME_MAP[colorMatch![1]]
      : COLOR_NAME_MAP[colorMatch![1]]
    if (!hex) continue

    const beforeColor = colorMatch ? piece.slice(0, piece.toLowerCase().indexOf(colorMatch[1])) : piece
    const afterColor = colorMatch ? piece.slice(piece.toLowerCase().indexOf(colorMatch[1]) + colorMatch[1].length) : ''
    const zonePhrase = (beforeColor + ' ' + afterColor).replace(/\b(en|in|de|du|des|la|le|les|un|une)\b/gi, ' ').trim()
    const zone = normalizeZoneTerm(zonePhrase || 'accent')
    overrides.push({ zone, hex, source: 'prompt' })
  }

  // Deduplicate by zone, keep the LAST mention so later prompt words win
  const deduped = new Map<string, ColorOverride>()
  for (const entry of overrides) deduped.set(entry.zone, entry)
  return Array.from(deduped.values())
}

/**
 * Merge analyzer palette with user/prompt overrides so that synthetic views
 * and correction prompts always pull from a single authoritative colour list.
 */
export function mergePaletteWithOverrides(
  palette: ReferencePaletteEntry[],
  overrides: ColorOverride[],
): ReferencePaletteEntry[] {
  if (overrides.length === 0) return palette
  const byZone = new Map<string, ReferencePaletteEntry>()
  for (const entry of palette) byZone.set(normalizeZoneTerm(entry.zone), { ...entry })
  for (const override of overrides) {
    const zone = normalizeZoneTerm(override.zone)
    const existing = byZone.get(zone)
    byZone.set(zone, {
      hex: override.hex,
      zone,
      prominence: existing ? Math.max(existing.prominence, 0.8) : 0.75,
    })
  }
  return Array.from(byZone.values()).sort((a, b) => b.prominence - a.prominence)
}

/**
 * Produce a compact string the FLUX prompt builder can splice in.
 * e.g. "use EXACT colours: body #1b2530, accent #d7a84a, eyes #2b6bff"
 */
export function formatPaletteInstruction(palette: ReferencePaletteEntry[]): string {
  if (palette.length === 0) return ''
  const joined = palette
    .slice(0, 6)
    .map((entry) => `${entry.zone} ${entry.hex}`)
    .join(', ')
  return `use these exact colours across all views (keep them consistent front/back/sides): ${joined}`
}

export function formatTextInstruction(visibleText: ReferenceVisibleText[]): string {
  if (visibleText.length === 0) return ''
  const joined = visibleText
    .slice(0, 6)
    .map((entry) => `"${entry.text}" (${entry.family}) at ${entry.location || 'its natural location'}`)
    .join('; ')
  return `REPLICATE VERBATIM any visible text — do NOT invent or scramble characters: ${joined}`
}

export function formatEntityFocusInstruction(
  entities: ReferenceEntity[],
  focusIndex: number,
): string {
  if (entities.length <= 1 || focusIndex < 0) return ''
  const focus = entities[focusIndex]
  const others = entities.filter((_, i) => i !== focusIndex).slice(0, 4)
  if (!focus) return ''
  const ignoreList = others.length > 0
    ? ` Ignore the other entities in the reference (${others.map((e) => e.label).join(', ')}) — they must NOT appear in the 3D output.`
    : ''
  return `FOCUS: the 3D subject is strictly "${focus.label}" (${focus.description || 'primary entity'}).${ignoreList}`
}
