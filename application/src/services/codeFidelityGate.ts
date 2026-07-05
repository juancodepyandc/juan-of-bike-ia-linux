// ---------------------------------------------------------------------------
// Code Fidelity Gate — v71
// Post-generation validation that the produced files actually match the
// requested SUBJECT. Catches the "Coca-Cola → restaurant generique" drift.
// ---------------------------------------------------------------------------

import type { CodeIntent } from './codeIntent'

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
  | 'image_markers_missing'
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
 *   2. The brand primary color hex MUST appear in CSS/JSX styles. -20 score
 *      and a retry hint when missing.
 *   3. At least one PLACEHOLDER_SUBJECT_IMG marker must appear in HTML/JSX
 *      when images were prepared (intent.__subjectImageDataUrls populated).
 *      -15 score otherwise.
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
    const primaryHex = profile.primaryColor.toLowerCase()
    const styleLower = styleBody.toLowerCase()
    const hasPrimary = styleLower.includes(primaryHex)
      // Also accept the hex without the '#' (some CSS frameworks tokenize it).
      || styleLower.includes(primaryHex.replace('#', ''))
    if (!hasPrimary) {
      issues.push('palette_missing')
      retryHints.push(
        `La couleur principale de ${displayName} (${profile.primaryColor}) n est pas presente dans les styles.`
        + ` Utilise-la pour le hero, les CTAs et les accents.`,
      )
      scorePenalty += 20
    }
  }

  // --- Rule 3: image markers must be used when images were prepared --------
  const stash = intent as unknown as { __subjectImageDataUrls?: string[]; __subjectImageDataUrl?: string }
  const imagesPrepared = (stash.__subjectImageDataUrls?.length ?? 0) > 0 || !!stash.__subjectImageDataUrl
  if (imagesPrepared) {
    const hasAnyMarker = /PLACEHOLDER_SUBJECT_IMG(_\d+)?/i.test(visualBody)
    if (!hasAnyMarker) {
      issues.push('image_markers_missing')
      retryHints.push(
        `Des images reelles de ${displayName} ont ete telechargees mais aucun marker PLACEHOLDER_SUBJECT_IMG n a ete utilise.`
        + ` Insere au minimum <img src="PLACEHOLDER_SUBJECT_IMG" ...> dans le hero et <img src="PLACEHOLDER_SUBJECT_IMG_2" ...> dans une section showcase.`,
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

  // --- Rule 6 (v77f) — shader signature must be present when the brand has a productShape.
  // The brand_landing variant promised a Fresnel halo / iridescence / liquid bg
  // shader. When the LLM drops it (cf. 7B stochasticity tour 10), we score it
  // and ship a copy-paste code snippet in the retry hint so the next pass can
  // just include it verbatim.
  if (profile.productShape) {
    // Looking for any of the 5 shader options the brand_landing variant suggests.
    const visualBodyOriginalCase = visualFiles.map((f) => f.content).join('\n')
    const hasShader = /\bShaderMaterial\s*\(/i.test(visualBodyOriginalCase)
      || /fragmentShader\s*:/i.test(visualBodyOriginalCase)
      || /\biridescence\s*:/i.test(visualBodyOriginalCase)
      || /BokehPass\b/i.test(visualBodyOriginalCase)
      || /UnrealBloomPass\b/i.test(visualBodyOriginalCase) && /customShaderPass/i.test(visualBodyOriginalCase)
    if (!hasShader) {
      issues.push('shader_signature_missing')
      retryHints.push(
        `${displayName} est une page brand_landing — le shader signature OBLIGATOIRE est manquant.`
        + ` Ajoute le halo Fresnel autour du produit 3D (THREE.ShaderMaterial avec uColor=${profile.primaryColor},`
        + ` vertexShader expose vNormalW + vViewDir, fragmentShader fresnel pow 3 + pulse sin uTime,`
        + ` AdditiveBlending + transparent + depthWrite:false).`
        + ` Le mesh halo est productMesh.geometry scaled 1.08x et ajoute via productMesh.add(halo).`
        + ` Anime via haloMat.uniforms.uTime.value = clock.getElapsedTime() dans le requestAnimationFrame loop.`,
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
