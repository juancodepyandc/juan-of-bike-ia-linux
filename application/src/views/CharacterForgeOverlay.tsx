/**
 * Character Forge — overlay plein écran rendu DANS la VoiceCopilot.
 * - Saisie du prompt
 * - Lancement de la pipeline 8 étapes via `runForgePipeline`
 * - Affichage live des étapes + détail
 * - À la fin: preview du portrait + « Enregistrer dans la galerie »
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Check, CircleDashed, Loader2, Play, Save, Sparkles, X } from 'lucide-react'
import { useAppStore } from '../stores/appStore.ts'
import type { AvatarEntry } from '../types/app.ts'
import {
  FORGE_STEPS,
  type ForgeResult,
  type ForgeStep,
  type ForgeStepId,
  type ForgeStepStatus,
  type RigPlan,
  runForgePipeline,
} from '../services/characterForge.ts'
import { useForgeQueueStore } from '../stores/forgeQueueStore.ts'
import { isBridgeReachable } from '../services/pythonJobClient.ts'
import RigEditor from '../components/RigEditor.tsx'
import RigPlayer from '../components/RigPlayer.tsx'

interface Props {
  open: boolean
  onClose: () => void
  onSaved?: (avatar: AvatarEntry) => void
  initialPrompt?: string
}

function initSteps(): ForgeStep[] {
  return FORGE_STEPS.map((s) => ({ ...s, status: 'pending' as ForgeStepStatus }))
}

function StatusIcon({ status }: { status: ForgeStepStatus }) {
  if (status === 'running') return <Loader2 size={16} className="animate-spin" />
  if (status === 'done')    return <Check size={16} />
  if (status === 'skipped') return <CircleDashed size={16} />
  if (status === 'error')   return <X size={16} />
  return <CircleDashed size={16} className="opacity-40" />
}

export default function CharacterForgeOverlay({ open, onClose, onSaved, initialPrompt = '' }: Props) {
  const mainModel = useAppStore((s) => s.mainModel)
  const addAvatar = useAppStore((s) => s.addAvatar)
  const setSelectedAvatar = useAppStore((s) => s.setSelectedAvatar)

  const [prompt, setPrompt] = useState(initialPrompt)
  const [steps, setSteps] = useState<ForgeStep[]>(initSteps)
  const [running, setRunning] = useState(false)
  const [status, setStatus] = useState<string>('')
  const [pct, setPct] = useState<number>(0)
  const [result, setResult] = useState<ForgeResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const enqueueForge = useForgeQueueStore((s) => s.enqueue)
  const queueJobs = useForgeQueueStore((s) => s.jobs)
  const currentJobIdRef = useRef<string | null>(null)
  // The job this overlay is currently tracking (the most recent enqueued one)
  const trackedJob = queueJobs.find((j) => j.id === currentJobIdRef.current) || null

  useEffect(() => {
    if (!open) return
    const currentJobs = useForgeQueueStore.getState().jobs
    const activeJob = currentJobs.find((j) => j.status === 'running')
      || currentJobs.find((j) => j.status === 'queued')
      || currentJobs.find((j) => j.status === 'done' && !j.saved)
      // Also surface the most recent errored job so the user can see the
      // actual failure + hit "Lancer" again (the pipeline will resume from
      // whichever artifact it already has).
      || [...currentJobs].reverse().find((j) => j.status === 'error')
    if (activeJob) {
      currentJobIdRef.current = activeJob.id
      setPrompt(activeJob.prompt)
      // Reconstruct step ticks from the stored artifacts so progress is
      // visible even after a reload. Inlined (not using patchStep) to avoid
      // a TDZ hoisting error — this effect has to hit the state once and
      // only once when the overlay opens.
      const a = activeJob.artifacts || {}
      setSteps(FORGE_STEPS.map((def) => {
        const s: ForgeStep = { ...def, status: 'pending' }
        if (def.id === 'intent'    && a.meta)         { s.status = 'done'; s.detail = `↻ ${a.meta.display_name}` }
        if (def.id === 'traits'    && a.traits)       { s.status = 'done'; s.detail = '↻ traits' }
        if (def.id === 'rig_plan'  && a.rig)          { s.status = 'done'; s.detail = `↻ rig (${a.rig.layers.length} layers)` }
        if (def.id === 'reference' && a.portraitUrl)  { s.status = 'done'; s.detail = '↻ portrait' }
        if (def.id === 'segment'   && a.features !== undefined) { s.status = a.features ? 'done' : 'skipped'; s.detail = '↻' }
        if (def.id === 'assemble'  && a.layerFiles?.length) { s.status = 'done'; s.detail = `↻ ${a.layerFiles.length} layers` }
        return s
      }))
      if (activeJob.status === 'done' && activeJob.result) {
        setResult(activeJob.result)
        setPct(100)
        setStatus('Forge complète. À toi de valider.')
      } else if (activeJob.status === 'running') {
        setPct(activeJob.progressPct ?? 0)
        setStatus(activeJob.stepDetail ?? '')
      } else if (activeJob.status === 'error') {
        setStatus(activeJob.stepDetail ?? '')
      } else {
        setStatus('En attente dans la file…')
      }
      setError(activeJob.error ?? null)
      return
    }
    // No active job: fresh overlay
    setPrompt(initialPrompt)
    setResult(null)
    setError(null)
    setPct(0)
    setStatus('')
    setSteps(initSteps())
    currentJobIdRef.current = null
  }, [open, initialPrompt])

  const patchStep = useCallback((id: ForgeStepId, patch: Partial<ForgeStep>) => {
    setSteps((prev) => prev.map((s) => (s.id === id ? { ...s, ...patch } : s)))
  }, [])

  const runPipeline = useCallback(() => {
    const trimmed = prompt.trim()
    if (!trimmed) return
    // The queue handles concurrency — a second press just enqueues a new job.
    const id = enqueueForge(trimmed)
    currentJobIdRef.current = id
    setError(null)
    setResult(null)
    setSteps(initSteps())
    setPct(0)
    setStatus('Dans la file…')
    // Fire-and-forget UX: close the overlay so the user can navigate freely.
    // The queue keeps running in the background, the floating Forge pill
    // shows status, and a push notification announces the result.
    window.setTimeout(() => { onClose() }, 500)
  }, [prompt, enqueueForge, onClose])

  // Reflect the tracked job's live state back into this overlay so the user
  // sees the same pipeline visualization whether the job is running now or
  // was launched from a previous overlay session.
  useEffect(() => {
    if (!trackedJob) return
    if (trackedJob.status === 'running') {
      setRunning(true)
      if (typeof trackedJob.progressPct === 'number') setPct(trackedJob.progressPct)
      if (trackedJob.stepDetail) setStatus(trackedJob.stepDetail)
    } else if (trackedJob.status === 'queued') {
      setRunning(false)
      setStatus('En attente dans la file…')
    } else if (trackedJob.status === 'done') {
      setRunning(false)
      if (trackedJob.result) { setResult(trackedJob.result); setPct(100); setStatus('Forge complète. À toi de valider.') }
    } else if (trackedJob.status === 'error') {
      setRunning(false)
      setError(trackedJob.error || 'Erreur inconnue')
    }
  }, [trackedJob?.status, trackedJob?.progressPct, trackedJob?.stepDetail, trackedJob?.result, trackedJob?.error, trackedJob])

  const commitToGallery = useCallback(() => {
    if (!result) return
    const ts = Date.now()
    const pathPayload = JSON.stringify({
      imageSrc: result.portraitUrl,
      features: result.features,
      forge: {
        meta: result.meta,
        traits: result.traits,
        rig: result.rig,
        variations: result.variationUrls,
        layers: result.layerFiles,
        baseLayer: result.baseLayerUrl,
      },
    })
    const entry: AvatarEntry = {
      id: `forge-${ts}`,
      label: (result.meta.display_name || prompt).slice(0, 25),
      type: 'live2d-flux',
      path: pathPayload,
      thumbnail: result.portraitUrl,
      builtIn: false,
      createdAt: ts,
      animationMode: result.animationMode,
      researchBrief: result.researchBrief,
      howTheySpeak: result.howTheySpeak,
    }
    addAvatar(entry)
    setSelectedAvatar(entry.id)
    onSaved?.(entry)
    onClose()
  }, [result, prompt, addAvatar, setSelectedAvatar, onSaved, onClose])

  const cancelRun = useCallback(() => {
    abortRef.current?.abort()
    setRunning(false)
    setError('Annulé par l\'utilisateur')
  }, [])

  const stepSummary = useMemo(
    () => steps.filter((s) => s.status === 'done' || s.status === 'skipped').length,
    [steps],
  )

  const [regenLayerId, setRegenLayerId] = useState<string | null>(null)
  const [regenPrompt, setRegenPrompt] = useState<string>('')
  const [rigEditorOpen, setRigEditorOpen] = useState<boolean>(false)
  const [rigMood, setRigMood] = useState<'idle' | 'talking' | 'excited' | 'sad' | 'thinking'>('idle')
  // Pre-flight: surface a clear banner BEFORE the user clicks Forger so they
  // don't burn through the pipeline only to see "Load failed" 30s later.
  const [bridgeReachable, setBridgeReachable] = useState<boolean | null>(null)
  useEffect(() => {
    if (!open) return
    let alive = true
    void isBridgeReachable().then((ok) => { if (alive) setBridgeReachable(ok) })
    return () => { alive = false }
  }, [open])
  const regenSingleLayer = useCallback(async (layerId: string, customPrompt: string) => {
    if (!result) return
    setRegenLayerId(layerId)
    try {
      const { runPythonScript } = await import('../hooks/useTauri')
      const args = [
        '--portrait', result.portraitUrl.replace(/^\//, 'public/'),
        '--rig', `public/avatars/${result.meta.id}_rig.json`,
        '--out', `public/avatars/${result.meta.id}_layers`,
        '--only-layer', layerId,
      ]
      if (customPrompt.trim()) { args.push('--custom-prompt', customPrompt.trim()) }
      const res = await runPythonScript('python-services/forge_layers.py', args)
      const out = (res as { output?: string }).output ?? ''
      const jsonLine = out.split('\n').filter((l) => l.trim().startsWith('{')).pop()
      if (!jsonLine) return
      const data = JSON.parse(jsonLine) as { ok: boolean; layers?: Array<{ layer: string; ok: boolean; path?: string; prompt?: string }> }
      const produced = (data.layers || []).find((l) => l.layer === layerId && l.ok && l.path)
      if (!produced) return
      const url = produced.path!.replace(/\\/g, '/').replace(/^.*?public\//, '/') + `?t=${Date.now()}`
      // Mutate result in place so the preview refreshes
      setResult((prev) => prev ? {
        ...prev,
        layerFiles: prev.layerFiles.map((l) => l.layerId === layerId ? { ...l, url } : l)
          .concat(prev.layerFiles.some((l) => l.layerId === layerId) ? [] : [{ layerId, url, prompt: produced.prompt || '' }]),
      } : prev)
    } finally {
      setRegenLayerId(null)
      setRegenPrompt('')
    }
  }, [result])

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          className="fixed inset-0 z-[80] flex flex-col bg-[#05060b]/95 backdrop-blur-md"
        >
          {/* Header */}
          <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-fuchsia-500/30 to-cyan-400/30 border border-white/10">
                <Sparkles size={16} className="text-white/80" />
              </div>
              <div>
                <div className="text-[11px] uppercase tracking-widest text-white/50">Character Forge</div>
                <div className="text-sm font-medium text-white/90">Créer un personnage</div>
              </div>
            </div>
            <button onClick={onClose}
              className="rounded-lg border border-white/10 bg-white/[0.04] px-3 py-1.5 text-[11px] text-white/60 hover:text-white/90 hover:bg-white/[0.08]">
              Fermer
            </button>
          </div>

          {/* Body */}
          <div className="flex-1 overflow-auto px-4 py-4">
            <div className="mx-auto grid max-w-5xl gap-4 lg:grid-cols-[1fr_1.2fr]">
              {/* Left: prompt + pipeline */}
              <div className="space-y-3">
                {bridgeReachable === false && (
                  <div className="rounded-xl border border-amber-400/40 bg-amber-500/10 p-3 text-[12px] text-amber-100">
                    <div className="font-semibold mb-1">⚠ Bridge Python injoignable</div>
                    <p className="text-amber-200/80 leading-relaxed">
                      La Forge a besoin du bridge local (port 3001) pour générer le portrait, segmenter les calques et écrire le rig. Démarre-le sur ton PC puis recharge la page. Tu peux quand même saisir ton prompt en attendant.
                    </p>
                  </div>
                )}
                <div className="rounded-xl border border-white/10 bg-white/[0.03] p-3">
                  <label className="block text-[11px] uppercase tracking-wider text-white/50 mb-2">
                    Prompt personnage
                  </label>
                  <textarea
                    value={prompt}
                    onChange={(e) => setPrompt(e.target.value)}
                    placeholder="Ex: Caine, the amazing digital circus — ou « assistant futuriste fille cheveux bleus »"
                    disabled={running}
                    rows={3}
                    className="w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm text-white placeholder-white/30 focus:border-fuchsia-400/50 focus:outline-none"
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); void runPipeline() }
                    }}
                  />
                  <div className="mt-2 flex items-center justify-between gap-2">
                    <span className="text-[10px] text-white/40">
                      {running ? `${stepSummary}/${steps.length} étapes` : 'Ctrl/⌘ + Entrée pour lancer'}
                    </span>
                    {running ? (
                      <button onClick={cancelRun}
                        className="rounded-lg border border-red-400/30 bg-red-500/10 px-3 py-1.5 text-[11px] font-medium text-red-200 hover:bg-red-500/20">
                        Annuler
                      </button>
                    ) : (
                      <button onClick={() => void runPipeline()}
                        disabled={!prompt.trim() || bridgeReachable === false}
                        title={bridgeReachable === false ? 'Bridge Python injoignable' : undefined}
                        className="flex items-center gap-1.5 rounded-lg border border-fuchsia-400/40 bg-fuchsia-500/20 px-3 py-1.5 text-[11px] font-medium text-fuchsia-100 hover:bg-fuchsia-500/30 disabled:opacity-40">
                        <Play size={12} /> Lancer la Forge
                      </button>
                    )}
                  </div>
                </div>

                {/* Pipeline */}
                <div className="rounded-xl border border-white/10 bg-white/[0.02] p-3">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[11px] uppercase tracking-wider text-white/50">Pipeline (8 étapes)</span>
                    <span className="text-[10px] font-mono text-white/40">{pct}%</span>
                  </div>
                  <div className="mb-3 h-1 overflow-hidden rounded-full bg-white/[0.05]">
                    <motion.div animate={{ width: `${Math.min(pct, 100)}%` }} transition={{ duration: 0.4 }}
                      className="h-full rounded-full bg-gradient-to-r from-fuchsia-400 to-cyan-400" />
                  </div>
                  <ol className="space-y-1.5">
                    {steps.map((s) => (
                      <li key={s.id}
                        className={`flex items-start gap-2 rounded-lg border px-2.5 py-1.5 text-[11px] transition-colors ${
                          s.status === 'running' ? 'border-fuchsia-400/30 bg-fuchsia-500/[0.08] text-white/90'
                          : s.status === 'done' ? 'border-emerald-400/20 bg-emerald-500/[0.05] text-white/75'
                          : s.status === 'error' ? 'border-red-400/30 bg-red-500/[0.08] text-red-200'
                          : s.status === 'skipped' ? 'border-white/10 bg-white/[0.02] text-white/50'
                          : 'border-white/5 bg-white/[0.01] text-white/30'
                        }`}>
                        <span className="mt-[1px] shrink-0">
                          <StatusIcon status={s.status} />
                        </span>
                        <span className="flex-1 min-w-0">
                          <span className="block font-medium">{s.label}</span>
                          {s.detail && <span className="block text-[10px] text-white/50 truncate">{s.detail}</span>}
                        </span>
                      </li>
                    ))}
                  </ol>
                  {status && !error && (
                    <p className="mt-2 truncate text-[10px] text-white/40">{status}</p>
                  )}
                  {error && (
                    <p className="mt-2 rounded-md border border-red-400/20 bg-red-500/10 px-2 py-1 text-[11px] text-red-200">
                      {error}
                    </p>
                  )}
                </div>
              </div>

              {/* Right: preview + meta */}
              <div className="space-y-3">
                <div className="relative overflow-hidden rounded-xl border border-white/10 bg-black/40 aspect-square flex items-center justify-center">
                  {result?.portraitUrl && result.layerFiles.length > 0 ? (
                    // Animated RigPlayer preview once layers are extracted
                    <RigPlayer
                      data={{
                        imageSrc: result.portraitUrl,
                        features: result.features,
                        forge: {
                          meta: result.meta,
                          rig: result.rig,
                          layers: result.layerFiles,
                          baseLayer: result.baseLayerUrl,
                        },
                      }}
                      mood={rigMood}
                      size={340}
                      parallax
                    />
                  ) : result?.portraitUrl ? (
                    <img src={result.portraitUrl} alt={result.meta.display_name}
                      className="h-full w-full object-cover" />
                  ) : (
                    <div className="flex h-full items-center justify-center text-[11px] text-white/30">
                      {running ? 'Portrait en cours de génération…' : 'Le portrait apparaîtra ici'}
                    </div>
                  )}
                  {running && !result?.portraitUrl && (
                    <div className="absolute inset-0 bg-gradient-to-br from-fuchsia-500/10 to-cyan-500/10 animate-pulse pointer-events-none" />
                  )}
                  {result?.portraitUrl && result.layerFiles.length > 0 && (
                    <div className="absolute bottom-2 left-2 right-2 flex justify-center gap-1">
                      {(['idle','talking','excited','sad','thinking'] as const).map((m) => (
                        <button key={m} type="button"
                          className={`rounded px-2 py-0.5 text-[9px] font-mono ${rigMood === m ? 'bg-fuchsia-500/50 text-white' : 'bg-black/40 text-white/60 hover:bg-black/60'}`}
                          onClick={() => setRigMood(m)}>{m}</button>
                      ))}
                    </div>
                  )}
                </div>

                {result && (
                  <div className="space-y-2">
                    <div className="rounded-xl border border-white/10 bg-white/[0.02] p-3">
                      <div className="text-[10px] uppercase tracking-wider text-white/40 mb-1">Identité</div>
                      <div className="text-sm font-medium text-white/90">{result.meta.display_name}</div>
                      {result.meta.franchise && (
                        <div className="text-[11px] text-white/50">{result.meta.franchise}{result.meta.creator ? ` · ${result.meta.creator}` : ''}</div>
                      )}
                      <div className="mt-1 flex flex-wrap gap-1">
                        <span className="rounded border border-white/10 bg-white/[0.04] px-1.5 py-0.5 text-[10px] font-mono text-white/60">
                          {result.meta.style_hint}
                        </span>
                        <span className="rounded border border-fuchsia-400/20 bg-fuchsia-500/10 px-1.5 py-0.5 text-[10px] font-mono text-fuchsia-100">
                          router: {result.meta.router_model}
                        </span>
                        <span className="rounded border border-cyan-400/20 bg-cyan-500/10 px-1.5 py-0.5 text-[10px] font-mono text-cyan-100">
                          anim: {result.animationMode}
                        </span>
                      </div>
                    </div>

                    {result.traits.signature_elements.length > 0 && (
                      <div className="rounded-xl border border-white/10 bg-white/[0.02] p-3">
                        <div className="text-[10px] uppercase tracking-wider text-white/40 mb-1">Signature</div>
                        <div className="flex flex-wrap gap-1">
                          {result.traits.signature_elements.map((el) => (
                            <span key={el} className="rounded border border-emerald-400/20 bg-emerald-500/10 px-1.5 py-0.5 text-[10px] text-emerald-100">
                              {el}
                            </span>
                          ))}
                        </div>
                        {result.traits.forbidden_elements.length > 0 && (
                          <div className="mt-2 flex flex-wrap gap-1">
                            <span className="text-[10px] text-white/40 mr-1">interdits :</span>
                            {result.traits.forbidden_elements.map((el) => (
                              <span key={el} className="rounded border border-red-400/20 bg-red-500/10 px-1.5 py-0.5 text-[10px] text-red-200 line-through">
                                {el}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    )}

                    <div className="rounded-xl border border-white/10 bg-white/[0.02] p-3">
                      <div className="flex items-center justify-between mb-1">
                        <div className="text-[10px] uppercase tracking-wider text-white/40">Rig</div>
                        <button
                          type="button"
                          className="text-[10px] rounded border border-white/15 bg-white/[0.04] px-2 py-0.5 text-white/70 hover:bg-white/[0.1]"
                          onClick={() => setRigEditorOpen((v) => !v)}>
                          {rigEditorOpen ? '✕ fermer éditeur' : '✎ éditer le rig'}
                        </button>
                      </div>
                      <div className="text-[11px] text-white/70">
                        {result.rig.layers.length} layers ·{' '}
                        {result.rig.layers.filter((l) => l.kind !== 'static').length} animés ·{' '}
                        {Object.keys(result.rig.anim_rules).filter((k) => !k.startsWith('_')).length} règles
                      </div>
                      {rigEditorOpen && (
                        <div className="mt-2">
                          <RigEditor
                            value={result.rig}
                            onChange={(nextRig: RigPlan) => {
                              setResult((prev) => prev ? { ...prev, rig: nextRig } : prev)
                            }}
                          />
                          <div className="mt-1 text-[10px] text-white/40">
                            Les modifications seront utilisées par la prochaine régénération de calque.
                          </div>
                        </div>
                      )}
                      <div className="mt-1 flex flex-wrap gap-1">
                        {result.rig.layers.slice(0, 10).map((l) => (
                          <button key={l.id}
                            type="button"
                            disabled={regenLayerId === l.id || l.kind === 'static'}
                            onClick={() => { setRegenLayerId(l.id); setRegenPrompt('') }}
                            className={`rounded px-1.5 py-0.5 text-[9px] font-mono cursor-pointer ${
                              l.kind === 'static'
                                ? 'border border-white/10 bg-white/[0.03] text-white/40 cursor-default'
                                : 'border border-white/15 bg-white/[0.08] text-white/80 hover:bg-white/[0.15]'
                            }`}
                            title={l.kind === 'static' ? 'layer static' : 'Régénérer ce calque'}>
                            {regenLayerId === l.id ? '…' : l.id}:{l.kind}
                          </button>
                        ))}
                        {result.rig.layers.length > 10 && (
                          <span className="text-[10px] text-white/30">+{result.rig.layers.length - 10}</span>
                        )}
                      </div>
                      {regenLayerId && !regenPrompt && result.rig.layers.find((l) => l.id === regenLayerId) && (
                        <div className="mt-2 flex flex-col gap-2 rounded-lg border border-fuchsia-400/30 bg-fuchsia-500/[0.06] p-2">
                          <div className="text-[10px] text-white/60">Régénération ciblée · <b>{regenLayerId}</b></div>
                          <input
                            type="text"
                            value={regenPrompt}
                            onChange={(e) => setRegenPrompt(e.target.value)}
                            placeholder="Prompt GroundingDINO (laisse vide pour heuristique par défaut)"
                            className="rounded border border-white/15 bg-black/30 px-2 py-1 text-[11px] text-white/90"
                          />
                          <div className="flex gap-2">
                            <button type="button"
                              onClick={() => void regenSingleLayer(regenLayerId, regenPrompt)}
                              className="rounded bg-fuchsia-500/40 px-2 py-1 text-[10px] font-medium text-white hover:bg-fuchsia-500/60">
                              Relancer SAM2 pour {regenLayerId}
                            </button>
                            <button type="button"
                              onClick={() => { setRegenLayerId(null); setRegenPrompt('') }}
                              className="rounded border border-white/15 px-2 py-1 text-[10px] text-white/60">
                              Annuler
                            </button>
                          </div>
                        </div>
                      )}
                    </div>

                    <div className="flex gap-2">
                      <button onClick={commitToGallery}
                        className="flex flex-1 items-center justify-center gap-2 rounded-xl border border-emerald-400/40 bg-emerald-500/20 px-4 py-3 text-sm font-medium text-emerald-100 hover:bg-emerald-500/30">
                        <Save size={16} /> Enregistrer dans la galerie
                      </button>
                      <button type="button"
                        onClick={async () => {
                          const mod = await import('../utils/exportForgeBundle')
                          await mod.downloadForgeBundle(result)
                        }}
                        title="Exporter meta + traits + rig + portrait + layers en ZIP"
                        className="flex items-center justify-center gap-2 rounded-xl border border-fuchsia-400/40 bg-fuchsia-500/20 px-4 py-3 text-sm font-medium text-fuchsia-100 hover:bg-fuchsia-500/30">
                        📦 Exporter ZIP
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
