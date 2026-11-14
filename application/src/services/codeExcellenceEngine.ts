// ---------------------------------------------------------------------------
// Aurora Code Excellence Engine
// 1. Explicit Constraint Extraction & AGI Implicit Feature Synthesis
// 2. Physical Motion Design Solver (Damped Harmonic Oscillator, Stagger, rAF Lerp, Spotlight)
// 3. Static / AST-like Algorithmic Complexity, Memory Leak, N+1 & Zero-Placeholder Auditor
// ---------------------------------------------------------------------------

import type { CodeIntent } from './codeIntent.ts'
import type { CodeFile } from './codeOrchestratorTypes.ts'

// ===========================================================================
// 1. TYPES & INTERFACES
// ===========================================================================

export type ImplicitFeaturePillar =
  | 'persistence'
  | 'error_resilience'
  | 'wcag_keyboard_a11y'
  | 'loading_empty_states'
  | 'realtime_search_filter'
  | 'keyboard_shortcuts'

export interface ExplicitConstraint {
  id: string
  category: 'stack' | 'architecture' | 'data_contract' | 'ui_ux' | 'performance' | 'security'
  description: string
  mustTokens: string[]
  satisfied?: boolean
}

export interface ImplicitFeatureSpec {
  pillar: ImplicitFeaturePillar
  title: string
  rationale: string
  implementationDirective: string
  verificationSignals: RegExp[]
  detectedInCode?: boolean
}

export interface SpringPhysicsConfig {
  mass: number
  stiffness: number
  damping: number
  initialVelocity?: number
}

export interface SpringPhysicsSolution {
  /** Damping ratio zeta = c / (2 * sqrt(m * k)) */
  dampingRatio: number
  /** Undamped natural angular frequency omega_0 = sqrt(k / m) (rad/s) */
  naturalFrequency: number
  /** Regime: underdamped (zeta < 1), critically_damped (zeta == 1), overdamped (zeta > 1) */
  regime: 'underdamped' | 'critically_damped' | 'overdamped'
  /** Settling time (seconds) to within 1% of equilibrium */
  settlingDurationMs: number
  /** Peak overshoot percentage (0 for critically/overdamped) */
  overshootPercent: number
  /** Fitted cubic-bezier(x1, y1, x2, y2) approximation for CSS transitions */
  cubicBezier: [number, number, number, number]
  /** Ready-to-use CSS cubic-bezier(...) string */
  cssEasing: string
  /** Sampled normalized trajectory [tNormalized, displacement] for WAAPI / keyframes */
  trajectorySamples: Array<{ tMs: number; value: number; velocity: number }>
  /** Generated CSS @keyframes block */
  cssKeyframes: string
}

export interface StaggerItemTiming {
  index: number
  row: number
  col: number
  delayMs: number
  durationMs: number
  easing: string
}

export interface SpotlightState {
  normX: number
  normY: number
  pixelX: number
  pixelY: number
  intensity: number
  cssVariables: Record<string, string>
  backgroundGradient: string
}

export type AlgorithmicIssueKind =
  | 'quadratic_loop'
  | 'loop_array_scan'
  | 'n_plus_one_io'
  | 'listener_or_timer_leak'
  | 'forbidden_placeholder'
  | 'layout_thrashing_animation'

export type IssueSeverity = 'critical' | 'warning' | 'info'

export interface AlgorithmicFinding {
  id: string
  file: string
  line: number
  kind: AlgorithmicIssueKind
  severity: IssueSeverity
  estimatedComplexity: string
  targetComplexity: string
  snippet: string
  explanation: string
  recommendation: string
}

export interface MotionAuditReport {
  score: number
  usesPhysicalCurves: boolean
  usesGpuCompositedProps: boolean
  supportsReducedMotion: boolean
  hasStaggerChoreography: boolean
  hasDynamicSpotlightOrDepth: boolean
  recommendedSpring: SpringPhysicsSolution
  warnings: string[]
}

export interface AlgorithmicAuditReport {
  score: number
  dominantComplexity: 'O(1)' | 'O(log N)' | 'O(N)' | 'O(N log N)' | 'O(N^2)' | 'O(N^3+)'
  quadraticCount: number
  nPlusOneCount: number
  leakCount: number
  placeholderCount: number
  findings: AlgorithmicFinding[]
  recommendations: string[]
}

export interface PromptExcellenceSynthesis {
  explicitConstraints: ExplicitConstraint[]
  implicitFeatures: ImplicitFeatureSpec[]
  recommendedSpringPreset: SpringPhysicsSolution
  synthesizedDirectiveBlock: string
}

export interface CodeExcellenceReport {
  overallScore: number
  fidelityScore: number
  motionScore: number
  algorithmicScore: number
  zeroPlaceholderPassed: boolean
  explicitConstraints: ExplicitConstraint[]
  implicitFeatures: ImplicitFeatureSpec[]
  motionAudit: MotionAuditReport
  algorithmicAudit: AlgorithmicAuditReport
  priorityRecommendations: string[]
}

// ===========================================================================
// 2. PHYSICAL MOTION DESIGN SOLVER (EXACT ANALYTICAL ODE + rAF LERP + SPOTLIGHT)
// ===========================================================================

/**
 * Solves the 2nd-order linear differential equation of a damped harmonic oscillator:
 *   m * x''(t) + c * x'(t) + k * (x(t) - 1) = 0, with x(0) = 0, x'(0) = v0
 * Returns exact analytical displacement & velocity samples, settling duration,
 * cubic-bezier approximation, and CSS keyframes.
 */
export function solveDampedSpring(
  config: SpringPhysicsConfig,
  keyframeName = 'aurora-spring-enter',
  sampleCount = 24,
): SpringPhysicsSolution {
  const mass = Math.max(0.05, config.mass)
  const stiffness = Math.max(1, config.stiffness)
  const damping = Math.max(0.1, config.damping)
  const v0 = config.initialVelocity ?? 0

  const omega0 = Math.sqrt(stiffness / mass)
  const zeta = damping / (2 * Math.sqrt(mass * stiffness))

  const regime: SpringPhysicsSolution['regime'] =
    Math.abs(zeta - 1) < 1e-3
      ? 'critically_damped'
      : zeta < 1
        ? 'underdamped'
        : 'overdamped'

  // Analytical displacement x(t) from 0 to 1 and velocity x'(t)
  const evaluateAt = (tSec: number): { value: number; velocity: number } => {
    if (tSec <= 0) return { value: 0, velocity: v0 }

    if (regime === 'underdamped') {
      const omegaD = omega0 * Math.sqrt(1 - zeta * zeta)
      const env = Math.exp(-zeta * omega0 * tSec)
      const c1 = -1
      const c2 = (v0 + zeta * omega0 * c1) / omegaD
      const cosTerm = Math.cos(omegaD * tSec)
      const sinTerm = Math.sin(omegaD * tSec)
      const displacementFromEq = env * (c1 * cosTerm + c2 * sinTerm)
      const velocity =
        -zeta * omega0 * displacementFromEq +
        env * (-c1 * omegaD * sinTerm + c2 * omegaD * cosTerm)
      return { value: 1 + displacementFromEq, velocity }
    }

    if (regime === 'critically_damped') {
      const env = Math.exp(-omega0 * tSec)
      const c1 = -1
      const c2 = v0 - omega0 * c1
      const displacementFromEq = env * (c1 + c2 * tSec)
      const velocity = env * (c2 - omega0 * (c1 + c2 * tSec))
      return { value: 1 + displacementFromEq, velocity }
    }

    // Overdamped (zeta > 1)
    const rootTerm = Math.sqrt(zeta * zeta - 1)
    const r1 = -omega0 * (zeta - rootTerm)
    const r2 = -omega0 * (zeta + rootTerm)
    const c2 = (v0 + r1) / (r2 - r1)
    const c1 = -1 - c2
    const e1 = Math.exp(r1 * tSec)
    const e2 = Math.exp(r2 * tSec)
    const displacementFromEq = c1 * e1 + c2 * e2
    const velocity = c1 * r1 * e1 + c2 * r2 * e2
    return { value: 1 + displacementFromEq, velocity }
  }

  // Estimate settling time (within 0.005 of target 1.0 and low velocity)
  const maxHorizonSec = Math.min(3.5, Math.max(0.22, 6.0 / ( Math.min(zeta, 1.2) * omega0 )))
  let settlingSec = maxHorizonSec
  const probeSteps = 120
  for (let i = probeSteps; i >= 1; i--) {
    const t = (i / probeSteps) * maxHorizonSec
    const { value, velocity } = evaluateAt(t)
    if (Math.abs(1 - value) > 0.006 || Math.abs(velocity) > 0.04) {
      settlingSec = Math.min(maxHorizonSec, ((i + 1) / probeSteps) * maxHorizonSec)
      break
    }
  }
  const settlingDurationMs = Math.round(Math.max(160, Math.min(1800, settlingSec * 1000)))

  // Sample trajectory & compute peak overshoot
  const steps = Math.max(8, sampleCount)
  const trajectorySamples: Array<{ tMs: number; value: number; velocity: number }> = []
  let maxVal = 1
  for (let i = 0; i <= steps; i++) {
    const ratio = i / steps
    const tSec = ratio * (settlingDurationMs / 1000)
    const { value, velocity } = evaluateAt(tSec)
    const clampedFinal = i === steps ? 1 : Number(value.toFixed(4))
    if (clampedFinal > maxVal) maxVal = clampedFinal
    trajectorySamples.push({
      tMs: Math.round(tSec * 1000),
      value: clampedFinal,
      velocity: Number(velocity.toFixed(4)),
    })
  }

  const overshootPercent = Number(Math.max(0, (maxVal - 1) * 100).toFixed(2))

  // Derive physically matched cubic-bezier control points [x1, y1, x2, y2]
  const x1 = Number(Math.max(0.12, Math.min(0.42, 0.22 / Math.sqrt(omega0 / 12))).toFixed(2))
  const y1 = Number(Math.max(0.65, Math.min(1.0, 1 - 0.15 * zeta)).toFixed(2))
  const x2 = Number(Math.max(0.2, Math.min(0.55, 0.32 * Math.min(1.3, zeta))).toFixed(2))
  const y2 = Number(
    (regime === 'underdamped'
      ? Math.min(1.35, 1 + (overshootPercent / 100) * 1.15)
      : 1.0
    ).toFixed(2),
  )
  const cubicBezier: [number, number, number, number] = [x1, y1, x2, y2]
  const cssEasing = `cubic-bezier(${x1}, ${y1}, ${x2}, ${y2})`

  const keyframeLines = trajectorySamples
    .filter((_, idx) => idx === 0 || idx === steps || idx % 3 === 0)
    .map((pt) => {
      const pct = Math.round((pt.tMs / settlingDurationMs) * 100)
      const scale = (0.96 + 0.04 * pt.value).toFixed(4)
      const translateY = ((1 - pt.value) * 12).toFixed(2)
      const opacity = Math.min(1, Math.max(0, pt.value * 1.15)).toFixed(3)
      return `  ${pct}% { opacity: ${opacity}; transform: translate3d(0, ${translateY}px, 0) scale(${scale}); }`
    })

  const cssKeyframes = `@keyframes ${keyframeName} {\n${keyframeLines.join('\n')}\n}`

  return {
    dampingRatio: Number(zeta.toFixed(3)),
    naturalFrequency: Number(omega0.toFixed(2)),
    regime,
    settlingDurationMs,
    overshootPercent,
    cubicBezier,
    cssEasing,
    trajectorySamples,
    cssKeyframes,
  }
}

/**
 * Canonical Physical Spring Presets (Critically Damped UI, Snappy Micro-interaction, Soft Spatial Reveal)
 */
export const PHYSICAL_SPRING_PRESETS: Record<
  'snappy_ui' | 'critically_damped' | 'spatial_reveal',
  SpringPhysicsConfig
> = {
  snappy_ui: { mass: 0.85, stiffness: 320, damping: 26, initialVelocity: 0.2 },
  critically_damped: { mass: 1.0, stiffness: 260, damping: 32.25, initialVelocity: 0 },
  spatial_reveal: { mass: 1.15, stiffness: 190, damping: 24, initialVelocity: 0 },
}

/**
 * Computes 2D spatial + index stagger timings with sub-linear saturation so large lists
 * never stall the user interface (> 450ms total cascade cap).
 */
export function computeStaggerChoreography(
  itemCount: number,
  columns = 3,
  baseDelayMs = 38,
  maxTotalCascadeMs = 420,
): StaggerItemTiming[] {
  const safeCount = Math.max(0, Math.min(200, itemCount))
  const safeCols = Math.max(1, columns)
  const spring = solveDampedSpring(PHYSICAL_SPRING_PRESETS.critically_damped)

  const results: StaggerItemTiming[] = []
  for (let i = 0; i < safeCount; i++) {
    const row = Math.floor(i / safeCols)
    const col = i % safeCols
    // Euclidean grid distance from top-left origin (0, 0)
    const radialDist = Math.hypot(row * 0.85, col * 0.65)
    // Sub-linear logarithmic damping prevents long lists from taking seconds to appear
    const rawDelay = radialDist * baseDelayMs
    const saturatedDelay = Math.round(
      maxTotalCascadeMs * (1 - Math.exp(-rawDelay / Math.max(1, maxTotalCascadeMs * 0.65))),
    )
    results.push({
      index: i,
      row,
      col,
      delayMs: saturatedDelay,
      durationMs: spring.settlingDurationMs,
      easing: spring.cssEasing,
    })
  }
  return results
}

/**
 * Frame-rate independent exponential smoothing (rAF Lerp):
 *   x(t + dt) = target + (current - target) * exp(-lambda * dtSec)
 * Guarantees identical physical trajectory at 30Hz, 60Hz, 120Hz, and 240Hz.
 */
export function stepFrameIndependentLerp(
  current: number,
  target: number,
  deltaTimeMs: number,
  smoothingLambda = 16,
): number {
  const dtSec = Math.max(0.001, Math.min(0.1, deltaTimeMs / 1000))
  const decay = Math.exp(-Math.max(0.5, smoothingLambda) * dtSec)
  const next = target + (current - target) * decay
  return Math.abs(target - next) < 1e-4 ? target : next
}

/**
 * Computes dynamic specular spotlight CSS variables and radial lighting gradient
 * from pointer coordinates relative to an element's bounding box.
 */
export function computeSpotlightLighting(
  pointerX: number,
  pointerY: number,
  boundsWidth: number,
  boundsHeight: number,
  accentColor = 'rgba(247, 131, 36, 0.14)',
  radiusPx = 420,
): SpotlightState {
  const w = Math.max(1, boundsWidth)
  const h = Math.max(1, boundsHeight)
  const clampedX = Math.max(0, Math.min(w, pointerX))
  const clampedY = Math.max(0, Math.min(h, pointerY))
  const normX = Number((clampedX / w).toFixed(4))
  const normY = Number((clampedY / h).toFixed(4))

  // Edge attenuation: slightly stronger near center, smooth falloff near borders
  const distFromCenter = Math.hypot(normX - 0.5, normY - 0.5)
  const intensity = Number(Math.max(0.35, Math.min(1, 1 - distFromCenter * 0.45)).toFixed(3))

  const backgroundGradient = `radial-gradient(${radiusPx}px circle at ${Math.round(clampedX)}px ${Math.round(clampedY)}px, ${accentColor}, transparent 72%)`

  return {
    normX,
    normY,
    pixelX: Math.round(clampedX),
    pixelY: Math.round(clampedY),
    intensity,
    cssVariables: {
      '--spotlight-x': `${Math.round(clampedX)}px`,
      '--spotlight-y': `${Math.round(clampedY)}px`,
      '--spotlight-norm-x': String(normX),
      '--spotlight-norm-y': String(normY),
      '--spotlight-intensity': String(intensity),
    },
    backgroundGradient,
  }
}

// ===========================================================================
// 3. EXPLICIT CONSTRAINT EXTRACTION & AGI IMPLICIT FEATURE SYNTHESIS
// ===========================================================================

const STACK_PATTERNS: Array<{ label: string; regex: RegExp; tokens: string[] }> = [
  { label: 'React / TSX', regex: /\b(react|tsx|jsx|nextjs|next\.js)\b/i, tokens: ['useState', 'useEffect', 'export'] },
  { label: 'TypeScript strict', regex: /\b(typescript|ts\b|typage)\b/i, tokens: ['interface', 'type'] },
  { label: 'Three.js / WebGL 3D', regex: /\b(three\.?js|webgl|shader|glsl|canvas\s*3d)\b/i, tokens: ['THREE', 'Scene', 'Camera', 'Renderer'] },
  { label: 'FastAPI / Python API', regex: /\b(fastapi|pydantic|uvicorn)\b/i, tokens: ['FastAPI', 'BaseModel', 'def '] },
  { label: 'Express / Node API', regex: /\b(express|node\.?js|fastify)\b/i, tokens: ['app.', 'req', 'res'] },
  { label: 'Rust / Cargo', regex: /\b(rust|cargo|tokio|axum|actix)\b/i, tokens: ['fn ', 'struct ', 'impl'] },
  { label: 'SQL / Persistence relationnelle', regex: /\b(sql|sqlite|postgres|postgresql|prisma|drizzle)\b/i, tokens: ['SELECT', 'CREATE', 'INDEX'] },
  { label: 'Tailwind / Design Tokens CSS', regex: /\b(tailwind|css\s*variables|glassmorphism|dark\s*mode)\b/i, tokens: ['className', 'var(--'] },
]

/**
 * Extracts explicit functional, architectural, and technical constraints from the user prompt.
 */
export function extractExplicitConstraints(prompt: string, intent?: CodeIntent | null): ExplicitConstraint[] {
  const constraints: ExplicitConstraint[] = []
  const normalized = prompt.trim()
  if (!normalized) return constraints

  // 1. Detect explicit technology & stack mentions
  for (const item of STACK_PATTERNS) {
    if (item.regex.test(normalized)) {
      constraints.push({
        id: `stack-${item.label.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`,
        category: 'stack',
        description: `Respect strict de la stack explicite : ${item.label}`,
        mustTokens: item.tokens,
      })
    }
  }

  // 2. Detect explicit data entities / CRUD / domain actions
  const crudMatch = normalized.match(/\b(crud|creer|ajouter|supprimer|modifier|editer|exporter|importer|panier|facture|kanban|tache|utilisateur|client|commande|graphique|chart|dashboard|tableau)\b/gi)
  if (crudMatch && crudMatch.length > 0) {
    const uniqueNouns = Array.from(new Set(crudMatch.map((m) => m.toLowerCase()))).slice(0, 6)
    constraints.push({
      id: 'domain-entities-operations',
      category: 'data_contract',
      description: `Opérations et entités métier explicites : ${uniqueNouns.join(', ')}`,
      mustTokens: uniqueNouns,
    })
  }

  // 3. Detect explicit API / endpoints / protocols
  if (/\b(api|rest|graphql|websocket|sse|endpoint|route|fetch|webhook)\b/i.test(normalized)) {
    constraints.push({
      id: 'explicit-api-contract',
      category: 'architecture',
      description: 'Contrat d’interface réseau/API typé avec validation des entrées et codes HTTP sémantiques',
      mustTokens: ['fetch', 'async', 'try', 'catch', 'status'],
    })
  }

  // 4. Detect explicit animation / visual / 3D / aesthetic requirements
  if (/\b(animation|motion|fluide|60\s*fps|transition|spring|ressort|parallax|spotlight|3d|interactif|moderne|premium)\b/i.test(normalized)) {
    constraints.push({
      id: 'explicit-motion-aesthetics',
      category: 'ui_ux',
      description: 'Chorégraphie Motion Design physique (cubic-bezier amorti, GPU transform/opacity, rAF 60fps)',
      mustTokens: ['cubic-bezier', 'transform', 'transition'],
    })
  }

  // 5. Detect explicit performance / algorithmic constraints
  if (/\b(performance|rapide|optimis|o\(n|complexite|cache|index| temps\s*reel|latence|concurrence)\b/i.test(normalized)) {
    constraints.push({
      id: 'explicit-algorithmic-perf',
      category: 'performance',
      description: 'Complexité algorithmique optimale O(N) / O(N log N) avec indexation par Map/Set et zéro boucle quadratique',
      mustTokens: ['Map', 'Set'],
    })
  }

  // Fallback baseline constraint derived from classified intent if prompt is very terse
  if (constraints.length === 0) {
    const projectType = intent?.projectType ?? 'application'
    constraints.push({
      id: 'baseline-complete-deliverable',
      category: 'architecture',
      description: `Livrable ${projectType} autonome, complet et directement exécutable sans aucun stub`,
      mustTokens: ['function', 'return'],
    })
  }

  return constraints
}

/**
 * Synthesizes implicit AGI quality features that elevate a raw user request into a
 * production-grade deliverable without hardcoding domain-specific gimmicks.
 */
export function synthesizeImplicitFeatures(prompt: string, intent?: CodeIntent | null): ImplicitFeatureSpec[] {
  const projectType = intent?.projectType ?? 'unknown'
  const isBackendOrCli =
    /^(api_|cli_|system_|compiler|os_kernel|distributed_system|data_python)/.test(projectType) ||
    (!/\b(ui|page|dashboard|interface|react|html|css|web|app)\b/i.test(prompt) &&
      /\b(cli|script|serveur|api|sql|algorithme|kernel|compilateur)\b/i.test(prompt))

  const specs: ImplicitFeatureSpec[] = [
    {
      pillar: 'persistence',
      title: 'Persistance d’état résiliente & Hydratation sûre',
      rationale:
        'Un utilisateur ne doit jamais perdre ses données au rechargement : sauvegarde automatique avec parsing JSON protégé et valeurs initiales réalistes.',
      implementationDirective: isBackendOrCli
        ? 'Inclure une couche de persistance transactionnelle ou sérialisation atomique avec validation de schéma à la lecture.'
        : 'Synchroniser l’état dans localStorage/IndexedDB via un wrapper try/catch résilient et pré-remplir avec un jeu de données initial cohérent.',
      verificationSignals: [/localStorage|sessionStorage|IndexedDB|sqlite|fs\.|writeFile|readFile|JSON\.parse/i],
    },
    {
      pillar: 'error_resilience',
      title: 'Gestion d’erreurs défensive & Dégradation gracieuse',
      rationale:
        'Toute opération I/O, réseau, parsing ou entrée utilisateur doit être protégée contre les crashs silencieux.',
      implementationDirective:
        'Encapsuler les appels asynchrones et le parsing dans des blocs try/catch explicites avec message d’erreur actionnable et état de reprise.',
      verificationSignals: [/\btry\s*\{[\s\S]*?\bcatch\b|\.catch\s*\(|Result<|ErrorBoundary|onError/i],
    },
    {
      pillar: 'wcag_keyboard_a11y',
      title: 'Accessibilité Clavier WCAG AA & Sémantique ARIA',
      rationale:
        'Contraste lisible (>= 4.5:1), navigation complète au clavier (Tab, Enter, Escape) et attributs ARIA sur les contrôles interactifs.',
      implementationDirective:
        'Ajouter aria-label / role sur les boutons d’icône, états :focus-visible nets, et support clavier complet sur les modales et listes.',
      verificationSignals: [/aria-label|role=|tabIndex|focus-visible|onKeyDown|prefers-reduced-motion/i],
    },
    {
      pillar: 'loading_empty_states',
      title: 'États Vides illustrés, Chargement & Feedback immédiat',
      rationale:
        'Chaque collection ou vue filtrée doit afficher un état vide explicite avec action rapide lorsque 0 élément ne correspond.',
      implementationDirective:
        'Prévoir un composant d’état vide (Empty State) avec bouton de réinitialisation ainsi qu’un indicateur visuel lors des traitements.',
      verificationSignals: [/\.length\s*===\s*0|isLoading|loading|empty|aucun\s+r[eé]sultat|no\s+results|skeleton/i],
    },
    {
      pillar: 'realtime_search_filter',
      title: 'Recherche, Filtrage & Tri instantanés en O(N)',
      rationale:
        'Dès qu’une interface ou un outil manipule une liste d’éléments, le filtrage multi-critères et le tri instantané décuplent l’utilisabilité.',
      implementationDirective:
        'Fournir un champ de recherche/filtrage temps réel mémoïsé (useMemo / index) insensible à la casse.',
      verificationSignals: [/\.filter\s*\(|toLowerCase\s*\(\)\.includes|searchQuery|filter|useMemo/i],
    },
    {
      pillar: 'keyboard_shortcuts',
      title: 'Raccourcis Clavier Rapides (Escape / Ctrl+K / Enter)',
      rationale:
        'Les raccourcis clavier offrent une ergonomie professionnelle immédiate.',
      implementationDirective:
        'Supporter Escape pour fermer/réinitialiser et Enter / Ctrl+K pour soumettre ou focaliser la recherche.',
      verificationSignals: [/Escape|keydown|metaKey|ctrlKey|Enter/i],
    },
  ]

  return specs
}

/**
 * Produces a complete Prompt Excellence Synthesis (Explicit Constraints + Implicit AGI Pillars + Physical Motion Spec).
 */
export function analyzePromptExcellence(prompt: string, intent?: CodeIntent | null): PromptExcellenceSynthesis {
  const explicitConstraints = extractExplicitConstraints(prompt, intent)
  const implicitFeatures = synthesizeImplicitFeatures(prompt, intent)
  const recommendedSpringPreset = solveDampedSpring(PHYSICAL_SPRING_PRESETS.critically_damped)

  const directiveLines: string[] = [
    '=== CONTRAT D’EXCELLENCE AURORA CODE (PRÉCISION + MOTION PHYSIQUE + ALGORITHMIQUE) ===',
    '1. EXIGENCES EXPLICITES VERROUILLÉES :',
    ...explicitConstraints.map((c) => `   - [${c.category.toUpperCase()}] ${c.description}`),
    '2. SYNTHÈSE AGI IMPLICITE (INCLURE SPONTANÉMENT SANS ALOURDIR) :',
    ...implicitFeatures.map((f) => `   - ${f.title} : ${f.implementationDirective}`),
    '3. MOTION DESIGN PHYSIQUE & OPTIQUE UI :',
    `   - Courbe ressort amortie recommandée : ${recommendedSpringPreset.cssEasing} (durée ~${recommendedSpringPreset.settlingDurationMs}ms, ζ=${recommendedSpringPreset.dampingRatio})`,
    '   - Animer exclusivement `transform` et `opacity` (zéro layout thrashing sur top/left/width/height).',
    '   - Respecter `@media (prefers-reduced-motion: reduce)` et les éclairages radiaux subtils.',
    '4. PERFORMANCE ALGORITHMIQUE & ZÉRO PLACEHOLDER :',
    '   - Complexité O(N) ou O(N log N) stricte : indexer par Map/Set au lieu de `.find()`/`.includes()` dans des boucles.',
    '   - Paralléliser les I/O indépendants (`Promise.all`) et nettoyer tous les listeners/timers.',
    '   - ZÉRO `TODO`, `FIXME`, `placeholder` ou fonction vide.',
  ]

  return {
    explicitConstraints,
    implicitFeatures,
    recommendedSpringPreset,
    synthesizedDirectiveBlock: directiveLines.join('\n'),
  }
}

/**
 * Enriches a user prompt non-destructively with the synthesized AGI excellence contract
 * if it hasn't already been injected.
 */
export function buildExcellenceEnrichedPrompt(prompt: string, intent?: CodeIntent | null): string {
  const trimmed = prompt.trim()
  if (!trimmed) return ''
  if (trimmed.includes('CONTRAT D’EXCELLENCE AURORA CODE')) return trimmed
  const synthesis = analyzePromptExcellence(trimmed, intent)
  return `${trimmed}\n\n${synthesis.synthesizedDirectiveBlock}`
}

// ===========================================================================
// 4. STATIC / AST-LIKE ALGORITHMIC, MEMORY LEAK, N+1 & MOTION AUDITOR
// ===========================================================================

const FORBIDDEN_PLACEHOLDER_REGEX =
  /\b(TODO|FIXME|HACK|XXX)\b|throw\s+new\s+Error\s*\(\s*['"`]Not\s+implemented|pass\s*#\s*todo|\bplaceholder\s+implementation\b/i

const LOOP_HEADER_REGEX =
  /\b(for\s*\(|while\s*\(|for\s+\w+\s+in\s+|\.(?:map|forEach|filter|reduce|flatMap)\s*\()/

const INNER_ARRAY_SCAN_REGEX =
  /\.(find|findIndex|includes|indexOf|lastIndexOf|filter|some|every)\s*\(/

const SEQUENTIAL_IO_IN_LOOP_REGEX =
  /\bawait\s+(?:fetch|axios\b|[a-zA-Z0-9_$]+\.(?:query|execute|findMany|findUnique|findOne|get|post|put|delete|send))\s*\(/

const LAYOUT_THRASHING_TRANSITION_REGEX =
  /transition(?:-property)?\s*:\s*[^;}\n]*\b(top|left|right|bottom|width|height|margin|padding)\b/i

/**
 * Strips comments and string contents on a single line for structural brace & loop tracking
 * without losing line numbers.
 */
function stripCommentsOnLine(line: string): string {
  return line
    .replace(/\/\/.*$/, '')
    .replace(/\/\*[\s\S]*?\*\//g, '')
}

/**
 * Audits a single code file for algorithmic bottlenecks ($O(N^2)$ nested loops, array scans inside loops,
 * N+1 sequential awaits inside loops, memory/listener leaks, layout-thrashing animations, and placeholders).
 */
export function analyzeFileAlgorithmics(file: CodeFile): AlgorithmicFinding[] {
  const findings: AlgorithmicFinding[] = []
  const lines = file.content.split('\n')
  const isStyleOrMarkupOnly = /\.(css|scss|less|html|svg|md|json|ya?ml)$/i.test(file.name)

  // Track active loop scopes via brace depth stack
  const loopDepthStack: Array<{ startLine: number; braceDepth: number }> = []
  let currentBraceDepth = 0

  // File-level leak detection counters
  let addListenerLine = 0
  const hasRemoveListener =
    /removeEventListener|\{\s*once\s*:\s*true\s*\}|AbortController/i.test(file.content)
  let setIntervalLine = 0
  const hasClearInterval = /clearInterval/i.test(file.content)

  for (let idx = 0; idx < lines.length; idx++) {
    const rawLine = lines[idx]
    const lineNum = idx + 1
    const trimmed = rawLine.trim()
    if (!trimmed) continue

    // 1. Check forbidden placeholders/TODOs in non-markdown files
    if (!/\.md$/i.test(file.name) && FORBIDDEN_PLACEHOLDER_REGEX.test(rawLine)) {
      findings.push({
        id: `${file.name}:L${lineNum}:placeholder`,
        file: file.name,
        line: lineNum,
        kind: 'forbidden_placeholder',
        severity: 'critical',
        estimatedComplexity: 'Incomplet',
        targetComplexity: '100% Implémenté',
        snippet: trimmed.slice(0, 110),
        explanation: 'Marqueur TODO/FIXME ou stub non implémenté détecté dans le livrable.',
        recommendation: 'Remplacer immédiatement le placeholder par l’implémentation complète et vérifiée.',
      })
    }

    // 2. Check layout-thrashing CSS animations
    if (LAYOUT_THRASHING_TRANSITION_REGEX.test(rawLine)) {
      findings.push({
        id: `${file.name}:L${lineNum}:layout-thrash`,
        file: file.name,
        line: lineNum,
        kind: 'layout_thrashing_animation',
        severity: 'warning',
        estimatedComplexity: 'CPU Layout/Paint 16ms+',
        targetComplexity: 'GPU Composite O(1)',
        snippet: trimmed.slice(0, 110),
        explanation: 'Transition CSS sur des propriétés géométriques (width/height/top/left) provoquant un recalcul de layout à chaque frame.',
        recommendation: 'Animer exclusivement `transform: translate3d(...) scale(...)` et `opacity` sur le compositeur GPU.',
      })
    }

    if (isStyleOrMarkupOnly) continue

    const codeOnly = stripCommentsOnLine(rawLine)
    if (!codeOnly.trim()) continue

    // Record listener / interval allocation lines
    if (addListenerLine === 0 && /\.addEventListener\s*\(/.test(codeOnly)) {
      addListenerLine = lineNum
    }
    if (setIntervalLine === 0 && /\bsetInterval\s*\(/.test(codeOnly)) {
      setIntervalLine = lineNum
    }

    const isLoopHeader = LOOP_HEADER_REGEX.test(codeOnly)
    const insideActiveLoop = loopDepthStack.length > 0

    // 3. Detect nested loop O(N^2)
    if (isLoopHeader && insideActiveLoop) {
      const outerLoop = loopDepthStack[loopDepthStack.length - 1]
      // Avoid flagging tiny fixed-bound loops like `for (let i = 0; i < 3; i++)`
      const isTinyFixedBound = /<\s*[2348]\b/.test(codeOnly)
      if (!isTinyFixedBound && lineNum - outerLoop.startLine <= 45) {
        findings.push({
          id: `${file.name}:L${lineNum}:quadratic-loop`,
          file: file.name,
          line: lineNum,
          kind: 'quadratic_loop',
          severity: 'warning',
          estimatedComplexity: loopDepthStack.length >= 2 ? 'O(N^3)' : 'O(N^2)',
          targetComplexity: 'O(N)',
          snippet: trimmed.slice(0, 110),
          explanation: `Boucle imbriquée détectée dans la boucle ouverte ligne ${outerLoop.startLine}.`,
          recommendation: 'Pré-indexer la collection secondaire dans une `Map` ou un `Set` en O(N) avant la boucle principale pour ramener la recherche interne en O(1).',
        })
      }
    }

    // 4. Detect O(N) array scan (.find / .includes / .indexOf) inside an active loop -> O(N^2)
    if (insideActiveLoop && !isLoopHeader && INNER_ARRAY_SCAN_REGEX.test(codeOnly)) {
      // Ignore string `.includes` heuristics when called on a literal or `.toLowerCase().includes(`
      const isStringFilter = /toLowerCase\(\)\.(?:includes|indexOf)|['"`]\.(?:includes|indexOf)/.test(codeOnly)
      if (!isStringFilter) {
        findings.push({
          id: `${file.name}:L${lineNum}:loop-array-scan`,
          file: file.name,
          line: lineNum,
          kind: 'loop_array_scan',
          severity: 'warning',
          estimatedComplexity: 'O(N * M)',
          targetComplexity: 'O(N + M)',
          snippet: trimmed.slice(0, 110),
          explanation: 'Appel de balayage linéaire (`.find` / `.includes` / `.indexOf`) à l’intérieur d’une boucle.',
          recommendation: 'Construire un index `new Map(items.map(x => [x.id, x]))` ou `new Set(...)` hors de la boucle pour un accès en O(1).',
        })
      }
    }

    // 5. Detect N+1 sequential await I/O inside an active loop
    if (insideActiveLoop && SEQUENTIAL_IO_IN_LOOP_REGEX.test(codeOnly)) {
      findings.push({
        id: `${file.name}:L${lineNum}:n-plus-one`,
        file: file.name,
        line: lineNum,
        kind: 'n_plus_one_io',
        severity: 'critical',
        estimatedComplexity: 'N+1 RTT séquentiels',
        targetComplexity: '1 Batch / Promise.all',
        snippet: trimmed.slice(0, 110),
        explanation: 'Appel réseau ou base de données `await` séquentiel exécuté à chaque itération de boucle (anti-pattern N+1).',
        recommendation: 'Regrouper les identifiants en une seule requête batch (`WHERE id IN (...)`) ou paralléliser avec `await Promise.all(...)`.',
      })
    }

    // Update brace depth and loop stack
    const openBraces = (codeOnly.match(/\{/g) || []).length
    const closeBraces = (codeOnly.match(/\}/g) || []).length

    if (isLoopHeader && openBraces > 0) {
      loopDepthStack.push({ startLine: lineNum, braceDepth: currentBraceDepth + 1 })
    }
    currentBraceDepth = Math.max(0, currentBraceDepth + openBraces - closeBraces)

    while (
      loopDepthStack.length > 0 &&
      currentBraceDepth < loopDepthStack[loopDepthStack.length - 1].braceDepth
    ) {
      loopDepthStack.pop()
    }
  }

  // 6. Report uncleaned event listeners or intervals
  if (addListenerLine > 0 && !hasRemoveListener) {
    findings.push({
      id: `${file.name}:L${addListenerLine}:listener-leak`,
      file: file.name,
      line: addListenerLine,
      kind: 'listener_or_timer_leak',
      severity: 'warning',
      estimatedComplexity: 'Fuite mémoire O(K)',
      targetComplexity: 'O(1) borné',
      snippet: lines[addListenerLine - 1]?.trim().slice(0, 110) ?? 'addEventListener(...)',
      explanation: '`addEventListener` détecté sans `removeEventListener`, `{ once: true }` ni `AbortController`.',
      recommendation: 'Nettoyer systématiquement l’écouteur dans le cleanup `useEffect(() => () => removeEventListener(...))` ou passer `{ once: true }`.',
    })
  }

  if (setIntervalLine > 0 && !hasClearInterval) {
    findings.push({
      id: `${file.name}:L${setIntervalLine}:interval-leak`,
      file: file.name,
      line: setIntervalLine,
      kind: 'listener_or_timer_leak',
      severity: 'warning',
      estimatedComplexity: 'Fuite timer actif',
      targetComplexity: 'Cleanup déterministe',
      snippet: lines[setIntervalLine - 1]?.trim().slice(0, 110) ?? 'setInterval(...)',
      explanation: '`setInterval` démarré sans `clearInterval` associé lors du démontage.',
      recommendation: 'Stocker l’identifiant du timer et appeler `clearInterval(id)` à la destruction du composant ou service.',
    })
  }

  return findings
}

/**
 * Audits Motion Design quality across all generated files.
 */
export function auditMotionDesign(files: CodeFile[]): MotionAuditReport {
  const recommendedSpring = solveDampedSpring(PHYSICAL_SPRING_PRESETS.critically_damped)
  if (files.length === 0) {
    return {
      score: 100,
      usesPhysicalCurves: true,
      usesGpuCompositedProps: true,
      supportsReducedMotion: true,
      hasStaggerChoreography: true,
      hasDynamicSpotlightOrDepth: true,
      recommendedSpring,
      warnings: [],
    }
  }

  const combined = files.map((f) => f.content).join('\n')
  const hasUiFiles = files.some((f) => /\.(tsx|jsx|vue|svelte|html|css|scss)$/i.test(f.name))

  if (!hasUiFiles) {
    return {
      score: 96,
      usesPhysicalCurves: true,
      usesGpuCompositedProps: true,
      supportsReducedMotion: true,
      hasStaggerChoreography: true,
      hasDynamicSpotlightOrDepth: true,
      recommendedSpring,
      warnings: [],
    }
  }

  const usesPhysicalCurves =
    /cubic-bezier\s*\(|spring|framer-motion|requestAnimationFrame/i.test(combined)
  const hasLayoutThrashing = LAYOUT_THRASHING_TRANSITION_REGEX.test(combined)
  const usesGpuCompositedProps =
    !hasLayoutThrashing && /\b(transform|translate3d|translateY|scale|opacity)\b/.test(combined)
  const supportsReducedMotion = /prefers-reduced-motion/i.test(combined)
  const hasStaggerChoreography =
    /animation-delay|transition-delay|stagger|--delay|\*\s*\d+ms/i.test(combined)
  const hasDynamicSpotlightOrDepth =
    /radial-gradient|backdrop-filter|backdrop-blur|box-shadow|--spotlight/i.test(combined)

  const warnings: string[] = []
  let score = 100

  if (!usesPhysicalCurves) {
    score -= 14
    warnings.push(
      `Remplacer les transitions linéaires par une courbe ressort amortie (${recommendedSpring.cssEasing}, ${recommendedSpring.settlingDurationMs}ms).`,
    )
  }
  if (!usesGpuCompositedProps) {
    score -= 16
    warnings.push(
      'Privilégier `transform` et `opacity` pour garantir un rendu 60fps sur le compositeur GPU sans reflow.',
    )
  }
  if (!supportsReducedMotion) {
    score -= 8
    warnings.push(
      'Ajouter `@media (prefers-reduced-motion: reduce)` pour respecter l’accessibilité vestibulaire.',
    )
  }
  if (!hasStaggerChoreography) {
    score -= 7
    warnings.push(
      'Ajouter un échelonnement `stagger` (transition-delay progressif borné à 420ms) sur les listes et cartes.',
    )
  }
  if (!hasDynamicSpotlightOrDepth) {
    score -= 7
    warnings.push(
      'Enrichir la profondeur optique avec un éclairage radial (`radial-gradient`) et des ombres multicouches douces.',
    )
  }

  return {
    score: Math.max(0, Math.min(100, score)),
    usesPhysicalCurves,
    usesGpuCompositedProps,
    supportsReducedMotion,
    hasStaggerChoreography,
    hasDynamicSpotlightOrDepth,
    recommendedSpring,
    warnings,
  }
}

/**
 * Runs the full Code Excellence Audit across all files, evaluating:
 * - Explicit constraint satisfaction & AGI Implicit feature coverage
 * - Physical Motion Design quality
 * - Algorithmic complexity ($O(N)$ vs $O(N^2)$), N+1 queries, memory leaks, and Zero-Placeholder compliance
 */
export function auditCodeExcellence(
  files: CodeFile[],
  prompt: string,
  intent?: CodeIntent | null,
): CodeExcellenceReport {
  const explicitConstraints = extractExplicitConstraints(prompt, intent)
  const implicitFeatures = synthesizeImplicitFeatures(prompt, intent)
  const motionAudit = auditMotionDesign(files)

  const combinedContent = files.map((f) => `${f.name}\n${f.content}`).join('\n')
  const combinedLower = combinedContent.toLowerCase()

  // Verify explicit constraints
  let satisfiedExplicit = 0
  const evaluatedExplicit = explicitConstraints.map((constraint) => {
    if (files.length === 0) return { ...constraint, satisfied: false }
    const satisfied =
      constraint.mustTokens.length === 0 ||
      constraint.mustTokens.some((tok) => combinedLower.includes(tok.toLowerCase()))
    if (satisfied) satisfiedExplicit++
    return { ...constraint, satisfied }
  })

  // Verify implicit AGI pillars
  let detectedImplicit = 0
  const evaluatedImplicit = implicitFeatures.map((feature) => {
    if (files.length === 0) return { ...feature, detectedInCode: false }
    const detectedInCode = feature.verificationSignals.some((rx) => rx.test(combinedContent))
    if (detectedInCode) detectedImplicit++
    return { ...feature, detectedInCode }
  })

  // Algorithmic static analysis across all files
  const allFindings = files.flatMap((file) => analyzeFileAlgorithmics(file))
  const quadraticCount = allFindings.filter(
    (f) => f.kind === 'quadratic_loop' || f.kind === 'loop_array_scan',
  ).length
  const nPlusOneCount = allFindings.filter((f) => f.kind === 'n_plus_one_io').length
  const leakCount = allFindings.filter((f) => f.kind === 'listener_or_timer_leak').length
  const placeholderCount = allFindings.filter((f) => f.kind === 'forbidden_placeholder').length

  const hasTripleLoop = allFindings.some((f) => f.estimatedComplexity === 'O(N^3)')
  const hasSorting = /\.sort\s*\(|\bsorted\s*\(/i.test(combinedContent)
  const hasLoops = LOOP_HEADER_REGEX.test(combinedContent)

  const dominantComplexity: AlgorithmicAuditReport['dominantComplexity'] = hasTripleLoop
    ? 'O(N^3+)'
    : quadraticCount > 0
      ? 'O(N^2)'
      : hasSorting
        ? 'O(N log N)'
        : hasLoops
          ? 'O(N)'
          : 'O(1)'

  let algorithmicScore = 100
  algorithmicScore -= placeholderCount * 25
  algorithmicScore -= nPlusOneCount * 18
  algorithmicScore -= quadraticCount * 12
  algorithmicScore -= leakCount * 10
  algorithmicScore = Math.max(0, Math.min(100, algorithmicScore))

  const algoRecommendations = Array.from(
    new Set(allFindings.map((f) => `${f.file}:L${f.line} — ${f.recommendation}`)),
  ).slice(0, 6)

  const algorithmicAudit: AlgorithmicAuditReport = {
    score: algorithmicScore,
    dominantComplexity,
    quadraticCount,
    nPlusOneCount,
    leakCount,
    placeholderCount,
    findings: allFindings,
    recommendations: algoRecommendations,
  }

  // Compute Fidelity score (Explicit weight 65%, Implicit AGI synthesis weight 35%)
  const explicitRatio =
    evaluatedExplicit.length > 0 ? satisfiedExplicit / evaluatedExplicit.length : 1
  const implicitRatio =
    evaluatedImplicit.length > 0 ? detectedImplicit / evaluatedImplicit.length : 1
  const fidelityScore =
    files.length === 0
      ? 100
      : Math.round(explicitRatio * 65 + implicitRatio * 35)

  const overallScore =
    files.length === 0
      ? 100
      : Math.round(fidelityScore * 0.4 + motionAudit.score * 0.25 + algorithmicScore * 0.35)

  const priorityRecommendations: string[] = [
    ...algoRecommendations,
    ...motionAudit.warnings,
    ...evaluatedImplicit
      .filter((f) => !f.detectedInCode && files.length > 0)
      .slice(0, 2)
      .map((f) => `Synthèse AGI (${f.title}) : ${f.implementationDirective}`),
  ].slice(0, 6)

  return {
    overallScore,
    fidelityScore,
    motionScore: motionAudit.score,
    algorithmicScore,
    zeroPlaceholderPassed: placeholderCount === 0,
    explicitConstraints: evaluatedExplicit,
    implicitFeatures: evaluatedImplicit,
    motionAudit,
    algorithmicAudit,
    priorityRecommendations,
  }
}
