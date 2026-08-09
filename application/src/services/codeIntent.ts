// ---------------------------------------------------------------------------
// Code Intent facade
// Extracted from codeIntent.ts during WS1 modularisation.
// ---------------------------------------------------------------------------

export { buildArchitecturePlanningPrompt } from './codeIntentArchitecturePrompt.ts'
export { classifyCodeIntent } from './codeIntentClassification.ts'
export { classifyPivotKindHeuristic, hasExplicitStackMention } from './codeIntentFollowup.ts'
export type {
  BrandProfile,
  CodeAssetPlan,
  CodeComplexity,
  CodeIntent,
  CodeIntentContext,
  CodeProjectType,
  GameKind,
  KnownGameEntry,
  PreviewType,
  PromptLanguage,
  SubjectDetection,
} from './codeIntentTypes.ts'
