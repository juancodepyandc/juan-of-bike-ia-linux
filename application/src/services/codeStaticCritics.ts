// Critics statiques qui s'exécutent SANS LLM sur du code généré.
// Façade publique: chaque famille de règles vit dans un module dédié.

import type { CodeProject, CriticFn, CritiqueAxis, CritiqueIssue, CritiqueReport } from './codeMultiPassCritique.ts'
import { buildReport } from './codeMultiPassCritique.ts'
import type { CodeIntent } from './codeIntent.ts'

import { syntaxCritic } from './codeStaticSyntax.ts'
import { securityCritic } from './codeStaticSecurity.ts'
import { structureCritic } from './codeStaticStructure.ts'
import { accessibilityCritic } from './codeStaticAccessibility.ts'
import { deliverableCompletenessCritic } from './codeStaticCompleteness.ts'
import { projectIntegrityCritic } from './codeStaticProjectIntegrity.ts'
import { complexityCritic } from './codeStaticComplexity.ts'

export { syntaxCritic } from './codeStaticSyntax.ts'
export { securityCritic } from './codeStaticSecurity.ts'
export { structureCritic } from './codeStaticStructure.ts'
export { accessibilityCritic } from './codeStaticAccessibility.ts'
export { deliverableCompletenessCritic } from './codeStaticCompleteness.ts'
export { projectIntegrityCritic } from './codeStaticProjectIntegrity.ts'
export { complexityCritic } from './codeStaticComplexity.ts'

// --- Composite critic ------------------------------------------------------
// Combines the 4 static critics into one report. Useful as a stand-in for
// the "first cheap pass" before paying the LLM critic.

export const compositeStaticCritic: CriticFn = async (project: CodeProject, intent: CodeIntent): Promise<CritiqueReport> => {
  const reports = await Promise.all([
    syntaxCritic(project, intent),
    securityCritic(project, intent),
    structureCritic(project, intent),
    deliverableCompletenessCritic(project, intent),
    projectIntegrityCritic(project, intent),
    complexityCritic(project, intent),
    accessibilityCritic(project, intent),
  ])
  const mergedScores: Partial<Record<CritiqueAxis, number>> = {}
  const allIssues: CritiqueIssue[] = []
  for (const r of reports) {
    for (const key of Object.keys(r.scores) as CritiqueAxis[]) {
      // Take the min across critics that scored the same axis (be strict).
      const prev = mergedScores[key]
      const next = r.scores[key]
      if (prev == null || next < prev) mergedScores[key] = next
    }
    allIssues.push(...r.issues)
  }
  return buildReport(mergedScores, allIssues)
}
