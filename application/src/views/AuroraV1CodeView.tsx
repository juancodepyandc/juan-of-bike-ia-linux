/**
 * AuroraV1CodeView — Editorial diff entry for the Code module.
 *
 * Visual chrome from _design/aurora_design_screens_v1/modules.jsx
 * (CodeScreen): three columns — file tree on the left with active model
 * panel below, "before" code pane in the centre, "after · streaming"
 * pane on the right with diff hunks (red insertion / green
 * application), bottom Accepter ⌘↵ / Réviser / Annuler bar.
 *
 * Real wiring: CodeView (2398 LOC of intent classification, architecture
 * planning, sandbox execution loop, dev-server preview, 22-language
 * support, design tokens, R3F + GLSL playground, Aurora-Connect
 * extension lookup) lazy-mounts as soon as the user clicks "Ouvrir
 * l'orchestrateur" — full feature parity guaranteed.
 */
import { useEffect, useMemo, useRef, useState } from 'react'
import { useCodeViewLogic } from '../hooks/useCodeViewLogic.ts'
import { useModuleStreak } from '../hooks/useModuleStreak.ts'
import { useFileDrop } from '../hooks/useFileDrop.ts'
import { extractGeneratedFiles, extractWebPreview, type ParsedFile } from '../services/codeOutputFiles.ts'
import { intelligentlyElevateFiles } from '../services/codeOutputIntelligent.ts'
import { useCodeStreamStore } from '../stores/codeStreamStore.ts'
import { downloadProjectZip } from '../utils/codeDownload.ts'
import { useModuleHistoryStore } from '../stores/moduleHistoryStore.ts'
import { AuroraV1CodeLiveView } from './auroraV1CodeLiveView.tsx'
import {
  AuroraV1CodeConfirmModal,
  AuroraV1CodeDropHint,
  AuroraV1CodeErrorDialog,
  AuroraV1CodePipelineBanner,
} from './auroraV1CodeOverlays.tsx'
import { AuroraV1CodeOutputPane } from './auroraV1CodeOutputPane.tsx'
import { AuroraV1CodePreviewPane } from './auroraV1CodePreviewPane.tsx'
import { AuroraV1CodeSidebar } from './auroraV1CodeSidebar.tsx'

export default function AuroraV1CodeView() {
  const [live, setLive] = useState(false)
  const code = useCodeViewLogic()
  const activeCodeSessionId = useModuleHistoryStore((s) => s.activeSessionId.code ?? null)
  const createCodeSession = useModuleHistoryStore((s) => s.createSession)
  const codeStreak = useModuleStreak('code')
  // v82n8 : detect "completed while away" — store has lastCompletedAt,
  // we remember our own last-seen value when this view mounts. If the
  // store's lastCompletedAt advances past it while we're alive, no
  // banner needed (the user is here). If we mount and the store's
  // lastCompletedAt > our last-seen, AND we have streamOutput, show a
  // small "généré pendant ton absence" banner that auto-dismisses.
  const lastCompletedAt = useCodeStreamStore((s) => s.lastCompletedAt)
  const runId = useCodeStreamStore((s) => s.runId)
  const errorDialog = useCodeStreamStore((s) => s.errorDialog)
  const dismissErrorDialog = useCodeStreamStore((s) => s.dismissErrorDialog)
  const retryAfterError = useCodeStreamStore((s) => s.retryAfterError)
  // v82nd : detect installed code editor at mount so the button label
  // says e.g. "Ouvrir dans VSCode" or "Ouvrir dans Cursor".
  const [editorName, setEditorName] = useState<string>('VSCode')
  const [openingFolder, setOpeningFolder] = useState(false)
  useEffect(() => {
    if (activeCodeSessionId) {
      code.activateSession(activeCodeSessionId)
      return
    }
    const created = createCodeSession('code')
    code.activateSession(created)
  }, [activeCodeSessionId, code.activateSession, createCodeSession])

  useEffect(() => {
    let cancelled = false
    void (async () => {
      try {
        const bridge = (await import('../utils/runtime')).getBridgeUrl()
        const r = await fetch(`${bridge}/api/code/detect-editor`, {
          signal: AbortSignal.timeout(3000),
        })
        if (!r.ok) return
        const j = await r.json() as { ok?: boolean; editor?: { name?: string } }
        if (!cancelled && j?.ok && j.editor?.name) setEditorName(j.editor.name)
      } catch { /* keep default */ }
    })()
    return () => { cancelled = true }
  }, [])
  const handleOpenInEditor = async () => {
    if (parsedFiles.length === 0 || openingFolder) return
    setOpeningFolder(true)
    try {
      const bridge = (await import('../utils/runtime')).getBridgeUrl()
      const r = await fetch(`${bridge}/api/code/open-folder`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          files: parsedFiles.map((f) => ({ path: f.path, content: f.content })),
          project_name: `aurora-${Date.now().toString(36)}`,
        }),
        signal: AbortSignal.timeout(8000),
      })
      const j = await r.json() as { ok?: boolean; project_dir?: string; editor?: { name?: string }; error?: string }
      if (!j?.ok) {
        // Surface as a small inline alert (use the existing error
        // dialog plumbing for consistency).
        useCodeStreamStore.setState({
          errorDialog: {
            title: `Impossible d'ouvrir dans ${editorName}`,
            message: j?.error || 'Échec inconnu lors de l\'ouverture du dossier.',
            suggestion: `Vérifie que ${editorName} est dans le PATH (commande "code" / "cursor"). Sinon le dossier est quand même écrit sur le disque.`,
          },
        })
      }
    } catch (e) {
      useCodeStreamStore.setState({
        errorDialog: {
          title: 'Bridge non joignable',
          message: e instanceof Error ? e.message : String(e),
          suggestion: 'Relance Aurora puis réessaie.',
        },
      })
    } finally {
      setOpeningFolder(false)
    }
  }
  // v85 : ZIP export of the whole project (keeps "télécharger comme
  // actuellement" but bundles the full tree, not one file at a time).
  const [downloadingZip, setDownloadingZip] = useState(false)
  // v85f : preview-before-accept — download / repo-write open a confirm modal
  // (rendered preview + file list) instead of acting immediately.
  const [confirmAction, setConfirmAction] = useState<null | 'download' | 'repo'>(null)
  const handleDownloadZip = async () => {
    if (code.files.length === 0 || downloadingZip) return
    setDownloadingZip(true)
    try {
      await downloadProjectZip(code.files, code.repoLabel || code.draft || 'aurora-projet')
    } finally {
      setDownloadingZip(false)
    }
  }
  // v85 : local mirror of the repo path so the user can type/paste it.
  const [repoPathInput, setRepoPathInput] = useState('')
  useEffect(() => { setRepoPathInput(code.repoPath ?? '') }, [code.repoPath])
  // v85e : live elapsed-time ticker for the current task (1s cadence while
  // streaming) — gives a real-time chrono next to the ETA.
  const [nowTick, setNowTick] = useState(() => Date.now())
  useEffect(() => {
    if (!code.streaming) return
    setNowTick(Date.now())
    const id = window.setInterval(() => setNowTick(Date.now()), 1000)
    return () => window.clearInterval(id)
  }, [code.streaming])
  const elapsedSec = code.streaming && code.genStartedAt ? Math.max(0, (nowTick - code.genStartedAt) / 1000) : null
  const lastSeenCompletedRef = useRef<number | null>(null)
  const lastSeenRunRef = useRef<number>(0)
  const [completedWhileAwayAt, setCompletedWhileAwayAt] = useState<number | null>(null)
  useEffect(() => {
    // First mount in this session : capture the current values, no banner.
    if (lastSeenCompletedRef.current === null) {
      lastSeenCompletedRef.current = lastCompletedAt
      lastSeenRunRef.current = runId
      return
    }
    // Subsequent re-mounts : if completion advanced AND it's the same
    // run we kicked off (or a new completed run), surface the banner.
    if (
      lastCompletedAt !== null
      && lastCompletedAt !== lastSeenCompletedRef.current
      && !code.streaming
    ) {
      setCompletedWhileAwayAt(lastCompletedAt)
      lastSeenCompletedRef.current = lastCompletedAt
      lastSeenRunRef.current = runId
      const t = window.setTimeout(() => setCompletedWhileAwayAt(null), 6000)
      return () => window.clearTimeout(t)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lastCompletedAt, runId])
  // v82n6 : real multi-file parsing. While streaming, every render
  // re-parses streamOutput so the user sees files appear progressively
  // in the left tree as fenced blocks land. Cheap (single string scan,
  // no DOM thrash beyond the tree).
  const parsedFiles = useMemo<ParsedFile[]>(() => {
    // v85 : the orchestrator now returns a STRUCTURED, validated, merged
    // file tree (code.files). Prefer it whenever we're not actively
    // streaming — it's the real project state (and survives navigation).
    // While tokens are still arriving we live-parse the stream so files
    // appear progressively in the tree.
    if (!code.streaming && code.files.length > 0) {
      return code.files.map((f) => ({ path: f.name, content: f.content, language: f.language }))
    }
    if (!code.streamOutput || code.streamOutput.length === 0) {
      return code.files.map((f) => ({ path: f.name, content: f.content, language: f.language }))
    }
    const raw = extractGeneratedFiles(code.streamOutput)
    // v82ni/v82nk : intelligent elevation via DOMParser. Passes the
    // user's prompt as a context fallback for image queries AND the
    // brand primary color (when brand-enrich detected one) so the
    // page is recolored to the brand's palette instead of the LLM's
    // training-default Tailwind violet/green.
    if (!code.streaming) {
      return intelligentlyElevateFiles(raw, code.draft, code.brandPrimary || '').files
    }
    return raw
  }, [code.streamOutput, code.streaming, code.draft, code.brandPrimary, code.files])
  const [activeFileIdx, setActiveFileIdx] = useState(0)
  // Auto-follow: when a new file appears, jump the cursor to it so the
  // user always sees the latest. If user manually clicked one earlier,
  // we keep their choice (clamp to bounds when files shrink/grow).
  const userPickedRef = useRef(false)
  useEffect(() => {
    if (parsedFiles.length === 0) {
      setActiveFileIdx(0)
      userPickedRef.current = false
      return
    }
    if (!userPickedRef.current) {
      setActiveFileIdx(parsedFiles.length - 1)
    } else {
      setActiveFileIdx((idx) => Math.min(idx, parsedFiles.length - 1))
    }
  }, [parsedFiles.length])
  const activeFile: ParsedFile | null = parsedFiles[activeFileIdx] ?? null
  // v82n6 : detect a runnable web preview (index.html or full <html>)
  // so the centre pane can show an iframe instead of the static BEFORE
  // demo. Only runs when stream completes (heavy regex) — during stream,
  // we keep the live code view to avoid reflow on every token.
  const webPreview = useMemo(
    () => (code.hasOutput && !code.streaming ? extractWebPreview(parsedFiles) : null),
    [code.hasOutput, code.streaming, parsedFiles],
  )
  // v82ir : tokens/s rolling window 3s pour speed indicator pendant stream.
  // v82it : tpsHistory cap 30 samples pour sparkline mini.
  // v82iv : finalStats persistant après le stream pour récap UX.
  const [tokensPerSec, setTokensPerSec] = useState<number | null>(null)
  const [tpsHistory, setTpsHistory] = useState<number[]>([])
  const [finalStats, setFinalStats] = useState<{
    avg: number; max: number; tokens: number; durationSec: number
  } | null>(null)
  const speedSamplesRef = useRef<Array<{ ts: number; len: number }>>([])
  const streamStartRef = useRef<number | null>(null)
  useEffect(() => {
    if (!code.streaming) {
      // v82iv : freeze final stats si on a un history non-vide avant reset.
      if (tpsHistory.length > 0 && streamStartRef.current !== null) {
        const avg = tpsHistory.reduce((a, b) => a + b, 0) / tpsHistory.length
        const max = Math.max(...tpsHistory)
        const tokens = Math.ceil(code.streamOutput.length / 4)
        const durationSec = (Date.now() - streamStartRef.current) / 1000
        setFinalStats({ avg, max, tokens, durationSec })
      }
      speedSamplesRef.current = []
      streamStartRef.current = null
      setTokensPerSec(null)
      setTpsHistory([])
      return
    }
    if (streamStartRef.current === null) {
      streamStartRef.current = Date.now()
      setFinalStats(null) // clear ancien recap au début du nouveau stream
    }
    const now = Date.now()
    const len = code.streamOutput.length
    speedSamplesRef.current.push({ ts: now, len })
    const cutoff = now - 3000
    speedSamplesRef.current = speedSamplesRef.current.filter((s) => s.ts >= cutoff)
    if (speedSamplesRef.current.length >= 2) {
      const first = speedSamplesRef.current[0]
      const last = speedSamplesRef.current[speedSamplesRef.current.length - 1]
      const dtSec = (last.ts - first.ts) / 1000
      const dCh = last.len - first.len
      if (dtSec > 0.2) {
        const tps = (dCh / 4) / dtSec
        setTokensPerSec(tps)
        setTpsHistory((h) => [...h, tps].slice(-30))
      }
    }
  }, [code.streamOutput, code.streaming])
  // v82fm : drop zone Code → injecte le contenu lu dans le prompt
  // courant (code.draft) entouré d'un fence. L'utilisateur tape ensuite
  // sa demande et envoie. Supporte text/PDF/DOCX (lazy via readTextFile).
  const drop = useFileDrop({
    onFiles: async (files) => {
      const { readTextFile } = await import('../utils/textFileExtract')
      const sections: string[] = []
      for (const f of files) {
        try {
          const text = await readTextFile(f)
          // Détection langue rapide pour fence
          const lang = (() => {
            const lower = f.name.toLowerCase()
            if (/\.tsx?$/.test(lower)) return 'typescript'
            if (/\.jsx?$/.test(lower)) return 'javascript'
            if (/\.py$/.test(lower)) return 'python'
            if (/\.rs$/.test(lower)) return 'rust'
            if (/\.go$/.test(lower)) return 'go'
            if (/\.java$/.test(lower)) return 'java'
            if (/\.cpp$|\.cc$|\.cxx$/.test(lower)) return 'cpp'
            if (/\.cs$/.test(lower)) return 'csharp'
            if (/\.rb$/.test(lower)) return 'ruby'
            if (/\.php$/.test(lower)) return 'php'
            if (/\.swift$/.test(lower)) return 'swift'
            if (/\.kt$/.test(lower)) return 'kotlin'
            if (/\.css$/.test(lower)) return 'css'
            if (/\.html?$/.test(lower)) return 'html'
            if (/\.sql$/.test(lower)) return 'sql'
            if (/\.json$/.test(lower)) return 'json'
            if (/\.ya?ml$/.test(lower)) return 'yaml'
            if (/\.md$/.test(lower)) return 'markdown'
            return ''
          })()
          // Clamp 30KB par fichier pour ne pas saturer le prompt
          const clamped = text.length > 30000
            ? text.slice(0, 30000) + '\n// ... [tronqué à 30KB] ...'
            : text
          sections.push(`### ${f.name}\n\`\`\`${lang}\n${clamped}\n\`\`\``)
        } catch {
          sections.push(`### ${f.name}\n(lecture impossible)`)
        }
      }
      const inject = sections.join('\n\n')
      code.setDraft(`${inject}\n\n${code.draft}`)
    },
    accept: ['txt', 'md', 'markdown', 'json', 'csv', 'log', 'py', 'js', 'ts', 'tsx', 'jsx', 'rs', 'go', 'java', 'cpp', 'cs', 'rb', 'php', 'swift', 'kt', 'html', 'css', 'sh', 'tex', 'xml', 'yaml', 'yml', 'sql', 'pdf', 'docx'],
    acceptMime: ['text/', 'application/pdf', 'application/json', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'],
    disabled: code.streaming,
  })

  // v82k7 : salle de code editorial native — no manga delegate.
  if (live) {
    return <AuroraV1CodeLiveView code={code} onClose={() => setLive(false)} />
  }

  return (
    <div {...drop.bind} className="aurora-v1-cols" style={{
      height: '100%', display: 'grid',
      gridTemplateColumns: '260px 1fr 1fr',
      // v82n9 : explicit single-row cap = viewport height. Without this
      // the grid implicit-row was content-sized so right column grew
      // beyond viewport, hiding the prompt input under overflow:hidden.
      gridTemplateRows: '1fr',
      background: 'var(--bg, #0c0a09)', color: 'var(--fg, #f5f5f5)',
      fontFamily: 'var(--font-sans, system-ui)', overflow: 'hidden',
      position: 'relative',
      outline: drop.isDraggingOver ? '2px dashed oklch(0.74 0.13 60)' : 'none',
      outlineOffset: drop.isDraggingOver ? '-6px' : '0',
      transition: 'outline 120ms ease',
    }}>
      <AuroraV1CodeErrorDialog
        dismissErrorDialog={dismissErrorDialog}
        errorDialog={errorDialog}
        retryAfterError={retryAfterError}
      />
      <AuroraV1CodeConfirmModal
        code={code}
        confirmAction={confirmAction}
        handleDownloadZip={handleDownloadZip}
        setConfirmAction={setConfirmAction}
        webPreview={webPreview}
      />
      <AuroraV1CodePipelineBanner
        code={code}
        completedWhileAwayAt={completedWhileAwayAt}
        elapsedSec={elapsedSec}
      />
      <AuroraV1CodeDropHint visible={drop.isDraggingOver} />
      <AuroraV1CodeSidebar
        activeFileIdx={activeFileIdx}
        code={code}
        downloadingZip={downloadingZip}
        parsedFiles={parsedFiles}
        repoPathInput={repoPathInput}
        setActiveFileIdx={setActiveFileIdx}
        setConfirmAction={setConfirmAction}
        setLive={setLive}
        setRepoPathInput={setRepoPathInput}
        userPickedRef={userPickedRef}
      />
      <AuroraV1CodePreviewPane
        activeFile={activeFile}
        code={code}
        parsedFiles={parsedFiles}
        webPreview={webPreview}
      />
      <AuroraV1CodeOutputPane
        code={code}
        codeStreak={codeStreak}
        editorName={editorName}
        finalStats={finalStats}
        handleOpenInEditor={handleOpenInEditor}
        live={live}
        openingFolder={openingFolder}
        parsedFiles={parsedFiles}
        setLive={setLive}
        tokensPerSec={tokensPerSec}
        tpsHistory={tpsHistory}
      />
    </div>
  )
}
