// ---------------------------------------------------------------------------
// codeVisualFidelity — gate qui inspecte le HTML/CSS/JS livre et MESURE le
// niveau visuel. Si le score est trop bas, l orchestrator force une regen
// avec une critique precise (au lieu de livrer une page Coca-Cola scolaire).
// ---------------------------------------------------------------------------

import type { CodeIntent } from './codeIntent'
import {
  scoreRenderedVisualAudit,
  type CodeVisualRenderAudit,
} from './codeVisualRenderAudit.ts'
import {
  AMBITION_BAR,
  AMBITION_EXCLUDED_CHECKS,
  resolveVisualAmbition,
  type VisualAmbition,
} from './codeVisualFidelityProfiles.ts'
import {
  PREMIUM_FONTS,
  SCOLAIRE_TITLES,
  FLAT_BG_COLORS,
  PLAIN_LIST,
  HAS_GRADIENT,
  HAS_MESH_BLUR,
  HAS_KEYFRAMES,
  HAS_TRANSITION,
  HAS_INTERSECTION_OBSERVER,
  HAS_RAF,
  HAS_INLINE_SVG,
  HAS_FLEX_OR_GRID,
  HAS_BACKDROP_FILTER,
  HAS_BORDER_RADIUS_LARGE,
  HAS_CSS_VARS,
  HAS_CLAMP,
  HAS_HOVER,
  HAS_FONT_LINK_PRECONNECT,
  HAS_TRANSFORM_3D,
  HAS_PARALLAX,
  HAS_MULTI_GRADIENTS,
  countFlatColoredCards,
  countImages,
  countSections,
  hasFlatColoredCardCluster,
  htmlSize,
} from './codeVisualFidelityDetectors.ts'

export { buildVisualFidelityCritique } from './codeVisualFidelityCritique.ts'

export type VisualFidelityCheck = {
  id: string
  label: string
  passed: boolean
  weight: number
  evidence?: string
}

export type VisualFidelityReport = {
  score: number          // 0..100
  passed: boolean        // true if score >= floor for the project type
  floor: number
  checks: VisualFidelityCheck[]
  failedChecks: string[] // ids of failed checks for re-gen prompt
  summary: string
  source?: 'source_static' | 'render_audit'
  viewports?: string[]
  /** Genre de projet effectivement juge (vitrine / application / outil). */
  ambition?: VisualAmbition
}

type CodeFile = { name: string; language: string; content: string }

// ---------------------------------------------------------------------------
// HTML / CSS / JS aggregation
// ---------------------------------------------------------------------------

function findHtml(files: CodeFile[]): string {
  return files.filter((f) => /\.(html|htm)$/i.test(f.name)).map((f) => f.content).join('\n')
}

/**
 * Surface de MARKUP a juger.
 *
 * Mesure reelle (run 960): un site React+Vite de 33 fichiers a ete note
 * « 0 section trouvee, 0 ko de HTML, 50/100 » — parce que cette porte ne lisait
 * que les `.html`, et que dans un projet a composants l `index.html` de Vite est
 * une coquille de 223 octets autour de `<div id="root">`. Le markup vit dans les
 * `.tsx` / `.vue` / `.svelte`. Juger la coquille revenait a juger le carton d un
 * livre. Sur un `static_web` la liste des composants est vide: comportement
 * strictement inchange.
 */
function findComponentMarkup(files: CodeFile[]): string {
  return files
    .filter((f) => /\.(jsx|tsx|vue|svelte|astro)$/i.test(f.name))
    .map((f) => f.content)
    .join('\n')
}
function findCss(files: CodeFile[]): string {
  return files.filter((f) => /\.(css|scss|less)$/i.test(f.name)).map((f) => f.content).join('\n')
}
function findJs(files: CodeFile[]): string {
  return files.filter((f) => /\.(js|mjs|jsx|tsx|ts)$/i.test(f.name)).map((f) => f.content).join('\n')
}
function aggregateAll(files: CodeFile[]): string {
  return files.map((f) => f.content).join('\n')
}

// ---------------------------------------------------------------------------
// Build the report
// ---------------------------------------------------------------------------

function isVisualType(intent: CodeIntent): boolean {
  return (
    intent.projectType === 'static_web'
    || intent.projectType.startsWith('spa_')
    || intent.projectType.startsWith('ssr_')
    || intent.projectType.startsWith('fullstack_')
    || intent.projectType === 'game_web'
  )
}

export function evaluateVisualFidelity(
  files: CodeFile[],
  intent: CodeIntent,
  renderAudit?: CodeVisualRenderAudit | null,
  /** Brief original: sert a reconnaitre le GENRE du projet (vitrine / application / outil). */
  prompt = '',
): VisualFidelityReport {
  const documentHtml = findHtml(files)
  const componentMarkup = findComponentMarkup(files)
  // Le markup juge = document + composants. Sur un projet sans composants,
  // c est exactement l ancien comportement.
  const html = componentMarkup ? `${documentHtml}\n${componentMarkup}` : documentHtml
  const css = findCss(files)
  const js = findJs(files)
  const all = aggregateAll(files)

  // Non-visual projects bypass the gate.
  if (!isVisualType(intent)) {
    return {
      score: 100, passed: true, floor: 0, checks: [], failedChecks: [],
      summary: 'Projet non visuel — gate visuel non applicable.',
      source: 'source_static',
    }
  }

  if (renderAudit && renderAudit.viewports.length > 0) {
    return scoreRenderedVisualAudit(renderAudit)
  }

  // No HTML at all = catastrophic for visual project, but the delivery gate
  // already catches this case. Still return 0 to be explicit.
  if (!html.trim() && !css.trim()) {
    return {
      score: 0, passed: false, floor: 70,
      checks: [{ id: 'has_markup', label: 'Aucun HTML/CSS livre', passed: false, weight: 100 }],
      failedChecks: ['has_markup'],
      summary: 'Aucun HTML / CSS exploitable.',
      source: 'source_static',
    }
  }

  const checks: VisualFidelityCheck[] = []

  // 1. Pas de motif scolaire <h1>Bienvenue / Welcome
  checks.push({
    id: 'no_scolaire_title',
    label: 'Pas de titre scolaire <h1>Bienvenue/Welcome',
    passed: !SCOLAIRE_TITLES.test(html),
    weight: 14,
    evidence: SCOLAIRE_TITLES.test(html) ? 'Pattern detecte: <h1>Bienvenue|Welcome' : undefined,
  })

  // 2. Pas de fond rouge plat
  checks.push({
    id: 'no_flat_red_bg',
    label: 'Pas de fond rouge plat (typique tutoriel)',
    passed: !FLAT_BG_COLORS.test(html) && !FLAT_BG_COLORS.test(css),
    weight: 5,
  })

  // 3. Pas de simple <ul><li> comme contenu principal
  checks.push({
    id: 'no_plain_list_only',
    label: 'Pas que des listes a puces simples',
    passed: !PLAIN_LIST.test(html) || (html.length > 8000),
    weight: 6,
  })

  // 4. Au moins 6 sections
  const secCount = countSections(html)
  checks.push({
    id: 'min_sections',
    label: `Au moins 6 sections (trouve: ${secCount})`,
    passed: secCount >= 6,
    weight: 12,
  })

  // 5. Polices premium
  checks.push({
    id: 'premium_fonts',
    label: 'Police premium (Inter / Manrope / Space Grotesk / etc.)',
    passed: PREMIUM_FONTS.test(html) || PREMIUM_FONTS.test(css) || HAS_FONT_LINK_PRECONNECT.test(html),
    weight: 8,
  })

  // 6. Au moins un gradient
  checks.push({
    id: 'has_gradient',
    label: 'Au moins un linear/radial-gradient',
    passed: HAS_GRADIENT.test(html) || HAS_GRADIENT.test(css),
    weight: 8,
  })

  // 7. Mesh / blur (depth)
  checks.push({
    id: 'has_depth',
    label: 'Effet de profondeur (blur / backdrop-filter)',
    passed: HAS_MESH_BLUR.test(html) || HAS_MESH_BLUR.test(css) || HAS_BACKDROP_FILTER.test(html) || HAS_BACKDROP_FILTER.test(css),
    weight: 8,
  })

  // 8. Animations (@keyframes ou transition + IntersectionObserver / rAF)
  const hasAnimations = (HAS_KEYFRAMES.test(all) || HAS_TRANSITION.test(all))
    && (HAS_INTERSECTION_OBSERVER.test(js) || HAS_RAF.test(js) || HAS_KEYFRAMES.test(all))
  checks.push({
    id: 'has_animations',
    label: 'Animations CSS/JS (keyframes + transitions + observer/rAF)',
    passed: hasAnimations,
    weight: 12,
  })

  // 9. SVG inline d'au moins 40 caracteres (pas un <svg/> vide)
  checks.push({
    id: 'has_inline_svg',
    label: 'SVG inline travaille (logo / illustration)',
    passed: HAS_INLINE_SVG.test(html),
    weight: 6,
  })

  // 10. Layout moderne (flex / grid)
  checks.push({
    id: 'has_modern_layout',
    label: 'Layout flex / grid utilise',
    passed: HAS_FLEX_OR_GRID.test(html) || HAS_FLEX_OR_GRID.test(css),
    weight: 5,
  })

  // 11. Bordures arrondies modernes
  checks.push({
    id: 'has_radius',
    label: 'border-radius >= 10px present',
    passed: HAS_BORDER_RADIUS_LARGE.test(html) || HAS_BORDER_RADIUS_LARGE.test(css),
    weight: 4,
  })

  // 12. Variables CSS (theme system)
  checks.push({
    id: 'has_css_vars',
    label: 'Variables CSS (theme system)',
    passed: HAS_CSS_VARS.test(html) || HAS_CSS_VARS.test(css),
    weight: 4,
  })

  // 13. Typographie responsive (clamp())
  checks.push({
    id: 'has_clamp',
    label: 'Typographie responsive (clamp())',
    passed: HAS_CLAMP.test(html) || HAS_CLAMP.test(css),
    weight: 4,
  })

  // 14. Au moins 1 image
  const imgCount = countImages(html)
  checks.push({
    id: 'has_images',
    label: `Au moins 2 images (trouve: ${imgCount})`,
    passed: imgCount >= 2,
    weight: 6,
  })

  // 15. :hover styles (interactions)
  checks.push({
    id: 'has_hover',
    label: 'Etats :hover definis',
    passed: HAS_HOVER.test(html) || HAS_HOVER.test(css),
    weight: 4,
  })

  // 16. Taille HTML (penalise les pages de 200 lignes max)
  const size = htmlSize(html)
  checks.push({
    id: 'html_size',
    label: `HTML > 6 ko (trouve: ${Math.round(size / 1024)} ko)`,
    passed: size > 6000,
    weight: 6,
  })

  // 17. Pas de seul <style> = body{...} de 5 lignes
  checks.push({
    id: 'rich_styling',
    label: 'CSS substantiel (> 1.5 ko)',
    passed: (css.length + (html.match(/<style[\s\S]*?<\/style>/i)?.[0]?.length ?? 0)) > 1500,
    weight: 6,
  })

  // 18. Transformations 3D (rotateY/X, perspective, preserve-3d)
  checks.push({
    id: 'has_3d_transforms',
    label: 'Transformations 3D (rotateY/X, perspective, preserve-3d)',
    passed: HAS_TRANSFORM_3D.test(html) || HAS_TRANSFORM_3D.test(css),
    weight: 8,
  })

  // 19. Scroll-driven / parallax (sticky + scroll-progress, IntersectionObserver, ScrollTrigger)
  checks.push({
    id: 'has_scroll_driven',
    label: 'Animation pilotee par scroll (sticky/IntersectionObserver/--p)',
    passed: HAS_PARALLAX.test(html) || HAS_PARALLAX.test(css) || HAS_PARALLAX.test(js),
    weight: 8,
  })

  // 20. Multi-gradient layered (depth feel)
  checks.push({
    id: 'has_layered_gradients',
    label: 'Au moins 2 gradients layered (depth)',
    passed: HAS_MULTI_GRADIENTS.test(html) || HAS_MULTI_GRADIENTS.test(css),
    weight: 6,
  })

  // 21. Pas de cluster de cartes plates colorees sans images (pattern scolaire #1)
  const flatCardCount = countFlatColoredCards(html)
  const hasCardCluster = hasFlatColoredCardCluster(html)
  checks.push({
    id: 'no_flat_card_cluster',
    label: `Pas de cartes plates colorees sans images (trouve: ${flatCardCount}, cluster: ${hasCardCluster ? 'oui' : 'non'})`,
    passed: flatCardCount < 2 && !hasCardCluster,
    weight: 14, // Tres fort — c est exactement le pattern que le user a refusu deux fois
    evidence: hasCardCluster ? 'Cluster de >=2 divs colores plats sans <img>/<svg> a l interieur' : (flatCardCount >= 2 ? `${flatCardCount} cartes plates detectees` : undefined),
  })

  // La barre ne bouge pas; ce qui compte pour l atteindre depend du GENRE. Un
  // outil a une page n a pas a fournir un hero, une galerie et une rotation 3D
  // au scroll — les exiger degrade le produit au lieu de l ameliorer.
  const ambition = resolveVisualAmbition(prompt, intent, files)
  const excluded = new Set(AMBITION_EXCLUDED_CHECKS[ambition])
  const scored = checks.filter((check) => !excluded.has(check.id))

  const totalWeight = scored.reduce((sum, c) => sum + c.weight, 0) || 1
  const earned = scored.filter((c) => c.passed).reduce((sum, c) => sum + c.weight, 0)
  const score = Math.round((earned / totalWeight) * 100)

  // Floor: 70 by default (raise from 65). Visual projects must clear it.
  const floor = 70

  const failedChecks = scored.filter((c) => !c.passed).map((c) => c.id)
  const blockingFailures = ['no_scolaire_title', 'no_flat_card_cluster']
  const passed = score >= floor && !blockingFailures.some((id) => failedChecks.includes(id))

  const summary = passed
    ? `Rendu visuel acceptable (${score}/100, barre ${AMBITION_BAR[ambition]}).`
    : `Rendu visuel insuffisant (${score}/100, seuil ${floor}). ${failedChecks.length} echec(s) de controle. Barre appliquee — ${AMBITION_BAR[ambition]}.`

  return { score, passed, floor, checks: scored, failedChecks, summary, source: 'source_static', ambition }
}
