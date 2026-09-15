// ---------------------------------------------------------------------------
// Increment reuse logic for follow-up code requests
// ---------------------------------------------------------------------------

import type { CodeIntent, CodeIntentContext, PreviewType } from './codeIntentTypes.ts'
import { classifyCodeAssetPlan } from './codeIntentAssets.ts'
import { BUNDLED_PREVIEW_PROJECTS, DEV_SERVER_PROJECTS, getBuildCommand, getDevCommand, getTestCommand } from './codeIntentCommands.ts'
import { estimateComplexity } from './codeIntentComplexity.ts'
import { estimateFileCount } from './codeIntentFileCount.ts'
import { classifyGameKind } from './codeIntentGameCatalog.ts'
import { hasExplicitStackMention } from './codeIntentFollowup.ts'

export function tryResolveIncrementReuse(prompt: string, lower: string, context?: CodeIntentContext): CodeIntent | null {
  const isIncrementReuse = context?.pivotKind === 'increment'
    && context.previousProjectType
    && context.previousProjectType !== 'unknown'

  if (!isIncrementReuse) {
    return null
  }

  const mentionsExplicitStack = hasExplicitStackMention(lower)
  if (mentionsExplicitStack) {
    return null
  }

  const assetPlan = classifyCodeAssetPlan(prompt)
  const complexity = estimateComplexity(prompt)
  const previousType = context.previousProjectType!
  const languages = context.previousLanguages ?? []
  const frameworks = context.previousFrameworks ?? []
  const needsDevServer = DEV_SERVER_PROJECTS.has(previousType)
  const needsBundling = BUNDLED_PREVIEW_PROJECTS.has(previousType) || previousType.startsWith('spa_')
  const previewType: PreviewType =
    needsDevServer ? 'dev_server'
      : (needsBundling) ? 'iframe_bundled'
      : (previousType === 'static_web' || previousType === 'game_web') ? 'iframe_static'
      : (previousType.startsWith('cli_') || previousType.startsWith('system_') || previousType === 'script' || previousType === 'data_python') ? 'console'
      : 'none'
  const isGameRequest = previousType === 'game_web'
  const { gameKind, knownGame } = classifyGameKind(lower, isGameRequest)

  return {
    projectType: previousType,
    complexity,
    languages,
    frameworks,
    features: [],
    needsDevServer,
    needsBundling,
    previewType,
    devCommand: getDevCommand(previousType),
    buildCommand: getBuildCommand(previousType),
    testCommand: getTestCommand(previousType),
    primaryModelRole: 'code',
    needsArchitecturePlanning: false,
    estimatedFileCount: estimateFileCount(complexity, previousType),
    assetPlan,
    ...(isGameRequest ? { gameKind, ...(knownGame ? { knownGame } : {}) } : {}),
  }
}
