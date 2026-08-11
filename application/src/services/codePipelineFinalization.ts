import type { CodeIntent } from './codeIntent.ts'
import type { CodeFile } from './codeOrchestrator.ts'
import { evaluateBrandFidelity } from './codeFidelityGate.ts'
import { upsertProjectSupportFiles } from './codeProjectSupportFiles.ts'
import { computeDesignPolishReport, isVisualProjectType, type DesignPolishReport } from './codeQualityGates.ts'
import {
  buildVisualFidelityCritique,
  evaluateVisualFidelity,
  type VisualFidelityReport,
} from './codeVisualFidelity.ts'
import { checkDesignTokens } from './codeDesignTokenGate.ts'
import { detectEmojiIcons } from './codeCompositionGate.ts'
import {
  summarizeAssetBundle,
  upsertAssetManifestFile,
  type CodeAssetBundle,
} from './codeInterModuleAssets.ts'

export type CodePipelineDelivery = {
  files: CodeFile[]
  notes: string
  score: number
  designReport: DesignPolishReport | null
  visualFidelity: VisualFidelityReport | null
  designTokens: ReturnType<typeof checkDesignTokens>
}

/**
 * Fait COMPTER la porte visuelle dans le score livre.
 *
 * Meme semantique que la porte de marque juste au-dessus: la correction du
 * modele reste dominante, l apparence pese, et un rendu qui echoue son seuil ne
 * peut pas etre livre comme "excellent". Le plafond 84 est celui deja utilise
 * par le mixage de l audit rendu, pour que les deux chemins notent pareil.
 */
export function blendVisualFidelityIntoScore(
  modelScore: number,
  report: VisualFidelityReport,
): number {
  const clamped = Math.max(0, Math.min(100, Math.round(modelScore)))
  const visual = Math.max(0, Math.min(100, Math.round(report.score)))
  let blended = Math.round(clamped * 0.75 + visual * 0.25)
  if (!report.passed) blended = Math.min(blended, Math.min(clamped, 84))
  return Math.max(0, Math.min(100, blended))
}

export function finalizeCodePipelineDelivery({
  files,
  notes,
  score,
  intent,
  enrichedPrompt,
  architecturePlan,
  assetBundle,
}: {
  files: CodeFile[]
  notes: string
  score: number
  intent: CodeIntent
  enrichedPrompt: string
  architecturePlan: string | null
  assetBundle: CodeAssetBundle | null
}): CodePipelineDelivery {
  const finalFiles = upsertAssetManifestFile(
    upsertProjectSupportFiles(files, intent, enrichedPrompt, architecturePlan),
    assetBundle,
  )
  const brandFidelity = evaluateBrandFidelity(intent, finalFiles)
  let adjustedScore = score
  if (brandFidelity.scoreCap !== null) adjustedScore = Math.min(adjustedScore, brandFidelity.scoreCap)
  if (brandFidelity.scorePenalty > 0) adjustedScore = Math.max(0, adjustedScore - brandFidelity.scorePenalty)

  // WS9 — porte visuelle SOURCE-STATIQUE, donc disponible sur TOUS les canaux.
  // La boucle du juge rendu vit dans la couche vue et n existe que pour l UI
  // Tauri: le CLI et le tunnel n avaient aucune garde visuelle. Cette
  // evaluation-la ne demande ni navigateur ni serveur de dev, elle inspecte le
  // HTML/CSS/JS livre — elle donne donc la meme note aux trois canaux, et se
  // laisse enrichir par l audit rendu quand celui-ci est disponible.
  const visualFidelity = evaluateVisualFidelity(finalFiles, intent)
  if (visualFidelity.checks.length > 0) {
    adjustedScore = blendVisualFidelityIntoScore(adjustedScore, visualFidelity)
  }

  // Porte des tokens de design: une variable CSS utilisee sans definition
  // ATTEIGNABLE fait jeter la declaration entiere par le navigateur. Un projet
  // livre a sorti un rendu totalement plat pour cette seule raison — sa feuille
  // de tokens existait mais n etait importee nulle part.
  const tokenReport = checkDesignTokens(finalFiles.map((f) => ({ name: f.name, content: f.content })))
  if (!tokenReport.ok) {
    // Meme semantique que les autres portes: un livrable dont l habillage ne
    // charge pas ne peut pas etre annonce comme excellent.
    adjustedScore = Math.min(adjustedScore, 70)
  }

  // Iconographie: un emoji en position d icone est la signature d un prototype.
  // Les chevauchements et les sections vides se mesurent au RENDU (navigateur),
  // donc dans le juge de rendu; ici on tient la part detectable a la source.
  const emojiIcons = detectEmojiIcons(finalFiles.map((f) => ({ name: f.name, content: f.content })))
  if (emojiIcons.length > 0) adjustedScore = Math.min(adjustedScore, 80)

  const fidelityNotes = brandFidelity.retryHint
    ? `${notes}\n\n## FIDELITE SUJET\n${brandFidelity.retryHint}`
    : notes
  const assetNotes = assetBundle
    ? `\n\n## ASSETS INTER-MODULES\n${summarizeAssetBundle(assetBundle)}`
    : ''
  // Une page sous le seuil ne part pas en silence: la critique precise part
  // avec la livraison, et sert de directive a une eventuelle passe esthetique.
  const visualNotes = visualFidelity.checks.length > 0 && !visualFidelity.passed
    ? `\n\n## QUALITE VISUELLE (${visualFidelity.score}/100, seuil ${visualFidelity.floor})\n${buildVisualFidelityCritique(visualFidelity)}`
    : ''

  const tokenNotes = tokenReport.ok ? '' : `\n\n${tokenReport.critique}`
  const iconNotes = emojiIcons.length === 0 ? '' : [
    '',
    '',
    '## ICONOGRAPHIE — EMOJI INTERDITS',
    `${emojiIcons.length} emoji sont employes comme icones: ${emojiIcons.slice(0, 8).join(' ')}.`,
    'Remplace-les par des SVG inline coherents (meme grille, meme epaisseur de trait). Un emoji est la signature d un prototype, jamais d un produit fini.',
  ].join('\n')

  return {
    files: finalFiles,
    notes: fidelityNotes + assetNotes + visualNotes + tokenNotes + iconNotes,
    score: adjustedScore,
    designReport: isVisualProjectType(intent.projectType) ? computeDesignPolishReport(finalFiles) : null,
    visualFidelity,
    designTokens: tokenReport,
  }
}
