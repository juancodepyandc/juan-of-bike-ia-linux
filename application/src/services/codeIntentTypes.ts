// ---------------------------------------------------------------------------
// Code intent public types
// Extracted from codeIntent.ts during WS1 modularisation.
// ---------------------------------------------------------------------------

export type CodeProjectType =
  | 'static_web'
  | 'spa_react'
  | 'spa_vue'
  | 'spa_angular'
  | 'spa_svelte'
  | 'ssr_nextjs'
  | 'ssr_nuxt'
  | 'ssr_remix'
  | 'api_express'
  | 'api_fastapi'
  | 'api_django'
  | 'api_flask'
  | 'api_spring'
  | 'api_gin'
  | 'api_actix'
  | 'api_dotnet'
  | 'fullstack_mern'
  | 'fullstack_nextjs'
  | 'fullstack_django'
  | 'fullstack_rails'
  | 'cli_node'
  | 'cli_python'
  | 'cli_rust'
  | 'cli_go'
  | 'cli_cpp'
  | 'desktop_electron'
  | 'desktop_tauri'
  | 'desktop_app'
  | 'mobile_rn'
  | 'mobile_flutter'
  | 'mobile_ios'
  | 'mobile_android'
  | 'library_npm'
  | 'library_pypi'
  | 'library_crate'
  | 'game_web'
  | 'game_unity'
  | 'engine_3d'
  | 'ide'
  | 'embedded_esp32'
  | 'embedded_arduino'
  | 'compiler'
  | 'os_kernel'
  | 'distributed_system'
  | 'system_c'
  | 'system_cpp'
  | 'system_rust'
  | 'data_python'
  | 'devops_docker'
  | 'script'
  | 'unknown'

export type CodeComplexity = 'trivial' | 'simple' | 'moderate' | 'complex' | 'enterprise'

export type PreviewType =
  | 'dev_server'
  | 'iframe_bundled'
  | 'iframe_static'
  | 'console'
  | 'none'


export type GameKind =
  | 'clone'     // Recreate a known game exactly (snake, tetris, flappy, etc.)
  | 'creative'  // Invent something original — no canonical reference
  | 'generic'   // Generic game request without enough detail to classify

/** A known game to clone, with its mechanics spelled out. */

export type KnownGameEntry = {
  canonical: string
  genre: string
  coreMechanics: string[]
  visualStyle: string
  controls: string
  winLoseCondition: string
}

export type PromptLanguage = 'fr' | 'en' | 'es' | 'de' | 'it' | 'pt' | 'unknown'

export type BrandProfile = {
  /** Hex (#RRGGBB) of the canonical brand color — injected as primary CSS accent. */
  primaryColor: string
  /** Optional secondary brand color used for gradients / accents. */
  secondaryColor?: string
  /** Tertiary brand color (rare — Pepsi blue/red/white triad, Google G colors). */
  tertiaryColor?: string
  /** Concrete product nouns associated with the brand — feeds image search and Codeur prompt. */
  productKeywords: string[]
  /** Short adjective list describing the visual vibe ("rouge pop retro", "minimal sharp white"). */
  designVibe: string
  /** Recommended typographic style ("bold serif retro", "geometric sans modern", "italic cursive"). */
  typoVibe: string
  /** Image search queries used by the orchestrator to fetch real assets via the bridge / extension. */
  imageQueries: string[]
  /**
   * Geometric primitive for 3D product: can, bottle, phone, shoe, car, watch, bag, headphones, controller, console, card, cup, logo, building, or null.
   */
  productShape?:
    | 'can' | 'bottle' | 'phone' | 'tablet' | 'laptop'
    | 'shoe' | 'car' | 'watch' | 'bag' | 'headphones'
    | 'controller' | 'console' | 'card' | 'cup' | 'logo' | 'building'
    | null
}

export type SubjectDetection = {
  canonical: string | null
  domain: string | null
  /**
   * 'brand'           — matched the in-memory `BRAND_DICTIONARY` (47 well-known brands, fast path).
   * 'inferred_brand'  — matched the capitalised-name heuristic; profile is missing and the
   *                     orchestrator should call `/api/brand/enrich` on the bridge to fill it.
   * 'quoted'          — first quoted phrase in the prompt (user explicitly named a topic).
   * 'object'          — first concrete noun from CONCRETE_OBJECT_TOKENS.
   * 'none'            — nothing recognisable; the page is generic.
   */
  source: 'brand' | 'inferred_brand' | 'quoted' | 'object' | 'none'
  raw: string
  /** Brand palette/keywords/queries — only set when source === 'brand' (cache hit). For
   * 'inferred_brand', the orchestrator dynamically fills this via /api/brand/enrich. */
  brandProfile?: BrandProfile
}

/**
 * Stoplist for the inferred-brand heuristic. Capitalised words at the start of a French
 * or English sentence are not brands, so we ignore them. We also bail on UI verbs ("Crée",
 * "Build") and section nouns ("Page", "Site") that the user puts at the start of a prompt.
 */

export type CodeAssetPlan = {
  /** Free-form style tokens kept as-is (for search queries and prompt hints). */
  styleHints: string[]
  /** Physical/digital objects or subjects mentioned that probably need a visual. */
  objectMentions: string[]
  /** Interactive / animation / effect tokens the page should feature. */
  effectMentions: string[]
  /** Color hex codes captured in the brief, if any ("#ff8800" etc.) */
  paletteHints: string[]
  /** User asked for a "pro / premium / attirant / moderne / …" rendering — research recommended. */
  wantsPremiumLook: boolean
  /** User implicitly or explicitly asked for illustrations (image / photo / picture / illustration / icon). */
  wantsImages: boolean
  /** User asked for 3D content (three.js, webgl, rotating model, …). */
  wants3D: boolean
  /** User expressly asked to research / source references online ("cherche", "trouve", "inspire-toi de", …). */
  wantsResearch: boolean
  /** Short research queries to feed `researchBestPractices` / image search BEFORE generation. */
  researchQueries: string[]
  /** Main subject of the page (brand, product, or noun). NEVER mistranslate this. */
  subject: SubjectDetection
  /** Language the user wrote the prompt in. All UI copy must be generated in this language. */
  language: PromptLanguage
}

// ---------------------------------------------------------------------------
// Keyword detection tables

export type CodeIntent = {
  projectType: CodeProjectType
  complexity: CodeComplexity
  languages: string[]
  frameworks: string[]
  features: string[]
  needsDevServer: boolean
  needsBundling: boolean
  previewType: PreviewType
  devCommand: string | null
  buildCommand: string | null
  testCommand: string | null
  /** Which model tier to use: 'code' for pure coding, 'planning' for architecture, 'analysis' for review */
  primaryModelRole: 'code' | 'planning' | 'analysis'
  /** Whether multi-file architecture planning is needed before generation */
  needsArchitecturePlanning: boolean
  /** Estimated file count for progress tracking */
  estimatedFileCount: number
  /** Rich analysis of the user brief to enrich the system prompt before generation. */
  assetPlan: CodeAssetPlan
  /** Game-specific classification — only set when projectType === 'game_web'. */
  gameKind?: GameKind
  /** The known game to clone — only set when gameKind === 'clone'. */
  knownGame?: KnownGameEntry
}

/**
 * Plan of what the user wants beyond "just code":
 *  - visual style clues ("moderne", "premium", "cyberpunk"…) → trigger web research
 *  - concrete objects / subjects to show ("velo gravel", "iphone 15", "chat siamois"…) → need image/3D assets
 *  - effects / animations asked ("parallax", "glow", "gsap", "three.js stars"…) → widen library hints
 *  - if paletteHints is set, the codeur will be told to reuse those colors precisely.
 */

export type CodeIntentContext = {
  /** Project type of the previous generation, if any. */
  previousProjectType?: CodeProjectType
  /** Languages used in the previous generation. */
  previousLanguages?: string[]
  /** Frameworks used in the previous generation. */
  previousFrameworks?: string[]
  /**
   * Follow-up classification resolved by `analyzeFollowUpIntent`:
   *  - 'increment'       → small patch over the same project, keep previous stack
   *  - 'pivot_platform'  → user wants the same concept on another stack/language
   *  - 'pivot_feature'   → major feature change in the same stack
   *  - 'fresh_start'     → unrelated new project, reclassify from scratch
   */
  pivotKind?: 'increment' | 'pivot_platform' | 'pivot_feature' | 'fresh_start'
}
