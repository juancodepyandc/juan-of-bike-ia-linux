// ---------------------------------------------------------------------------
// Code asset plan classification
// Extracted from codeIntent.ts during WS1 modularisation.
// ---------------------------------------------------------------------------

import type { CodeAssetPlan } from './codeIntentTypes.ts'
import {
  COLOR_HEX_REGEX,
  EFFECT_TOKENS,
  IMAGE_TOKENS,
  PREMIUM_LOOK_TOKENS,
  RESEARCH_TRIGGER_TOKENS,
  THREED_TOKENS,
  buildResearchQueries,
  extractMentions,
  extractObjectMentions,
} from './codeIntentAssetTokens.ts'
import { detectPromptLanguage } from './codeIntentLanguage.ts'
import { detectSubject } from './codeIntentSubject.ts'
import { normalizeSignalText } from './codeIntentSignalUtils.ts'

export function classifyCodeAssetPlan(prompt: string): CodeAssetPlan {
  const lower = normalizeSignalText(prompt)
  const styleHints = extractMentions(lower, PREMIUM_LOOK_TOKENS)
  const objectMentions = extractObjectMentions(prompt)
  const effectMentions = extractMentions(lower, EFFECT_TOKENS)
  const wantsImages = extractMentions(lower, IMAGE_TOKENS).length > 0 || objectMentions.length > 0
  const wants3D = extractMentions(lower, THREED_TOKENS).length > 0
  const wantsResearch = extractMentions(lower, RESEARCH_TRIGGER_TOKENS).length > 0
  const wantsPremiumLook = styleHints.length > 0
  const paletteHints = Array.from(new Set((prompt.match(COLOR_HEX_REGEX) || []).map((c) => c.toLowerCase())))
  const researchQueries = buildResearchQueries(prompt, styleHints, objectMentions, wantsPremiumLook || wantsResearch)
  const subject = detectSubject(prompt)
  const language = detectPromptLanguage(prompt)

  // If we detected a brand, inject brand-specific research queries upfront
  // so the page actually looks like the brand (colors, tone, visuals).
  if (subject.source === 'brand' && subject.canonical) {
    const brand = subject.canonical
    researchQueries.unshift(
      `${brand} brand colors hex codes`,
      `${brand} official logo png`,
      `${brand} website design style`,
    )
  }

  return {
    styleHints,
    objectMentions,
    effectMentions,
    paletteHints,
    wantsPremiumLook,
    wantsImages,
    wants3D,
    wantsResearch: wantsResearch || wantsPremiumLook || objectMentions.length > 0 || subject.source !== 'none',
    researchQueries: Array.from(new Set(researchQueries)).slice(0, 8),
    subject,
    language,
  }
}
