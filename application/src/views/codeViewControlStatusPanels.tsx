import { Archive, Code2, FolderOpen, Globe, Loader2, MessageSquare, Palette, ScanSearch } from 'lucide-react'
import type { CodeIntent, CodeProjectType } from '../services/codeIntent'
import type { CodePreflightReport } from '../services/codePreflight'
import type { FollowUpAnalysis } from '../services/codeOrchestrator'
import type { DevServerState } from '../services/codeDevServer'

export type RecentCodeMessage = { role: string; content?: string }
export type DesignReport = { score: number; missing: string[]; penalties: string[] }

export function CodeIntentPanel({
  intent,
  formatProjectType,
}: {
  intent: CodeIntent
  formatProjectType: (type: CodeProjectType) => string
}) {
  return (
    <div className="rounded-[1.5rem] border border-aurora-accent/20 bg-aurora-accent/8 px-4 py-3 space-y-2">
      <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.2em] text-aurora-accent-light">
        <Code2 size={13} />
        <span>Projet detecte</span>
      </div>
      <div className="grid grid-cols-2 gap-2 text-[11px]">
        <div><span className="text-aurora-text-dim">Type: </span><span className="text-aurora-text">{formatProjectType(intent.projectType)}</span></div>
        <div><span className="text-aurora-text-dim">Complexite: </span><span className="text-aurora-text">{intent.complexity}</span></div>
        {intent.frameworks.length > 0 && (
          <div className="col-span-2"><span className="text-aurora-text-dim">Frameworks: </span><span className="text-aurora-text">{intent.frameworks.join(', ')}</span></div>
        )}
        {intent.gameKind && (
          <div className="col-span-2">
            <span className="text-aurora-text-dim">Mode jeu: </span>
            <span className="text-aurora-text">
              {intent.gameKind === 'clone' && intent.knownGame
                ? `Clone de ${intent.knownGame.canonical}`
                : intent.gameKind === 'creative' ? 'Creation originale' : 'Jeu generique'}
            </span>
          </div>
        )}
        {intent.features.length > 0 && (
          <div className="col-span-2"><span className="text-aurora-text-dim">Features: </span><span className="text-aurora-text">{intent.features.join(', ')}</span></div>
        )}
        <div><span className="text-aurora-text-dim">Preview: </span><span className="text-aurora-text">{intent.previewType.replace(/_/g, ' ')}</span></div>
        <div><span className="text-aurora-text-dim">~Fichiers: </span><span className="text-aurora-text">{intent.estimatedFileCount}</span></div>
      </div>
      {intent.needsDevServer && (
        <div className="flex items-center gap-1.5 text-[11px] text-aurora-accent-light">
          <Globe size={11} />
          <span>Dev server: {intent.devCommand}</span>
        </div>
      )}
    </div>
  )
}

export function CodePreflightPanel({ report }: { report: CodePreflightReport }) {
  return (
    <div className="rounded-[1.5rem] border border-sky-400/20 bg-sky-400/10 px-4 py-3 space-y-3">
      <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.2em] text-sky-300">
        <ScanSearch size={13} />
        <span>Preflight local</span>
      </div>
      <p className="text-xs leading-relaxed text-aurora-text">{report.summary}</p>
      <div className="grid grid-cols-2 gap-2 text-[11px]">
        <div><span className="text-aurora-text-dim">Stack: </span><span className="text-aurora-text">{report.chosenStack}</span></div>
        <div><span className="text-aurora-text-dim">PM: </span><span className="text-aurora-text">{report.packageManager || 'aucun'}</span></div>
      </div>
      {report.mustInspectFirst.length > 0 && (
        <p className="text-[11px] leading-relaxed text-aurora-text-muted">A inspecter d abord: {report.mustInspectFirst.slice(0, 4).join(', ')}</p>
      )}
      {report.localConstraints.length > 0 && (
        <p className="text-[11px] leading-relaxed text-aurora-text-muted">Contraintes locales: {report.localConstraints.slice(0, 2).join(' | ')}</p>
      )}
    </div>
  )
}

export function CodeDevServerStatus({ state }: { state: DevServerState }) {
  if (!state.running || !state.url) return null
  return (
    <div className="rounded-[1.5rem] border border-green-500/25 bg-green-500/10 px-4 py-3">
      <div className="flex items-center gap-2 text-[11px] text-green-400">
        <Globe size={13} />
        <span>Dev server actif: {state.url}</span>
      </div>
    </div>
  )
}

export function CodeDesignPanel({ report }: { report: DesignReport }) {
  const level = report.score >= 80 ? 'premium' : report.score >= 60 ? 'correct' : 'a refaire'
  return (
    <details className="rounded-[1.5rem] border border-purple-500/25 bg-purple-500/8 px-4 py-3">
      <summary className="cursor-pointer flex items-center justify-between gap-2 text-[11px]">
        <div className="flex items-center gap-2">
          <Palette size={13} className="text-purple-300" />
          <span className="text-aurora-text">Design polish</span>
          <span className={`font-semibold ${report.score >= 80 ? 'text-emerald-300' : report.score >= 60 ? 'text-amber-300' : 'text-rose-300'}`}>{report.score}/100</span>
        </div>
        <span className="text-[10px] text-aurora-text-muted">{level}</span>
      </summary>
      {(report.missing.length > 0 || report.penalties.length > 0) && (
        <div className="mt-3 space-y-2 text-[10.5px] text-aurora-text-muted">
          {report.missing.length > 0 && (
            <div>
              <div className="text-amber-300 font-semibold mb-1">Manquant ({report.missing.length})</div>
              <ul className="space-y-0.5 pl-3 list-disc">{report.missing.slice(0, 6).map((item) => <li key={item}>{item}</li>)}</ul>
            </div>
          )}
          {report.penalties.length > 0 && (
            <div>
              <div className="text-rose-300 font-semibold mb-1">Penalites ({report.penalties.length})</div>
              <ul className="space-y-0.5 pl-3 list-disc">{report.penalties.map((item) => <li key={item}>{item}</li>)}</ul>
            </div>
          )}
        </div>
      )}
    </details>
  )
}

export function CodeConversationPanel({
  conversationTurns,
  recentMessages,
  followUpAnalysis,
  clearConversation,
}: {
  conversationTurns: number
  recentMessages: RecentCodeMessage[]
  followUpAnalysis: FollowUpAnalysis | null
  clearConversation: () => void
}) {
  return (
    <div className="rounded-[1.5rem] border border-aurora-accent/20 bg-aurora-accent/8 px-4 py-3 space-y-2">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-[11px] text-aurora-accent-light">
          <MessageSquare size={13} />
          <span>Discussion active ({conversationTurns} tour{recentMessages.length > 2 ? 's' : ''})</span>
        </div>
        <button onClick={clearConversation} className="text-[10px] uppercase tracking-wider text-aurora-text-muted hover:text-aurora-text transition-colors" title="Effacer la discussion et repartir a zero">Reset</button>
      </div>
      {followUpAnalysis && <FollowUpMode analysis={followUpAnalysis} />}
      {recentMessages.length > 0 && (
        <div className="space-y-1">
          {recentMessages.slice(-4).map((message, index) => {
            const preview = (message.content || '').replace(/\s+/g, ' ').slice(0, 110)
            const isUser = message.role === 'user'
            return (
              <div key={`${message.role}-${index}`} className="text-[10px] leading-snug">
                <span className={isUser ? 'text-aurora-cyan' : 'text-aurora-accent-light'}>{isUser ? 'Toi:' : 'IA:'}</span>{' '}
                <span className="text-aurora-text-muted">{preview}{preview.length >= 110 ? '...' : ''}</span>
              </div>
            )
          })}
        </div>
      )}
      <p className="text-[10px] text-aurora-text-muted">Tape une suite (&laquo;ajoute un bouton&raquo;, &laquo;la m&ecirc;me chose en Python&raquo;...). Le prompt se conserve apr&egrave;s g&eacute;n&eacute;ration.</p>
    </div>
  )
}

function FollowUpMode({ analysis }: { analysis: FollowUpAnalysis }) {
  const label = analysis.kind === 'pivot_platform' ? 'Pivot plateforme'
    : analysis.kind === 'pivot_feature' ? 'Pivot fonctionnel'
      : analysis.kind === 'fresh_start' ? 'Nouveau projet'
        : analysis.kind === 'clarify_only' ? 'Clarification' : 'Patch incremental'
  const tone = analysis.kind === 'pivot_platform' ? 'border-amber-400/30 bg-amber-400/10 text-amber-200'
    : analysis.kind === 'fresh_start' ? 'border-sky-400/30 bg-sky-400/10 text-sky-200'
      : analysis.kind === 'pivot_feature' ? 'border-violet-400/30 bg-violet-400/10 text-violet-200'
        : 'border-emerald-400/30 bg-emerald-400/10 text-emerald-200'
  return (
    <div className={`rounded-xl border px-2.5 py-1.5 text-[11px] ${tone}`}>
      <span className="font-semibold">Mode: {label}</span>
      {analysis.pivotReason && <span className="ml-1 opacity-80">- {analysis.pivotReason.slice(0, 80)}</span>}
    </div>
  )
}

export function CodeSavedProjectPanel({
  savedProjectPath,
  saveFeedback,
  saveTarget,
  onSave,
}: {
  savedProjectPath: string | null
  saveFeedback: string | null
  saveTarget: 'workspace' | 'zip' | null
  onSave: (target: 'workspace' | 'zip') => Promise<void>
}) {
  return (
    <div className="rounded-[1.5rem] border border-aurora-accent/25 bg-aurora-accent/8 p-4 space-y-3">
      <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.2em] text-aurora-accent-light"><Archive size={13} /><span>Export persistant</span></div>
      <p className="text-xs leading-relaxed text-aurora-text-muted">Les boutons restent disponibles meme si tu as ferme la popup finale. Le projet exporte inclut aussi `start.sh` quand un demarrage automatique est possible sur Linux/macOS.</p>
      <div className="grid grid-cols-2 gap-2">
        <SaveButton target="workspace" activeTarget={saveTarget} onSave={onSave} />
        <SaveButton target="zip" activeTarget={saveTarget} onSave={onSave} />
      </div>
      {savedProjectPath && <p className="text-[11px] leading-relaxed text-aurora-text-dim break-all">Derniere sauvegarde: {savedProjectPath}</p>}
      {saveFeedback && <p className="text-[11px] leading-relaxed text-aurora-red break-all">{saveFeedback}</p>}
    </div>
  )
}

function SaveButton({ target, activeTarget, onSave }: { target: 'workspace' | 'zip'; activeTarget: 'workspace' | 'zip' | null; onSave: (target: 'workspace' | 'zip') => Promise<void> }) {
  const pending = activeTarget === target
  const Icon = target === 'workspace' ? FolderOpen : Archive
  return (
    <button onClick={() => void onSave(target)} disabled={activeTarget !== null} className="inline-flex items-center justify-center gap-2 rounded-2xl border border-aurora-border/35 bg-aurora-surface/70 px-3 py-3 text-sm text-aurora-text transition-colors hover:border-aurora-accent/35 disabled:cursor-not-allowed disabled:opacity-60">
      {pending ? <Loader2 size={15} className="animate-spin" /> : <Icon size={15} />}
      <span>{target === 'workspace' ? 'Workspace' : 'ZIP'}</span>
    </button>
  )
}
