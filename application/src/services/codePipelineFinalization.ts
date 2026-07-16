import type { CodeIntent } from './codeIntent.ts'
import type { CodeFile } from './codeOrchestrator.ts'
import { evaluateBrandFidelity } from './codeFidelityGate.ts'
import { upsertProjectSupportFiles } from './codeProjectSupportFiles.ts'
import { computeDesignPolishReport, isVisualProjectType, type DesignPolishReport } from './codeQualityGates.ts'
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

  const fidelityNotes = brandFidelity.retryHint
    ? `${notes}\n\n## FIDELITE SUJET\n${brandFidelity.retryHint}`
    : notes
  const assetNotes = assetBundle
    ? `\n\n## ASSETS INTER-MODULES\n${summarizeAssetBundle(assetBundle)}`
    : ''

  return {
    files: finalFiles,
    notes: fidelityNotes + assetNotes,
    score: adjustedScore,
    designReport: isVisualProjectType(intent.projectType) ? computeDesignPolishReport(finalFiles) : null,
  }
}
