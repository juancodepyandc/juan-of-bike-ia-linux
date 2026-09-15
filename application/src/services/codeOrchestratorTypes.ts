import type { VisualFidelityReport } from './codeVisualFidelity.ts'
import type { RecoveryEvent } from './ollamaResilience.ts'
import type { CorrectionPass } from './codeAutoCorrection.ts'
import type { CodeIntent } from './codeIntent.ts'
import type { CodePreflightReport } from './codePreflight.ts'
import type { CodeSandboxResult } from './codeSandbox.ts'
import type { DesignPolishReport } from './codeQualityGates.ts'
import type { FollowUpAnalysis } from './codeFollowUpAnalysis.ts'

export type CodeFile = {
  name: string
  language: string
  content: string
}

export type CodeOrchestrationPhase =
  | 'intent'
  | 'preflight'
  | 'planning'
  | 'generation'
  | 'validation'
  | 'correction'
  | 'research'
  | 'dev_server'
  | 'done'
  // Le travail EXISTE mais le pipeline n a pas pu aller au bout a cause d une
  // panne d infrastructure (modele injoignable, reseau coupe). Ce n est ni une
  // reussite ni un echec de code: c est une interruption, et les fichiers deja
  // produits sont livres tels quels.
  | 'interrupted'
  | 'error'

export type CodeOrchestrationResult = {
  files: CodeFile[]
  notes: string
  sandboxResult: CodeSandboxResult | null
  intent: CodeIntent
  preflightReport: CodePreflightReport | null
  correctionLog: CorrectionPass[]
  phase: CodeOrchestrationPhase
  architecturePlan: string | null
  totalAttempts: number
  finalScore: number
  recoveryEvents: RecoveryEvent[]
  followUp: FollowUpAnalysis | null
  designReport?: DesignPolishReport | null
  /** WS9 source-statique: disponible sur les trois canaux, pas seulement l UI. */
  visualFidelity?: VisualFidelityReport | null
}

export type PhaseCallback = (detail: string, progress: number) => void

export type OrchestrateCodeGenerationOptions = {
  prompt: string
  enrichedPrompt: string
  conversationHistory: import('../types/app.ts').OllamaMessage[]
  existingFiles: CodeFile[]
  contextImages: string[]
  userFileDataUrls?: Record<string, string>
  configuredCodeModel: string
  visionModel: string
  setPhase: PhaseCallback
  onToken: (token: string) => void
  onFilesUpdate: (files: CodeFile[], notes: string) => void
  onValidationUpdate: (result: CodeSandboxResult) => void
  onCorrectionLogUpdate: (log: CorrectionPass[], attempt: number, score: number) => void
  onRecoveryEvent?: (event: RecoveryEvent) => void
  onFollowUpAnalysis?: (analysis: FollowUpAnalysis) => void
  signal?: AbortSignal
  modelRouting?: import('./codePipelineRuntime.ts').CodeModelRoutingContext
}
