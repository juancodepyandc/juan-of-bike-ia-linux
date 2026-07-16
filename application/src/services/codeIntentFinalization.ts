import { classifyCodeAssetPlan } from './codeIntentAssets.ts'
import { BUNDLED_PREVIEW_PROJECTS, DEV_SERVER_PROJECTS, getBuildCommand, getDevCommand, getTestCommand } from './codeIntentCommands.ts'
import { estimateComplexity } from './codeIntentComplexity.ts'
import { estimateFileCount, isWholeProductRequest, minimumFileCountForIntent } from './codeIntentFileCount.ts'
import { classifyGameKind } from './codeIntentGameCatalog.ts'
import { containsSignal } from './codeIntentSignalUtils.ts'
import type { CodeIntent, CodeProjectType, PreviewType } from './codeIntentTypes.ts'

const FEATURE_KEYWORDS: Record<string, string> = {
  auth: 'authentication',
  login: 'authentication',
  connexion: 'authentication',
  jwt: 'jwt',
  oauth: 'oauth',
  database: 'database',
  'base de donnee': 'database',
  bdd: 'database',
  mongodb: 'mongodb',
  postgres: 'postgresql',
  mysql: 'mysql',
  sqlite: 'sqlite',
  redis: 'redis',
  cache: 'caching',
  websocket: 'websocket',
  upload: 'file-upload',
  email: 'email',
  notification: 'notifications',
  search: 'search',
  recherche: 'search',
  pagination: 'pagination',
  'dark mode': 'dark-mode',
  responsive: 'responsive',
  i18n: 'i18n',
  internationalisation: 'i18n',
  test: 'testing',
  docker: 'docker',
  'ci/cd': 'ci-cd',
  deploy: 'deployment',
  stripe: 'payments',
  paiement: 'payments',
  payment: 'payments',
}

function consolePreviewProject(projectType: CodeProjectType): boolean {
  return projectType.startsWith('cli_')
    || projectType.startsWith('system_')
    || projectType.startsWith('embedded_')
    || projectType === 'script'
    || projectType === 'data_python'
    || projectType === 'compiler'
    || projectType === 'os_kernel'
    || projectType === 'distributed_system'
}

function resolvePreviewType(projectType: CodeProjectType, fallback: PreviewType): PreviewType {
  if (DEV_SERVER_PROJECTS.has(projectType)) return 'dev_server'
  if (BUNDLED_PREVIEW_PROJECTS.has(projectType) || projectType.startsWith('spa_')) return 'iframe_bundled'
  if (projectType === 'static_web' || projectType === 'game_web') return 'iframe_static'
  if (consolePreviewProject(projectType)) return 'console'
  return fallback
}

export function finalizeCodeIntentClassification({
  prompt,
  normalizedPrompt,
  projectType: initialProjectType,
  languages,
  frameworks,
  features,
}: {
  prompt: string
  normalizedPrompt: string
  projectType: CodeProjectType
  languages: string[]
  frameworks: string[]
  features: string[]
}): CodeIntent {
  let projectType = initialProjectType
  for (const [keyword, feature] of Object.entries(FEATURE_KEYWORDS)) {
    if (containsSignal(normalizedPrompt, keyword) && !features.includes(feature)) features.push(feature)
  }

  const uniqueLanguages = [...new Set(languages)]
  const uniqueFrameworks = [...new Set(frameworks)]
  const uniqueFeatures = [...new Set(features)]
  const complexity = estimateComplexity(prompt)
  const initialPreviewType = resolvePreviewType(projectType, 'none')
  const wholeProductRequest = isWholeProductRequest(normalizedPrompt)
  const needsArchitecturePlanning = complexity === 'complex'
    || complexity === 'enterprise'
    || uniqueFeatures.length >= 3
    || wholeProductRequest
  const assetPlan = classifyCodeAssetPlan(prompt)
  if (assetPlan.wants3D && !uniqueFeatures.includes('3d')) uniqueFeatures.push('3d')

  if (assetPlan.wants3D && (projectType === 'static_web' || (projectType as string) === 'unknown')) {
    projectType = 'game_web'
    if (!uniqueFrameworks.includes('three.js')) uniqueFrameworks.push('three.js')
    if (!uniqueLanguages.includes('javascript')) uniqueLanguages.push('javascript')
  } else if (assetPlan.wants3D) {
    const supportsWeb3D = projectType === 'game_web'
      || projectType.startsWith('spa_')
      || projectType.startsWith('ssr_')
      || projectType.startsWith('fullstack_')
      || projectType.startsWith('desktop_')
    if (supportsWeb3D && !uniqueFrameworks.includes('three.js')) uniqueFrameworks.push('three.js')
  }

  const previewType = resolvePreviewType(projectType, initialPreviewType)
  const isGameRequest = projectType === 'game_web'
  const { gameKind, knownGame } = classifyGameKind(normalizedPrompt, isGameRequest)
  const estimatedFileCount = Math.max(
    estimateFileCount(complexity, projectType),
    minimumFileCountForIntent(projectType, uniqueFeatures, wholeProductRequest),
  )

  return {
    projectType,
    complexity,
    languages: uniqueLanguages,
    frameworks: uniqueFrameworks,
    features: uniqueFeatures,
    needsDevServer: DEV_SERVER_PROJECTS.has(projectType),
    needsBundling: BUNDLED_PREVIEW_PROJECTS.has(projectType) || projectType.startsWith('spa_'),
    previewType,
    devCommand: getDevCommand(projectType),
    buildCommand: getBuildCommand(projectType),
    testCommand: getTestCommand(projectType),
    primaryModelRole: needsArchitecturePlanning ? 'planning' : 'code',
    needsArchitecturePlanning,
    estimatedFileCount,
    assetPlan,
    ...(isGameRequest ? { gameKind, ...(knownGame ? { knownGame } : {}) } : {}),
  }
}
