import type { ComponentProps, Dispatch, SetStateAction } from 'react'
import { AlertTriangle, Loader2, Play, StopCircle } from 'lucide-react'
import ConnectorRecommendationsPanel from '../components/ConnectorRecommendationsPanel.tsx'
import { StudioDiagnosticsPanel } from '../components/StudioHero.tsx'
import type { CodeFile } from '../services/codeOrchestrator.ts'

type CodeViewControlActionsProps = {
  canGenerate: boolean
  diagnostics: ComponentProps<typeof StudioDiagnosticsPanel>['diagnostics']
  error: string | null
  files: CodeFile[]
  generate: () => void | Promise<void>
  hasConversation: boolean
  isGenerating: boolean
  progress: string
  prompt: string
  setPrompt: Dispatch<SetStateAction<string>>
  stopGeneration: () => void
  streamCharsTotal: number
}

export function CodeViewControlActions({
  canGenerate,
  diagnostics,
  error,
  files,
  generate,
  hasConversation,
  isGenerating,
  progress,
  prompt,
  setPrompt,
  stopGeneration,
  streamCharsTotal,
}: CodeViewControlActionsProps) {
  return (
    <>
          {/* Generate / Stop buttons */}
          <div className="flex gap-3">
            <button
              onClick={() => void generate()}
              disabled={!canGenerate}
              className={`group/btn relative flex-1 inline-flex items-center justify-center gap-2 overflow-hidden rounded-[1.4rem] px-4 py-3.5 text-sm font-bold tracking-wide transition-all duration-300 ${
                canGenerate
                  ? 'text-white hover:scale-[1.015] active:scale-[0.99]'
                  : 'opacity-60 cursor-not-allowed'
              }`}
              style={canGenerate ? {
                background: 'var(--v4code-accent-grad, linear-gradient(135deg, var(--ft-accent, #e63412) 0%, var(--ft-accent-2, #f78324) 55%, var(--ft-accent-3, #ffd24a) 100%))',
                boxShadow: 'var(--v4code-accent-shadow-lg, 0 8px 32px -8px color-mix(in srgb, var(--ft-accent, #e63412) 55%, transparent), 0 1px 0 color-mix(in srgb, var(--ft-accent-3, #ffd24a) 40%, transparent) inset)',
                fontFamily: 'var(--font-display, "Bangers", Impact, sans-serif)',
                letterSpacing: '0.08em',
                fontSize: '0.95rem',
              } : {
                background: 'color-mix(in srgb, var(--fg, var(--ft-ink, #1a140d)) 6%, transparent)',
                color: 'var(--fg-mute, color-mix(in srgb, var(--ft-ink, #1a140d) 35%, transparent))',
              }}
            >
              {canGenerate && (
                <span
                  className="pointer-events-none absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/25 to-transparent transition-transform duration-700 group-hover/btn:translate-x-full"
                  aria-hidden
                />
              )}
              {isGenerating ? (
                <>
                  <Loader2 size={18} className="relative animate-spin" />
                  <span className="relative">
                    {progress || 'Generation...'}
                    {streamCharsTotal > 0 && (
                      <span className="ml-2 text-xs opacity-70">
                        · {(streamCharsTotal / 1000).toFixed(1)}k chars
                      </span>
                    )}
                  </span>
                </>
              ) : (
                <>
                  <Play size={18} className="relative" />
                  <span className="relative">{hasConversation ? 'Continuer' : 'Generer'}</span>
                </>
              )}
            </button>

            <button
              onClick={stopGeneration}
              disabled={!isGenerating}
              className={`inline-flex items-center justify-center gap-2 rounded-[1.4rem] px-4 py-3 text-sm font-medium transition-colors ${
                isGenerating
                  ? 'border border-aurora-red/30 bg-aurora-red/12 text-aurora-red'
                  : 'border border-aurora-border/35 bg-aurora-surface-2 text-aurora-text-dim opacity-60 cursor-not-allowed'
              }`}
            >
              <StopCircle size={18} />
              <span>Stop</span>
            </button>
          </div>

          {/* "Inspecter design" — v69: affiche le score + missing + penalties
              sans regenerer. Pratique pour comprendre POURQUOI le design
              n est pas pousse avant de cliquer "Refaire". */}
          {files.length > 0 && !isGenerating && (
            <button
              onClick={async () => {
                const { computeDesignPolishReportPublic } = await import('../services/codeOrchestrator')
                const report = computeDesignPolishReportPublic(files)
                const status = report.score >= 80 ? '✅ Premium' : report.score >= 70 ? '🟢 Bon' : report.score >= 50 ? '🟠 Moyen' : '🔴 Scolaire'
                const summary = [
                  `${status} — ${report.score}/100 (seuil premium 70)`,
                  '',
                  ...(report.missing.length > 0 ? ['Patterns MANQUANTS:', ...report.missing.map((m) => `  ✗ ${m}`)] : ['Tous les patterns essentiels detectes ✓']),
                  ...(report.penalties.length > 0 ? ['', 'Defauts trouves:', ...report.penalties.map((p) => `  ⚠ ${p}`)] : []),
                ].join('\n')
                window.alert(summary)
              }}
              className="mt-2 flex w-full items-center justify-center gap-2 rounded-[1.4rem] border px-4 py-2.5 text-xs font-medium transition-colors"
              style={{
                border: '1px solid var(--line, color-mix(in srgb, var(--ft-ink, #1a140d) 18%, transparent))',
                background: 'var(--bg-card, color-mix(in srgb, var(--ft-paper-3, #faf3de) 65%, transparent))',
                color: 'var(--fg-dim, color-mix(in srgb, var(--ft-ink, #1a140d) 75%, transparent))',
              }}
              title="Audit le design des fichiers generes (score 0-100, missing patterns, penalties) sans regenerer."
            >
              🔍 Inspecter design
            </button>
          )}

          {/* "Refaire en plus pousse" — v69: maintenant intelligent. Au lieu
              d un texte boost generique, calcule le DesignPolishReport sur
              les fichiers existants et envoie au LLM la liste exacte des
              patterns manquants + penalties detectees. Le LLM regenere avec
              une cible precise au lieu d un vague "fais plus pousse". */}
          {files.length > 0 && !isGenerating && (
            <button
              onClick={async () => {
                // Lazy-import pour eviter d alourdir le bundle initial
                const { computeDesignPolishReportPublic } = await import('../services/codeOrchestrator')
                const report = computeDesignPolishReportPublic(files)
                const lines: string[] = [
                  `Refais le projet en CORRIGEANT EXACTEMENT ces points (audit design ${report.score}/100 — seuil 70):`,
                ]
                if (report.missing.length > 0) {
                  lines.push('', 'Patterns MANQUANTS a ajouter imperativement:')
                  for (const m of report.missing) lines.push(`  ✗ ${m}`)
                }
                if (report.penalties.length > 0) {
                  lines.push('', 'Defauts a corriger:')
                  for (const p of report.penalties) lines.push(`  ⚠ ${p}`)
                }
                lines.push(
                  '',
                  'Refais le projet COMPLET en respectant maintenant TOUS ces points.',
                  '',
                  `Demande originale:\n${prompt || (files[0]?.content?.slice(0, 200) ?? 'meme projet')}`
                )
                setPrompt(lines.join('\n'))
                void generate()
              }}
              className="mt-2 flex w-full items-center justify-center gap-2 rounded-[1.4rem] border px-4 py-3 text-sm font-medium transition-colors"
              style={{
                border: '1px solid color-mix(in srgb, var(--aura-code, var(--ft-accent, #e63412)) 35%, transparent)',
                background: 'var(--v4code-accent-soft-grad, linear-gradient(135deg, color-mix(in srgb, var(--ft-accent-2, #f78324) 14%, transparent), color-mix(in srgb, var(--ft-accent-3, #ffd24a) 8%, transparent)))',
                color: 'var(--fg, var(--ft-ink, #1a140d))',
              }}
              title="Audit le design genere et regenere avec correction ciblee des patterns manquants (score, missing, penalties)."
            >
              ✨ Refaire en plus poussé (audit design)
            </button>
          )}

          {/* Status / Error */}
          {(progress || error) && (
            <div className="space-y-3">
              {progress && (
                <div className="rounded-[1.5rem] border border-aurora-border/40 bg-aurora-surface/70 px-4 py-4">
                  <p className="text-[11px] uppercase tracking-[0.2em] text-aurora-text-dim">Etat courant</p>
                  <p className="mt-2 text-sm text-aurora-text">{progress}</p>
                </div>
              )}
              {error && (
                <div className="flex items-start gap-2 rounded-[1.5rem] border border-aurora-red/25 bg-aurora-red/10 px-3 py-3">
                  <AlertTriangle size={16} className="mt-0.5 shrink-0 text-aurora-red" />
                  <p className="text-xs leading-relaxed text-aurora-red">{error}</p>
                </div>
              )}
            </div>
          )}

          <StudioDiagnosticsPanel diagnostics={diagnostics} title="Preflight code" />
          <ConnectorRecommendationsPanel module="code" compact className="code-connector-recommendations" />
    </>
  )
}
