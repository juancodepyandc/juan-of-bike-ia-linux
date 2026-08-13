import type { CodeFile } from './codeOrchestrator.ts'
import { parseArchitecturePlanJson } from './codeArchitecturePlan.ts'
import { isBinaryAssetPath } from './codeBinaryAssetPaths.ts'
import { isGeneratedArtifactPath } from './codeCodegenDependencies.ts'

const DOCUMENTATION_PLAN_EXTENSIONS = new Set(['md', 'txt', 'rst', 'adoc'])

function normalizePath(path: string) {
  return path.replace(/\\/g, '/').replace(/^\.\/+/, '').toLowerCase()
}

function isDocumentationPlanPath(path: string) {
  const extension = path.split('.').pop()?.toLowerCase() || ''
  return DOCUMENTATION_PLAN_EXTENSIONS.has(extension)
}

export type ArchitecturePlanContractReport = {
  ok: boolean
  missingRequiredFiles: string[]
  checkedRequiredFiles: string[]
}

export function checkArchitecturePlanFileContract(
  files: CodeFile[],
  architecturePlan: string | null | undefined,
): ArchitecturePlanContractReport | null {
  const parsed = parseArchitecturePlanJson(architecturePlan)
  if (!parsed.ok) return null

  const delivered = new Set(files.map((file) => normalizePath(file.name)))
  const requiredFiles = parsed.plan.files
    .filter((file) => file.required !== false)
    .map((file) => file.path)
    .filter((path) => !isDocumentationPlanPath(path))
    // Meme predicat que la file de generation, obligatoirement: reclamer un
    // binaire que la file ne produit plus (et qu aucun modele de texte ne peut
    // ecrire) declencherait une regeneration sans issue — le piege du
    // « conseil irrealisable » deja paye quatre passes au run 1031.
    .filter((path) => !isBinaryAssetPath(path))
    // Idem pour un artefact genere: le reclamer declencherait une regeneration
    // sans issue, puisque aucun modele ne peut l ecrire.
    .filter((path) => !isGeneratedArtifactPath(path))

  const missingRequiredFiles = requiredFiles.filter((path) => !delivered.has(normalizePath(path)))

  return {
    ok: missingRequiredFiles.length === 0,
    missingRequiredFiles,
    checkedRequiredFiles: requiredFiles,
  }
}

export function describeArchitecturePlanContractIssue(
  files: CodeFile[],
  architecturePlan: string | null | undefined,
): string | null {
  const report = checkArchitecturePlanFileContract(files, architecturePlan)
  if (!report || report.ok) return null

  return [
    'Plan d architecture non respecte: fichiers requis absents.',
    `Fichiers manquants: ${report.missingRequiredFiles.slice(0, 12).join(', ')}`,
    `Contrat verifie sur ${report.checkedRequiredFiles.length} fichier(s) requis.`,
    'Regenerer en livrant chaque fichier requis du plan, complet, via AURORA_CODE_VFS/1.',
  ].join(' ')
}
