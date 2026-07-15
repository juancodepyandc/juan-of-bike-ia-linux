// ---------------------------------------------------------------------------
// Code intent file count estimates
// Extracted from codeIntent.ts during WS1 modularisation.
// ---------------------------------------------------------------------------

import type { CodeComplexity, CodeProjectType } from './codeIntentTypes.ts'

export function estimateFileCount(complexity: CodeComplexity, projectType: CodeProjectType): number {
  const base: Record<CodeComplexity, number> = {
    trivial: 1,
    simple: 3,
    moderate: 8,
    complex: 18,
    enterprise: 35,
  }

  const multiplier: Partial<Record<CodeProjectType, number>> = {
    spa_react: 1.5,
    spa_vue: 1.5,
    spa_angular: 2.0,
    ssr_nextjs: 1.8,
    fullstack_mern: 2.0,
    fullstack_nextjs: 2.0,
    fullstack_django: 1.6,
    api_spring: 1.5,
    desktop_electron: 1.5,
    desktop_tauri: 1.8,
  }

  return Math.round(base[complexity] * (multiplier[projectType] ?? 1.0))
}

export function isWholeProductRequest(normalizedLower: string): boolean {
  return /\b(app|application|logiciel|outil|plateforme|dashboard|tableau de bord|studio|crm|erp|saas|marketplace|backoffice|admin)\b/i.test(normalizedLower)
    && /\b(complet|complete|entiere|entier|professionnel|pro|client|production|mvp|fonctionnalites|workflow|tunnel|ui|interface|module)\b/i.test(normalizedLower)
}

export function minimumFileCountForIntent(projectType: CodeProjectType, features: string[], wholeProduct: boolean): number {
  const has = (feature: string) => features.includes(feature)
  if (projectType === 'static_web') return wholeProduct || has('multipage') ? 4 : 3
  if (projectType === 'game_web') return 3
  if (projectType.startsWith('spa_')) return wholeProduct ? 10 : 6
  if (projectType === 'desktop_tauri') return wholeProduct ? 14 : 8
  if (projectType === 'desktop_electron') return wholeProduct ? 10 : 6
  if (projectType === 'mobile_rn' || projectType === 'mobile_flutter') return wholeProduct ? 10 : 6
  if (projectType.startsWith('api_') || projectType.startsWith('fullstack_') || projectType.startsWith('ssr_')) return wholeProduct ? 10 : 6
  if (projectType.startsWith('cli_') || projectType.startsWith('system_') || projectType === 'data_python') return wholeProduct ? 5 : 3
  return wholeProduct ? 4 : 1
}
