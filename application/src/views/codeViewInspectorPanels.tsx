import { useEffect, useMemo, useRef, useState } from 'react'
import LyraCharacter from '../components/voice/LyraCharacter.tsx'
import { analyzeCyclomaticComplexity, computeHalstead } from '../services/codeStructuralAnalysis.ts'
import { detectFileLanguage } from './codeViewLanguage.ts'

// ---------------------------------------------------------------------------
// Code console panel — small left-side panel that replaces the old mini
// preview. Shows tokens-as-they-stream, sandbox output, errors, recovery and
// progress. The HTML render lives in the BIG viewer on the right.
// ---------------------------------------------------------------------------

type StepEntry = {
  ts: number
  message: string
  kind: 'info' | 'recover' | 'error' | 'success'
}

export function CodeConsolePanel({
  consoleOutput,
  streamContent,
  isGenerating,
  recoveryStatus,
  progress,
  errorMessage,
  sandboxOk,
}: {
  consoleOutput: string
  streamContent: string
  isGenerating: boolean
  recoveryStatus: string | null
  progress: string
  errorMessage: string | null
  sandboxOk: boolean | null
}) {
  const [tab, setTab] = useState<'etapes' | 'sandbox' | 'erreurs'>('etapes')
  const [steps, setSteps] = useState<StepEntry[]>([])
  const logRef = useRef<HTMLPreElement>(null)
  const stepsRef = useRef<HTMLDivElement>(null)

  // Pipeline step journal — dedup consecutive duplicates, cap to last 60 entries.
  useEffect(() => {
    if (!progress) return
    setSteps((prev) => {
      const last = prev[prev.length - 1]
      if (last && last.message === progress) return prev
      const kind: StepEntry['kind'] = 'info'
      const next = [...prev, { ts: Date.now(), message: progress, kind }]
      return next.slice(-60)
    })
  }, [progress])

  useEffect(() => {
    if (!recoveryStatus) return
    setSteps((prev) => {
      const last = prev[prev.length - 1]
      if (last && last.message === recoveryStatus) return prev
      const entry: StepEntry = { ts: Date.now(), message: recoveryStatus, kind: 'recover' }
      return [...prev, entry].slice(-60)
    })
  }, [recoveryStatus])

  useEffect(() => {
    if (!errorMessage) return
    setSteps((prev) => {
      const entry: StepEntry = { ts: Date.now(), message: errorMessage, kind: 'error' }
      return [...prev, entry].slice(-60)
    })
    setTab('erreurs')
  }, [errorMessage])

  useEffect(() => {
    if (sandboxOk === true) {
      setSteps((prev) => {
        const entry: StepEntry = { ts: Date.now(), message: 'Sandbox: validation reussie.', kind: 'success' }
        return [...prev, entry].slice(-60)
      })
    }
  }, [sandboxOk])

  // Reset journal each time a new generation starts from an idle state.
  const prevGenerating = useRef(false)
  useEffect(() => {
    if (isGenerating && !prevGenerating.current) setSteps([])
    prevGenerating.current = isGenerating
  }, [isGenerating])

  useEffect(() => {
    if (tab === 'etapes' && stepsRef.current) stepsRef.current.scrollTop = stepsRef.current.scrollHeight
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
  }, [steps, consoleOutput, errorMessage, tab])

  const sandboxTail = consoleOutput.length > 40_000
    ? `${consoleOutput.slice(0, 10_000)}\n...[tronque]...\n${consoleOutput.slice(-20_000)}`
    : consoleOutput

  const pillColor = errorMessage
    ? 'bg-aurora-red/20 text-aurora-red'
    : sandboxOk === true
      ? 'bg-aurora-green/20 text-aurora-green'
      : isGenerating
        ? 'bg-aurora-accent/20 text-aurora-accent-light'
        : 'bg-aurora-surface-2/60 text-aurora-text-dim'

  const hasError = Boolean(errorMessage)
  // The big viewer already shows the token stream as it is written (mode Code),
  // so the console intentionally does NOT duplicate that firehose of characters.
  // It shows WHAT the orchestrator is doing, WHY it might be slow, and WHERE it failed.
  const tokenHint = streamContent.length > 0
    ? `${Math.round(streamContent.length / 100) / 10}k chars dans le stream — voir le code en direct dans l onglet Code du grand viewer.`
    : ''

  return (
    <div className="rounded-[1.6rem] border border-aurora-border/35 bg-[#0d1117] overflow-hidden flex flex-col min-h-[18rem]">
      <div className="flex items-center justify-between border-b border-white/10 px-3 py-2">
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.2em] text-aurora-text-dim">
          <span className={`inline-block h-1.5 w-1.5 rounded-full ${isGenerating ? 'bg-aurora-accent animate-pulse' : hasError ? 'bg-aurora-red' : sandboxOk ? 'bg-aurora-green' : 'bg-aurora-text-dim'}`} />
          <span>Journal</span>
        </div>
        <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${pillColor}`}>
          {hasError ? 'ERR' : sandboxOk === true ? 'OK' : isGenerating ? 'LIVE' : 'IDLE'}
        </span>
      </div>

      <div className="flex items-center gap-1 border-b border-white/10 bg-[#0a0f14] px-2 py-1.5">
        {(['etapes', 'sandbox', 'erreurs'] as const).map((key) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`rounded-md px-2 py-1 text-[10px] uppercase tracking-wider transition-colors ${
              tab === key
                ? 'bg-aurora-accent/20 text-aurora-accent-light'
                : 'text-aurora-text-dim hover:text-aurora-text'
            }`}
          >
            {key === 'etapes' ? 'Etapes' : key === 'sandbox' ? 'Sandbox' : 'Erreurs'}
            {key === 'erreurs' && hasError && (
              <span className="ml-1 inline-block h-1.5 w-1.5 rounded-full bg-aurora-red" />
            )}
          </button>
        ))}
      </div>

      {tab === 'etapes' && (
        <div ref={stepsRef} className="flex-1 overflow-auto px-2 py-2 text-[10.5px] leading-[1.5] max-h-[26rem] space-y-1">
          {steps.length === 0 && (
            <div className="px-2 py-4 text-aurora-text-dim">
              {isGenerating ? 'Demarrage du pipeline...' : 'Lance une generation pour voir les etapes du pipeline ici.'}
            </div>
          )}
          {steps.map((entry, i) => {
            const color = entry.kind === 'error'
              ? 'border-aurora-red/30 bg-aurora-red/10 text-aurora-red'
              : entry.kind === 'recover'
                ? 'border-aurora-yellow/30 bg-aurora-yellow/10 text-aurora-yellow'
                : entry.kind === 'success'
                  ? 'border-aurora-green/30 bg-aurora-green/10 text-aurora-green'
                  : 'border-aurora-border/30 bg-aurora-surface-2/40 text-aurora-text'
            const time = new Date(entry.ts).toLocaleTimeString('fr-FR', { hour12: false })
            return (
              <div key={i} className={`rounded-lg border px-2 py-1 ${color}`}>
                <div className="flex items-start gap-2">
                  <span className="shrink-0 text-[9px] opacity-60 mt-0.5">{time}</span>
                  <span className="flex-1 break-words">{entry.message}</span>
                </div>
              </div>
            )
          })}
          {tokenHint && (
            <div className="px-2 pt-2 text-[9.5px] text-aurora-text-dim italic">{tokenHint}</div>
          )}
        </div>
      )}

      {tab === 'sandbox' && (
        <pre
          ref={logRef}
          className="flex-1 overflow-auto px-3 py-2 text-[10.5px] leading-[1.45] text-gray-200 whitespace-pre-wrap break-words font-mono max-h-[26rem]"
        >
          {sandboxTail || 'Aucune sortie sandbox pour le moment.'}
        </pre>
      )}

      {tab === 'erreurs' && (
        <pre
          ref={logRef}
          className="flex-1 overflow-auto px-3 py-2 text-[10.5px] leading-[1.45] text-aurora-red whitespace-pre-wrap break-words font-mono max-h-[26rem]"
        >
          {errorMessage || 'Aucune erreur pour le moment.'}
        </pre>
      )}

      {(progress || recoveryStatus) && (
        <div className="border-t border-white/10 px-3 py-1.5 text-[10px] text-aurora-text-dim truncate">
          {recoveryStatus ? `↺ ${recoveryStatus}` : progress}
        </div>
      )}
    </div>
  )
}

// v83i — Panneau de critique statique temps-réel sur le fichier actif.
// Affiche : complexité cyclomatique par fonction + Halstead + verdict global.
export function CodeCritiquePanel({ content, language }: { content: string; language: string }) {
  const complexity = useMemo(() => analyzeCyclomaticComplexity(content, language), [content, language])
  const halstead = useMemo(() => computeHalstead(content, language), [content, language])
  const lines = content.split(/\r?\n/).length
  const worst = complexity.reduce((max, fn) => (fn.cyclomaticComplexity > max ? fn.cyclomaticComplexity : max), 0)
  const avg = complexity.length
    ? Math.round((complexity.reduce((s, fn) => s + fn.cyclomaticComplexity, 0) / complexity.length) * 10) / 10
    : 0
  const verdict =
    worst >= 20 ? { tone: 'rose', label: 'À refactorer', detail: 'Une fonction dépasse 20 (ingérable).' }
    : worst >= 11 ? { tone: 'amber', label: 'Complexe', detail: 'Au moins une fonction très complexe (>10).' }
    : worst >= 6 ? { tone: 'sky', label: 'Modéré', detail: 'Tout reste sous contrôle.' }
    : complexity.length === 0 ? { tone: 'slate', label: '—', detail: 'Aucune fonction détectée.' }
    : { tone: 'emerald', label: 'Propre', detail: 'Branches peu nombreuses, lisible.' }
  const toneCls: Record<string, string> = {
    rose: 'bg-rose-500/15 text-rose-200 border-rose-500/30',
    amber: 'bg-amber-500/15 text-amber-200 border-amber-500/30',
    sky: 'bg-sky-500/15 text-sky-200 border-sky-500/30',
    emerald: 'bg-emerald-500/15 text-emerald-200 border-emerald-500/30',
    slate: 'bg-white/5 text-aurora-text-dim border-white/10',
  }
  return (
    <div className="rounded-[1.6rem] border border-aurora-border/35 bg-aurora-surface/65 p-3 text-[11px]">
      <div className="flex items-center justify-between mb-2">
        <span className="uppercase tracking-[0.2em] text-aurora-text-dim">Critique statique</span>
        <span className={`rounded-md border px-2 py-0.5 text-[10px] font-mono ${toneCls[verdict.tone]}`}>{verdict.label}</span>
      </div>
      <div className="grid grid-cols-2 gap-1.5 mb-2">
        <Mini label="Lignes" value={String(lines)} />
        <Mini label="Fonctions" value={String(complexity.length)} />
        <Mini label="Pire McCabe" value={worst > 0 ? String(worst) : '—'} />
        <Mini label="Moy McCabe" value={complexity.length > 0 ? String(avg) : '—'} />
        <Mini label="Halstead vol" value={Math.round(halstead.volume).toString()} />
        <Mini label="Bugs prédits" value={halstead.predictedBugs.toFixed(2)} />
      </div>
      <p className="text-[10px] text-aurora-text-dim italic">{verdict.detail}</p>
      {complexity.length > 0 && worst >= 6 && (
        <div className="mt-2 space-y-1 max-h-32 overflow-auto">
          {complexity
            .filter((fn) => fn.cyclomaticComplexity >= 6)
            .sort((a, b) => b.cyclomaticComplexity - a.cyclomaticComplexity)
            .slice(0, 5)
            .map((fn, i) => (
              <div key={i} className="flex items-center justify-between rounded-md bg-black/30 px-2 py-1 text-[10px] font-mono">
                <span className="text-aurora-text/85 truncate">{fn.name}</span>
                <span className={`shrink-0 ml-2 px-1.5 rounded ${fn.cyclomaticComplexity >= 20 ? 'bg-rose-500/30 text-rose-200' : fn.cyclomaticComplexity >= 11 ? 'bg-amber-500/30 text-amber-200' : 'bg-sky-500/30 text-sky-200'}`}>
                  {fn.cyclomaticComplexity}
                </span>
              </div>
            ))}
        </div>
      )}
    </div>
  )
}

function Mini({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-black/30 border border-white/5 px-2 py-1">
      <div className="text-[9px] uppercase tracking-wider text-aurora-text-dim">{label}</div>
      <div className="text-[12px] font-mono text-aurora-text">{value}</div>
    </div>
  )
}

// v84k — Lyra commentator pour Code : réagit à la qualité du fichier actif.
export function CodeLyraCommentator({
  content,
  language,
  isGenerating,
}: { content: string; language: string; isGenerating: boolean }) {
  const complexity = useMemo(() => analyzeCyclomaticComplexity(content, language), [content, language])
  const worst = complexity.reduce((m, fn) => (fn.cyclomaticComplexity > m ? fn.cyclomaticComplexity : m), 0)
  const emotion: 'focus' | 'happy' | 'sad' | 'curious' = isGenerating
    ? 'focus'
    : worst >= 15
      ? 'sad'
      : worst >= 6
        ? 'curious'
        : 'happy'
  const verdict =
    isGenerating ? 'je code…'
    : worst >= 20 ? 'à refactor sérieusement'
    : worst >= 11 ? 'ça commence à être touffu'
    : worst >= 6 ? 'lisible mais surveille'
    : complexity.length === 0 ? 'rien à analyser'
    : 'propre, bravo'
  return (
    <div className="flex items-center gap-3 rounded-[1.6rem] border border-aurora-border/35 bg-aurora-surface/65 p-3">
      <div style={{ width: 48, height: 60, flexShrink: 0 }}>
        <LyraCharacter
          phase={isGenerating ? 'thinking' : 'idle'}
          emotion={emotion}
          accent="#67d2ff"
          size={48}
        />
      </div>
      <div className="text-[11px] text-aurora-text-dim">
        <div className="font-mono uppercase tracking-wider text-aurora-text">{verdict}</div>
        {worst > 0 && <div className="mt-0.5">McCabe max : {worst}</div>}
      </div>
    </div>
  )
}

// v83t — Chip de détection de langage du fichier actif.
// Detection : extension fichier + heuristiques signatures (shebang, imports).
export function CodeLanguageChip({
  fileName,
  declaredLang,
  content,
}: {
  fileName: string
  declaredLang?: string
  content: string
}) {
  const detected = useMemo(() => detectFileLanguage(fileName, content), [fileName, content])
  const lang = declaredLang || detected.lang
  const conf = declaredLang ? 1 : detected.confidence
  const TYPED_LANGS = new Set(['ts', 'tsx', 'typescript', 'rust', 'go', 'kotlin', 'swift', 'scala', 'c', 'cpp', 'csharp', 'java'])
  const isTyped = TYPED_LANGS.has(lang.toLowerCase())
  const sizeKb = (new Blob([content]).size / 1024)
  return (
    <div className="rounded-[1.6rem] border border-aurora-border/35 bg-aurora-surface/65 p-3 text-[11px]">
      <div className="flex items-center justify-between mb-2">
        <span className="uppercase tracking-[0.2em] text-aurora-text-dim">Fichier</span>
        <span className="font-mono text-aurora-text-dim">{sizeKb.toFixed(1)} KB</span>
      </div>
      <div className="flex flex-wrap gap-1.5">
        <span className="rounded-md border border-aurora-accent/40 bg-aurora-accent/15 px-2 py-0.5 text-[10px] font-mono text-aurora-accent-light">
          {lang}
        </span>
        <span className="rounded-md border border-white/10 bg-white/[0.03] px-2 py-0.5 text-[10px] font-mono text-aurora-text-dim">
          {isTyped ? 'typé' : 'dynamique'}
        </span>
        <span className="rounded-md border border-white/10 bg-white/[0.03] px-2 py-0.5 text-[10px] font-mono text-aurora-text-dim">
          {Math.round(conf * 100)}% conf
        </span>
        {detected.shebang && (
          <span className="rounded-md border border-emerald-500/30 bg-emerald-500/15 px-2 py-0.5 text-[10px] font-mono text-emerald-200">
            shebang
          </span>
        )}
      </div>
    </div>
  )
}
