/**
 * v77zl — humanoid anatomy directive block builder (pure, dep-free).
 *
 * Pulls Meshy-grade humanoid priors into the FLUX reference prompt before
 * the diffusion model ever sees the user request. The Hunyuan3D shape
 * pipeline downstream cannot recover anatomical proportions on its own —
 * if the reference image already shows a chibi blob, Hunyuan will
 * faithfully reproduce a chibi blob 3D mesh. So the corrections must be
 * baked into the FLUX prompt itself, not into post-hoc validation.
 *
 * Two callers:
 *  - buildFluxVisualDescription on first pass, no previousMetrics
 *  - same on auto-correction retries, with previousMetrics from the v77zj
 *    Python validator so the next reference image cannot re-emit the same
 *    proportion failure category.
 *
 * Pure: no Tauri / React deps so node --test can exercise it directly.
 */

export type HumanoidAnatomyIntent = {
  purpose:
    | 'visual_preview'
    | 'printable_prototype'
    | 'mechanical_part'
    | 'character'
    | 'body_part'
    | 'product'
    | 'game_asset'
  subjectKind:
    | 'object'
    | 'mechanical_part'
    | 'assembly'
    | 'character'
    | 'creature'
    | 'body_part'
    | 'product'
    | 'vehicle'
    | 'architecture'
    | 'tool'
    | 'electrical_system'
}

export type HumanoidProportionMetrics = {
  /** vertical_extent / max(other extents). Adults 3-4, chibi ~2, blob ~1. */
  aspectRatio?: number | null
  /** share of vertices in top 1/8 of vertical axis. Adults ~0.15, chibi ~0.30+. */
  headVertexFraction?: number | null
  /** head zone width / bottom-25% width. Adults ~0.4, inverted >1. */
  headBodyWidthRatio?: number | null
}

export function buildHumanoidAnatomyBlock(
  intent: HumanoidAnatomyIntent,
  prompt: string,
  previousMetrics?: HumanoidProportionMetrics | null,
): string {
  const isHumanoid = (
    intent.purpose === 'character'
    || intent.purpose === 'body_part'
    || intent.subjectKind === 'character'
    || intent.subjectKind === 'creature'
    || intent.subjectKind === 'body_part'
  )
  if (!isHumanoid) return ''

  const realisticRequested = /\b(realiste|realistic|adult|adulte|photorealist)\b/i.test(prompt)
  const stylizedRequested = /\b(chibi|cartoon|anime|stylis[eé])\b/i.test(prompt)

  const baseLines: string[] = [
    'HUMANOID ANATOMY DIRECTIVES (Meshy-grade requirement):',
    '- Full-body framing: subject occupies the WHOLE vertical extent of the image, head at top, feet at bottom, NO head close-up, NO waist crop',
    '- Vertical silhouette aspect ratio at least 3:1 (height:width) — the subject is taller than wide',
    '- Head occupies approximately 12% of the total vertical extent for realistic adult (1:7 head:body), 18% for young adult, 25% for child',
    '- Hips and feet zone WIDER than the head zone (no inverted proportions, no head wider than shoulders unless explicit helmet/coiffure was requested)',
    '- Limbs separated and clearly visible: arms not glued to torso, legs distinct, fingers on each hand',
    '- Bilateral symmetry: left and right halves match (left arm = right arm length, left ear = right ear, left eye = right eye)',
    '- Stable centered standing pose by default (T-pose or A-pose) unless an explicit action verb appears in the user prompt',
  ]

  if (realisticRequested && !stylizedRequested) {
    baseLines.push(
      '- Realistic adult mode: 1:7 head:body ratio, photorealistic skin texture, sharp clothing edges, individual hair strands not blobby masses, defined facial features (eye shape, nose bridge, jawline)',
      '- NO chibi proportions, NO oversized head, NO marshmallow body — push toward real adult anatomy',
    )
  } else if (stylizedRequested) {
    baseLines.push(
      '- Stylised mode acknowledged: chibi/anime allowed but still respect bilateral symmetry, clear limb separation, full-body framing',
    )
  } else {
    baseLines.push(
      '- Neutral character mode: respect both realistic adult proportions OR stylised proportions if obvious from costume cues, but never blob silhouettes',
    )
  }

  if (previousMetrics) {
    const aspect = previousMetrics.aspectRatio ?? null
    const headFraction = previousMetrics.headVertexFraction ?? null
    const headWidth = previousMetrics.headBodyWidthRatio ?? null
    const corrections: string[] = []
    if (aspect !== null && aspect < 1.4) {
      corrections.push(`PREVIOUS ATTEMPT FAILED: silhouette was blob-shaped (height:width = ${aspect.toFixed(2)}). This time MUST be 3:1 vertical.`)
    } else if (aspect !== null && aspect < 1.8) {
      corrections.push(`PREVIOUS ATTEMPT FAILED: silhouette was squat (height:width = ${aspect.toFixed(2)}). This time MUST be 3:1 vertical for adult.`)
    }
    if (headFraction !== null && headFraction > 0.45) {
      corrections.push(`PREVIOUS ATTEMPT FAILED: head dominated (${(headFraction * 100).toFixed(0)}% of vertices in top 1/8). Show FULL BODY, head ~12% of total height.`)
    } else if (headFraction !== null && headFraction > 0.30 && realisticRequested) {
      corrections.push(`PREVIOUS ATTEMPT FAILED: chibi proportions (${(headFraction * 100).toFixed(0)}% head) but realistic was requested. Push toward 1:7 adult.`)
    }
    if (headWidth !== null && headWidth > 1.5) {
      corrections.push(`PREVIOUS ATTEMPT FAILED: head was ${headWidth.toFixed(2)}x wider than legs. Hips and feet MUST be wider than head this time.`)
    }
    if (corrections.length > 0) {
      baseLines.push('', 'CORRECTIONS FROM PREVIOUS ATTEMPT:')
      baseLines.push(...corrections.map((c) => `- ${c}`))
    }
  }

  return `\n\n${baseLines.join('\n')}\n`
}
