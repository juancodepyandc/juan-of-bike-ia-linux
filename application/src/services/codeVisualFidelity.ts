// ---------------------------------------------------------------------------
// codeVisualFidelity — gate qui inspecte le HTML/CSS/JS livre et MESURE le
// niveau visuel. Si le score est trop bas, l orchestrator force une regen
// avec une critique precise (au lieu de livrer une page Coca-Cola scolaire).
// ---------------------------------------------------------------------------

import type { CodeIntent } from './codeIntent'
import {
  buildRenderedVisualAuditCritique,
  scoreRenderedVisualAudit,
  type CodeVisualRenderAudit,
} from './codeVisualRenderAudit.ts'

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
}

type CodeFile = { name: string; language: string; content: string }

// ---------------------------------------------------------------------------
// HTML / CSS / JS aggregation
// ---------------------------------------------------------------------------

function findHtml(files: CodeFile[]): string {
  return files.filter((f) => /\.(html|htm)$/i.test(f.name)).map((f) => f.content).join('\n')
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
// Detector helpers
// ---------------------------------------------------------------------------

const PREMIUM_FONTS = /Inter|Manrope|Satoshi|DM\s*Sans|Space\s*Grotesk|Plus\s*Jakarta|Poppins|Outfit|Sora|Bungee/i
const SCOLAIRE_TITLES = /<h1[^>]*>\s*Bienvenue\b|<h1[^>]*>\s*Welcome\b/i
const FLAT_BG_COLORS = /background\s*:\s*(red|blue|green|yellow|orange|purple|pink|#[0-9a-f]{3,6})\s*[;}"]|background-color\s*:\s*(red|blue|green|yellow|orange|purple|pink)\b/i
const PLAIN_LIST = /<ul[^>]*>(?:\s*<li[^>]*>[^<]{0,80}<\/li>\s*){2,8}\s*<\/ul>/i
const HAS_GRADIENT = /linear-gradient|radial-gradient|conic-gradient/i
const HAS_MESH_BLUR = /filter\s*:\s*blur\(\s*[8-9]\d|filter\s*:\s*blur\(\s*1\d{2,}/i
const HAS_KEYFRAMES = /@keyframes/i
const HAS_TRANSITION = /transition\s*:|transition:/i
const HAS_INTERSECTION_OBSERVER = /IntersectionObserver/i
const HAS_RAF = /requestAnimationFrame/i
const HAS_INLINE_SVG = /<svg\b[^>]*>[\s\S]{120,}?<\/svg>/i
const HAS_FLEX_OR_GRID = /display\s*:\s*(flex|grid|inline-flex|inline-grid)/i
const HAS_BACKDROP_FILTER = /backdrop-filter\s*:|-webkit-backdrop-filter\s*:/i
const HAS_BORDER_RADIUS_LARGE = /border-radius\s*:\s*([1-9]\d|1\.|2\.|3\.)/i
const HAS_CSS_VARS = /var\(\s*--/i
const HAS_CLAMP = /clamp\s*\(/i
const HAS_HOVER = /:hover/i
const HAS_FONT_LINK_PRECONNECT = /fonts\.googleapis\.com|fonts\.gstatic\.com/i
const HAS_TRANSFORM_3D = /transform\s*:[^;]*(?:rotate3d|rotateX|rotateY|rotateZ|perspective|translate3d|preserve-3d)/i
const HAS_PARALLAX = /scroll-driven|sticky|IntersectionObserver|ScrollTrigger|--p\s*\)/i
const HAS_MULTI_GRADIENTS = /linear-gradient[\s\S]*linear-gradient|radial-gradient[\s\S]*radial-gradient/i

// ---------------------------------------------------------------------------
// Section counter — counts <section> + obvious semantic wrappers
// ---------------------------------------------------------------------------

function countSections(html: string): number {
  const sections = (html.match(/<section\b/gi) || []).length
  // Count semantic <article> too if there are no sections
  if (sections === 0) {
    const articles = (html.match(/<article\b/gi) || []).length
    if (articles > 0) return articles
  }
  return sections
}

function countImages(html: string): number {
  // Includes <img>, srcset, AND background-image url() inside <style>.
  const imgTags = (html.match(/<img\b/gi) || []).length
  const bgImgs = (html.match(/background(-image)?\s*:[^;]*url\(/gi) || []).length
  return imgTags + bgImgs
}

/** Count "card-like" elements that are JUST flat colored boxes with text —
 *  the scolaire pattern the user keeps complaining about. */
function countFlatColoredCards(html: string): number {
  // Look for repeated <div> blocks that have a solid background color but
  // NO <img>, NO svg path inside, NO gradient, NO transform.
  const divRegex = /<div[^>]*style="[^"]*background[^"]*"[^>]*>([\s\S]{0,300})<\/div>/gi
  let count = 0
  let m: RegExpExecArray | null
  while ((m = divRegex.exec(html)) !== null) {
    const content = m[1]
    if (/<(img|svg|canvas|video)\b/i.test(content)) continue
    if (/linear-gradient|radial-gradient/i.test(m[0])) continue
    count += 1
  }
  return count
}

/** Detect the typical "trois cartes rouges plates" pattern that the user
 *  flagged twice — multiple sibling divs with the same solid background
 *  color and no images inside. */
function hasFlatColoredCardCluster(html: string): boolean {
  // Look for 2+ consecutive elements with the same flat background, no images.
  const flatPattern = /<div[^>]*background[^>]*>\s*<[^>]+>[^<]{1,80}<\/[^>]+>\s*<\/div>\s*<div[^>]*background/i
  return flatPattern.test(html)
}

function htmlSize(html: string): number {
  return html.length
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
): VisualFidelityReport {
  const html = findHtml(files)
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

  const totalWeight = checks.reduce((sum, c) => sum + c.weight, 0)
  const earned = checks.filter((c) => c.passed).reduce((sum, c) => sum + c.weight, 0)
  const score = Math.round((earned / totalWeight) * 100)

  // Floor: 70 by default (raise from 65). Visual projects must clear it.
  const floor = 70

  const failedChecks = checks.filter((c) => !c.passed).map((c) => c.id)
  const blockingFailures = ['no_scolaire_title', 'no_flat_card_cluster']
  const passed = score >= floor && !blockingFailures.some((id) => failedChecks.includes(id))

  const summary = passed
    ? `Rendu visuel acceptable (${score}/100).`
    : `Rendu visuel insuffisant (${score}/100, seuil ${floor}). ${failedChecks.length} echec(s) de controle.`

  return { score, passed, floor, checks, failedChecks, summary, source: 'source_static' }
}

/**
 * Build the critique block injected in the regeneration prompt when the
 * visual fidelity check fails. Concrete and direct so the LLM understands
 * what needs to change.
 */
export function buildVisualFidelityCritique(report: VisualFidelityReport): string {
  if (report.passed) return ''
  if (report.source === 'render_audit') return buildRenderedVisualAuditCritique(report)

  const failed = report.checks.filter((c) => !c.passed)
  return [
    '## ECHEC DU CONTROLE QUALITE VISUEL — REGENERATION OBLIGATOIRE',
    `Score actuel: ${report.score}/100 (seuil minimum: ${report.floor}).`,
    '',
    'Ta page precedente etait trop pauvre. Voici les controles qui ont echoue:',
    ...failed.map((c) => `- ${c.label}${c.evidence ? ` — ${c.evidence}` : ''}`),
    '',
    'CORRIGE ABSOLUMENT POUR LA PROCHAINE LIVRAISON:',
    failed.find((c) => c.id === 'no_scolaire_title') ? '- SUPPRIME tout titre "Bienvenue chez X" — remplace par un slogan court et fort en deux lignes.' : '',
    failed.find((c) => c.id === 'min_sections') ? '- AJOUTE des sections (objectif: 7-10): hero / anatomie / materiaux / galerie / specs / KPIs / compare / testimonials / CTA / footer.' : '',
    failed.find((c) => c.id === 'has_gradient') ? '- AJOUTE des gradients (mesh blobs en arriere-plan, gradient text sur les hero, gradient buttons).' : '',
    failed.find((c) => c.id === 'has_depth') ? '- AJOUTE de la profondeur via filter: blur(120-160px) sur des blobs absolute + backdrop-filter sur la nav.' : '',
    failed.find((c) => c.id === 'has_animations') ? '- AJOUTE des animations: @keyframes, transitions cubic-bezier, IntersectionObserver pour scroll reveal.' : '',
    failed.find((c) => c.id === 'has_inline_svg') ? '- AJOUTE au moins un SVG inline travaille (logo de la marque, icones, illustrations).' : '',
    failed.find((c) => c.id === 'has_images') ? '- UTILISE les placeholders d images PLACEHOLDER_IMG_HERO/DETAIL/LIFESTYLE1/LIFESTYLE2 dans <img src="...">.' : '',
    failed.find((c) => c.id === 'premium_fonts') ? '- IMPORTE Inter ou Space Grotesk via Google Fonts (preconnect + display=swap).' : '',
    failed.find((c) => c.id === 'has_css_vars') ? '- DECLARE des variables CSS dans :root pour --bg, --fg, --accent, --border.' : '',
    failed.find((c) => c.id === 'has_clamp') ? '- UTILISE clamp() pour les tailles de police responsive.' : '',
    failed.find((c) => c.id === 'has_hover') ? '- AJOUTE des etats :hover sur les liens, cartes, boutons.' : '',
    failed.find((c) => c.id === 'html_size') ? '- DEVELOPPE le contenu — la page doit faire au moins 8 ko de HTML, pas 1 ko.' : '',
    failed.find((c) => c.id === 'rich_styling') ? '- DEVELOPPE le CSS — la page doit avoir au moins 2-3 ko de CSS, pas 200 lignes.' : '',
    failed.find((c) => c.id === 'has_3d_transforms') ? '- AJOUTE des transformations 3D: rotateY au scroll OU perspective + preserve-3d sur les cards (flip 3D) OU rotation continue de la bouteille/produit.' : '',
    failed.find((c) => c.id === 'has_scroll_driven') ? '- AJOUTE une animation pilotee par scroll: section sticky avec --p, IntersectionObserver, OU ScrollTrigger. Le visuel principal doit reagir au scroll.' : '',
    failed.find((c) => c.id === 'has_layered_gradients') ? '- AJOUTE au moins 2 gradients layered (mesh blobs en fond + gradient hero text).' : '',
    failed.find((c) => c.id === 'no_flat_card_cluster')
      ? '- ECHEC CRITIQUE: tu as livre des CARTES PLATES COLOREES sans images (`<div style="background:red">Texte</div>`). C est exactement le pattern interdit.\n  CORRIGE: chaque carte DOIT contenir soit un <img src="PLACEHOLDER_IMG_*">, soit un SVG inline travaille (>100 chars), soit un canvas. Les cards sans visuel sont REJETEES.\n  Si tu utilises des cards (saveurs, materiaux, produits, services), CHACUNE doit avoir une image au-dessus du texte.'
      : '',
    '',
    'Reprends le STARTER TEMPLATE fourni et remplace UNIQUEMENT les {{slots}} par du contenu adapte. NE simplifie PAS le squelette.',
    'AUCUN DIV avec `background: <couleur unie>` SANS image/svg/canvas a l interieur. Aucune exception.',
  ].filter(Boolean).join('\n')
}
