import { ollamaChat } from '../hooks/useTauri.ts'
import type { PreparedContextFile } from '../utils/multimodalContext.ts'
import { findBestReferenceVisual, type ReferenceSearchProfile, type ReferenceVisualSelection } from './referenceVisualResearch.ts'
import type { ThreeDReferenceSupport } from './threeDReferenceSupport.ts'
import type { ThreeDIntent } from './threeDIntent.ts'
import { isPersonReproductionPrompt } from './threeDClarification.ts'
import {
  formatPaletteInstruction,
  formatTextInstruction,
  formatEntityFocusInstruction,
  type ReferenceEntity,
  type ReferencePaletteEntry,
  type ReferenceVisibleText,
} from './visualReferenceAnalyzer.ts'

export type ThreeDViewOverlay = {
  palette?: ReferencePaletteEntry[]
  visibleText?: ReferenceVisibleText[]
  entities?: ReferenceEntity[]
  focusEntityIndex?: number
  colorPromptNote?: string
  extraFidelityLines?: string[]
  /**
   * Structural facts pulled from web research or manual specs, e.g.
   *   ["Strimer V2 Plus routes 12 RGB light guides in parallel",
   *    "Lian Li combs spaced every 12mm",
   *    "24-pin male ATX connector on one end, 24-pin female on the other"]
   * Injected into every FLUX view directive so the shape stays coherent with
   * both the user-uploaded reference AND the product knowledge the assistant
   * dug up online.
   */
  researchAnchors?: string[]
  /** Small high-frequency features that must not be flattened into blobs. */
  detailFocusZones?: string[]
}

export type ThreeDViewTag = 'front' | 'back' | 'left' | 'right'
export type ThreeDViewSourceKind = 'user' | 'external' | 'reuse' | 'synthetic'

export type ResolvedPreparedViews = {
  enabled: boolean
  assignments: Array<{ view: ThreeDViewTag; file: PreparedContextFile }>
  primary: PreparedContextFile | null
  summary: string | null
  inferredFromOrder: boolean
}

export type ThreeDViewVerification = {
  view: ThreeDViewTag
  passed: boolean
  angleCorrect: boolean
  subjectPresent: boolean
  singleEntity: boolean
  functionalDetailsFound: string[]
  functionalDetailsMissing: string[]
  lightingCoherent: boolean
  notes: string
}

export type ThreeDViewAssignment = {
  view: ThreeDViewTag
  sourceKind: ThreeDViewSourceKind
  file?: PreparedContextFile
  externalReference?: ReferenceVisualSelection
  reuseFrom?: ThreeDViewTag
  /** FLUX prompt used when sourceKind === 'synthetic' */
  syntheticPrompt?: string
  /** Blob for synthetic or materialized external views */
  resolvedBlob?: Blob
  verification?: ThreeDViewVerification
  notes: string[]
}

export type ThreeDViewPlan = {
  shouldUseMultiview: boolean
  primaryView: ThreeDViewTag
  assignments: ThreeDViewAssignment[]
  sourceNotes: string[]
  verificationNotes: string[]
  lightingNotes: string[]
  functionalVerificationSummary: string[]
  inferredFromOrder: boolean
}

type ViewStrategy = {
  needsMultiview: boolean
  requiredViews: ThreeDViewTag[]
  optionalViews: ThreeDViewTag[]
  reuseMap: Partial<Record<ThreeDViewTag, ThreeDViewTag>>
  verificationChecks: string[]
  lightingRequirements: string[]
  viewRequirements: Partial<Record<ThreeDViewTag, string[]>>
  /** Per-view FLUX generation directives for autonomous synthetic generation */
  viewGenerationDirectives: Partial<Record<ThreeDViewTag, string>>
}

const VIEW_ORDER: ThreeDViewTag[] = ['front', 'left', 'back', 'right']

function uniqueStrings(values: string[]) {
  return Array.from(new Set(values.map((value) => value.trim()).filter(Boolean)))
}

function short(text: string, limit = 180) {
  const normalized = text.replace(/\s+/g, ' ').trim()
  return normalized.length <= limit ? normalized : `${normalized.slice(0, limit)}...`
}

function extractJson<T>(text: string): T | null {
  const match = text.match(/\{[\s\S]*\}/)
  if (!match) return null

  try {
    return JSON.parse(match[0]) as T
  } catch {
    return null
  }
}

export function normalizeNameTokens(name: string) {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim().split(/\s+/).filter(Boolean)
}

export function detectReferenceViewTag(name: string): ThreeDViewTag | null {
  const normalized = normalizeNameTokens(name)
  // 31/07: l'utilisateur nomme naturellement ses fichiers « face » et
  // « dos » — ces mots n'etaient PAS reconnus, sa vraie vue de dos etait
  // ignoree et MV-Adapter re-inventait un dos par-dessus.
  if (normalized.includes('front') || normalized.includes('avant') || normalized.includes('face')) return 'front'
  if (normalized.includes('back') || normalized.includes('rear') || normalized.includes('arriere') || normalized.includes('dos')) return 'back'
  if (normalized.includes('left') || normalized.includes('gauche')) return 'left'
  if (normalized.includes('right') || normalized.includes('droite') || normalized.includes('profil')) return 'right'
  return null
}

export function resolvePreparedReferenceViews(files: PreparedContextFile[]): ResolvedPreparedViews {
  const imageFiles = files.filter((file) => file.kind === 'image' && file.stagedPath)
  const assigned = new Map<ThreeDViewTag, PreparedContextFile>()
  const leftovers: PreparedContextFile[] = []
  let inferredFromOrder = false

  for (const file of imageFiles) {
    const tag = detectReferenceViewTag(file.name)
    if (tag && !assigned.has(tag)) {
      assigned.set(tag, file)
      continue
    }
    leftovers.push(file)
  }

  // If only ONE image uploaded with no filename view tag, assign it to 'front' by default
  // so the multiview planner can generate complementary views from it
  if (imageFiles.length === 1 && assigned.size === 0 && leftovers.length === 1) {
    assigned.set('front', leftovers.shift()!)
    inferredFromOrder = true
  } else {
    for (const view of VIEW_ORDER) {
      if (assigned.has(view) || leftovers.length === 0) continue
      assigned.set(view, leftovers.shift()!)
      inferredFromOrder = true
    }
  }

  const assignments = VIEW_ORDER.flatMap((view) => {
    const file = assigned.get(view)
    return file ? [{ view, file }] : []
  })
  const primary = assigned.get('front') || assignments[0]?.file || null

  return {
    // Enable multiview even with just 1 image so complementary views get generated
    enabled: assignments.length >= 1,
    assignments,
    primary,
    summary: assignments.length >= 1 ? assignments.map(({ view }) => view).join(', ') : null,
    inferredFromOrder,
  }
}

/**
 * Detect which view angle an uploaded image represents using the vision model.
 * Returns a view tag or null if detection fails.
 */
export async function detectUploadedImageView({
  imageBase64,
  prompt,
  model,
}: {
  imageBase64: string
  prompt: string
  model: string
}): Promise<{ detectedView: ThreeDViewTag; confidence: number } | null> {
  try {
    const response = await ollamaChat(model, [
      {
        role: 'system',
        content: `/no_think
You are an image angle detector. Given a reference image of an object/character/product, determine from which angle it was photographed.

Return ONLY valid JSON: {"view":"front"|"back"|"left"|"right","confidence":0-100}

Rules:
- "front": main face, logo, screen, face, primary interface facing camera
- "back": rear side, back panel, back of head, rear connectors
- "left": left profile view
- "right": right profile view
- For characters: face visible = front, back of head = back
- For products: main branding/interface side = front
- For three-quarter views: pick the dominant visible face (front-left = front)
- confidence: how sure you are (>80 = certain, 50-80 = probable, <50 = guess)`,
      },
      {
        role: 'user',
        content: `Subject context: ${prompt.split('\n')[0].trim()}\nWhich angle is this image taken from?`,
        images: [imageBase64],
      },
    ])
    const text = (response?.message?.content || '').trim()
    const cleaned = text.replace(/<think>[\s\S]*?<\/think>/g, '').replace(/<think>[\s\S]*$/g, '').trim()
    const parsed = extractJson<{ view: string; confidence: number }>(cleaned)
    if (parsed && VIEW_ORDER.includes(parsed.view as ThreeDViewTag)) {
      return { detectedView: parsed.view as ThreeDViewTag, confidence: parsed.confidence ?? 60 }
    }
  } catch {
    // Detection non-critical
  }
  return null
}

function sanitizeViewList(values: unknown, fallback: ThreeDViewTag[]) {
  if (!Array.isArray(values)) return fallback
  const normalized = values
    .map((value) => String(value).toLowerCase().trim())
    .filter((value): value is ThreeDViewTag => VIEW_ORDER.includes(value as ThreeDViewTag))
  return normalized.length > 0 ? Array.from(new Set(normalized)) : fallback
}

function sanitizeReuseMap(value: unknown) {
  const output: Partial<Record<ThreeDViewTag, ThreeDViewTag>> = {}
  if (!value || typeof value !== 'object') return output
  for (const [key, rawTarget] of Object.entries(value)) {
    const source = String(key).toLowerCase().trim()
    const target = String(rawTarget).toLowerCase().trim()
    if (VIEW_ORDER.includes(source as ThreeDViewTag) && VIEW_ORDER.includes(target as ThreeDViewTag) && source !== target) {
      output[source as ThreeDViewTag] = target as ThreeDViewTag
    }
  }
  return output
}

function sanitizeViewRequirements(value: unknown) {
  const output: Partial<Record<ThreeDViewTag, string[]>> = {}
  if (!value || typeof value !== 'object') return output
  for (const [key, rawItems] of Object.entries(value)) {
    const view = String(key).toLowerCase().trim()
    if (!VIEW_ORDER.includes(view as ThreeDViewTag) || !Array.isArray(rawItems)) continue
    output[view as ThreeDViewTag] = uniqueStrings(rawItems.map((item) => short(String(item), 120)))
  }
  return output
}

function promptSignalsEmissiveLighting(prompt: string, referenceSupport: ThreeDReferenceSupport) {
  const normalized = prompt.toLowerCase()
  return /\b(led|rgb|argb|neon|emissive|light guide|backlit|illuminated|eclaire|lumineux|strimer|light bar)\b/i.test(normalized)
    || /\b(led|rgb|argb|strimer|light guide|emissive)\b/i.test(referenceSupport.searchProfile.subjectLabel.toLowerCase())
}

function buildFallbackVerificationChecks(prompt: string, intent: ThreeDIntent) {
  const checks = [...intent.anchoredPartsFocus, ...intent.movingPartsFocus]

  if (intent.systemClass === 'belt_drive') {
    checks.push('aligned pulleys', 'continuous belt loop', 'static frame')
  }
  if (intent.systemClass === 'gear_train') {
    checks.push('gear mesh order', 'axle alignment', 'housing supports')
  }
  if (intent.systemClass === 'cylinder_actuator') {
    checks.push('rod axis', 'cylinder mounts', 'clevis or actuator endpoint')
  }
  if (intent.systemClass === 'hinge_joint') {
    checks.push('hinge pin', 'fixed bracket', 'moving leaf')
  }
  if (intent.systemClass === 'linkage') {
    checks.push('pivot order', 'grounded frame', 'link endpoints')
  }
  if (intent.systemClass === 'pc_cabling') {
    checks.push('connector count', 'connector orientation', 'cable comb spacing', 'light guides when present')
  }
  if (intent.systemClass === 'electrical_harness' || intent.systemClass === 'cable_routing') {
    checks.push('connector endpoints', 'branch points', 'routing anchors', 'bend radius plausibility')
  }

  if (intent.purpose === 'character' || intent.subjectKind === 'character' || intent.subjectKind === 'creature') {
    checks.push('recognizable hairstyle', 'costume silhouette', 'main facial markers')
  }

  if (/\b(charniere|hinge|connector|connecteur|plug|socket|prise|port)\b/i.test(prompt.toLowerCase())) {
    checks.push('requested connector or hinge family visible')
  }

  return uniqueStrings(checks).slice(0, 8)
}

function buildFallbackLightingRequirements(prompt: string, intent: ThreeDIntent, referenceSupport: ThreeDReferenceSupport) {
  if (!promptSignalsEmissiveLighting(prompt, referenceSupport)) return []

  const notes = ['keep emissive or LED elements visible and coherent']
  if (intent.systemClass === 'pc_cabling') {
    notes.push('light guides must remain continuous', 'do not remove LED strips or diffuser bars')
  }
  return uniqueStrings(notes)
}

function analyzeSymmetry(prompt: string, intent: ThreeDIntent): {
  leftRightSymmetric: boolean
  frontBackSymmetric: boolean
  reason: string
} {
  const normalized = prompt.toLowerCase()
  const axialSymmetry = intent.wantsSymmetry
    || /\b(symetrique|symmetric|symmetrical|identical both sides|same on both sides|cylindrical|round|circular|pulley|gear|bearing|roller|shaft)\b/i.test(normalized)
  const flatCableLike = /\b(flat|ribbon|strimer|extension cable|sleeved cable|faisceau plat)\b/i.test(normalized)

  // Characters and creatures: left/right are usually mirror-symmetric, but front and back are ALWAYS different
  if (intent.subjectKind === 'character' || intent.subjectKind === 'creature' || intent.purpose === 'character') {
    return {
      leftRightSymmetric: true,
      frontBackSymmetric: false,
      reason: 'personnage/creature: gauche-droite symetriques, face et dos toujours differents (visage vs dos, poitrine vs dos)',
    }
  }

  // Cables with connectors on both ends: front/back may differ (different connector types)
  if (intent.systemClass === 'pc_cabling' || intent.systemClass === 'cable_routing' || intent.systemClass === 'electrical_harness') {
    const hasDifferentEnds = /\b(24[\s-]?pin|8[\s-]?pin|12vhpwr|pcie|atx|eps|sata|molex|male|female|mâle|femelle)\b/i.test(normalized)
    return {
      leftRightSymmetric: flatCableLike,
      frontBackSymmetric: flatCableLike && !hasDifferentEnds,
      reason: hasDifferentEnds
        ? 'cable avec connecteurs differents aux extremites: chaque vue peut montrer un connecteur different'
        : flatCableLike
          ? 'cable plat: les deux faces et cotes sont similaires'
          : 'cable: les cotes peuvent differer selon le routage et les branches',
    }
  }

  // Fully axially symmetric objects (pulleys, gears, shafts, bearings)
  if (axialSymmetry) {
    return {
      leftRightSymmetric: true,
      frontBackSymmetric: true,
      reason: 'objet axialement symetrique: toutes les vues orthogonales sont equivalentes',
    }
  }

  // Mechanical parts with hinge/linkage: front/back often differ (hinge axis vs. back plate)
  if (intent.systemClass === 'hinge_joint' || intent.systemClass === 'linkage') {
    return {
      leftRightSymmetric: false,
      frontBackSymmetric: false,
      reason: 'systeme articule: chaque vue revele des details mecaniques differents',
    }
  }

  // Vehicles: left/right symmetric, front/back different
  if (intent.subjectKind === 'vehicle') {
    return {
      leftRightSymmetric: true,
      frontBackSymmetric: false,
      reason: 'vehicule: gauche-droite symetriques, avant et arriere toujours differents',
    }
  }

  // Generic objects: conservative, assume different
  return {
    leftRightSymmetric: false,
    frontBackSymmetric: false,
    reason: 'objet generique: pas de symetrie presumee sans indication explicite',
  }
}

/**
 * Build per-view FLUX generation directives.
 * `enrichedDescription` is the full visual description from taskIntelligence —
 * it tells FLUX what the subject actually LOOKS LIKE, not just its name.
 * Without it, FLUX only sees "Front view of Naruto" and invents everything.
 */
function buildViewGenerationDirectives(
  prompt: string,
  intent: ThreeDIntent,
  referenceSupport: ThreeDReferenceSupport,
  enrichedDescription = '',
  overlay?: ThreeDViewOverlay,
): Partial<Record<ThreeDViewTag, string>> {
  const subjectLabel = referenceSupport.searchProfile.subjectLabel || prompt.split(/[,.\n]/)[0]?.trim() || prompt
  const isCharacter = intent.subjectKind === 'character' || intent.subjectKind === 'creature' || intent.purpose === 'character'
  const isCable = intent.systemClass === 'pc_cabling' || intent.systemClass === 'cable_routing' || intent.systemClass === 'electrical_harness'
  const isMechanical = intent.systemClass !== 'generic' && !isCable
  const hasLed = promptSignalsEmissiveLighting(prompt, referenceSupport)

  // Identity lines from intent analysis
  const identityLines = intent.referencePromptAdditions
    .filter((line) => /^(THIS IS NOT|Visual description:|DO NOT generate|Generate ONLY|The .+ is a)/i.test(line))
    .slice(0, 3)
    .map((line) => line.replace(/\.$/, ''))

  // Extract the enriched visual description (truncated for FLUX prompt budget)
  const visualDescription = enrichedDescription
    ? short(enrichedDescription.replace(/\n+/g, '. ').replace(/\s+/g, ' '), 600)
    : ''

  // ── Overlay instructions from reference analyzer + user overrides ──
  // These pin colours, transcribe visible text verbatim, and scope FLUX to
  // the single entity the user cares about when the reference shows several.
  const paletteLine = overlay?.palette ? formatPaletteInstruction(overlay.palette) : ''
  const textLine = overlay?.visibleText ? formatTextInstruction(overlay.visibleText) : ''
  const focusLine = overlay?.entities && typeof overlay.focusEntityIndex === 'number'
    ? formatEntityFocusInstruction(overlay.entities, overlay.focusEntityIndex)
    : ''
  const colorPromptNote = overlay?.colorPromptNote && overlay.colorPromptNote.trim()
    ? `user colour request (overrides any default): ${overlay.colorPromptNote.trim()}`
    : ''
  const extraFidelityLines = (overlay?.extraFidelityLines || []).filter(Boolean)
  const researchAnchors = (overlay?.researchAnchors || []).filter(Boolean)
  const researchLine = researchAnchors.length > 0
    ? `structural facts that MUST be respected (from product knowledge/web research, cross-checked against the user reference): ${researchAnchors.slice(0, 6).join(' | ')}`
    : ''
  const detailFocusZones = (overlay?.detailFocusZones || []).filter(Boolean)
  const detailFocusLine = detailFocusZones.length > 0
    ? `preserve these small high-frequency features as DISTINCT geometric surfaces (NOT flattened into blobs): ${detailFocusZones.slice(0, 6).join(', ')}`
    : ''

  // Hard anti-blob rules for logos, displays, connectors, fan blades, etc.
  // The user reported integrated OLED screens being swallowed into the block
  // above and fan blades being rendered as lumpy spheres, which is exactly
  // the failure mode Hunyuan3D exhibits when the reference does not clearly
  // separate those features. We bake the separation into every view prompt.
  const fineDetailRules = [
    'any integrated display/OLED/LCD panel must stay a DISTINCT FLAT RECTANGULAR surface — NEVER merge it into the surrounding heatsink or housing block',
    'engraved or printed logos and model numbers must read as SURFACE DETAIL with readable typography — NEVER replace them with smooth or blobby geometry',
    'fans must show each individual blade as a SEPARATE volume with visible gaps between blades — NEVER collapse blades into a single disc or sphere cluster',
    'connectors, ports and headers must keep their exact pin count and keying shape — NEVER round them into featureless nubs',
    'small features (screws, screw heads, vents, indicator LEDs, capacitors) stay as INDIVIDUALLY resolvable shapes, never merged with neighbouring geometry',
  ]

  const overlayBlock = [
    paletteLine,
    textLine,
    focusLine,
    colorPromptNote,
    researchLine,
    detailFocusLine,
    ...fineDetailRules,
    ...extraFidelityLines,
  ].filter(Boolean)

  // HARD RULES that prevent FLUX from generating multi-entity or split-view images
  const hardRules = [
    'solid black studio background',
    'EXACTLY ONE single isolated subject centered in frame',
    'ONLY ONE ENTITY IN THE ENTIRE IMAGE — if the subject is a character there must be exactly 1 character, if it is a cable there must be exactly 1 cable',
    'the ENTIRE canvas is ONE continuous single-angle photograph of that ONE subject',
    'NEVER split the image into multiple panels or side-by-side views',
    'NEVER place two copies of the subject next to each other',
    'NEVER generate a turnaround sheet, character lineup, or composite multi-view',
    'no mirror copies, no duplicated subjects, no tiled views',
    'high edge separation, no text overlay, no UI, no watermark',
    'consistent studio lighting for 3D reconstruction',
  ]

  // Merge identity + visual description + analyzer overlay into each directive
  // so FLUX has a single authoritative source for colour, text and focus.
  const subjectBlock = [
    visualDescription ? `VISUAL DESCRIPTION: ${visualDescription}` : '',
    ...identityLines,
    ...overlayBlock,
  ].filter(Boolean)

  const ledNote = hasLed
    ? 'LED light guides and emissive elements must remain visible and consistent across all views'
    : ''

  const directives: Partial<Record<ThreeDViewTag, string>> = {}

  if (isCharacter) {
    const characterBase = [
      ...hardRules,
      ...subjectBlock,
      'full body visible from head to feet without any cropping',
      'arms slightly away from body for clean 3D reconstruction silhouette',
      'neutral or relaxed standing pose, same pose across all views',
      'SAME proportions, SAME height, SAME costume, SAME hairstyle in every view',
      'SAME accessories in every view: gloves, wristbands, belts, boots, scarf/collar/cape must never appear/disappear between views',
      'hands visible and outside pockets in every view; never hide a hand inside clothing because it breaks rigging and texture projection',
      'strict turnaround sheet logic across separate images: only the camera angle changes, never the identity, clothing, pose language, gender, body type or material zones',
      'PHOTOREALISTIC rendering by default — sharp fabric folds, visible skin texture, realistic hair strands NOT blobby masses, anatomically correct proportions',
      'NEVER produce a blobby, marshmallow, or cartoon-like character unless anime style is explicitly requested',
      'precise finger separation, clear knuckle definition, realistic joint articulation',
      'clothing must show proper draping, folds, seams and material texture — NOT smooth featureless surfaces',
    ]
    directives.front = [
      `FRONT VIEW: ${subjectLabel} facing the camera directly`,
      ...characterBase,
      'face fully visible and recognizable',
      'costume front details, belt, buttons, accessories visible',
      'eyes looking toward camera',
    ].join('. ')
    directives.back = [
      `BACK VIEW: ${subjectLabel} seen from directly behind, back of character facing camera`,
      ...characterBase,
      'BACK OF HEAD visible: hair rear, ponytail, braid or hair texture from behind',
      'costume rear details: cape, backpack, belt back, any rear accessories',
      'NO FACE VISIBLE — the camera is behind the character',
      'same exact body proportions and pose as the front view',
    ].join('. ')
    directives.left = [
      `LEFT SIDE VIEW: ${subjectLabel} seen in left profile, left shoulder toward camera`,
      ...characterBase,
      'full left side profile of face visible',
      'body depth and thickness readable',
      'arm and leg separation clear from side angle',
    ].join('. ')
    directives.right = [
      `RIGHT SIDE VIEW: ${subjectLabel} seen in right profile, right shoulder toward camera`,
      ...characterBase,
      'full right side profile of face visible',
      'mirror image of the left side view',
    ].join('. ')
  } else if (isCable) {
    const cableBase = [
      ...hardRules,
      ...subjectBlock,
      'DO NOT generate a PC case, tower, chassis or any computer housing',
      'show ONLY the cable product itself, completely isolated on black background',
      'show the complete cable from one connector end to the other',
      hasLed ? 'RGB light guides must glow with visible colors along the cable length' : '',
      hasLed ? 'cable combs must be visible holding the light guide tubes in organized rows' : '',
      ledNote,
    ].filter(Boolean)
    directives.front = [
      `FRONT VIEW: ${subjectLabel}, connector end facing camera`,
      ...cableBase,
      'connector pins, housing and interface fully readable',
      hasLed ? 'light guide tubes visible from front, parallel transparent tubes with RGB glow' : '',
    ].filter(Boolean).join('. ')
    directives.back = [
      `BACK VIEW: ${subjectLabel}, rear connector or cable exit facing camera`,
      ...cableBase,
      'rear connector or cable bundle exit visible',
      'strain relief and cable anchoring visible',
      hasLed ? 'LED diffuser channel or strip backside visible' : '',
    ].filter(Boolean).join('. ')
    directives.left = [
      `LEFT SIDE VIEW: ${subjectLabel}, seen from the left side in profile`,
      ...cableBase,
      'cable thickness and cross-section profile visible',
      'comb spacing and sleeve profile readable',
      hasLed ? 'light guide edge glow visible from side' : '',
    ].filter(Boolean).join('. ')
    directives.right = [
      `RIGHT SIDE VIEW: ${subjectLabel}, seen from the right side in profile`,
      ...cableBase,
      'opposite side cable profile and routing visible',
      'branch points and anchoring readable from this angle',
    ].filter(Boolean).join('. ')
  } else if (isMechanical) {
    const mechBase = [
      ...hardRules,
      ...subjectBlock,
      `system class: ${intent.systemClass}`,
      intent.movingPartsFocus.length > 0 ? `moving parts: ${intent.movingPartsFocus.slice(0, 3).join(', ')}` : '',
      intent.anchoredPartsFocus.length > 0 ? `fixed parts: ${intent.anchoredPartsFocus.slice(0, 3).join(', ')}` : '',
      'hard-surface mechanical render with clean edges and precise geometry',
      'no melted surfaces, no organic deformation on rigid parts',
      ledNote,
    ].filter(Boolean)
    directives.front = [
      `FRONT VIEW: ${subjectLabel}, main functional face toward camera`,
      ...mechBase,
      'all primary interfaces, connectors, pivots and shafts readable',
      'main axis of operation visible',
    ].join('. ')
    directives.back = [
      `BACK VIEW: ${subjectLabel}, rear face toward camera`,
      ...mechBase,
      'rear mounting points, back plate and hidden interfaces visible',
      'support brackets and rear structure readable',
    ].join('. ')
    directives.left = [
      `LEFT SIDE VIEW: ${subjectLabel}, left profile toward camera`,
      ...mechBase,
      'side profile showing depth, shaft axes and pivot alignment',
      'side-accessible connectors and mechanisms visible',
    ].join('. ')
    directives.right = [
      `RIGHT SIDE VIEW: ${subjectLabel}, right profile toward camera`,
      ...mechBase,
      'opposite side profile with any asymmetric mechanisms visible',
    ].join('. ')
  } else {
    const genericBase = [
      ...hardRules,
      ...subjectBlock,
      'all visible details and proportions readable',
      ledNote,
    ].filter(Boolean)
    directives.front = [`FRONT VIEW: ${subjectLabel} facing camera`, ...genericBase].join('. ')
    directives.back = [`BACK VIEW: ${subjectLabel} rear toward camera`, ...genericBase].join('. ')
    directives.left = [`LEFT SIDE VIEW: ${subjectLabel} left profile toward camera`, ...genericBase].join('. ')
    directives.right = [`RIGHT SIDE VIEW: ${subjectLabel} right profile toward camera`, ...genericBase].join('. ')
  }

  return directives
}

function buildFallbackViewStrategy(
  prompt: string,
  intent: ThreeDIntent,
  referenceSupport: ThreeDReferenceSupport,
  enrichedDescription = '',
  overlay?: ThreeDViewOverlay,
): ViewStrategy {
  const exactLike = referenceSupport.referenceMode !== 'freeform' || intent.needsResearch
  const structuredSubject = intent.systemClass !== 'generic' || intent.subjectKind === 'electrical_system' || intent.subjectKind === 'mechanical_part'
  const isCharacter = intent.subjectKind === 'character' || intent.subjectKind === 'creature' || intent.purpose === 'character'
  // v77zk: real-person reproduction forces strict multi-view ingestion
  // (Hunyuan3D-2mv shape model) regardless of any other heuristic. A
  // single-view shape pipeline is not enough to recover a recognizable
  // likeness — at least front + profile + back is needed.
  const personReproduction = isPersonReproductionPrompt(prompt)
  const symmetry = analyzeSymmetry(prompt, intent)

  // Characters always need all 4 views for zero deformation; complex subjects need at least 3
  const requiredViews: ThreeDViewTag[] = isCharacter
    ? ['front', 'back', 'left', 'right']
    : structuredSubject || exactLike
      ? ['front', 'back', 'left']
      : ['front']
  const optionalViews: ThreeDViewTag[] = isCharacter
    ? []
    : structuredSubject || exactLike
      ? ['right']
      : ['back', 'left', 'right']
  const reuseMap: Partial<Record<ThreeDViewTag, ThreeDViewTag>> = {}

  // Apply symmetry-based reuse only where proven safe
  if (symmetry.leftRightSymmetric) {
    reuseMap.right = 'left'
  }
  if (symmetry.frontBackSymmetric) {
    reuseMap.back = 'front'
  }

  const viewRequirements: Partial<Record<ThreeDViewTag, string[]>> = {
    front: ['main silhouette readable', 'primary subject identity preserved'],
    left: structuredSubject ? ['side profile readable', 'depth and side connectors visible'] : ['side silhouette readable'],
    back: isCharacter
      ? ['rear of character visible', 'hair back, costume rear, no face visible', 'same proportions as front']
      : ['rear structure readable'],
    right: ['opposite side profile readable'],
  }

  if (intent.systemClass === 'pc_cabling') {
    viewRequirements.front = uniqueStrings([...(viewRequirements.front || []), 'connector interfaces visible', 'light guides visible when present'])
    viewRequirements.left = uniqueStrings([...(viewRequirements.left || []), 'cable thickness and comb spacing visible'])
    viewRequirements.back = uniqueStrings([...(viewRequirements.back || []), 'rear connector or cable exit visible'])
  }

  if (isCharacter) {
    viewRequirements.front = uniqueStrings([...(viewRequirements.front || []), 'face visible', 'full body head to feet', 'costume front details'])
    viewRequirements.back = uniqueStrings([...(viewRequirements.back || []), 'back of head and hair', 'costume rear', 'cape or backpack if present'])
  }

  return {
    // v77zk: personReproduction is the strongest forcing signal — for a real
    // person we always need multi-view shape, even when no extra metadata
    // suggested it.
    needsMultiview: personReproduction || isCharacter || structuredSubject || exactLike,
    requiredViews,
    optionalViews,
    reuseMap,
    verificationChecks: buildFallbackVerificationChecks(prompt, intent),
    lightingRequirements: buildFallbackLightingRequirements(prompt, intent, referenceSupport),
    viewRequirements,
    viewGenerationDirectives: buildViewGenerationDirectives(prompt, intent, referenceSupport, enrichedDescription, overlay),
  }
}

async function buildViewStrategy({
  prompt,
  intent,
  model,
  researchContext,
  referenceSupport,
  enrichedDescription,
  overlay,
}: {
  prompt: string
  intent: ThreeDIntent
  model: string
  researchContext: string
  referenceSupport: ThreeDReferenceSupport
  enrichedDescription: string
  overlay?: ThreeDViewOverlay
}) {
  const fallback = buildFallbackViewStrategy(prompt, intent, referenceSupport, enrichedDescription, overlay)
  const symmetry = analyzeSymmetry(prompt, intent)

  try {
    const response = await ollamaChat(model, [
      {
        role: 'system',
        content: [
          '/no_think',
          'You plan autonomous reference views for a 3D reconstruction pipeline.',
          'Return only valid JSON with this exact shape:',
          '{"needsMultiview":true,"requiredViews":["front","left"],"optionalViews":["back","right"],"reuseMap":{"right":"left"},"verificationChecks":["..."],"lightingRequirements":["..."],"viewRequirements":{"front":["..."],"left":["..."],"back":["..."],"right":["..."]}}',
          'Choose views from front, back, left, right only.',
          '',
          'CRITICAL SYMMETRY RULES:',
          '- For characters and creatures: front and back are ALWAYS different (face vs. back of head, chest vs. back). NEVER reuse front for back.',
          '- For characters: left and right sides are usually mirror-symmetric and CAN be reused.',
          '- For cables with different connector types at each end: front and back may differ.',
          '- For fully axially symmetric objects (gears, pulleys, shafts): all views can be reused.',
          '- For vehicles: left/right symmetric, but front/back always different.',
          '- When in doubt, do NOT reuse - generate a separate view.',
          '',
          `Current symmetry analysis: left-right symmetric: ${symmetry.leftRightSymmetric}, front-back symmetric: ${symmetry.frontBackSymmetric}. Reason: ${symmetry.reason}`,
          '',
          'reuseMap means a missing view can safely reuse another view ONLY when truly symmetric.',
          'verificationChecks must focus on functional details such as connectors, hinges, shafts, brackets, branches, light guides, or iconic character markers.',
          'lightingRequirements should mention LED, emissive, illuminated or signal-light details only when relevant.',
        ].join('\n'),
      },
      {
        role: 'user',
        content: [
          `Prompt: ${prompt}`,
          `Intent summary: ${intent.summary}`,
          `Subject label: ${referenceSupport.searchProfile.subjectLabel}`,
          referenceSupport.sourceNotes.length > 0 ? `Reference notes: ${referenceSupport.sourceNotes.join(' | ')}` : '',
          researchContext ? `Research context:\n${short(researchContext, 900)}` : '',
        ].filter(Boolean).join('\n\n'),
      },
    ], 0.05)

    const parsed = extractJson<{
      needsMultiview?: boolean
      requiredViews?: unknown
      optionalViews?: unknown
      reuseMap?: unknown
      verificationChecks?: unknown
      lightingRequirements?: unknown
      viewRequirements?: unknown
    }>(response?.message?.content || '')

    // Sanitize reuseMap but enforce symmetry constraints
    const rawReuse = { ...fallback.reuseMap, ...sanitizeReuseMap(parsed?.reuseMap) }
    // Never allow front->back reuse for characters
    if (!symmetry.frontBackSymmetric) {
      if (rawReuse.back === 'front') delete rawReuse.back
      if (rawReuse.front === 'back') delete rawReuse.front
    }
    if (!symmetry.leftRightSymmetric) {
      if (rawReuse.right === 'left') delete rawReuse.right
      if (rawReuse.left === 'right') delete rawReuse.left
    }

    return {
      needsMultiview: parsed?.needsMultiview ?? fallback.needsMultiview,
      requiredViews: sanitizeViewList(parsed?.requiredViews, fallback.requiredViews),
      optionalViews: sanitizeViewList(parsed?.optionalViews, fallback.optionalViews),
      reuseMap: rawReuse,
      verificationChecks: uniqueStrings(
        Array.isArray(parsed?.verificationChecks)
          ? parsed!.verificationChecks!.map((item) => short(String(item), 120))
          : fallback.verificationChecks,
      ).slice(0, 8),
      lightingRequirements: uniqueStrings(
        Array.isArray(parsed?.lightingRequirements)
          ? parsed!.lightingRequirements!.map((item) => short(String(item), 120))
          : fallback.lightingRequirements,
      ).slice(0, 5),
      viewRequirements: {
        ...fallback.viewRequirements,
        ...sanitizeViewRequirements(parsed?.viewRequirements),
      },
      viewGenerationDirectives: fallback.viewGenerationDirectives,
    } satisfies ViewStrategy
  } catch {
    return fallback
  }
}

function buildViewQueries(
  prompt: string,
  intent: ThreeDIntent,
  referenceSupport: ThreeDReferenceSupport,
  view: ThreeDViewTag,
) {
  const subjectLabel = referenceSupport.searchProfile.subjectLabel || prompt
  const baseQueries = [
    `${subjectLabel} ${view} view`,
    `${subjectLabel} ${view} reference`,
    `${subjectLabel} ${view} photo`,
  ]

  if (intent.systemClass !== 'generic') {
    baseQueries.push(`${subjectLabel} ${view} technical view`)
  }
  if (intent.purpose === 'character' || intent.subjectKind === 'character' || intent.subjectKind === 'creature') {
    baseQueries.push(`${subjectLabel} ${view} character design`)
  }

  return uniqueStrings(baseQueries.map((query) => short(query, 180))).slice(0, 4)
}

function buildViewProfile(
  baseProfile: ReferenceSearchProfile,
  strategy: ViewStrategy,
  view: ThreeDViewTag,
) {
  return {
    ...baseProfile,
    viewLabel: view,
    requiredElements: uniqueStrings([
      ...baseProfile.requiredElements,
      ...(strategy.viewRequirements[view] || []),
    ]).slice(0, 8),
    verificationChecks: strategy.verificationChecks,
    lightingRequirements: strategy.lightingRequirements,
    allowMirroredEquivalent: strategy.reuseMap[view] !== undefined,
  } satisfies ReferenceSearchProfile
}

/**
 * Verify a single view image using the vision model.
 * Checks: correct angle, subject presence, functional details, lighting coherence.
 */
export async function verifyViewImage({
  view,
  imageBase64,
  prompt,
  model,
  strategy,
  referenceSupport,
}: {
  view: ThreeDViewTag
  imageBase64: string
  prompt: string
  model: string
  strategy: ViewStrategy
  referenceSupport: ThreeDReferenceSupport
}): Promise<ThreeDViewVerification> {
  const viewReqs = strategy.viewRequirements[view] || []
  const functionalChecks = strategy.verificationChecks
  const lightingReqs = strategy.lightingRequirements

  try {
    const response = await ollamaChat(model, [
      {
        role: 'system',
        content: [
          '/no_think',
          'You verify whether a reference image for 3D reconstruction shows the correct view and required details.',
          'Return only valid JSON with this exact shape:',
          '{"angleCorrect":true,"subjectPresent":true,"singleEntity":true,"functionalDetailsFound":["..."],"functionalDetailsMissing":["..."],"lightingCoherent":true,"notes":"..."}',
          'angleCorrect: does the image actually show the requested view angle (front/back/left/right)?',
          'subjectPresent: is the main subject clearly visible and identifiable?',
          'singleEntity: does the image show EXACTLY ONE entity from ONE angle? If the image is split into panels, shows side-by-side views, or contains multiple copies of the subject, singleEntity MUST be false.',
          'functionalDetailsFound: which of the requested functional details are actually visible?',
          'functionalDetailsMissing: which required functional details are NOT visible or wrong?',
          'lightingCoherent: are LED/emissive elements consistent and visible when required?',
          'Be strict: if the view shows the wrong angle, angleCorrect must be false.',
          'Be strict: if the image is a multi-view composite (left+right, front+back on same image), singleEntity must be false.',
          'Be strict: if there are TWO copies of the subject visible (even from different angles), singleEntity must be false.',
          'For back views of characters: the face must NOT be visible, only the rear.',
        ].join('\n'),
      },
      {
        role: 'user',
        content: [
          `Requested view: ${view}`,
          `Subject: ${referenceSupport.searchProfile.subjectLabel}`,
          `Original prompt: ${short(prompt, 200)}`,
          viewReqs.length > 0 ? `View requirements: ${viewReqs.join(', ')}` : '',
          functionalChecks.length > 0 ? `Functional details to verify: ${functionalChecks.join(', ')}` : '',
          lightingReqs.length > 0 ? `Lighting/LED requirements: ${lightingReqs.join(', ')}` : '',
        ].filter(Boolean).join('\n'),
        images: [imageBase64],
      },
    ], 0.05)

    const parsed = extractJson<{
      angleCorrect?: boolean
      subjectPresent?: boolean
      singleEntity?: boolean
      functionalDetailsFound?: string[]
      functionalDetailsMissing?: string[]
      lightingCoherent?: boolean
      notes?: string
    }>(response?.message?.content || '')

    const angleCorrect = parsed?.angleCorrect ?? true
    const subjectPresent = parsed?.subjectPresent ?? true
    const singleEntity = parsed?.singleEntity ?? true
    const functionalDetailsFound = Array.isArray(parsed?.functionalDetailsFound)
      ? parsed!.functionalDetailsFound!.map((s) => String(s)).filter(Boolean)
      : []
    const functionalDetailsMissing = Array.isArray(parsed?.functionalDetailsMissing)
      ? parsed!.functionalDetailsMissing!.map((s) => String(s)).filter(Boolean)
      : []
    const lightingCoherent = parsed?.lightingCoherent ?? true
    const passed = angleCorrect && subjectPresent && singleEntity && (functionalDetailsMissing.length <= 1) && lightingCoherent

    return {
      view,
      passed,
      angleCorrect,
      subjectPresent,
      singleEntity,
      functionalDetailsFound,
      functionalDetailsMissing,
      lightingCoherent,
      notes: parsed?.notes || '',
    }
  } catch {
    // If verification fails, assume the view is OK to avoid blocking
    return {
      view,
      passed: true,
      angleCorrect: true,
      subjectPresent: true,
      singleEntity: true,
      functionalDetailsFound: [],
      functionalDetailsMissing: [],
      lightingCoherent: true,
      notes: 'verification skipped due to error',
    }
  }
}

/**
 * Build a strengthened FLUX prompt for retrying a view that failed verification.
 */
function buildRetryDirective(
  baseDirective: string,
  verification: ThreeDViewVerification,
): string {
  const fixes: string[] = []

  if (!verification.angleCorrect) {
    fixes.push(`CRITICAL: the image must show the ${verification.view} view, not another angle`)
  }
  if (!verification.subjectPresent) {
    fixes.push('the main subject must be clearly visible and centered')
  }
  if (!verification.singleEntity) {
    fixes.push('CRITICAL: the image must show EXACTLY ONE entity from ONE angle. Do NOT split the image into panels. Do NOT show the subject from multiple angles. Do NOT place two copies of the subject side by side. The ENTIRE image must be ONE continuous single-angle view')
  }
  if (verification.functionalDetailsMissing.length > 0) {
    fixes.push(`missing functional details that MUST appear: ${verification.functionalDetailsMissing.join(', ')}`)
  }
  if (!verification.lightingCoherent) {
    fixes.push('LED and emissive elements must be visible and coherent')
  }

  return fixes.length > 0
    ? `${baseDirective}. CORRECTIONS: ${fixes.join('. ')}`
    : baseDirective
}

function primaryViewFromAssignments(assignments: ThreeDViewAssignment[]) {
  return assignments.find((assignment) => assignment.view === 'front')?.view
    || assignments[0]?.view
    || 'front'
}

export async function prepareThreeDViewPlan({
  prompt,
  intent,
  model,
  researchContext,
  referenceSupport,
  preparedContext,
  enrichedDescription,
  overlay,
}: {
  prompt: string
  intent: ThreeDIntent
  model: string
  researchContext: string
  referenceSupport: ThreeDReferenceSupport
  preparedContext: PreparedContextFile[]
  /** Full visual description from taskIntelligence so synthetic views know what to draw */
  enrichedDescription?: string
  /** Palette, visible text, entity focus harvested from the actual user reference */
  overlay?: ThreeDViewOverlay
}): Promise<ThreeDViewPlan> {
  const provided = resolvePreparedReferenceViews(preparedContext)
  const strategy = await buildViewStrategy({
    prompt,
    intent,
    model,
    researchContext,
    referenceSupport,
    enrichedDescription: enrichedDescription || '',
    overlay,
  })

  const assignments = new Map<ThreeDViewTag, ThreeDViewAssignment>()

  // 1. User-provided views take priority
  for (const { view, file } of provided.assignments) {
    assignments.set(view, {
      view,
      sourceKind: 'user',
      file,
      notes: [provided.inferredFromOrder ? 'vue utilisateur mappee par ordre de fichiers' : 'vue utilisateur fournie'],
    })
  }

  // 2. Use external reference from support as front if no user front
  // — mais JAMAIS quand l'utilisateur a fourni une photo (30/07: son chat
  // ailé a ete remplace par un portrait trouve sur le web). S'il a donne une
  // image sans vue front, sa PREMIERE image devient la face.
  if (!assignments.has('front') && provided.assignments.length > 0) {
    const premiere = provided.assignments[0]
    assignments.set('front', {
      view: 'front',
      sourceKind: 'user',
      file: premiere.file,
      notes: ['photo utilisateur promue en face (aucune vue front taguee)'],
    })
  }
  if (!assignments.has('front') && referenceSupport.externalReference && provided.assignments.length === 0) {
    assignments.set('front', {
      view: 'front',
      sourceKind: 'external',
      externalReference: referenceSupport.externalReference,
      notes: ['vue front issue de la recherche externe principale'],
    })
  }

  // 3. Apply symmetry-based reuse where safe
  for (const view of VIEW_ORDER) {
    const reuseFrom = strategy.reuseMap[view]
    if (!assignments.has(view) && reuseFrom && assignments.has(reuseFrom)) {
      assignments.set(view, {
        view,
        sourceKind: 'reuse',
        reuseFrom,
        notes: [`vue ${view} re-utilisee depuis ${reuseFrom} (symetrie validee: ${analyzeSymmetry(prompt, intent).reason})`],
      })
    }
  }

  // 4. Try external search for missing required AND optional views
  // Be aggressive: search ALL views when multiview is needed, not just when < 2 assignments.
  // The more real reference images we find from different angles, the higher the fidelity.
  const hasUserProvidedImage = provided.assignments.length > 0
  for (const view of VIEW_ORDER) {
    if (assignments.has(view)) continue
    const isRequired = strategy.requiredViews.includes(view)
    const isOptional = strategy.optionalViews.includes(view)
    // Search required views always. Search optional views when multiview is active
    // or when user provided a reference (we want complementary angles).
    // 30/07 (audit): la presence d'une photo utilisateur DECLENCHAIT des
    // recherches web de vues complementaires — images d'un AUTRE sujet
    // melangees a la photo dans references/. Photo presente = zero recherche
    // web; les vues complementaires viennent de MV-Adapter (image -> vues).
    const shouldSearch = !hasUserProvidedImage && (isRequired || (isOptional && strategy.needsMultiview))
    if (!shouldSearch) continue

    const externalReference = await findBestReferenceVisual({
      prompt,
      model,
      queries: buildViewQueries(prompt, intent, referenceSupport, view),
      profile: buildViewProfile(referenceSupport.searchProfile, strategy, view),
    })

    if (externalReference) {
      assignments.set(view, {
        view,
        sourceKind: 'external',
        externalReference,
        notes: [`vue ${view} trouvee par recherche externe: ${externalReference.title}`],
      })
    }
  }

  // 5. Reuse pass after search for any remaining gaps
  for (const view of VIEW_ORDER) {
    const reuseFrom = strategy.reuseMap[view]
    if (!assignments.has(view) && reuseFrom && assignments.has(reuseFrom)) {
      assignments.set(view, {
        view,
        sourceKind: 'reuse',
        reuseFrom,
        notes: [`vue ${view} re-utilisee depuis ${reuseFrom} apres verification des autres vues`],
      })
    }
  }

  // 6. Autonomous synthetic generation for still-missing required AND optional views when multiview is needed
  const allViewsToConsider = strategy.needsMultiview
    ? [...strategy.requiredViews, ...strategy.optionalViews]
    : strategy.requiredViews
  for (const view of VIEW_ORDER) {
    if (assignments.has(view)) continue
    if (!allViewsToConsider.includes(view)) continue

    const directive = strategy.viewGenerationDirectives[view]
    if (directive) {
      assignments.set(view, {
        view,
        sourceKind: 'synthetic',
        syntheticPrompt: directive,
        notes: [`vue ${view} marquee pour generation synthetique autonome via FLUX`],
      })
    }
  }

  const orderedAssignments = VIEW_ORDER.flatMap((view) => {
    const assignment = assignments.get(view)
    return assignment ? [assignment] : []
  })

  const viewCount = orderedAssignments.length
  const syntheticCount = orderedAssignments.filter((a) => a.sourceKind === 'synthetic').length
  const reuseCount = orderedAssignments.filter((a) => a.sourceKind === 'reuse').length

  const symmetry = analyzeSymmetry(prompt, intent)
  const sourceNotes = uniqueStrings([
    viewCount > 0 ? `Plan de vues: ${orderedAssignments.map((assignment) => `${assignment.view}=${assignment.sourceKind}${assignment.reuseFrom ? `(${assignment.reuseFrom})` : ''}`).join(', ')}` : '',
    provided.inferredFromOrder ? 'Certaines vues utilisateur ont ete inferrees depuis l ordre des fichiers.' : '',
    syntheticCount > 0 ? `${syntheticCount} vue(s) seront generee(s) automatiquement par FLUX.` : '',
    reuseCount > 0 ? `Symetrie: ${symmetry.reason}` : '',
  ])

  const functionalVerificationSummary = strategy.verificationChecks.length > 0
    ? [`Details fonctionnels a verifier par vue: ${strategy.verificationChecks.slice(0, 4).join(', ')}`]
    : []

  // Force multiview when user provided at least 1 image OR we found multiple external references
  const hasUserImage = orderedAssignments.some((a) => a.sourceKind === 'user')
  const hasExternalImages = orderedAssignments.filter((a) => a.sourceKind === 'external').length
  const shouldForceMultiview = (hasUserImage || hasExternalImages >= 2) && viewCount >= 2

  return {
    shouldUseMultiview: (strategy.needsMultiview || shouldForceMultiview) && viewCount >= 2 && orderedAssignments.some((a) => a.view === 'front'),
    primaryView: primaryViewFromAssignments(orderedAssignments),
    assignments: orderedAssignments,
    sourceNotes,
    verificationNotes: strategy.verificationChecks,
    lightingNotes: strategy.lightingRequirements,
    functionalVerificationSummary,
    inferredFromOrder: provided.inferredFromOrder,
  }
}

/**
 * Get the FLUX generation directive for a synthetic view.
 * Used by ModelView to generate the image via ComfyUI.
 */
export function getSyntheticViewDirective(assignment: ThreeDViewAssignment): string | null {
  if (assignment.sourceKind !== 'synthetic') return null
  return assignment.syntheticPrompt || null
}

/**
 * Build a corrected directive for retry after verification failure.
 */
export function buildCorrectedViewDirective(
  assignment: ThreeDViewAssignment,
  verification: ThreeDViewVerification,
): string | null {
  const base = assignment.syntheticPrompt
  if (!base) return null
  return buildRetryDirective(base, verification)
}
