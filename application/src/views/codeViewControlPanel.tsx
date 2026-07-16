import type { ComponentProps, Dispatch, SetStateAction } from 'react'
import { Archive, BookOpen, Bot, Code2, FolderOpen, Globe, Loader2, MessageSquare, ScanSearch, Sparkles, Workflow } from 'lucide-react'
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

type RecentCodeMessage = { role: string; content?: string }
type DesignReport = { score: number; missing: string[]; penalties: string[] }

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

          {/* Intent panel (shows after classification) */}
          {intent && (
            <div className="rounded-[1.5rem] border border-aurora-accent/20 bg-aurora-accent/8 px-4 py-3 space-y-2">
              <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.2em] text-aurora-accent-light">
                <Code2 size={13} />
                <span>Projet detecte</span>
              </div>
              <div className="grid grid-cols-2 gap-2 text-[11px]">
                <div>
                  <span className="text-aurora-text-dim">Type: </span>
                  <span className="text-aurora-text">{formatProjectType(intent.projectType)}</span>
                </div>
                <div>
                  <span className="text-aurora-text-dim">Complexite: </span>
                  <span className="text-aurora-text">{intent.complexity}</span>
                </div>
                {intent.frameworks.length > 0 && (
                  <div className="col-span-2">
                    <span className="text-aurora-text-dim">Frameworks: </span>
                    <span className="text-aurora-text">{intent.frameworks.join(', ')}</span>
                  </div>
                )}
                {intent.gameKind && (
                  <div className="col-span-2">
                    <span className="text-aurora-text-dim">Mode jeu: </span>
                    <span className="text-aurora-text">
                      {intent.gameKind === 'clone' && intent.knownGame
                        ? `Clone de ${intent.knownGame.canonical}`
                        : intent.gameKind === 'creative'
                          ? '✦ Création originale'
                          : 'Jeu générique'}
                    </span>
                  </div>
                )}
                {intent.features.length > 0 && (
                  <div className="col-span-2">
                    <span className="text-aurora-text-dim">Features: </span>
                    <span className="text-aurora-text">{intent.features.join(', ')}</span>
                  </div>
                )}
                <div>
                  <span className="text-aurora-text-dim">Preview: </span>
                  <span className="text-aurora-text">{intent.previewType.replace(/_/g, ' ')}</span>
                </div>
                <div>
                  <span className="text-aurora-text-dim">~Fichiers: </span>
                  <span className="text-aurora-text">{intent.estimatedFileCount}</span>
                </div>
              </div>
              {intent.needsDevServer && (
                <div className="flex items-center gap-1.5 text-[11px] text-aurora-accent-light">
                  <Globe size={11} />
                  <span>Dev server: {intent.devCommand}</span>
                </div>
              )}
            </div>
          )}

          {preflightReport && (
            <div className="rounded-[1.5rem] border border-sky-400/20 bg-sky-400/10 px-4 py-3 space-y-3">
              <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.2em] text-sky-300">
                <ScanSearch size={13} />
                <span>Preflight local</span>
              </div>
              <p className="text-xs leading-relaxed text-aurora-text">{preflightReport.summary}</p>
              <div className="grid grid-cols-2 gap-2 text-[11px]">
                <div>
                  <span className="text-aurora-text-dim">Stack: </span>
                  <span className="text-aurora-text">{preflightReport.chosenStack}</span>
                </div>
                <div>
                  <span className="text-aurora-text-dim">PM: </span>
                  <span className="text-aurora-text">{preflightReport.packageManager || 'aucun'}</span>
                </div>
              </div>
              {preflightReport.mustInspectFirst.length > 0 && (
                <p className="text-[11px] leading-relaxed text-aurora-text-muted">
                  A inspecter d abord: {preflightReport.mustInspectFirst.slice(0, 4).join(', ')}
                </p>
              )}
              {preflightReport.localConstraints.length > 0 && (
                <p className="text-[11px] leading-relaxed text-aurora-text-muted">
                  Contraintes locales: {preflightReport.localConstraints.slice(0, 2).join(' | ')}
                </p>
              )}
            </div>
          )}

          {/* Dev server status */}
          {devServerState.running && devServerState.url && (
            <div className="rounded-[1.5rem] border border-green-500/25 bg-green-500/10 px-4 py-3">
              <div className="flex items-center gap-2 text-[11px] text-green-400">
                <Globe size={13} />
                <span>Dev server actif: {devServerState.url}</span>
              </div>
            </div>
          )}

          {/* Correction log */}
          <CodeCorrectionLog
            correctionLog={correctionLog}
            intent={intent}
            totalAttempts={totalAttempts}
            finalScore={finalScore}
            isRunning={isGenerating}
          />

          {/* v73: design polish badge — only for visual projects, gives the
              user a one-glance signal of whether the LLM produced premium
              CSS or just a stub. Click to expand the missing-checks list. */}
          {designReport && (
            <details className="rounded-[1.5rem] border border-purple-500/25 bg-gradient-to-br from-purple-500/8 to-pink-500/5 px-4 py-3">
              <summary className="cursor-pointer flex items-center justify-between gap-2 text-[11px]">
                <div className="flex items-center gap-2">
                  <span className="text-purple-300">{designReport.score >= 80 ? '✨' : designReport.score >= 60 ? '🎨' : '⚠'}</span>
                  <span className="text-aurora-text">Design polish</span>
                  <span className={`font-semibold ${designReport.score >= 80 ? 'text-emerald-300' : designReport.score >= 60 ? 'text-amber-300' : 'text-rose-300'}`}>
                    {designReport.score}/100
                  </span>
                </div>
                <span className="text-[10px] text-aurora-text-muted">
                  {designReport.score >= 80 ? 'premium' : designReport.score >= 60 ? 'correct' : 'a refaire'}
                </span>
              </summary>
              {(designReport.missing.length > 0 || designReport.penalties.length > 0) && (
                <div className="mt-3 space-y-2 text-[10.5px] text-aurora-text-muted">
                  {designReport.missing.length > 0 && (
                    <div>
                      <div className="text-amber-300 font-semibold mb-1">Manquant ({designReport.missing.length})</div>
                      <ul className="space-y-0.5 pl-3 list-disc">
                        {designReport.missing.slice(0, 6).map((m, i) => <li key={i}>{m}</li>)}
                      </ul>
                    </div>
                  )}
                  {designReport.penalties.length > 0 && (
                    <div>
                      <div className="text-rose-300 font-semibold mb-1">Penalites ({designReport.penalties.length})</div>
                      <ul className="space-y-0.5 pl-3 list-disc">
                        {designReport.penalties.map((p, i) => <li key={i}>{p}</li>)}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </details>
          )}

          {/* Conversation context — enriched with mode + last 2 turns */}
          {hasConversation && (
            <div className="rounded-[1.5rem] border border-aurora-accent/20 bg-aurora-accent/8 px-4 py-3 space-y-2">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 text-[11px] text-aurora-accent-light">
                  <MessageSquare size={13} />
                  <span>Discussion active ({conversationTurns} tour{recentMessages.length > 2 ? 's' : ''})</span>
                </div>
                <button
                  onClick={clearConversation}
                  className="text-[10px] uppercase tracking-wider text-aurora-text-muted hover:text-aurora-text transition-colors"
                  title="Effacer la discussion et repartir a zero"
                >
                  Reset
                </button>
              </div>
              {followUpAnalysis && (
                <div className={`rounded-xl px-2.5 py-1.5 text-[11px] ${
                  followUpAnalysis.kind === 'pivot_platform' ? 'border border-amber-400/30 bg-amber-400/10 text-amber-200'
                  : followUpAnalysis.kind === 'fresh_start' ? 'border border-sky-400/30 bg-sky-400/10 text-sky-200'
                  : followUpAnalysis.kind === 'pivot_feature' ? 'border border-violet-400/30 bg-violet-400/10 text-violet-200'
                  : 'border border-emerald-400/30 bg-emerald-400/10 text-emerald-200'
                }`}>
                  <span className="font-semibold">
                    {followUpAnalysis.kind === 'pivot_platform' ? 'Mode: Pivot plateforme'
                    : followUpAnalysis.kind === 'pivot_feature' ? 'Mode: Pivot fonctionnel'
                    : followUpAnalysis.kind === 'fresh_start' ? 'Mode: Nouveau projet'
                    : followUpAnalysis.kind === 'clarify_only' ? 'Mode: Clarification'
                    : 'Mode: Patch incremental'}
                  </span>
                  {followUpAnalysis.pivotReason && (
                    <span className="ml-1 opacity-80">— {followUpAnalysis.pivotReason.slice(0, 80)}</span>
                  )}
                </div>
              )}
              {recentMessages.length > 0 && (
                <div className="space-y-1">
                  {recentMessages.slice(-4).map((msg, idx) => {
                    const preview = (msg.content || '').replace(/\s+/g, ' ').slice(0, 110)
                    const isUser = msg.role === 'user'
                    return (
                      <div key={idx} className="text-[10px] leading-snug">
                        <span className={isUser ? 'text-aurora-cyan' : 'text-aurora-accent-light'}>
                          {isUser ? 'Toi:' : 'IA:'}
                        </span>{' '}
                        <span className="text-aurora-text-muted">{preview}{preview.length >= 110 ? '...' : ''}</span>
                      </div>
                    )
                  })}
                </div>
              )}
              <p className="text-[10px] text-aurora-text-muted">
                Tape une suite (&laquo;ajoute un bouton&raquo;, &laquo;la m&ecirc;me chose en Python&raquo;...). Le prompt se conserve apr&egrave;s g&eacute;n&eacute;ration.
              </p>
            </div>
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
            <div className="rounded-[1.5rem] border border-aurora-accent/25 bg-aurora-accent/8 p-4 space-y-3">
              <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.2em] text-aurora-accent-light">
                <Archive size={13} />
                <span>Export persistant</span>
              </div>
              <p className="text-xs leading-relaxed text-aurora-text-muted">
                Les boutons restent disponibles meme si tu as ferme la popup finale. Le projet exporte inclut aussi `start.sh` quand un demarrage automatique est possible sur Linux/macOS.
              </p>
              <div className="grid grid-cols-2 gap-2">
                <button
                  onClick={() => void handlePersistentSave('workspace')}
                  disabled={saveTarget !== null}
                  className="inline-flex items-center justify-center gap-2 rounded-2xl border border-aurora-border/35 bg-aurora-surface/70 px-3 py-3 text-sm text-aurora-text transition-colors hover:border-aurora-accent/35 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {saveTarget === 'workspace' ? <Loader2 size={15} className="animate-spin" /> : <FolderOpen size={15} />}
                  <span>Workspace</span>
                </button>
                <button
                  onClick={() => void handlePersistentSave('zip')}
                  disabled={saveTarget !== null}
                  className="inline-flex items-center justify-center gap-2 rounded-2xl border border-aurora-border/35 bg-aurora-surface/70 px-3 py-3 text-sm text-aurora-text transition-colors hover:border-aurora-accent/35 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {saveTarget === 'zip' ? <Loader2 size={15} className="animate-spin" /> : <Archive size={15} />}
                  <span>ZIP</span>
                </button>
              </div>
              {savedProjectPath && (
                <p className="text-[11px] leading-relaxed text-aurora-text-dim break-all">
                  Derniere sauvegarde: {savedProjectPath}
                </p>
              )}
              {saveFeedback && (
                <p className="text-[11px] leading-relaxed text-aurora-red break-all">
                  {saveFeedback}
                </p>
              )}
            </div>
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
