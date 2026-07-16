import type { CodeIntent } from './codeIntent.ts'
import type { FollowUpAnalysis } from './codeFollowUpAnalysis.ts'
import type { PhaseCallback } from './codeOrchestrator.ts'
import { withTimeout } from './llmTimebox.ts'
import { RESEARCH_PHASE_TIMEOUT_MS } from './codePipelineRuntime.ts'

export function looksLikeSimpleTechBrief(prompt: string): boolean {
  const promptLower = prompt.toLowerCase()
  return prompt.length < 300 &&
    /\b(simple|minimal|basique|petit|petite|un\s+bouton|une\s+page|index\.html|une\s+fonction|calcul|console|cli|script)\b/i.test(promptLower) &&
    !/\b(comme|pour|de la marque|site de|brand|logo de)\b/i.test(promptLower)
}

export function buildResearchPhaseLabel(intent: CodeIntent): string {
  const ap = intent.assetPlan
  if (ap?.researchQueries.length) {
    return `Recherche de references visuelles en ligne (${ap.researchQueries.slice(0, 2).join(' | ')})... cela peut prendre jusqu a 30s`
  }
  if (ap?.wantsPremiumLook) {
    return 'Recherche de tendances de design premium... cela peut prendre jusqu a 30s'
  }
  return 'Recherche des meilleures pratiques pour ce type de projet...'
}

export function shouldRunDesignReferenceResearch(intent: CodeIntent, prompt: string, simpleTechBrief = looksLikeSimpleTechBrief(prompt)): boolean {
  if (simpleTechBrief) return false
  const visualTypes = [
    'static_web',
    'spa_react',
    'spa_vue',
    'spa_svelte',
    'spa_angular',
    'ssr_nextjs',
    'ssr_nuxt',
    'ssr_remix',
    'fullstack_mern',
    'fullstack_nextjs',
    'game_web',
    'mobile_rn',
    'mobile_flutter',
    'mobile_ios',
    'mobile_android',
    'desktop_electron',
    'desktop_tauri',
    'desktop_app',
    'ide',
  ]
  return visualTypes.includes(intent.projectType) || Boolean(intent.assetPlan?.wantsPremiumLook)
}

export function buildBrandProfileBlock(intent: CodeIntent): string {
  const brandSubject = intent.assetPlan?.subject
  if (brandSubject?.source !== 'brand' || !brandSubject.brandProfile) return ''

  const profile = brandSubject.brandProfile
  const palette: string[] = []
  if (profile.primaryColor) palette.push(`primaire ${profile.primaryColor}`)
  if (profile.secondaryColor) palette.push(`secondaire ${profile.secondaryColor}`)
  if (profile.tertiaryColor) palette.push(`tertiaire ${profile.tertiaryColor}`)
  return [
    `## PROFIL DE MARQUE — ${brandSubject.canonical}`,
    `- Domaine: ${brandSubject.domain ?? 'inconnu'}.`,
    palette.length ? `- Palette canonique: ${palette.join(', ')}.` : '',
    profile.productKeywords.length ? `- Produits / mots-cles: ${profile.productKeywords.join(', ')}.` : '',
    profile.designVibe ? `- Vibe visuel: ${profile.designVibe}.` : '',
    profile.typoVibe ? `- Typo: ${profile.typoVibe}.` : '',
    `- Le plan d architecture et le code DOIVENT respecter cette identite. Les couleurs du starter generique ne s appliquent pas.`,
  ].filter(Boolean).join('\n')
}

export async function prepareCodePlanningContext({
  prompt,
  reformulatedEnriched,
  intent,
  followUp,
  configuredCodeModel,
  setPhase,
}: {
  prompt: string
  reformulatedEnriched: string
  intent: CodeIntent
  followUp: FollowUpAnalysis | null
  configuredCodeModel: string
  setPhase: PhaseCallback
}): Promise<{
  planningPrompt: string
  bestPracticesContext: string
  brandProfileBlock: string
}> {
  const ap = intent.assetPlan
  setPhase(buildResearchPhaseLabel(intent), 14)
  let bestPracticesContext = ''
  try {
    const { researchBestPractices } = await import('./codeResearch.ts')
    bestPracticesContext = await withTimeout(researchBestPractices(prompt, intent, configuredCodeModel), {
      label: 'Code research best practices',
      timeoutMs: RESEARCH_PHASE_TIMEOUT_MS,
    })
    if (bestPracticesContext) {
      setPhase('Meilleures pratiques trouvees — integration dans la planification...', 16)
    }
  } catch {
    // Research is non-blocking — continue without it.
  }

  const simpleTechBrief = looksLikeSimpleTechBrief(prompt)
  let designResearchBlock = ''
  if (shouldRunDesignReferenceResearch(intent, prompt, simpleTechBrief)) {
    setPhase('Recherche de references UX/UI par archetype design...', 15)
    try {
      const { runDesignResearch, serializeDesignResearch } = await import('./codeDesignResearch.ts')
      const research = await withTimeout(
        runDesignResearch(prompt, intent, configuredCodeModel),
        { label: 'Design reference research', timeoutMs: RESEARCH_PHASE_TIMEOUT_MS },
      )
      designResearchBlock = serializeDesignResearch(research)
      setPhase('References UX/UI integrees dans la planification.', 17)
    } catch {
      // Design research is a quality booster, not a hard dependency.
    }
  }

  if (ap?.subject?.source === 'inferred_brand' && !ap.subject.brandProfile && ap.subject.canonical && !simpleTechBrief) {
    setPhase(`Enrichissement dynamique du profil de marque "${ap.subject.canonical}" (Wikipedia + Ollama)...`, 13)
    try {
      const { fetchBrandProfileFromBridge } = await import('./codeSubjectAssets.ts')
      const enriched = await withTimeout(
        fetchBrandProfileFromBridge(ap.subject.canonical),
        { label: 'Brand enrich (bridge)', timeoutMs: 20_000 },
      )
      if (enriched) {
        ap.subject.brandProfile = enriched
        ;(ap.subject as { source: string }).source = 'brand'
        if (enriched.imageQueries?.length && ap.researchQueries) {
          for (const query of enriched.imageQueries.slice(0, 3).reverse()) {
            ap.researchQueries.unshift(query)
          }
        }
        setPhase(`Profil "${ap.subject.canonical}" enrichi (palette ${enriched.primaryColor}, produit ${enriched.productShape ?? 'logo'}).`, 14)
      } else {
        setPhase(`Pas de profil enrichi trouve pour "${ap.subject.canonical}" — generic fallback.`, 14)
      }
    } catch (err) {
      console.warn('[CodeOrchestrator] brand enrich failed:', err)
    }
  }

  const brandProfileBlock = buildBrandProfileBlock(intent)
  const planningExtras: string[] = []
  if (bestPracticesContext) planningExtras.push(`## MEILLEURES PRATIQUES TROUVEES (a integrer dans le plan):\n${bestPracticesContext}`)
  if (designResearchBlock) planningExtras.push(designResearchBlock)
  if (brandProfileBlock) planningExtras.push(brandProfileBlock)
  if (followUp?.migrationSummary && followUp.kind === 'pivot_platform') {
    planningExtras.push(`## MIGRATION DE PROJET (conserve le concept, change la stack)\n${followUp.migrationSummary}`)
  }

  return {
    planningPrompt: planningExtras.length
      ? `${reformulatedEnriched}\n\n${planningExtras.join('\n\n')}`
      : reformulatedEnriched,
    bestPracticesContext,
    brandProfileBlock,
  }
}
