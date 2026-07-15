import type { CodeIntent } from './codeIntent.ts'
import type { FollowUpAnalysis } from './codeFollowUpAnalysis.ts'
import type { PhaseCallback } from './codeOrchestrator.ts'
import { withTimeout } from './llmTimebox.ts'
import { RESEARCH_PHASE_TIMEOUT_MS } from './codePipelineRuntime.ts'

type SubjectImage = {
  dataUrl: string
  source?: string
  query?: string
}

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

export function buildSubjectImagePromptBlock(images: SubjectImage[]): string {
  const acceptable = images.filter((img) => img.dataUrl.length <= 350_000)
  if (acceptable.length === 0) return ''

  const sourcesLine = acceptable
    .map((img, idx) => `  ${idx + 1}. ${img.query || 'subject'} -> ${img.source || 'unknown'}`)
    .join('\n')
  return [
    `## IMAGES REELLES DU SUJET (telechargees pour toi en amont — ${acceptable.length})`,
    `- ${acceptable.length} photo(s) / illustration(s) du sujet ont ete trouvees et converties en data URLs.`,
    '- Tu DOIS les utiliser DIRECTEMENT dans la page avec ces markers literaux:',
    '  - `PLACEHOLDER_SUBJECT_IMG`     -> image principale (hero / produit central).',
    acceptable.length >= 2 ? '  - `PLACEHOLDER_SUBJECT_IMG_1`   -> image principale (alias du marker non numerote).' : '',
    acceptable.length >= 2 ? '  - `PLACEHOLDER_SUBJECT_IMG_2`   -> image secondaire (lifestyle / contexte).' : '',
    acceptable.length >= 3 ? '  - `PLACEHOLDER_SUBJECT_IMG_3`   -> image tertiaire (detail / texture / variante).' : '',
    acceptable.length >= 4 ? '  - `PLACEHOLDER_SUBJECT_IMG_4`   -> image complementaire (gallery).' : '',
    '- Au build final, chaque marker sera remplace par la data URL correspondante.',
    '- Tu peux reutiliser le meme marker plusieurs fois (hero + showcase + footer). Tout marker sans image associee sera neutralise.',
    '- Sources originales:',
    sourcesLine,
  ].filter(Boolean).join('\n')
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
  subjectImageBlock: string
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

  let subjectImageBlock = ''
  const wantsRealImage = ap && (ap.wantsImages || ap.subject?.source === 'brand' || (ap.objectMentions?.length ?? 0) > 0)
  if (wantsRealImage && !simpleTechBrief) {
    const isBrand = ap.subject?.source === 'brand'
    setPhase(
      isBrand
        ? 'Recuperation des images officielles de la marque (logo + produit + lifestyle)...'
        : 'Telechargement d images reelles du sujet (peut prendre 10-30s)...',
      17,
    )
    try {
      const { fetchSubjectImages } = await import('./codeSubjectAssets.ts')
      const images = await withTimeout(
        fetchSubjectImages(intent),
        { label: 'Subject images fetch (multi)', timeoutMs: 45_000 },
      )
      const acceptable = images.filter((img) => img.dataUrl.length <= 350_000)
      if (acceptable.length > 0) {
        const dataUrls = acceptable.map((img) => img.dataUrl)
        ;(intent as any).__subjectImageDataUrls = dataUrls
        ;(intent as any).__subjectImageDataUrl = dataUrls[0]
        subjectImageBlock = buildSubjectImagePromptBlock(acceptable)
        setPhase(
          isBrand
            ? `${acceptable.length} image(s) de la marque telechargees — injection dans le prompt...`
            : `${acceptable.length} image(s) du sujet telechargees — injection dans le prompt...`,
          19,
        )
      } else if (images.length > 0) {
        console.warn('[CodeOrchestrator] All fetched subject images exceed the 350KB inline budget — skipping.')
      }
    } catch (err) {
      console.warn('[CodeOrchestrator] Subject image fetch failed:', err)
    }
  }

  const brandProfileBlock = buildBrandProfileBlock(intent)
  const planningExtras: string[] = []
  if (bestPracticesContext) planningExtras.push(`## MEILLEURES PRATIQUES TROUVEES (a integrer dans le plan):\n${bestPracticesContext}`)
  if (brandProfileBlock) planningExtras.push(brandProfileBlock)
  if (subjectImageBlock) planningExtras.push(subjectImageBlock)
  if (followUp?.migrationSummary && followUp.kind === 'pivot_platform') {
    planningExtras.push(`## MIGRATION DE PROJET (conserve le concept, change la stack)\n${followUp.migrationSummary}`)
  }

  return {
    planningPrompt: planningExtras.length
      ? `${reformulatedEnriched}\n\n${planningExtras.join('\n\n')}`
      : reformulatedEnriched,
    bestPracticesContext,
    subjectImageBlock,
    brandProfileBlock,
  }
}
