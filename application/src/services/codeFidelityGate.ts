// ---------------------------------------------------------------------------
// Code Fidelity Gate — v71
// Post-generation validation that the produced files actually match the
// requested SUBJECT. Catches the "Coca-Cola → restaurant generique" drift.
// ---------------------------------------------------------------------------

import type { CodeIntent } from './codeIntent'
import { hasPerceptualColorMatch } from './codeColorMetrics.ts'
import { CODE_ASSET_MANIFEST_PATH } from './codeInterModuleAssets.ts'

/** Local file shape — a subset of `CodeFile` from codeOrchestrator. We keep
 * a local type alias to avoid a circular import (orchestrator → fidelity → orchestrator). */
type CodeFile = {
  name: string
  language: string
  content: string
}

export type BrandFidelityIssue =
  | 'subject_name_missing'
  | 'palette_missing'
  | 'image_asset_missing'
  | 'product_keywords_missing'
  | 'used_off_topic_terms'
  | 'shader_signature_missing'

export type BrandFidelityReport = {
  /** Score reduction to apply on the orchestrator-side fidelity score (0..100). */
  scorePenalty: number
  /** Hard cap to apply when the most critical rule (subject name) is broken. */
  scoreCap: number | null
  /** Issues detected, listed for retry hints. */
  issues: BrandFidelityIssue[]
  /** Human-readable hint to feed into a retry prompt. Empty when no issues. */
  retryHint: string
  /** Whether this report should be considered a hard failure that mandates retry. */
  shouldRetry: boolean
}

const OFF_TOPIC_DRIFT_PATTERNS: Array<{ pattern: RegExp; reason: string }> = [
  { pattern: /\brestaurant(s)?\b/i, reason: 'mention de "restaurant" dans le rendu' },
  { pattern: /\bmenu du jour\b/i, reason: 'menu du jour' },
  { pattern: /\btable d hote\b/i, reason: 'table d hote' },
  { pattern: /\bchef etoile\b/i, reason: 'chef etoile' },
  { pattern: /\breservation table\b/i, reason: 'reservation table' },
  { pattern: /\bblog (culinaire|food|cuisine)\b/i, reason: 'blog culinaire generique' },
  { pattern: /\bsaas (platform|abstract|generic)\b/i, reason: 'SaaS abstract pivot' },
]

/**
 * Run the brand-fidelity gate on the generated files. Only fires when the
 * intent has a brand subject — generic prompts are exempt.
 *
 * Rules:
 *   1. The brand display name MUST appear (case-insensitive) in at least one
 *      visual file (HTML/JSX/TSX/Vue/Svelte/CSS title/comment doesn't count
 *      — must be in actual visible content). Otherwise → score capped at 30.
 *   2. The brand primary color must appear perceptually in CSS/JSX styles
 *      (hex/rgb/oklch accepted via deltaE Lab). -20 score when missing.
 *   3. At least one inter-module image marker or materialized asset reference
 *      must appear in visual code when the asset manifest provides an image.
 *   4. At least 1 product keyword from the brand profile must appear in
 *      copy (titles, paragraphs). -10 score otherwise.
 *   5. Off-topic terms ("restaurant", "menu du jour", ...) must NOT appear
 *      when the brand domain is not food. -25 score and `subject_name_missing`
 *      type issue when found.
 */
export function evaluateBrandFidelity(intent: CodeIntent, files: CodeFile[]): BrandFidelityReport {
  const subject = intent.assetPlan?.subject
  if (!subject || subject.source !== 'brand' || !subject.canonical || !subject.brandProfile) {
    return { scorePenalty: 0, scoreCap: null, issues: [], retryHint: '', shouldRetry: false }
  }

  const profile = subject.brandProfile
  const displayName = subject.canonical
  const issues: BrandFidelityIssue[] = []
  const retryHints: string[] = []
  let scorePenalty = 0
  let scoreCap: number | null = null

  // Concatenate visual file contents for content-level checks.
  const visualFiles = files.filter((f) => isVisualFile(f.name))
  const visualBody = visualFiles.map((f) => f.content).join('\n').toLowerCase()
  const styleBody = files
    .filter((f) => /\.(css|scss|sass|less|styl|tsx|jsx|vue|svelte|html)$/i.test(f.name))
    .map((f) => f.content)
    .join('\n')

  // --- Rule 1: subject name must appear in visible content -----------------
  const nameAppearances = countAppearances(visualBody, displayName.toLowerCase())
  if (nameAppearances === 0) {
    issues.push('subject_name_missing')
    retryHints.push(
      `Tu n as pas mentionne "${displayName}" dans le rendu. La page DOIT etre sur ${displayName}, pas sur un sujet adjacent.`
      + ` Ajoute "${displayName}" dans le <title>, le hero <h1>, et au moins 3 sections.`,
    )
    scoreCap = scoreCap === null ? 30 : Math.min(scoreCap, 30)
  } else if (nameAppearances < 3) {
    // Mentioned but not enough — still a partial issue but no hard cap.
    retryHints.push(
      `"${displayName}" n apparait que ${nameAppearances} fois dans le rendu.`
      + ` Renforce la presence de la marque dans les titres de section et le hero.`,
    )
    scorePenalty += 10
  }

  // --- Rule 2: primary color must appear in CSS/styles ---------------------
  if (profile.primaryColor) {
    if (!hasPerceptualColorMatch(styleBody, profile.primaryColor)) {
      issues.push('palette_missing')
      retryHints.push(
        `La couleur principale de ${displayName} (${profile.primaryColor}) n est pas presente perceptuellement dans les styles.`
        + ` Utilise une couleur proche deltaE/Lab pour le hero, les CTAs et les accents (hex, rgb ou oklch accepte).`,
      )
      scorePenalty += 20
    }
  }

  // --- Rule 3: a generated inter-module image must be referenced ------------
  const manifest = files.find((file) => file.name === CODE_ASSET_MANIFEST_PATH)
  let imageReferences: string[] = []
  try {
    const assets = JSON.parse(manifest?.content || '{}')?.assets
    if (Array.isArray(assets)) {
      imageReferences = assets
        .filter((asset) => asset?.kind === 'image')
        .flatMap((asset) => [asset.path, asset.previewUrl].filter((value): value is string => typeof value === 'string'))
    }
  } catch {
    imageReferences = []
  }
  if (imageReferences.length > 0) {
    const hasImageReference = /PLACEHOLDER_(?:SUBJECT_)?IMG(?:_[A-Z0-9]+)?/i.test(visualBody)
      || imageReferences.some((reference) => visualBody.includes(reference.toLowerCase()))
    if (!hasImageReference) {
      issues.push('image_asset_missing')
      retryHints.push(
        `Un asset image optimise de ${displayName} est disponible mais le rendu ne le reference pas.`
        + ` Utilise PLACEHOLDER_SUBJECT_IMG dans le hero ou le chemin image du manifeste ${CODE_ASSET_MANIFEST_PATH}.`,
      )
      scorePenalty += 15
    }
  }

  // --- Rule 4: at least one product keyword in copy ------------------------
  const productKeywords = profile.productKeywords ?? []
  if (productKeywords.length > 0) {
    const matched = productKeywords.filter((kw) => visualBody.includes(kw.toLowerCase()))
    if (matched.length === 0) {
      issues.push('product_keywords_missing')
      retryHints.push(
        `Aucun mot-cle produit de ${displayName} (${productKeywords.slice(0, 4).join(', ')}) n apparait dans le copy.`
        + ` Integre au moins 2 de ces termes dans des titres de section.`,
      )
      scorePenalty += 10
    }
  }

  // --- Rule 5: off-topic terms (only when the domain is NOT food/restaurant)
  const isFoodBrand = /food|restaurant|cafe|coffee|fast/i.test(subject.domain ?? '')
  if (!isFoodBrand) {
    for (const drift of OFF_TOPIC_DRIFT_PATTERNS) {
      if (drift.pattern.test(visualBody)) {
        issues.push('used_off_topic_terms')
        retryHints.push(
          `Le rendu contient ${drift.reason} alors que le sujet est ${displayName} (${subject.domain ?? 'autre domaine'}).`
          + ` Reecris ces sections en parlant de ${displayName} explicitement.`,
        )
        scorePenalty += 25
        break
      }
    }
  }

  // --- Rule 6 — a signature visual effect must be present when the brand has
  // a concrete product shape. This no longer forces one Fresnel shader: CSS 3D,
  // iridescence, bloom, custom shader or a canvas product treatment are valid.
  if (profile.productShape) {
    // Looking for any of the signature options the brand_landing variant suggests.
    const visualBodyOriginalCase = visualFiles.map((f) => f.content).join('\n')
    const hasShader = /\bShaderMaterial\s*\(/i.test(visualBodyOriginalCase)
      || /fragmentShader\s*:/i.test(visualBodyOriginalCase)
      || /\biridescence\s*:/i.test(visualBodyOriginalCase)
      || /BokehPass\b/i.test(visualBodyOriginalCase)
      || /UnrealBloomPass\b/i.test(visualBodyOriginalCase) && /customShaderPass/i.test(visualBodyOriginalCase)
      || /transform\s*:[^;]*(?:rotateY|rotateX|translateZ|preserve-3d|perspective)/i.test(visualBodyOriginalCase)
      || /getContext\(\s*['"]2d['"]\s*\)|getContext\(\s*['"]webgl/i.test(visualBodyOriginalCase)
    if (!hasShader) {
      issues.push('shader_signature_missing')
      retryHints.push(
        `${displayName} est une page brand_landing — l effet signature produit est manquant.`
        + ` Ajoute une execution visuelle forte adaptee a la stack: shader Three.js, iridescence/bloom, produit CSS 3D, canvas product treatment ou background liquide aux couleurs de marque.`,
      )
      scorePenalty += 10
    }
  }

  // Final cap clamp.
  if (scoreCap !== null) {
    scoreCap = Math.max(0, Math.min(scoreCap, 100))
  }
  scorePenalty = Math.max(0, Math.min(scorePenalty, 90))

  const shouldRetry = issues.includes('subject_name_missing')
    || issues.includes('used_off_topic_terms')
    || issues.includes('shader_signature_missing')

  return {
    scorePenalty,
    scoreCap,
    issues,
    retryHint: retryHints.length > 0
      ? retryHints.map((line, idx) => `${idx + 1}. ${line}`).join('\n')
      : '',
    shouldRetry,
  }
}

function isVisualFile(name: string): boolean {
  return /\.(html|htm|jsx|tsx|vue|svelte|astro|mdx|md)$/i.test(name)
}

function countAppearances(text: string, needle: string): number {
  if (!needle) return 0
  const escaped = needle.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const re = new RegExp(escaped, 'gi')
  const matches = text.match(re)
  return matches ? matches.length : 0
}
