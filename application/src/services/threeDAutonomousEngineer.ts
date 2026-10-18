/**
 * 3D Autonomous Engineer (v77zak + Multilingual FR/EN Precision Upgrade)
 *
 * Replaces human guessing with deterministic, senior-3D-engineer strategies:
 * - Recognizes subjects automatically (FR + EN)
 * - Decides monoview vs multiview intelligently (1 real reference > synthetic drift)
 * - Computes geometric & topological constraints (watertight, manifold, PBR 16K readiness)
 * - Handles OOM / timeout failures with adaptive fallbacks
 *
 * Pipeline: TRELLIS.2-4B (primary) → Hunyuan3D (fallback) → Auto-Rescue + PBR 16K
 */

import type { PreparedContextFile } from '../utils/multimodalContext.ts'
import type { ThreeDIntent } from './threeDIntent.ts'

export type ThreeDSubjectAnalysis = {
  likelySubject: 'character' | 'creature' | 'product' | 'mechanical' | 'architecture' | 'unknown'
  confidence: 'high' | 'medium' | 'low'
  keyTraits: string[]
  estimatedComplexity: 'simple' | 'moderate' | 'complex'
  tolerances?: {
    targetWatertight: boolean
    requiresSymmetryLock: boolean
    recommendedPbrResolution: '4K' | '8K' | '16K'
  }
}

export type ThreeDGenerationStrategy = {
  monoview: boolean
  whyMonoview: string
  targetImageCount: number
  searchStrategy: 'aggressive' | 'moderate' | 'minimal'
  estimatedSuccessRate: number
  fallbackIfFails: 'hunyuan3d' | 'reduce_complexity' | 'monoview_only'
}

export type ThreeDEngineerDecision = {
  analysis: ThreeDSubjectAnalysis
  strategy: ThreeDGenerationStrategy
  reasoning: string[]
  shouldProceed: boolean
  warningIfAny: string | null
}

/**
 * Analyze prompt (FR + EN) + images → decide subject, traits, and engineering tolerances.
 */
export function analyzeSubject(
  prompt: string,
  intent: ThreeDIntent,
  userImages: PreparedContextFile[],
): ThreeDSubjectAnalysis {
  const hasUserImage = userImages.length > 0

  const isCharacter =
    /\b(character|person|humanoid|avatar|hero|villain|npc|player|personnage|humain|humanoïde|guerrier|chevalier|mage|soldat|homme|femme|enfant|samouraï|ninja)\b/i.test(prompt)
    || intent.subjectKind === 'character'
    || intent.purpose === 'character'

  const isCreature =
    /\b(creature|animal|beast|monster|dragon|alien|demon|ghost|créature|monstre|bête|dinosaure|loup|chien|chat|cheval|oiseau| démon)\b/i.test(prompt)
    || intent.subjectKind === 'creature'

  const isMechanical =
    /\b(machine|mechanical|engine|mechanism|robot|automaton|apparatus|gear|piston|turbine|bearing|pulley|mécanisme|mécanique|moteur|engrenage|poulie|courroie|roulement|vérin|châssis|drone|véhicule|voiture|moto)\b/i.test(prompt)
    || intent.systemClass !== 'generic'
    || intent.subjectKind === 'mechanical_part'
    || intent.subjectKind === 'electrical_system'

  const isArchitecture =
    /\b(building|house|structure|architecture|space|room|interior|castle|tower|bridge|bâtiment|maison|château|tour|pont|intérieur|pièce|temple|cathédrale)\b/i.test(prompt)

  const isProduct =
    /\b(product|item|gadget|device|tool|object|furniture|chair|table|lamp|bottle|helmet|produit|objet|outil|meuble|chaise|lampe|casque|boîtier)\b/i.test(prompt)
    || intent.purpose === 'product'
    || intent.purpose === 'game_asset'

  const keyTraits: string[] = []
  if (isCharacter) keyTraits.push('bipedal humanoid')
  if (isCreature && /\b(four|quadr|wing|fly|ailes|quadrupède|volant)\b/i.test(prompt)) {
    keyTraits.push('non-humanoid locomotion')
  }
  if (/\b(armor|suit|costume|clothing|armure|tenue|vêtement|cape)\b/i.test(prompt)) {
    keyTraits.push('complex surface detail')
  }
  if (/\b(weapon|sword|gun|staff|shield|arme|épée|fusil|bouclier|bâton|arc)\b/i.test(prompt)) {
    keyTraits.push('held accessory')
  }
  if (/\b(small|tiny|miniature|précis|millimétrique|tolérance|iso)\b/i.test(prompt)) {
    keyTraits.push('fine detail focus')
  }
  if (/\b(transparent|glass|crystal|metal|chrome|gold|steel|verre|cristal|métal|acier|or|cuivre|carbone)\b/i.test(prompt)) {
    keyTraits.push('special PBR material')
  }

  const likelySubject = isCharacter
    ? 'character'
    : isCreature
      ? 'creature'
      : isMechanical
        ? 'mechanical'
        : isArchitecture
          ? 'architecture'
          : isProduct
            ? 'product'
            : 'unknown'

  const confidence = hasUserImage ? 'high' : likelySubject === 'unknown' ? 'low' : 'medium'

  const estimatedComplexity =
    keyTraits.length > 3 || /\b(complex|detailed|intricate|ornate|complexe|détaillé|articulé|assemblage)\b/i.test(prompt)
      ? 'complex'
      : keyTraits.length > 0
        ? 'moderate'
        : 'simple'

  return {
    likelySubject,
    confidence,
    keyTraits,
    estimatedComplexity,
    tolerances: {
      targetWatertight: isMechanical || isProduct || intent.requiresDimensionalPrecision,
      requiresSymmetryLock: isCharacter || isMechanical || intent.wantsSymmetry,
      recommendedPbrResolution: estimatedComplexity === 'complex' ? '16K' : '8K',
    },
  }
}

/**
 * Decide optimal generation strategy (Monoview vs Multiview + Web Reference Strategy).
 */
export function decideGenerationStrategy(
  analysis: ThreeDSubjectAnalysis,
  userImageCount: number,
  canSearchWeb: boolean,
): ThreeDGenerationStrategy {
  // Core engineering rule:
  // - If user provides a reference image: ALWAYS monoview (1 real reference beats synthetic halluncinations)
  // - If no user image: multiview ONLY for character/creature (needs 4 views for full 360° anatomy)
  // - If no user image: monoview for mechanical/product/architecture
  const monoview =
    userImageCount > 0
      ? true
      : analysis.likelySubject !== 'character' && analysis.likelySubject !== 'creature'

  const targetImageCount =
    userImageCount === 0
      ? analysis.likelySubject === 'character' || analysis.likelySubject === 'creature'
        ? 4
        : 1
      : userImageCount

  const searchStrategy =
    analysis.confidence === 'high' && canSearchWeb
      ? 'aggressive'
      : canSearchWeb
        ? 'moderate'
        : 'minimal'

  const baseSuccess = analysis.likelySubject === 'character' ? 0.78 : 0.88
  const userImageBoost = userImageCount > 0 ? 0.14 : 0
  const complexityPenalty = analysis.estimatedComplexity === 'complex' ? -0.08 : 0
  const estimatedSuccessRate = Math.min(0.97, Math.max(0.55, baseSuccess + userImageBoost + complexityPenalty))

  const fallbackIfFails =
    userImageCount > 0
      ? 'monoview_only'
      : analysis.estimatedComplexity === 'complex'
        ? 'reduce_complexity'
        : 'hunyuan3d'

  return {
    monoview,
    whyMonoview:
      userImageCount > 0
        ? `User provided ${userImageCount} image(s). One real reference is better than synthetic alternatives.`
        : analysis.likelySubject === 'character' || analysis.likelySubject === 'creature'
          ? 'Character/creature detected with no user image. Will generate 4 synthetic views for multi-view shape reconstruction.'
          : 'Non-character subject without user reference. Monoview sufficient with smart reference search.',
    targetImageCount,
    searchStrategy,
    estimatedSuccessRate,
    fallbackIfFails,
  }
}

/**
 * Combine analysis + strategy + user intent into an autonomous engineering decision.
 */
export function engineerDecision(
  prompt: string,
  intent: ThreeDIntent,
  userImages: PreparedContextFile[],
  canSearchWeb: boolean = true,
): ThreeDEngineerDecision {
  const analysis = analyzeSubject(prompt, intent, userImages)
  const strategy = decideGenerationStrategy(analysis, userImages.length, canSearchWeb)

  const reasoning: string[] = [
    `Subject analysis: ${analysis.likelySubject} (${analysis.confidence} confidence)`,
    `Key traits: ${analysis.keyTraits.length > 0 ? analysis.keyTraits.join(', ') : 'standard'}`,
    `User provided: ${userImages.length} image(s)`,
    `Strategy: ${strategy.monoview ? 'Monoview' : `Multiview (target ${strategy.targetImageCount} views)`}`,
    `${strategy.whyMonoview}`,
    `Web search: ${strategy.searchStrategy}`,
    `Estimated success: ${(strategy.estimatedSuccessRate * 100).toFixed(0)}%`,
    `Fallback if error: ${strategy.fallbackIfFails}`,
  ]

  let warningIfAny: string | null = null
  if (strategy.estimatedSuccessRate < 0.65) {
    warningIfAny =
      `Low confidence (${(strategy.estimatedSuccessRate * 100).toFixed(0)}%). ` +
      `Consider providing a reference image for better results.`
  }
  if (analysis.estimatedComplexity === 'complex' && analysis.confidence === 'low') {
    warningIfAny = `Complex subject with low confidence. May require retries.`
  }

  return {
    analysis,
    strategy,
    reasoning,
    shouldProceed: true,
    warningIfAny,
  }
}

/**
 * Map engineer decision → view planner strategy.
 */
export function engineerToViewPlanStrategy(decision: ThreeDEngineerDecision): {
  needsMultiview: boolean
  requiredViewCount: number
  searchAggressively: boolean
  avoidSynthetics: boolean
} {
  const { strategy } = decision

  return {
    needsMultiview: !strategy.monoview,
    requiredViewCount: strategy.targetImageCount,
    searchAggressively: strategy.searchStrategy === 'aggressive',
    avoidSynthetics: strategy.monoview,
  }
}

/**
 * Adaptive error recovery when TRELLIS.2 or texture baking encounters OOM or timeout.
 */
export function engineerErrorRecovery(
  strategy: ThreeDGenerationStrategy,
  error: string,
  originalUserImages: number,
): {
  action: 'retry_hunyuan3d' | 'reduce_views' | 'monoview_only' | 'simplify_prompt' | 'abort'
  reason: string
  modifiedStrategy?: Partial<ThreeDGenerationStrategy>
} {
  const isOOM = /OOM|memory|CUDA out of memory/i.test(error)
  const isTimeout = /timeout|took too long|timed out/i.test(error)

  if (isOOM) {
    if (strategy.monoview && originalUserImages > 0) {
      return {
        action: 'monoview_only',
        reason: "OOM on texture generation. Keeping user's single image as-is.",
        modifiedStrategy: { fallbackIfFails: 'hunyuan3d' },
      }
    }
    if (!strategy.monoview) {
      return {
        action: 'reduce_views',
        reason: 'OOM on multiview. Reducing to monoview.',
        modifiedStrategy: { monoview: true, targetImageCount: 1, fallbackIfFails: 'hunyuan3d' },
      }
    }
    return {
      action: 'retry_hunyuan3d',
      reason: 'OOM on Trellis. Trying Hunyuan3D with reduced texture detail.',
    }
  }

  if (isTimeout) {
    return {
      action: 'simplify_prompt',
      reason: 'Timeout. Simplifying complexity for retry.',
    }
  }

  return {
    action: 'abort',
    reason: `Unrecoverable error: ${error}`,
  }
}
