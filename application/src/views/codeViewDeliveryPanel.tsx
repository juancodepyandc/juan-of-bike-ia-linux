import { lazy, Suspense, type Dispatch, type RefObject, type SetStateAction } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Check, Clipboard, Code2, Download, Eye, FileCode2, Globe, Loader2, Search, Sparkles } from 'lucide-react'
import CodeFileTree from '../components/CodeFileTree'
import type { CodeFile } from '../services/codeOrchestrator'
import type { CodeIntent } from '../services/codeIntent'
import type { CodeSandboxResult } from '../services/codeSandbox'
import type { DevServerState } from '../services/codeDevServer'
import { CodeConsolePanel, CodeCritiquePanel, CodeLanguageChip, CodeLyraCommentator } from './codeViewInspectorPanels'
import { BigLivePreviewFrame, type BigViewport } from './codeViewPreviewPanel'
import { countFileSearchMatches } from './codeViewSearch'

const CodeBlock = lazy(() => import('../components/CodeBlock'))

type CodeViewDeliveryPanelProps = {
  activeFile: number
  activeFileData: CodeFile | null
  bigPreviewIframeRef: RefObject<HTMLIFrameElement | null>
  bigViewport: BigViewport
  bigViewMode: 'code' | 'preview'
  consoleOutput: string
  copied: boolean
  copyCurrentFile: () => void
  devServerState: DevServerState
  error: string | null
  fileSearch: string
  files: CodeFile[]
  intent: CodeIntent | null
  isGenerating: boolean
  notes: string
  progress: string
  recoveryStatus: string | null
  setActiveFile: Dispatch<SetStateAction<number>>
  setBigViewport: Dispatch<SetStateAction<BigViewport>>
  setBigViewMode: Dispatch<SetStateAction<'code' | 'preview'>>
  setFileSearch: Dispatch<SetStateAction<string>>
  setShowLineNumbers: Dispatch<SetStateAction<boolean>>
  showLineNumbers: boolean
  streamPreview: string
  validationResult: CodeSandboxResult | null
}

export function CodeViewDeliveryPanel({
  activeFile,
  activeFileData,
  bigPreviewIframeRef,
  bigViewport,
  bigViewMode,
  consoleOutput,
  copied,
  copyCurrentFile,
  devServerState,
  error,
  fileSearch,
  files,
  intent,
  isGenerating,
  notes,
  progress,
  recoveryStatus,
  setActiveFile,
  setBigViewport,
  setBigViewMode,
  setFileSearch,
  setShowLineNumbers,
  showLineNumbers,
  streamPreview,
  validationResult,
}: CodeViewDeliveryPanelProps) {
  return (
    <>
        {/* RIGHT PANEL — Code output */}
        <div
          className="min-w-0 overflow-hidden rounded-[1.9rem] backdrop-blur-2xl"
          style={{
            border: '1px solid var(--line, color-mix(in srgb, var(--ft-ink, #1a140d) 16%, transparent))',
            background: 'var(--v4code-card-bg, color-mix(in srgb, var(--ft-paper-3, #faf3de) 75%, transparent))',
            boxShadow: 'var(--v4code-card-shadow, 0 12px 50px -15px color-mix(in srgb, var(--ft-ink, #1a140d) 45%, transparent), inset 0 1px 0 color-mix(in srgb, var(--ft-paper, #f3ead4) 70%, transparent))',
          }}
        >
          <div className="border-b border-aurora-border/30 px-5 py-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-[11px] uppercase tracking-[0.22em] text-aurora-text-dim">Livraison</p>
                <h2 className="mt-1 text-lg font-semibold text-aurora-text">Scene code</h2>
              </div>

              {activeFileData && (
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    onClick={copyCurrentFile}
                    className="inline-flex items-center gap-1.5 rounded-xl border border-aurora-border/40 bg-aurora-surface-2 px-3 py-2 text-xs text-aurora-text hover:border-aurora-accent/35 transition-colors"
                    title="Copier le fichier dans le presse-papiers"
                  >
                    {copied ? <Check size={14} className="text-aurora-green" /> : <Clipboard size={14} />}
                    <span>{copied ? 'Copie' : 'Copier'}</span>
                  </button>
                  <button
                    onClick={() => {
                      if (!activeFileData) return
                      const blob = new Blob([activeFileData.content], { type: 'text/plain;charset=utf-8' })
                      const url = URL.createObjectURL(blob)
                      const anchor = document.createElement('a')
                      anchor.href = url
                      anchor.download = activeFileData.name.split('/').pop() || 'file.txt'
                      anchor.click()
                      setTimeout(() => URL.revokeObjectURL(url), 1000)
                    }}
                    className="inline-flex items-center gap-1.5 rounded-xl border border-aurora-border/40 bg-aurora-surface-2 px-3 py-2 text-xs text-aurora-text hover:border-aurora-accent/35 transition-colors"
                    title="Telecharger ce fichier"
                  >
                    <Download size={14} />
                    <span>Download</span>
                  </button>
                  <button
                    onClick={() => setShowLineNumbers((v) => !v)}
                    className={`inline-flex items-center gap-1.5 rounded-xl border px-3 py-2 text-xs transition-colors ${
                      showLineNumbers ? 'border-aurora-accent/40 bg-aurora-accent/10 text-aurora-accent' : 'border-aurora-border/40 bg-aurora-surface-2 text-aurora-text-dim hover:text-aurora-text'
                    }`}
                    title="Afficher/masquer les numeros de ligne"
                  >
                    # Lignes
                  </button>
                </div>
              )}
            </div>
          </div>

          <div className="grid min-h-[34rem] gap-4 p-5 xl:grid-cols-[minmax(0,17rem)_minmax(0,1fr)]">
            {/* File tree + Preview */}
            <div className="min-h-0 flex flex-col gap-4">
              <div className="rounded-[1.6rem] border border-aurora-border/35 bg-aurora-surface/65 p-3">
                <div className="flex items-center gap-2 px-2 pb-3 text-[11px] uppercase tracking-[0.2em] text-aurora-text-dim">
                  <FileCode2 size={13} />
                  <span>Fichiers ({files.length})</span>
                </div>

                <CodeFileTree
                  files={files}
                  activeFile={activeFile}
                  onSelectFile={setActiveFile}
                />
              </div>

              {activeFileData && (
                <>
                  <CodeLanguageChip
                    fileName={activeFileData.name}
                    declaredLang={activeFileData.language}
                    content={activeFileData.content}
                  />
                  <CodeCritiquePanel content={activeFileData.content} language={activeFileData.language ?? activeFileData.name} />
                  <CodeLyraCommentator
                    content={activeFileData.content}
                    language={activeFileData.language ?? activeFileData.name}
                    isGenerating={isGenerating}
                  />
                </>
              )}

              <CodeConsolePanel
                consoleOutput={consoleOutput}
                streamContent={streamPreview}
                isGenerating={isGenerating}
                recoveryStatus={recoveryStatus}
                progress={progress}
                errorMessage={error}
                sandboxOk={validationResult?.ok ?? null}
              />

              {intent?.previewType === 'dev_server' && devServerState?.running && devServerState.url && (
                <div className="rounded-[1.6rem] border border-aurora-border/35 bg-aurora-surface/65 p-3 text-[11px] text-aurora-text-dim">
                  <div className="flex items-center gap-2 uppercase tracking-[0.2em]">
                    <Globe size={13} />
                    <span>Dev server actif</span>
                  </div>
                  <a
                    href={devServerState.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-2 block truncate text-aurora-accent-light hover:underline"
                  >
                    {devServerState.url}
                  </a>
                </div>
              )}
            </div>

            {/* Code viewer */}
            <div className="min-h-0 overflow-hidden rounded-[1.6rem] border border-aurora-border/35 bg-[#091116]">
              <div className="border-b border-aurora-border/25 px-4 py-3">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-[11px] uppercase tracking-[0.2em] text-aurora-text-dim">
                      {bigViewMode === 'preview' ? '🎬 Simulateur live' : '📝 Code source'}
                    </p>
                    <p className="mt-1 text-sm text-aurora-text">
                      {bigViewMode === 'preview'
                        ? (isGenerating ? 'La page se construit a mesure que le code arrive' : files.length > 0 ? 'Apercu interactif de l app — clique-toi dedans' : 'Lance une generation pour voir l apercu se construire en direct')
                        : (activeFileData?.name || (isGenerating ? 'Streaming en direct' : 'En attente de generation'))}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="flex items-center rounded-lg border border-aurora-border/35 bg-aurora-surface-2/60 p-0.5">
                      <button
                        onClick={() => setBigViewMode('code')}
                        title="Voir le code en cours d ecriture"
                        className={`flex h-7 items-center gap-1 rounded-md px-2.5 text-[11px] transition-colors ${
                          bigViewMode === 'code'
                            ? 'bg-aurora-accent/20 text-aurora-accent-light'
                            : 'text-aurora-text-dim hover:text-aurora-text'
                        }`}
                      >
                        <Code2 size={12} />
                        <span>Code</span>
                      </button>
                      <button
                        onClick={() => setBigViewMode('preview')}
                        title="Simulateur live — apercu interactif de l app/web en cours de generation"
                        className={`flex h-7 items-center gap-1.5 rounded-md px-2.5 text-[11px] font-medium transition-colors ${
                          bigViewMode === 'preview'
                            ? 'bg-aurora-accent/20 text-aurora-accent-light shadow-[inset_0_0_0_1px_rgba(251,146,60,0.35)]'
                            : 'text-aurora-text-dim hover:text-aurora-text'
                        }`}
                      >
                        <Eye size={12} />
                        <span>Simulateur</span>
                      </button>
                    </div>
                    <div className="inline-flex items-center gap-2 rounded-full border border-aurora-border/35 bg-aurora-surface/60 px-3 py-1.5 text-[11px] text-aurora-text-dim">
                      <Sparkles size={12} />
                      <span>{files.length > 0 ? `${files.length} fichier(s)` : isGenerating ? 'Streaming...' : 'Aucun fichier livre'}</span>
                      {isGenerating && (
                        <span className="inline-flex items-center gap-1 rounded-full bg-aurora-accent/15 px-1.5 text-[9px] text-aurora-accent-light">
                          <span className="h-1.5 w-1.5 rounded-full bg-aurora-accent animate-pulse" />
                          Live
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              </div>

              {bigViewMode === 'code' && activeFileData && (
                <div className="flex items-center gap-2 border-b border-aurora-border/25 bg-aurora-surface/30 px-4 py-2">
                  <Search size={12} className="text-aurora-text-dim" />
                  <input
                    value={fileSearch}
                    onChange={(event) => setFileSearch(event.target.value)}
                    placeholder="Chercher dans ce fichier (case insensitive)..."
                    className="min-w-0 flex-1 bg-transparent text-[11px] text-aurora-text outline-none placeholder:text-aurora-text-dim"
                  />
                  {fileSearch && (
                    <>
                      <span className="text-[10px] text-aurora-text-dim">
                        {countFileSearchMatches(activeFileData.content, fileSearch)} match(s)
                      </span>
                      <button
                        onClick={() => setFileSearch('')}
                        className="text-[10px] text-aurora-text-dim hover:text-aurora-text"
                      >
                        Clear
                      </button>
                    </>
                  )}
                </div>
              )}

              <div className="min-h-[28rem] overflow-auto">
                {bigViewMode === 'preview' ? (
                  <BigLivePreviewFrame
                    files={files}
                    streamContent={streamPreview}
                    isGenerating={isGenerating}
                    iframeRef={bigPreviewIframeRef}
                    viewport={bigViewport}
                    onViewportChange={setBigViewport}
                  />
                ) : activeFileData ? (
                  <Suspense fallback={<pre className="px-5 py-5 text-[13px] text-aurora-text-dim">Chargement du highlighter...</pre>}>
                    <CodeBlock
                      code={activeFileData.content}
                      language={activeFileData.language ?? activeFileData.name}
                      showLineNumbers={showLineNumbers}
                      search={fileSearch}
                    />
                  </Suspense>
                ) : streamPreview ? (
                  <div className="px-5 py-5">
                    <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-aurora-accent/20 bg-aurora-accent/10 px-3 py-1.5 text-[11px] text-aurora-accent-light">
                      <Loader2 size={12} className="animate-spin" />
                      <span>Streaming du modele</span>
                    </div>
                    <pre className="text-[13px] leading-6 text-aurora-text whitespace-pre-wrap">
                      <code>{streamPreview}</code>
                    </pre>
                  </div>
                ) : (
                  <div className="grid h-full place-items-center p-6">
                    <div className="max-w-lg text-center">
                      <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-[1.8rem] border border-aurora-border/35 bg-aurora-surface-2">
                        <Code2 size={30} className="text-aurora-text-dim" />
                      </div>
                      <p className="mt-4 text-sm text-aurora-text">
                        Donne une mission code pour activer le pipeline expert avec auto-correction.
                      </p>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Validation result */}
          <AnimatePresence>
            {validationResult && (
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 8 }}
                className="border-t border-aurora-border/30 px-5 py-4"
              >
                <div className={`rounded-[1.4rem] border px-4 py-4 ${
                  validationResult.ok
                    ? 'border-aurora-green/25 bg-aurora-green/10'
                    : 'border-aurora-red/25 bg-aurora-red/10'
                }`}>
                  <div className="flex items-center justify-between">
                    <p className={`text-[11px] uppercase tracking-[0.22em] ${
                      validationResult.ok ? 'text-aurora-green' : 'text-aurora-red'
                    }`}>Sandbox</p>
                    {validationResult.detectedLanguage && (
                      <span className="rounded-full border border-aurora-border/30 bg-aurora-surface-2/50 px-2 py-0.5 text-[10px] text-aurora-text-dim">
                        {validationResult.detectedLanguage}
                      </span>
                    )}
                  </div>
                  <p className="mt-2 text-sm leading-relaxed text-aurora-text">{validationResult.summary}</p>
                  <p className="mt-2 text-xs text-aurora-text-dim">{validationResult.rootPath}</p>

                  {validationResult.steps.length > 0 && (
                    <div className="mt-4 space-y-3">
                      {validationResult.steps.map((step) => (
                        <div key={`${step.label}-${step.command}`} className="rounded-2xl border border-aurora-border/30 bg-aurora-surface/50 px-3 py-3">
                          <div className="flex items-center justify-between gap-3">
                            <p className="text-sm text-aurora-text">{step.label}</p>
                            <span className={`text-[11px] ${step.ok ? 'text-aurora-green' : 'text-aurora-red'}`}>
                              {step.ok ? 'OK' : 'ECHEC'}
                            </span>
                          </div>
                          <p className="mt-1 text-[11px] text-aurora-text-dim">{step.command}</p>
                          {step.output && (
                            <pre className="mt-3 overflow-auto rounded-xl border border-aurora-border/25 bg-[#091116] px-3 py-3 text-[11px] leading-5 text-aurora-text-dim whitespace-pre-wrap max-h-32">
                              <code>{step.output}</code>
                            </pre>
                          )}
                        </div>
                      ))}
                    </div>
                  )}

                  {validationResult.question && (
                    <p className="mt-4 text-sm leading-relaxed text-aurora-text">{validationResult.question}</p>
                  )}
                </div>
              </motion.div>
            )}
            {notes && (
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 8 }}
                className="border-t border-aurora-border/30 px-5 py-4"
              >
                <div className="rounded-[1.4rem] border border-aurora-yellow/25 bg-aurora-yellow/10 px-4 py-4">
                  <p className="text-[11px] uppercase tracking-[0.22em] text-aurora-yellow">Notes</p>
                  <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-aurora-text">{notes}</p>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
    </>
  )
}
