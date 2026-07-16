import type { ComponentProps, Dispatch, SetStateAction } from 'react'
import { BookOpen, Bot, Loader2, ScanSearch, Sparkles, Workflow } from 'lucide-react'
import CodeCorrectionLog from '../components/CodeCorrectionLog'
import ContextFilesField from '../components/ContextFilesField'
import VoicePushToTalk from '../components/VoicePushToTalk'
import ModuleAssetPackCard from '../components/ModuleAssetPackCard'
import SessionSwitcher from '../components/SessionSwitcher'
import type { CorrectionPass } from '../services/codeAutoCorrection'
import type { CodePreflightReport } from '../services/codePreflight'
import type { CodeFile, FollowUpAnalysis } from '../services/codeOrchestrator'
import type { CodeIntent, CodeProjectType } from '../services/codeIntent'
import type { DevServerState } from '../services/codeDevServer'
import type { SaveDialogData } from '../components/SaveDialog'
import { CodeViewControlActions } from './codeViewControlActions'
import {
  CodeConversationPanel,
  CodeDesignPanel,
  CodeDevServerStatus,
  CodeIntentPanel,
  CodePreflightPanel,
  CodeSavedProjectPanel,
  type DesignReport,
  type RecentCodeMessage,
} from './codeViewControlStatusPanels'

type CodeViewControlPanelProps = {
  assetPack: ComponentProps<typeof ModuleAssetPackCard>['pack']
  canGenerate: boolean
  clearConversation: () => void
  contextFiles: File[]
  conversationTurns: number
  correctionLog: CorrectionPass[]
  designReport: DesignReport | null
  devServerState: DevServerState
  diagnostics: ComponentProps<typeof CodeViewControlActions>['diagnostics']
  error: string | null
  files: CodeFile[]
  finalScore: number
  followUpAnalysis: FollowUpAnalysis | null
  formatProjectType: (type: CodeProjectType) => string
  generate: () => void | Promise<void>
  handlePersistentSave: (target: 'workspace' | 'zip') => Promise<void>
  handleSessionChange: () => void
  hasConversation: boolean
  intent: CodeIntent | null
  isGenerating: boolean
  ollamaRunning: boolean
  pipelineLabel: string
  preflightReport: CodePreflightReport | null
  progress: string
  prompt: string
  promptGuide: string[]
  recentMessages: RecentCodeMessage[]
  recoveryStatus: string | null
  saveFeedback: string | null
  savedProjectData: SaveDialogData | null
  savedProjectPath: string | null
  saveTarget: 'workspace' | 'zip' | null
  setContextFiles: Dispatch<SetStateAction<File[]>>
  setPrompt: Dispatch<SetStateAction<string>>
  setPromptLibraryOpen: Dispatch<SetStateAction<boolean>>
  stopGeneration: () => void
  streamCharsTotal: number
  totalAttempts: number
}

export function CodeViewControlPanel({
  assetPack,
  canGenerate,
  clearConversation,
  contextFiles,
  conversationTurns,
  correctionLog,
  designReport,
  devServerState,
  diagnostics,
  error,
  files,
  finalScore,
  followUpAnalysis,
  formatProjectType,
  generate,
  handlePersistentSave,
  handleSessionChange,
  hasConversation,
  intent,
  isGenerating,
  ollamaRunning,
  pipelineLabel,
  preflightReport,
  progress,
  prompt,
  promptGuide,
  recentMessages,
  recoveryStatus,
  saveFeedback,
  savedProjectData,
  savedProjectPath,
  saveTarget,
  setContextFiles,
  setPrompt,
  setPromptLibraryOpen,
  stopGeneration,
  streamCharsTotal,
  totalAttempts,
}: CodeViewControlPanelProps) {
  return (
    <>
        {/* LEFT PANEL */}
        <div
          className="xl:sticky xl:top-4 self-start overflow-y-auto overscroll-contain scroll-shell max-h-[60vh] sm:max-h-[calc(100vh-12rem)] rounded-[1.4rem] sm:rounded-[1.9rem] p-3 sm:p-4 space-y-3 sm:space-y-4 backdrop-blur-2xl"
          style={{
            border: '1px solid var(--line, color-mix(in srgb, var(--ft-ink, #1a140d) 18%, transparent))',
            background: 'var(--v4code-card-bg, color-mix(in srgb, var(--ft-paper-3, #faf3de) 78%, transparent))',
            boxShadow: 'var(--v4code-card-shadow, 0 8px 40px -12px color-mix(in srgb, var(--ft-ink, #1a140d) 35%, transparent))',
          }}
        >
          {/* Session switcher */}
          <SessionSwitcher module="code" onSessionChange={handleSessionChange} />

          {/* Mission */}
          <div
            className="group relative overflow-hidden rounded-[1.5rem] p-4 backdrop-blur-xl transition-all duration-300"
            style={{
              border: '1px solid var(--line, color-mix(in srgb, var(--ft-ink, #1a140d) 14%, transparent))',
              background: 'var(--v4code-card-bg, linear-gradient(135deg, color-mix(in srgb, var(--ft-paper, #f3ead4) 92%, transparent) 0%, color-mix(in srgb, var(--ft-paper-3, #faf3de) 60%, transparent) 100%))',
              boxShadow: 'var(--v4code-card-inset, inset 0 1px 0 color-mix(in srgb, var(--ft-paper-3, #faf3de) 60%, transparent))',
            }}
          >
            <div
              className="pointer-events-none absolute -top-8 -right-8 h-32 w-32 rounded-full blur-2xl opacity-60 group-hover:opacity-90 transition-opacity duration-500"
              style={{ background: 'radial-gradient(circle at center, color-mix(in srgb, var(--aura-code, var(--ft-accent-2, #f78324)) 50%, transparent) 0%, transparent 70%)' }}
            />
            <div className="relative flex items-start justify-between gap-3">
              <div>
                <p
                  className="text-[10px] uppercase tracking-[0.28em] font-semibold"
                  style={{ color: 'var(--fg-dim, color-mix(in srgb, var(--ft-ink, #1a140d) 55%, transparent))' }}
                >
                  Mission
                </p>
                <p
                  className="mt-2 text-sm leading-relaxed"
                  style={{ color: 'var(--fg, color-mix(in srgb, var(--ft-ink, #1a140d) 95%, transparent))' }}
                >
                  Donne le livrable, la stack, les contraintes et le niveau de finition attendu.
                </p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setPromptLibraryOpen(true)}
                  title="Bibliotheque de prompts"
                  className="flex h-8 w-8 items-center justify-center rounded-xl transition-all duration-200 hover:scale-105"
                  style={{
                    border: '1px solid var(--line, color-mix(in srgb, var(--ft-ink, #1a140d) 20%, transparent))',
                    background: 'var(--bg-card, color-mix(in srgb, var(--ft-paper-3, #faf3de) 70%, transparent))',
                    color: 'var(--fg-dim, color-mix(in srgb, var(--ft-ink, #1a140d) 60%, transparent))',
                  }}
                >
                  <BookOpen size={14} />
                </button>
                <div
                  className="relative flex h-11 w-11 items-center justify-center rounded-2xl text-white shadow-lg transition-transform duration-300 group-hover:scale-105"
                  style={{
                    background: 'var(--v4code-accent-grad, linear-gradient(135deg, var(--ft-accent, #e63412) 0%, var(--ft-accent-2, #f78324) 60%, var(--ft-accent-3, #ffd24a) 100%))',
                    boxShadow: 'var(--v4code-accent-shadow, 0 8px 22px -6px color-mix(in srgb, var(--ft-accent, #e63412) 65%, transparent))',
                  }}
                >
                  <Sparkles size={18} className="relative" />
                </div>
              </div>
            </div>

            <textarea
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              placeholder="Ex: Dashboard React multi-page avec auth JWT, CRUD utilisateurs, graphiques recharts, dark mode, responsive. Ou: API FastAPI complete avec PostgreSQL, JWT, Docker."
              rows={7}
              className="relative mt-4 w-full resize-none rounded-2xl px-3.5 py-3 text-sm outline-none transition-all duration-200"
              style={{
                border: '1px solid var(--line, color-mix(in srgb, var(--ft-ink, #1a140d) 18%, transparent))',
                background: 'var(--bg-input, color-mix(in srgb, var(--ft-paper, #f3ead4) 70%, transparent))',
                color: 'var(--fg, var(--ft-ink, #1a140d))',
              }}
            />
            <div className="mt-2 flex items-center gap-2">
              <VoicePushToTalk
                onTranscript={(text) => setPrompt((prev) => (prev.trim() ? `${prev}\n${text}` : text))}
                label="Dicter le brief du projet"
                size={36}
              />
              <span className="text-[11px] text-aurora-text-dim">Dicte ton brief — la transcription s'ajoute à la fin.</span>
            </div>
          </div>

          {/* Brief guide */}
          <div
            className="rounded-[1.5rem] p-4 backdrop-blur-xl"
            style={{
              border: '1px solid var(--line, color-mix(in srgb, var(--ft-ink, #1a140d) 12%, transparent))',
              background: 'var(--v4code-card-bg, color-mix(in srgb, var(--ft-paper-3, #faf3de) 72%, transparent))',
            }}
          >
            <div
              className="flex items-center gap-2 text-[10px] uppercase tracking-[0.28em] font-semibold"
              style={{ color: 'var(--fg-dim, color-mix(in srgb, var(--ft-ink, #1a140d) 55%, transparent))' }}
            >
              <ScanSearch size={13} />
              <span>Guide de brief</span>
            </div>
            <div className="mt-3 space-y-2">
              {promptGuide.map((item) => (
                <div
                  key={item}
                  className="rounded-2xl px-3 py-3 text-xs leading-relaxed transition-colors"
                  style={{
                    border: '1px solid var(--line, color-mix(in srgb, var(--ft-ink, #1a140d) 10%, transparent))',
                    background: 'var(--bg-card, color-mix(in srgb, var(--ft-paper, #f3ead4) 65%, transparent))',
                    color: 'var(--fg-dim, color-mix(in srgb, var(--ft-ink, #1a140d) 80%, transparent))',
                  }}
                >
                  {item}
                </div>
              ))}
            </div>
          </div>

          <ContextFilesField
            files={contextFiles}
            onFilesChange={setContextFiles}
            accept=".png,.jpg,.jpeg,.webp,.gif,.pdf,.txt,.md,.json,.csv,.tsv,.xlsx,.xls,.xlsm"
            hint="Ajoute captures d ecran, PDF, textes ou tableurs pour guider la generation."
          />

          <ModuleAssetPackCard pack={assetPack} />

          {/* Runtime + Pipeline info */}
          <div className="grid grid-cols-2 gap-3">
            <div
              className="group/card relative overflow-hidden rounded-[1.5rem] p-4 backdrop-blur-xl transition-colors"
              style={{
                border: '1px solid var(--line, color-mix(in srgb, var(--ft-ink, #1a140d) 12%, transparent))',
                background: 'var(--v4code-card-bg, color-mix(in srgb, var(--ft-paper-3, #faf3de) 72%, transparent))',
              }}
            >
              <div
                className="absolute -top-6 -right-6 h-20 w-20 rounded-full blur-2xl opacity-60 transition-opacity duration-500 group-hover/card:opacity-90"
                style={{
                  background: ollamaRunning
                    ? 'color-mix(in srgb, var(--aura-code, var(--ft-accent-3, #ffd24a)) 50%, transparent)'
                    : 'color-mix(in srgb, var(--accent, var(--ft-accent-2, #f78324)) 40%, transparent)',
                }}
              />
              <div
                className="relative flex items-center gap-2 text-[10px] uppercase tracking-[0.28em] font-semibold"
                style={{ color: 'var(--fg-dim, color-mix(in srgb, var(--ft-ink, #1a140d) 55%, transparent))' }}
              >
                <Bot size={13} />
                <span>Runtime</span>
              </div>
              <p className="relative mt-2 text-sm" style={{ color: 'var(--fg, var(--ft-ink, #1a140d))' }}>
                {ollamaRunning
                  ? 'Serveur et modele actifs.'
                  : 'Demarrage automatique a la demande.'}
              </p>
            </div>

            <div
              className="group/card relative overflow-hidden rounded-[1.5rem] p-4 backdrop-blur-xl transition-colors"
              style={{
                border: '1px solid var(--line, color-mix(in srgb, var(--ft-ink, #1a140d) 12%, transparent))',
                background: 'var(--v4code-card-bg, color-mix(in srgb, var(--ft-paper-3, #faf3de) 72%, transparent))',
              }}
            >
              <div
                className="absolute -top-6 -right-6 h-20 w-20 rounded-full blur-2xl opacity-60 transition-opacity duration-500 group-hover/card:opacity-90"
                style={{ background: 'color-mix(in srgb, var(--accent, var(--ft-accent, #e63412)) 35%, transparent)' }}
              />
              <div
                className="relative flex items-center gap-2 text-[10px] uppercase tracking-[0.28em] font-semibold"
                style={{ color: 'var(--fg-dim, color-mix(in srgb, var(--ft-ink, #1a140d) 55%, transparent))' }}
              >
                <Workflow size={13} />
                <span>Pipeline</span>
              </div>
              <p className="relative mt-2 text-[11px] leading-relaxed" style={{ color: 'var(--fg, var(--ft-ink, #1a140d))' }}>{pipelineLabel}</p>
            </div>
          </div>

          {intent && <CodeIntentPanel intent={intent} formatProjectType={formatProjectType} />}
          {preflightReport && <CodePreflightPanel report={preflightReport} />}
          <CodeDevServerStatus state={devServerState} />

          {/* Correction log */}
          <CodeCorrectionLog
            correctionLog={correctionLog}
            intent={intent}
            totalAttempts={totalAttempts}
            finalScore={finalScore}
            isRunning={isGenerating}
          />

          {designReport && <CodeDesignPanel report={designReport} />}

          {hasConversation && (
            <CodeConversationPanel
              conversationTurns={conversationTurns}
              recentMessages={recentMessages}
              followUpAnalysis={followUpAnalysis}
              clearConversation={clearConversation}
            />
          )}

          {/* Recovery status */}
          {recoveryStatus && (
            <div className="rounded-[1.5rem] border border-aurora-yellow/25 bg-aurora-yellow/10 px-4 py-3">
              <div className="flex items-center gap-2 text-[11px] text-aurora-yellow">
                <Loader2 size={13} className="animate-spin" />
                <span>Auto-reparation: {recoveryStatus}</span>
              </div>
            </div>
          )}

          {savedProjectData && (
            <CodeSavedProjectPanel
              savedProjectPath={savedProjectPath}
              saveFeedback={saveFeedback}
              saveTarget={saveTarget}
              onSave={handlePersistentSave}
            />
          )}

          <CodeViewControlActions
            canGenerate={canGenerate}
            diagnostics={diagnostics}
            error={error}
            files={files}
            generate={generate}
            hasConversation={hasConversation}
            isGenerating={isGenerating}
            progress={progress}
            prompt={prompt}
            setPrompt={setPrompt}
            stopGeneration={stopGeneration}
            streamCharsTotal={streamCharsTotal}
          />
        </div>
    </>
  )
}
