import { ollamaChat } from '../hooks/useTauri'
import { findBestReferenceVisual, type ReferenceSearchProfile, type ReferenceVisualSelection } from './referenceVisualResearch'
import type { ThreeDIntent } from './threeDIntent'

export type ThreeDReferenceMode = 'freeform' | 'known_subject' | 'exact_reference'
export type ThreeDDimensionStrategy = 'user_override' | 'auto_researched' | 'visual_only'

export type ThreeDReferenceSupport = {
  referenceMode: ThreeDReferenceMode
  dimensionStrategy: ThreeDDimensionStrategy
  externalReference: ReferenceVisualSelection | null
  dimensionNotes: string[]
  sourceNotes: string[]
  searchProfile: ReferenceSearchProfile
}

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

function hasExplicitUserDimensions(prompt: string) {
  return /\b\d+(?:[.,]\d+)?\s?(?:mm|millimetres?|millimeters?|cm|m|in|inch|inches|degres?|degrees?)\b/i.test(prompt)
}

function hasExplicitScaleOverride(prompt: string) {
  return /\b(plus grand|plus petit|agrandi|reduit|miniature|oversized|scaled up|scaled down|taille differente|different size|non a l echelle reelle)\b/i.test(prompt.toLowerCase())
}

function hasStrictVariantSignal(prompt: string) {
  return /\b(v\d+(?:\.\d+)?|mk\d+|gen\s?\d+|plus|pro|max|ultra|mini|24[\s-]?pin|8[\s-]?pin|12vhpwr|pcie|argb|rgb|led|strimer|lian li|identique|exact|exactement|fidele|faithful|same as|natsu|lucy|zoro|naruto)\b/i.test(prompt.toLowerCase())
}

function isLedCablePrompt(prompt: string, intent: ThreeDIntent) {
  return intent.systemClass === 'pc_cabling'
    && /\b(strimer|argb|rgb|led|light guide|diffuser|24[\s-]?pin|8[\s-]?pin|12vhpwr|pcie extension|cable extension)\b/i.test(prompt.toLowerCase())
}

function stripInstructionLead(prompt: string) {
  return prompt
    .replace(/^(fais|fait|genere|g[ée]n[èe]re|cree|cr[ée]e|montre|reproduis|reproduit|modele|mod[ée]lise|donne moi|fais moi|je veux|j'aimerais|j aimerais)\s+/i, '')
    .replace(/\b(en 3d|3d model|modele 3d|mesh|representation 3d|reconstruction 3d)\b/gi, ' ')
    .replace(/\b(identique|exactement|exacte?|fidele|faithful|ressemblant|same as)\b/gi, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

function extractSubjectFocus(prompt: string, intent: ThreeDIntent) {
  const firstSegment = prompt.split(/\n|[.!?]/)[0]?.trim() || prompt.trim()
  const cleaned = stripInstructionLead(firstSegment)
  const withoutTrailingClauses = cleaned
    .replace(/\b(avec|without|sans|sur|fond|background|pose|mouvement|animation|rotation|taille|size|dimensions?)\b[\s\S]*$/i, '')
    .replace(/\s+/g, ' ')
    .trim()

  if (withoutTrailingClauses) return short(withoutTrailingClauses, 96)

  if (intent.systemClass === 'pc_cabling' && /\bstrimer\b/i.test(prompt)) {
    return /\blian li\b/i.test(prompt) ? 'Lian Li Strimer Plus v2' : 'Strimer RGB cable extension'
  }

  return short(cleaned || prompt, 96)
}

function buildIdentityTerms(prompt: string, subjectLabel: string, intent: ThreeDIntent) {
  const combined = `${subjectLabel} ${prompt}`
  const baseTokens = Array.from(new Set(
    combined
      .toLowerCase()
      .replace(/[^a-z0-9+\- ]+/g, ' ')
      .split(/\s+/)
      .filter((token) => token.length >= 3)
      .filter((token) => !['with', 'sans', 'avec', 'fond', 'background', 'modele', 'model', 'mesh', 'render', 'image', 'reference', 'product', 'produit'].includes(token)),
  ))

  if (intent.systemClass === 'pc_cabling') {
    return baseTokens.filter((token) => ['lian', 'strimer', 'plus', 'rgb', 'argb', '12vhpwr', 'pcie', '24-pin', '24', '8-pin', '8', 'v2'].includes(token) || token.length >= 5).slice(0, 6)
  }

  if (intent.purpose === 'character' || intent.subjectKind === 'character' || intent.subjectKind === 'creature') {
    return baseTokens.slice(0, 5)
  }

  return baseTokens.slice(0, 6)
}

function detectPreferredDomains(prompt: string, intent: ThreeDIntent) {
  const domains: string[] = []
  const normalized = prompt.toLowerCase()

  const brandDomainMap: Array<[RegExp, string]> = [
    [/\blian li\b/i, 'lian-li.com'],
    [/\bcablemod\b/i, 'cablemod.com'],
    [/\bcorsair\b/i, 'corsair.com'],
    [/\bnzxt\b/i, 'nzxt.com'],
    [/\bnoctua\b/i, 'noctua.at'],
    [/\bphanteks\b/i, 'phanteks.com'],
    [/\bdeepcool\b/i, 'deepcool.com'],
    [/\bcooler master\b/i, 'coolermaster.com'],
    [/\bbe quiet\b/i, 'bequiet.com'],
  ]

  for (const [pattern, domain] of brandDomainMap) {
    if (pattern.test(normalized)) domains.push(domain)
  }

  if (intent.purpose === 'character' || intent.subjectKind === 'character' || intent.subjectKind === 'creature') {
    domains.push('fandom.com', 'wikipedia.org')
  }

  return uniqueStrings(domains)
}

function detectBlockedDomains(prompt: string, intent: ThreeDIntent, strictIdentity: boolean) {
  const domains = [
    'pinterest.com',
    'facebook.com',
    'instagram.com',
    'x.com',
    'twitter.com',
  ]

  if (strictIdentity || intent.purpose === 'character' || intent.subjectKind === 'character' || intent.subjectKind === 'creature') {
    domains.push('alphacoders.com', 'wallpapercave.com', 'wallpaperaccess.com')
  }

  if (intent.systemClass === 'pc_cabling' || intent.systemClass === 'cable_routing' || intent.systemClass === 'electrical_harness') {
    domains.push('amazon.com', 'amazon.fr', 'ebay.com', 'aliexpress.com')
  }

  return uniqueStrings(domains)
}

function buildRequiredPageTerms(prompt: string, subjectLabel: string, intent: ThreeDIntent) {
  const terms = buildIdentityTerms(prompt, subjectLabel, intent)

  if (intent.systemClass === 'pc_cabling') {
    terms.push('cable', 'extension')
    if (/\bstrimer\b/i.test(prompt.toLowerCase())) {
      terms.push('strimer')
    }
  }

  if (intent.purpose === 'character' || intent.subjectKind === 'character' || intent.subjectKind === 'creature') {
    terms.push('character', 'official')
  }

  return uniqueStrings(terms).slice(0, 8)
}

function detectReferenceMode(prompt: string, intent: ThreeDIntent): ThreeDReferenceMode {
  const normalized = prompt.toLowerCase()

  if (/\b(reference exacte|exact reference|same subject|meme sujet|modele reel|real object|objet reel|existing object|existing character|personnage existant|character existant|official design|datasheet|oem|marque|brand|modele|identique|exactement|fidele|faithful)\b/i.test(normalized)) {
    return 'exact_reference'
  }

  // Known product brands/models → exact reference (user expects the EXACT product, not a generic version)
  if (/\b(strimer|cablemod|lian li|noctua|be quiet|corsair|nzxt|cooler master|deepcool|phanteks|ekwb|arctic)\b/i.test(normalized)) {
    return 'exact_reference'
  }

  if (
    intent.needsResearch
    || /\b(anime|manga|personnage|character|hero|waifu|villain|product|produit|component|composant|piece|part|cable|connector|connecteur|courroie|belt|poulie|pulley|verin|gear|engrenage|bearing|roulement)\b/i.test(normalized)
  ) {
    return 'known_subject'
  }

  return 'freeform'
}

function fallbackSearchProfile(prompt: string, intent: ThreeDIntent, referenceMode: ThreeDReferenceMode): ReferenceSearchProfile {
  const subjectLabel = extractSubjectFocus(prompt, intent) || short(prompt, 90)
  const forbiddenElements: string[] = []
  const forbiddenPageTerms: string[] = []

  if (intent.purpose === 'character' || intent.subjectKind === 'character' || intent.subjectKind === 'creature') {
    forbiddenElements.push('other characters', 'mascot companions', 'group shot', 'wrong character', 'gender-swapped redesign', 'wrong body type', 'blurry face')
    forbiddenPageTerms.push('group', 'duo', 'team', 'party', 'happy')
  }

  if (intent.systemClass === 'pc_cabling' || intent.systemClass === 'cable_routing' || intent.systemClass === 'electrical_harness') {
    forbiddenElements.push(
      'full PC case', 'whole computer setup', 'irrelevant components', 'background build scene',
      'PC tower', 'desktop tower', 'computer case', 'boitier PC', 'tour PC',
      'motherboard installed in case', 'full system build', 'complete PC',
      'any image where a PC case or chassis is the dominant subject',
    )
    forbiddenPageTerms.push('case', 'tower', 'chassis', 'boitier', 'desktop')
  }

  if (intent.requiresDimensionalPrecision || intent.systemClass !== 'generic') {
    forbiddenElements.push('decorative props', 'exploded scene', 'marketing lifestyle shot')
  }

  const ledCablePrompt = isLedCablePrompt(prompt, intent)
  const strictIdentity = referenceMode === 'exact_reference'
    || intent.purpose === 'character'
    || intent.subjectKind === 'character'
    || hasStrictVariantSignal(prompt)

  let effectiveSubjectLabel = subjectLabel
  if (ledCablePrompt && /\bstrimer\b/i.test(prompt.toLowerCase())) {
    effectiveSubjectLabel = `${subjectLabel} (addressable RGB cable extension with light-guide tubes and cable combs, NOT a PC case)`
  } else if (ledCablePrompt) {
    effectiveSubjectLabel = `${subjectLabel} (RGB LED cable extension product, NOT a PC case or tower)`
  } else if (intent.systemClass === 'pc_cabling' && /\b(extension|sleeved)\b/i.test(prompt.toLowerCase())) {
    effectiveSubjectLabel = `${subjectLabel} (sleeved cable extension product, NOT a PC case)`
  }

  const identityTerms = buildIdentityTerms(prompt, subjectLabel, intent)
  const preferredDomains = detectPreferredDomains(prompt, intent)
  const requiredPageTerms = buildRequiredPageTerms(prompt, subjectLabel, intent)
  const minimumScore = referenceMode === 'exact_reference'
    ? (ledCablePrompt || intent.purpose === 'character' || intent.subjectKind === 'character' || intent.subjectKind === 'creature' ? 92 : 90)
    : strictIdentity
      ? (intent.purpose === 'character' || intent.subjectKind === 'character' || intent.subjectKind === 'creature' ? 88 : 86)
      : 72

  return {
    subjectLabel: effectiveSubjectLabel,
    requiredElements: uniqueStrings([
      ...intent.movingPartsFocus.slice(0, 3),
      ...intent.anchoredPartsFocus.slice(0, 3),
      ...(intent.referenceFraming === 'isolated_subject'
        ? ['single isolated subject', 'no host device around the subject']
        : []),
      ...(ledCablePrompt
        ? ['rgb light guides', 'cable combs', 'visible connector ends', 'isolated cable assembly', 'NO PC case in the image']
        : []),
      ...(intent.systemClass === 'pc_cabling' && !ledCablePrompt
        ? ['isolated cable product', 'visible connectors', 'NO PC case or tower']
        : []),
      ...(intent.purpose === 'character' || intent.subjectKind === 'character' || intent.subjectKind === 'creature'
        ? ['single solo character', 'full body visible', 'sharp readable face', 'exact hairstyle and costume silhouette', 'official gender/body type preserved', 'no companion creature']
        : []),
    ]),
    forbiddenElements: uniqueStrings(forbiddenElements),
    preferIsolatedSubject: true,
    allowAdditionalSubjects: false,
    strictIdentity,
    identityTerms,
    requiredPageTerms,
    preferredDomains,
    blockedDomains: detectBlockedDomains(prompt, intent, strictIdentity),
    forbiddenPageTerms: uniqueStrings(forbiddenPageTerms),
    minimumScore,
  }
}

async function buildSearchProfile({
  prompt,
  intent,
  model,
  researchContext,
  referenceMode,
}: {
  prompt: string
  intent: ThreeDIntent
  model: string
  researchContext: string
  referenceMode: ThreeDReferenceMode
}) {
  const fallback = fallbackSearchProfile(prompt, intent, referenceMode)

  try {
    const response = await ollamaChat(model, [
      {
        role: 'system',
        content: [
          '/no_think',
          'You prepare a strict visual-reference search profile for a 3D reference-image pipeline.',
          'Return only valid JSON with this exact shape:',
          '{"subjectLabel":"...","requiredElements":["..."],"forbiddenElements":["..."],"preferIsolatedSubject":true,"allowAdditionalSubjects":false,"strictIdentity":true}',
          'subjectLabel must be the exact main subject to match, not the whole instruction.',
          'requiredElements should be short visual requirements that must appear on the reference image.',
          'forbiddenElements should name parasite elements that would make a candidate unusable.',
          'If the user wants a known character, product or exact real subject, strictIdentity should be true.',
          'If the user wants a component or cable, prefer isolated subject and forbid full environment shots unless explicitly requested.',
        ].join('\n'),
      },
      {
        role: 'user',
        content: [
          `Prompt: ${prompt}`,
          `3D intent: ${intent.summary}`,
          researchContext ? `Research context:\n${short(researchContext, 700)}` : '',
        ].filter(Boolean).join('\n\n'),
      },
    ], 0.05)

    const parsed = extractJson<ReferenceSearchProfile>(response?.message?.content || '')
    if (!parsed?.subjectLabel?.trim()) {
      return fallback
    }

    return {
      subjectLabel: short(parsed.subjectLabel, 90),
      requiredElements: uniqueStrings([...(parsed.requiredElements || []), ...fallback.requiredElements]).slice(0, 6),
      forbiddenElements: uniqueStrings([...(parsed.forbiddenElements || []), ...fallback.forbiddenElements]).slice(0, 8),
      preferIsolatedSubject: parsed.preferIsolatedSubject ?? fallback.preferIsolatedSubject,
      allowAdditionalSubjects: parsed.allowAdditionalSubjects ?? fallback.allowAdditionalSubjects,
      strictIdentity: parsed.strictIdentity ?? fallback.strictIdentity,
      identityTerms: fallback.identityTerms,
      requiredPageTerms: fallback.requiredPageTerms,
      preferredDomains: fallback.preferredDomains,
      blockedDomains: fallback.blockedDomains,
      forbiddenPageTerms: fallback.forbiddenPageTerms,
      minimumScore: fallback.minimumScore,
    } satisfies ReferenceSearchProfile
  } catch {
    return fallback
  }
}

function extractDimensionNotes(researchContext: string) {
  const metricPattern = /\b\d+(?:[.,]\d+)?\s?(?:mm|millimetres?|millimeters?|cm|m|in|inch|inches|kg|g|lb|lbs|degrees?|degres?)\b/i
  const keywordPattern = /\b(diameter|diametre|diameter|width|largeur|height|hauteur|length|longueur|depth|profondeur|stroke|course|pitch|entraxe|spacing|tooth|teeth|rayon|radius)\b/i

  return uniqueStrings(
    researchContext
      .split(/\n|(?<=[.!?])\s+/)
      .map((line) => line.replace(/^[-*\s]+/, '').trim())
      .filter((line) => line && !/^source:/i.test(line) && !/^indice:/i.test(line))
      .filter((line) => metricPattern.test(line) || keywordPattern.test(line))
      .map((line) => short(line, 160)),
  ).slice(0, 4)
}

function buildReferenceQueries(
  prompt: string,
  intent: ThreeDIntent,
  webSearchTerms: string[],
  requestedChanges: string[],
  profile: ReferenceSearchProfile,
) {
  const queries = [
    profile.subjectLabel || prompt,
    ...intent.researchQueries,
    ...webSearchTerms,
    ...requestedChanges,
  ]

  if (intent.purpose === 'character' || intent.subjectKind === 'character' || intent.subjectKind === 'creature') {
    queries.push(`${profile.subjectLabel} official character design`)
    queries.push(`${profile.subjectLabel} full body reference`)
    queries.push(`${profile.subjectLabel} solo character official art`)
    queries.push(`${profile.subjectLabel} official art solo no companion`)
    queries.push(`site:fandom.com ${profile.subjectLabel}`)
  }

  if (intent.requiresDimensionalPrecision || intent.systemClass !== 'generic') {
    queries.push(`${profile.subjectLabel} dimensions size measurements`)
    queries.push(`${profile.subjectLabel} technical reference photo`)
  }

  if (profile.preferIsolatedSubject) {
    queries.push(`${profile.subjectLabel} isolated subject`)
  }

  // For PC cables, add product-specific search queries that describe what the product IS
  if (intent.systemClass === 'pc_cabling') {
    const promptLower = prompt.toLowerCase()
    if (/\bstrimer\b/i.test(promptLower)) {
      queries.push('Lian Li Strimer Plus RGB cable extension isolated product photo')
      queries.push('Lian Li Strimer Plus v2 isolated cable product')
      queries.push('Strimer addressable RGB light guide cable product')
      queries.push('site:lian-li.com "strimer plus v2" cable')
    }
    if (/\b(sleeved|cablemod)\b/i.test(promptLower)) {
      queries.push('sleeved PSU extension cable isolated product photo')
    }
    if (/\b12vhpwr\b/i.test(promptLower)) {
      queries.push('12VHPWR cable adapter isolated product photo')
    }
    // Always add a generic cable-specific query to avoid getting PC case results
    queries.push('PC power cable extension isolated product close-up')
  }

  return uniqueStrings(queries.map((query) => short(query, 180))).slice(0, 8)
}

export async function prepareThreeDReferenceSupport({
  prompt,
  intent,
  model,
  researchContext,
  webSearchTerms,
  requestedChanges,
}: {
  prompt: string
  intent: ThreeDIntent
  model: string
  researchContext: string
  webSearchTerms: string[]
  requestedChanges: string[]
}): Promise<ThreeDReferenceSupport> {
  const referenceMode = detectReferenceMode(prompt, intent)
  const dimensionNotes = extractDimensionNotes(researchContext)
  const searchProfile = await buildSearchProfile({
    prompt,
    intent,
    model,
    researchContext,
    referenceMode,
  })
  const dimensionStrategy: ThreeDDimensionStrategy = hasExplicitUserDimensions(prompt) || hasExplicitScaleOverride(prompt)
    ? 'user_override'
    : dimensionNotes.length > 0 && (intent.requiresDimensionalPrecision || referenceMode !== 'freeform')
      ? 'auto_researched'
      : 'visual_only'

  const shouldSearchExternalReference = referenceMode !== 'freeform' || intent.needsResearch || intent.systemClass !== 'generic'
  const externalReference = shouldSearchExternalReference
    ? await findBestReferenceVisual({
      prompt,
      model,
      queries: buildReferenceQueries(prompt, intent, webSearchTerms, requestedChanges, searchProfile),
      profile: searchProfile,
    })
    : null

  const sourceNotes = uniqueStrings([
    searchProfile.subjectLabel ? `Sujet vise: ${searchProfile.subjectLabel}` : '',
    externalReference ? `Reference visuelle retenue: ${externalReference.title}` : '',
    searchProfile.minimumScore ? `Seuil de fidelite recherche: ${searchProfile.minimumScore}/100` : '',
    dimensionStrategy === 'auto_researched'
      ? `Dimensions auto-recherchees: ${dimensionNotes.join(' | ')}`
      : dimensionStrategy === 'user_override'
        ? 'Dimensions prioritaires: contraintes utilisateur'
        : '',
  ])

  return {
    referenceMode,
    dimensionStrategy,
    externalReference,
    dimensionNotes,
    sourceNotes,
    searchProfile,
  }
}
