import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import VoicePushToTalk from '../components/VoicePushToTalk'
import { AnimatePresence, motion } from 'framer-motion'
import { Brush, Download, ImageOff, Loader2, Maximize, Send, Sparkles, StopCircle, X } from 'lucide-react'
const InpaintingPanel = lazy(() => import('../components/InpaintingPanel'))
import { createFluxWorkflow, getAvailableStyles, type FluxStyle } from '../utils/fluxWorkflow'
import { parseImageIntent, buildNegativePrompt, resolveReferenceDenoise } from '../utils/imagePromptParser'
import {
  comfyuiGetHistory,
  comfyuiGetImage,
  comfyuiQueuePrompt,
  comfyuiUploadImage,
  ensureComfyUIRunning,
} from '../hooks/useTauri'
import { useModuleHistoryStore } from '../stores/moduleHistoryStore'
import { useModuleDraftsStore } from '../stores/moduleDraftsStore'
import { saveBlob, loadBlobUrl, pruneOldBlobs, deleteBlob } from '../utils/blobStore'

type Character = 'natsu' | 'lucy'

const PORTRAITS: Record<Character, string> = {
  natsu: '/fairy/natsu.png',
  lucy:  '/fairy/lucy.png',
}

type GeneratedCard = {
  id: string
  url: string
  prompt: string
  style: FluxStyle
  timestamp: number
  rotation: number
}

function readCharacter(): Character {
  try {
    const v = window.localStorage.getItem('ft-who')
    return v === 'lucy' ? 'lucy' : 'natsu'
  } catch { return 'natsu' }
}

function pickRotation() {
  return Math.random() * 6 - 3
}

async function waitForComfyOutput(promptId: string, signal: AbortSignal): Promise<string[]> {
  const maxMs = 6 * 60 * 1000
  const startedAt = Date.now()
  while (Date.now() - startedAt < maxMs) {
    if (signal.aborted) throw new DOMException('Aborted', 'AbortError')
    try {
      const hist = await comfyuiGetHistory(promptId)
      if (hist && typeof hist === 'object') {
        const payload = Object.values(hist)[0] as any
        const outputs = payload?.outputs
        if (outputs && typeof outputs === 'object') {
          const filenames: string[] = []
          for (const node of Object.values(outputs) as any[]) {
            if (node?.images && Array.isArray(node.images)) {
              for (const img of node.images) {
                if (img?.filename) filenames.push(img.filename as string)
              }
            }
          }
          if (filenames.length > 0) return filenames
        }
      }
    } catch {
    }
    await new Promise((r) => setTimeout(r, 1500))
  }
  throw new Error('ComfyUI: timeout d\'attente du rendu (6 min)')
}

export default function MangaImageView() {
  const [who, setWho] = useState<Character>(readCharacter)
  useEffect(() => {
    const t = window.setInterval(() => setWho(readCharacter()), 800)
    return () => window.clearInterval(t)
  }, [])

  const styles = useMemo(() => getAvailableStyles().slice(0, 10), [])
  const imgDraft = useModuleDraftsStore((s) => s.drafts.image)
  const setImgDraft = useModuleDraftsStore((s) => s.setDraft)
  const [prompt, setPrompt] = useState<string>(() => imgDraft?.prompt ?? '')
  const [negPrompt, setNegPrompt] = useState<string>(() => (imgDraft?.options?.negPrompt as string) ?? '')
  const [showNeg, setShowNeg] = useState<boolean>(() => Boolean((imgDraft?.options?.negPrompt as string) ?? ''))
  const [style, setStyle] = useState<FluxStyle>(() => ((imgDraft?.style as FluxStyle) ?? 'manga'))
  useEffect(() => {
    const id = window.setTimeout(() => {
      setImgDraft('image', {
        prompt,
        style,
        options: { negPrompt },
      })
    }, 200)
    return () => window.clearTimeout(id)
  }, [prompt, style, negPrompt, setImgDraft])
  const [refPreview, setRefPreview] = useState<string | null>(null)
  const [refFilename, setRefFilename] = useState<string | null>(null)
  const [refDenoise, setRefDenoise] = useState(0.7)

  const [refUploading, setRefUploading] = useState(false)
  const [seed, setSeed] = useState<string>(() => (imgDraft?.options?.seed as string) ?? '')
  const [batch, setBatch] = useState<1 | 2 | 3 | 4>(() => ((imgDraft?.options?.batch as 1|2|3|4) ?? 1))
  const [dimensions, setDimensions] = useState<'square' | 'portrait' | 'landscape'>(() =>
    ((imgDraft?.options?.dimensions as 'square'|'portrait'|'landscape') ?? 'square')
  )
  useEffect(() => {
    setImgDraft('image', { options: { seed, batch, dimensions } })
  }, [seed, batch, dimensions, setImgDraft])

  const DIMENSIONS = {
    square: { w: 1024, h: 1024, label: '1:1' },
    portrait: { w: 832, h: 1216, label: '2:3' },
    landscape: { w: 1216, h: 832, label: '3:2' },
  } as const
  const [images, setImages] = useState<GeneratedCard[]>([])
  const [current, setCurrent] = useState<GeneratedCard | null>(null)
  const previewIntent = useMemo(
    () => parseImageIntent(prompt, { hasReference: Boolean(refFilename || current) }),
    [current, prompt, refFilename],
  )
  const effectiveDenoise: number | null = useMemo(() => {
    if (!refFilename && !(current && previewIntent.isEditIntent)) return null
    return previewIntent.isEditIntent
      ? resolveReferenceDenoise(previewIntent, refDenoise, style)
      : refDenoise
  }, [current, refFilename, refDenoise, style, previewIntent])

  useEffect(() => {
    const id = window.setTimeout(() => {
      const meta = images.map(({ url: _url, ...rest }) => rest)
      setImgDraft('image', { scratch: { gallery: meta } })
    }, 250)
    return () => window.clearTimeout(id)
  }, [images, setImgDraft])

  useEffect(() => {
    let alive = true
    const meta = (imgDraft?.scratch?.gallery as Array<Omit<GeneratedCard, 'url'>> | undefined) ?? []
    if (meta.length === 0) return
    ;(async () => {
      const hydrated: GeneratedCard[] = []
      for (const m of meta) {
        const url = await loadBlobUrl(m.id)
        if (url) hydrated.push({ ...m, url })
      }
      if (alive && hydrated.length > 0) {
        setImages(hydrated)
        setCurrent(hydrated[0])
      }
    })()
    return () => { alive = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const [resumeBanner, setResumeBanner] = useState<{ minutes: number; text: string } | null>(null)
  useEffect(() => {
    let alive = true
    const raw = (() => { try { return localStorage.getItem('aurora.pendingComfyPrompt.v1') } catch { return null } })()
    if (!raw) return
    let pending: { promptId: string; prompt: string; style: FluxStyle; runSeed: number | null; rotation: number; startedAt: number } | null = null
    try { pending = JSON.parse(raw) } catch { pending = null }
    if (!pending?.promptId) {
      try { localStorage.removeItem('aurora.pendingComfyPrompt.v1') } catch {}
      return
    }
    const elapsedMin = Math.max(0, Math.round((Date.now() - pending.startedAt) / 60_000))
    setResumeBanner({ minutes: elapsedMin, text: pending.prompt })

    ;(async () => {
      const maxMs = 10 * 60 * 1000
      const startedAt = Date.now()
      while (alive && Date.now() - startedAt < maxMs) {
        try {
          const hist = await comfyuiGetHistory(pending.promptId)
          if (hist && typeof hist === 'object') {
            const payload = Object.values(hist)[0] as { outputs?: Record<string, { images?: Array<{ filename?: string }> }> } | undefined
            const outputs = payload?.outputs
            if (outputs) {
              const filenames: string[] = []
              for (const node of Object.values(outputs)) {
                for (const img of node?.images ?? []) {
                  if (img?.filename) filenames.push(img.filename)
                }
              }
              if (filenames.length > 0 && alive) {
                const blob = await comfyuiGetImage(filenames[0])
                const cardId = `img-resume-${Date.now()}`
                const url = await saveBlob(cardId, blob, 'image')
                const card: GeneratedCard = {
                  id: cardId, url,
                  prompt: pending.prompt,
                  style: pending.style,
                  timestamp: Date.now(),
                  rotation: pending.rotation,
                }
                setImages((prev) => [card, ...prev].slice(0, 24))
                setCurrent(card)
                try { localStorage.removeItem('aurora.pendingComfyPrompt.v1') } catch {}
                if (alive) setResumeBanner(null)
                return
              }
            }
          }
        } catch {
        }
        await new Promise((r) => setTimeout(r, 2500))
      }
      try { localStorage.removeItem('aurora.pendingComfyPrompt.v1') } catch {}
      if (alive) setResumeBanner(null)
    })()

    return () => { alive = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  const [inpaintOpen, setInpaintOpen] = useState(false)
  const [upscaling, setUpscaling] = useState(false)
  const upscaleCurrent = async (scale: 2 | 4) => {
    if (!current || upscaling) return
    setUpscaling(true)
    try {
      const mod = await import('../utils/upscaleImage')
      const { url, method } = await mod.upscaleAuto(current.url, scale)
      try {
        const blob = await fetch(url).then((r) => r.blob())
        const newId = `${current.id}-x${scale}-${method}`
        const savedUrl = await saveBlob(newId, blob, 'image')
        const card: GeneratedCard = { ...current, id: newId, url: savedUrl }
        setImages((prev) => [card, ...prev].slice(0, 24))
        setCurrent(card)
      } catch {
        const card: GeneratedCard = { ...current, id: `${current.id}-x${scale}-${method}`, url }
        setImages((prev) => [card, ...prev].slice(0, 24))
        setCurrent(card)
      }
    } catch (err) {
      console.warn('[upscale]', err)
    } finally { setUpscaling(false) }
  }
  const [generating, setGenerating] = useState(false)
  const [progress, setProgress] = useState<string>('')
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const onUploadReference = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setRefUploading(true)
    setError(null)
    try {
      const up = await ensureComfyUIRunning()
      if (!up.ok) throw new Error(up.error || 'ComfyUI indisponible')
      const res = await comfyuiUploadImage(file, `ref_${Date.now()}_${file.name}`)
      setRefFilename(res.name)
      setRefPreview(URL.createObjectURL(file))
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setRefUploading(false)
      e.target.value = ''
    }
  }
  const clearReference = () => {
    if (refPreview) URL.revokeObjectURL(refPreview)
    setRefPreview(null)
    setRefFilename(null)
  }

  const { pushMessage } = useModuleHistoryStore()

  const queuePrompt = useCallback(async () => {
    const text = prompt.trim()
    if (!text || generating) return
    setError(null)
    setGenerating(true)
    setProgress('Vérification de ComfyUI…')
    abortRef.current = new AbortController()
    const ac = abortRef.current

    try {
      const up = await ensureComfyUIRunning()
      if (!up.ok) throw new Error(up.error || 'ComfyUI indisponible')

      const intent = parseImageIntent(text, { hasReference: Boolean(refFilename || current) })
      const cleanedText = intent.cleanedPrompt
      const mergedNegative = buildNegativePrompt(negPrompt, intent.removals)
      const editDenoise = resolveReferenceDenoise(intent, refDenoise, style)

      let groundedReference: { filename: string; denoise?: number } | null = refFilename
        ? {
            filename: refFilename,
            denoise: intent.isEditIntent ? editDenoise : refDenoise,
          }
        : null

      if (!groundedReference && current && intent.isEditIntent) {
        try {
          setProgress('Preparation de l image actuelle comme reference...')
          const response = await fetch(current.url, { signal: ac.signal })
          if (response.ok) {
            const blob = await response.blob()
            const file = new File([blob], `aurora_current_${Date.now()}.png`, { type: blob.type || 'image/png' })
            const uploaded = await comfyuiUploadImage(file)
            if (uploaded?.name) groundedReference = { filename: uploaded.name, denoise: editDenoise }
          }
        } catch {
        }
      }

      if (!groundedReference && !intent.isEditIntent) {
        try {
          setProgress('Recherche de reference visuelle (Aurora Connect)...')
          const { searchReferenceImages } = await import('../services/auroraExtensionBridge')
          const refResult = await searchReferenceImages(cleanedText, { limit: 1, signal: ac.signal })
          if (refResult.ok && refResult.data.length > 0) {
            const ref = refResult.data[0]
            try {
              const response = await fetch(ref.url, { signal: ac.signal })
              if (response.ok) {
                const blob = await response.blob()
                const file = new File([blob], `aurora_extref_${Date.now()}.png`, { type: blob.type || 'image/png' })
                const uploaded = await comfyuiUploadImage(file)
                if (uploaded?.name) {
                  groundedReference = { filename: uploaded.name, denoise: 0.40 }
                }
              }
            } catch {
            }
          }
        } catch {
        }
      }

      const parsedSeed = seed.trim() ? Number(seed.trim()) : null
      const baseSeed = (parsedSeed !== null && !Number.isNaN(parsedSeed)) ? parsedSeed : null

      for (let k = 0; k < batch; k++) {
        if (ac.signal.aborted) break
        const runSeed = baseSeed !== null ? baseSeed + k : null
        setProgress(batch > 1 ? `Construction ${k + 1}/${batch}…` : 'Construction du workflow FLUX…')
        const dim = DIMENSIONS[dimensions]
        const workflow = createFluxWorkflow({
          prompt: cleanedText,
          negativePrompt: mergedNegative,
          style,
          width: dim.w,
          height: dim.h,
          steps: 28,
          filenamePrefix: `manga_${Date.now()}_${k}`,
          referenceImage: groundedReference,
          seed: runSeed,
          editIntent: intent,
        })

        setProgress(batch > 1 ? `Envoi ${k + 1}/${batch}…` : 'Envoi à ComfyUI…')
        const queueResponse = await comfyuiQueuePrompt(workflow)
        const parsed = typeof queueResponse === 'string' ? JSON.parse(queueResponse) : queueResponse
        const promptId = parsed?.prompt_id as string | undefined
        if (!promptId) throw new Error('ComfyUI n\'a pas retourné de prompt_id')

        try {
          localStorage.setItem('aurora.pendingComfyPrompt.v1', JSON.stringify({
            promptId, prompt: text, style, runSeed, rotation: pickRotation(), startedAt: Date.now(),
          }))
        } catch {
        }

        setProgress(batch > 1 ? `Rendu ${k + 1}/${batch}… (30-90s)` : 'Rendu en cours… (30-90s)')
        const filenames = await waitForComfyOutput(promptId, ac.signal)

        setProgress(batch > 1 ? `Image ${k + 1}/${batch}…` : 'Récupération de l\'image…')
        const first = filenames[0]
        const blob = await comfyuiGetImage(first)
        try { localStorage.removeItem('aurora.pendingComfyPrompt.v1') } catch {}
        const cardId = `img-${Date.now()}-${k}`
        const url = await saveBlob(cardId, blob, 'image')
        const card: GeneratedCard = {
          id: cardId,
          url,
          prompt: text,
          style,
          timestamp: Date.now(),
          rotation: pickRotation(),
        }
        setImages((prev) => [card, ...prev].slice(0, 24))
        setCurrent(card)
        void pruneOldBlobs('image', 24)

        try {
          pushMessage('image', { role: 'user', content: text })
          pushMessage('image', { role: 'assistant', content: `[image:${url}] style:${style}${runSeed !== null ? ` seed:${runSeed}` : ''}` })
        } catch {
        }
      }

      setProgress('Prêt')
      if (batch === 1) setPrompt('')
    } catch (err) {
      if ((err as Error)?.name === 'AbortError') {
        setProgress('Annulé')
      } else {
        const msg = err instanceof Error ? err.message : String(err)
        setError(msg)
        setProgress('')
      }
    } finally {
      setGenerating(false)
    }
  }, [prompt, style, generating, pushMessage, negPrompt, refFilename, refDenoise, seed, batch, dimensions, current])

  const onStop = () => abortRef.current?.abort()

  const downloadCurrent = async () => {
    if (!current) return
    const { downloadImageUniversal } = await import('../utils/imageDownload')
    await downloadImageUniversal(current, {
      filename: `fairy-tail-${current.style}-${current.id}.png`,
    })
  }

  const coreStyles = useMemo(() => styles.slice(0, 8), [styles])
  const extraStyles = useMemo(() => styles.slice(8), [styles])
  const STYLE_RADIUS = 102
  const styleNodes = useMemo(() => coreStyles.map((s, i) => {
    const angle = (i / coreStyles.length) * Math.PI * 2 - Math.PI / 2
    return {
      ...s,
      x: Math.cos(angle) * STYLE_RADIUS,
      y: Math.sin(angle) * STYLE_RADIUS,
    }
  }), [coreStyles])

  return (
    <div className="mi-root">
      <div className="mi-stage">
        <div className="mi-frame">
          <AnimatePresence mode="wait">
            {current ? (
              <motion.img
                key={current.id}
                src={current.url}
                alt=""
                className="mi-image"
                initial={{ scale: 0.9, opacity: 0, rotate: -2 }}
                animate={{ scale: 1, opacity: 1, rotate: 0 }}
                exit={{ scale: 0.95, opacity: 0 }}
                transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
              />
            ) : generating ? (
              <motion.div
                key="loading"
                className="mi-loading"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
              >
                <Loader2 size={42} strokeWidth={2.2} className="mi-spin" />
                <div className="mi-loading-text">{progress || 'Rendu manga en cours…'}</div>
              </motion.div>
            ) : (
              <motion.div
                key="placeholder"
                className="mi-placeholder"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
              >
                <img src={PORTRAITS[who]} alt={who} className="mi-placeholder-portrait" />
                <div className="mi-placeholder-banner">
                  {who === 'natsu' ? 'PRÊT À ENFLAMMER LA TOILE' : 'PRÊTE À OUVRIR LA PORTE'}
                </div>
                <p className="mi-placeholder-hint">
                  Décris ta scène, choisis un style, clique <strong>INVOQUER</strong>.
                </p>
              </motion.div>
            )}
          </AnimatePresence>

          <div className="mi-frame-sfx-1">{who === 'natsu' ? 'FLUX !' : 'STELLA !'}</div>
          <div className="mi-frame-sfx-2">#{images.length + 1}</div>

          {current && !generating && (
            <button type="button" className="mi-download" onClick={downloadCurrent} title="Télécharger">
              <Download size={14} strokeWidth={2.4} /> PNG
            </button>
          )}
          {current && !generating && (
            <button type="button" className="mi-inpaint" onClick={() => setInpaintOpen(true)} title="Retouche par brosse (LaMa)">
              <Brush size={14} strokeWidth={2.4} /> Retouche
            </button>
          )}
          {current && !generating && (
            <button type="button" className="mi-upscale" disabled={upscaling}
              onClick={() => void upscaleCurrent(2)} title="Upscale 2x (ESRGAN si disponible, sinon bicubic)">
              {upscaling ? <Loader2 size={14} className="mi-spin" /> : <Maximize size={14} strokeWidth={2.4} />} 2×
            </button>
          )}
          {current && !generating && (
            <button type="button" className="mi-upscale is-four" disabled={upscaling}
              onClick={() => void upscaleCurrent(4)} title="Upscale 4x">
              {upscaling ? '…' : '4×'}
            </button>
          )}
          {current && !generating && (
            <div className="mi-frame-caption">{current.prompt}</div>
          )}
        </div>

        <div className="mi-wheel-wrap">
          <div className="mi-wheel" aria-label="Sélecteur de style">
            <div className="mi-wheel-center">
              <span className="mi-wheel-label">STYLE</span>
              <span className="mi-wheel-value">{styles.find((s) => s.id === style)?.label ?? style}</span>
            </div>
            {styleNodes.map((s) => {
              const isActive = s.id === style
              const shortLabel = s.label.split(/\s|\//)[0].slice(0, 6)
              return (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => setStyle(s.id)}
                  className={`mi-wheel-node ${isActive ? 'is-active' : ''}`}
                  style={{ left: `calc(50% + ${s.x}px)`, top: `calc(50% + ${s.y}px)` }}
                  title={s.label}
                >
                  <span className="mi-wheel-node-label">{shortLabel}</span>
                </button>
              )
            })}
          </div>
          {extraStyles.length > 0 && (
            <div className="mi-wheel-extras" role="tablist">
              {extraStyles.map((s) => (
                <button
                  key={s.id}
                  type="button"
                  role="tab"
                  aria-selected={style === s.id}
                  onClick={() => setStyle(s.id)}
                  className={`mi-wheel-extra ${style === s.id ? 'is-active' : ''}`}
                  title={s.label}
                >
                  {s.label}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {resumeBanner && (
        <div style={{
          margin: '0 1rem 0.75rem',
          padding: '0.6rem 0.9rem',
          borderRadius: 12,
          border: '1px solid rgba(251, 191, 36, 0.4)',
          background: 'rgba(251, 191, 36, 0.1)',
          color: '#fef3c7',
          fontSize: 12,
        }}>
          <div style={{ fontWeight: 600, marginBottom: 2 }}>⏳ Reprise d'une image en cours</div>
          <div style={{ opacity: 0.85, lineHeight: 1.4 }}>
            Le PC finit une image demarree il y a {resumeBanner.minutes} min
            {resumeBanner.text ? ` (« ${resumeBanner.text.slice(0, 60)}${resumeBanner.text.length > 60 ? '…' : ''} »)` : ''}.
            Elle apparaitra ici des que ComfyUI a termine.
          </div>
        </div>
      )}

      <div className="mi-command">
        <div className="mi-prompt-card">
          <div className="mi-prompt-kicker">PROMPT</div>
          <textarea
            className="mi-prompt-input"
            rows={2}
            placeholder={who === 'natsu'
              ? 'Ex: vélo gravel orange, atelier, étincelles, ciel orageux…'
              : 'Ex: portrait stellaire, nuit étoilée, porte dorée, lumière douce…'}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); void queuePrompt() }
            }}
            disabled={generating}
          />
          <div className="mt-2 flex items-center gap-2">
            <VoicePushToTalk
              onTranscript={(t) => setPrompt((prev) => (prev?.trim() ? `${prev}, ${t}` : t))}
              label="Dicter ton prompt manga"
              size={32}
              variant="glass"
            />
            <span style={{ fontSize: 11, opacity: 0.55 }}>Dicte au micro.</span>
          </div>
          {(previewIntent.removals.length > 0
            || previewIntent.isEditIntent
            || effectiveDenoise !== null) && (
            <div style={{
              margin: '6px 0 8px',
              padding: '6px 10px',
              background: 'var(--ft-paper-2, rgba(0,0,0,0.04))',
              border: '1px dashed var(--ft-line, rgba(0,0,0,0.18))',
              borderRadius: 6, fontSize: 11,
              fontFamily: 'JetBrains Mono, monospace',
              color: 'var(--ft-muted, #6a5a42)',
              display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap',
            }}>
              {previewIntent.removals.length > 0 && (
                <>
                  <span>− retirer :</span>
                  {previewIntent.removals.map((r, i) => (
                    <span key={i} style={{
                      padding: '1px 6px', borderRadius: 99,
                      background: 'rgba(198, 42, 12, 0.12)',
                      color: 'var(--ft-blood, #c62a0c)',
                      fontWeight: 600,
                    }}>{r}</span>
                  ))}
                </>
              )}
              {previewIntent.isEditIntent && (
                <span style={{
                  padding: '1px 6px', borderRadius: 99,
                  background: 'rgba(31, 78, 201, 0.12)',
                  color: 'var(--ft-info, #1f4ec9)',
                  fontWeight: 600,
                }}>{previewIntent.editContract.label}</span>
              )}
              {effectiveDenoise !== null && (
                <span style={{
                  padding: '1px 6px', borderRadius: 99,
                  background: 'var(--ft-paper-3, rgba(0,0,0,0.05))',
                  color: 'var(--ft-dim, #8a7a5f)',
                  marginLeft: 'auto',
                }}>denoise {effectiveDenoise.toFixed(2)}</span>
              )}
            </div>
          )}
          <div className="mi-prompt-footer">
            <span className="mi-prompt-hint">⌘⏎ invoquer · {progress || 'prêt'}</span>
            <button type="button" className="mi-neg-toggle"
              onClick={() => setShowNeg((v) => !v)}
              title="Prompt négatif (ce que tu ne veux PAS voir)">
              {showNeg ? '− neg' : '+ neg'}{negPrompt.trim() ? ' •' : ''}
            </button>
            {error && <span className="mi-prompt-error"><X size={12} strokeWidth={2.4} /> {error}</span>}
          </div>
          {showNeg && (
            <>
              <textarea
                className="mi-prompt-input mi-neg-input"
                rows={1}
                placeholder="Ex: blurry, low quality, watermark, extra fingers, text"
                value={negPrompt}
                onChange={(e) => setNegPrompt(e.target.value)}
                disabled={generating}
              />
              <p className="mi-neg-hint" style={{ fontSize: '10px', color: 'rgba(255,255,255,0.45)', marginTop: 4, paddingLeft: 4 }}>
                Note FLUX dev : ces concepts sont retirés du prompt positif (pas de tour négative dédiée).
              </p>
            </>
          )}
          <div className="mi-gen-row">
            <label className="mi-gen-field" title="Seed pour reproduire un résultat — vide = aléatoire">
              🎲 seed
              <input
                type="text"
                inputMode="numeric"
                pattern="[0-9]*"
                placeholder="random"
                value={seed}
                onChange={(e) => setSeed(e.target.value.replace(/[^0-9]/g, '').slice(0, 10))}
                disabled={generating}
              />
              {seed && !generating && (
                <button type="button" className="mi-gen-clear" onClick={() => setSeed('')} title="Random">✕</button>
              )}
            </label>
            <div className="mi-gen-field">
              🖼 batch
              <div className="mi-batch-group" role="radiogroup" aria-label="Nombre d'images">
                {[1, 2, 3, 4].map((n) => (
                  <button
                    key={n}
                    type="button"
                    role="radio"
                    aria-checked={batch === n}
                    className={`mi-batch-btn ${batch === n ? 'is-on' : ''}`}
                    onClick={() => setBatch(n as 1 | 2 | 3 | 4)}
                    disabled={generating}
                  >
                    ×{n}
                  </button>
                ))}
              </div>
            </div>
            <div className="mi-gen-field" title={`Dimensions : ${DIMENSIONS[dimensions].w}×${DIMENSIONS[dimensions].h}`}>
              📐 ratio
              <div className="mi-batch-group" role="radiogroup" aria-label="Ratio d'image">
                {(['square', 'portrait', 'landscape'] as const).map((d) => (
                  <button
                    key={d}
                    type="button"
                    role="radio"
                    aria-checked={dimensions === d}
                    className={`mi-batch-btn ${dimensions === d ? 'is-on' : ''}`}
                    onClick={() => setDimensions(d)}
                    disabled={generating}
                    title={`${DIMENSIONS[d].label} — ${DIMENSIONS[d].w}×${DIMENSIONS[d].h}`}
                  >
                    {DIMENSIONS[d].label}
                  </button>
                ))}
              </div>
            </div>
          </div>
          <div className="mi-ref-row">
            {refPreview ? (
              <div className="mi-ref-chip">
                <img src={refPreview} alt="référence" />
                <div className="mi-ref-meta">
                  <span>Référence · denoise {refDenoise.toFixed(2)}</span>
                  <input
                    type="range"
                    min={0.3}
                    max={0.95}
                    step={0.05}
                    value={refDenoise}
                    onChange={(e) => setRefDenoise(Number(e.target.value))}
                    disabled={generating}
                    title="0.3 = garde beaucoup la réf · 0.95 = très libre"
                  />
                </div>
                <button type="button" className="mi-ref-close" onClick={clearReference} disabled={generating}>✕</button>
              </div>
            ) : (
              <label className="mi-ref-add" title="Uploader une image de référence (style/pose)">
                <input
                  type="file"
                  accept="image/*"
                  onChange={onUploadReference}
                  disabled={generating || refUploading}
                  style={{ display: 'none' }}
                />
                {refUploading ? '⏳ Upload…' : '📎 Référence (IP-Adapter)'}
              </label>
            )}
          </div>
        </div>

        {generating ? (
          <button type="button" className="mi-stamp is-stop" onClick={onStop}>
            <StopCircle size={18} strokeWidth={2.4} /> STOP !
          </button>
        ) : (
          <button
            type="button"
            className="mi-stamp"
            onClick={() => void queuePrompt()}
            disabled={!prompt.trim()}
          >
            <Sparkles size={16} strokeWidth={2.4} /> {who === 'natsu' ? 'FLAMBER !' : 'INVOQUER !'}
          </button>
        )}
      </div>

      {images.length > 0 && (
        <div className="mi-strip">
          <div className="mi-strip-head">
            <span className="mi-strip-title">COLLECTION</span>
            <span className="mi-strip-count">{images.length} pièce{images.length > 1 ? 's' : ''}</span>
          </div>
          <div className="mi-strip-track">
            {images.map((img) => (
              <button
                key={img.id}
                type="button"
                className={`mi-polaroid ${current?.id === img.id ? 'is-active' : ''}`}
                style={{ transform: `rotate(${img.rotation}deg)` }}
                onClick={() => setCurrent(img)}
                title={img.prompt}
              >
                <img src={img.url} alt="" />
                <div className="mi-polaroid-caption">{img.style}</div>
              </button>
            ))}
          </div>
        </div>
      )}

      {images.length === 0 && !generating && (
        <div className="mi-empty">
          <ImageOff size={14} strokeWidth={2.4} />
          <span>Aucune création pour l'instant — lance ta première invocation.</span>
        </div>
      )}

      {inpaintOpen && current && (
        <Suspense fallback={null}>
          <InpaintingPanel
            imageSrc={current.url}
            onClose={() => setInpaintOpen(false)}
            onApply={async (newUrl) => {
              const newId = `inpaint-${Date.now()}`
              try {
                const blob = await fetch(newUrl).then((r) => r.blob())
                const savedUrl = await saveBlob(newId, blob, 'image')
                const card: GeneratedCard = { ...current, id: newId, url: savedUrl }
                setImages((prev) => [card, ...prev].slice(0, 24))
                setCurrent(card)
              } catch {
                const card: GeneratedCard = { ...current, id: newId, url: newUrl }
                setImages((prev) => [card, ...prev].slice(0, 24))
                setCurrent(card)
              }
            }}
          />
        </Suspense>
      )}
    </div>
  )
}
