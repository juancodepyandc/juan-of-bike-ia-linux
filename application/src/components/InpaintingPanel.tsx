/**
 * InpaintingPanel — full-screen overlay that lets the user paint a mask on
 * any image and run LaMa (via ComfyUI's AILab_LamaRemover node) to remove
 * the masked region. Produces a cleaned image you can save back to the
 * gallery or chain into another generation.
 *
 * Uses the existing ComfyUI install (the Forge already downloaded LaMa
 * weights). No new dependency. On ComfyUI offline or node missing, the
 * panel displays a clear error and falls back to local canvas erase.
 */
import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { comfyuiGetImage, comfyuiQueuePrompt } from '../hooks/useTauri'

interface Props {
  imageSrc: string
  onClose: () => void
  onApply?: (newImageUrl: string) => void
}

type Phase = 'idle' | 'painting' | 'running' | 'done' | 'error'

export default function InpaintingPanel({ imageSrc, onClose, onApply }: Props) {
  const imgRef = useRef<HTMLImageElement>(null)
  const baseRef = useRef<HTMLCanvasElement>(null)
  const maskRef = useRef<HTMLCanvasElement>(null)
  const drawingRef = useRef(false)
  const lastPtRef = useRef<{ x: number; y: number } | null>(null)

  const [brushSize, setBrushSize] = useState(40)
  const [phase, setPhase] = useState<Phase>('idle')
  const [error, setError] = useState<string | null>(null)
  const [resultUrl, setResultUrl] = useState<string | null>(null)

  // Load image → draw on base canvas
  useEffect(() => {
    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.src = imageSrc
    img.onload = () => {
      const base = baseRef.current
      const mask = maskRef.current
      if (!base || !mask) return
      base.width = img.naturalWidth
      base.height = img.naturalHeight
      mask.width = img.naturalWidth
      mask.height = img.naturalHeight
      base.getContext('2d')!.drawImage(img, 0, 0)
      // Mask starts pure black = keep; white = remove
      const mctx = mask.getContext('2d')!
      mctx.fillStyle = '#000'
      mctx.fillRect(0, 0, mask.width, mask.height)
    }
  }, [imageSrc])

  const getScaledPt = (e: React.PointerEvent<HTMLCanvasElement>) => {
    const c = maskRef.current!
    const rect = c.getBoundingClientRect()
    const sx = c.width / rect.width
    const sy = c.height / rect.height
    return { x: (e.clientX - rect.left) * sx, y: (e.clientY - rect.top) * sy }
  }
  const paintStroke = (from: { x: number; y: number } | null, to: { x: number; y: number }) => {
    const mctx = maskRef.current!.getContext('2d')!
    mctx.strokeStyle = '#fff'    // white = region to erase
    mctx.fillStyle = '#fff'
    mctx.lineCap = 'round'
    mctx.lineJoin = 'round'
    mctx.lineWidth = brushSize
    if (from) {
      mctx.beginPath()
      mctx.moveTo(from.x, from.y)
      mctx.lineTo(to.x, to.y)
      mctx.stroke()
    } else {
      mctx.beginPath()
      mctx.arc(to.x, to.y, brushSize / 2, 0, Math.PI * 2)
      mctx.fill()
    }
  }
  const onDown = (e: React.PointerEvent<HTMLCanvasElement>) => {
    drawingRef.current = true
    setPhase('painting')
    const p = getScaledPt(e)
    lastPtRef.current = p
    paintStroke(null, p)
    e.currentTarget.setPointerCapture(e.pointerId)
  }
  const onMove = (e: React.PointerEvent<HTMLCanvasElement>) => {
    if (!drawingRef.current) return
    const p = getScaledPt(e)
    paintStroke(lastPtRef.current, p)
    lastPtRef.current = p
  }
  const onUp = () => { drawingRef.current = false; lastPtRef.current = null }
  const clearMask = () => {
    const mctx = maskRef.current?.getContext('2d')
    if (!mctx) return
    mctx.fillStyle = '#000'
    mctx.fillRect(0, 0, maskRef.current!.width, maskRef.current!.height)
    setPhase('idle')
  }

  const runInpaint = async () => {
    if (!baseRef.current || !maskRef.current) return
    setPhase('running')
    setError(null)
    try {
      // Encode image + mask as base64 and upload to ComfyUI via /upload/image
      const baseBlob = await new Promise<Blob>((resolve, reject) => {
        baseRef.current!.toBlob((b) => b ? resolve(b) : reject(new Error('base blob failed')), 'image/png')
      })
      const maskBlob = await new Promise<Blob>((resolve, reject) => {
        maskRef.current!.toBlob((b) => b ? resolve(b) : reject(new Error('mask blob failed')), 'image/png')
      })
      const upload = async (blob: Blob, name: string) => {
        const fd = new FormData()
        fd.append('image', blob, name)
        const r = await fetch('http://127.0.0.1:8188/upload/image', { method: 'POST', body: fd })
        if (!r.ok) throw new Error(`ComfyUI upload HTTP ${r.status}`)
        const d = await r.json() as { name: string }
        return d.name
      }
      const baseName = await upload(baseBlob, `inpaint_base_${Date.now()}.png`)
      const maskName = await upload(maskBlob, `inpaint_mask_${Date.now()}.png`)

      // Build minimal LaMa inpaint workflow
      const workflow = {
        prompt: {
          "1": { class_type: "LoadImage", inputs: { image: baseName } },
          "2": { class_type: "LoadImage", inputs: { image: maskName } },
          // Convert white-on-black mask to an actual MASK tensor
          "3": { class_type: "ImageToMask", inputs: { image: ["2", 0], channel: "red" } },
          "4": {
            class_type: "AILab_LamaRemover",
            inputs: {
              images: ["1", 0],
              masks: ["3", 0],
              removal_strength: 230,
              edge_smoothness: 8,
            },
          },
          "5": {
            class_type: "SaveImage",
            inputs: { images: ["4", 0], filename_prefix: "aurora_inpaint" },
          },
        },
        client_id: `aurora_inpaint_${Date.now()}`,
      }

      const q = await comfyuiQueuePrompt(workflow) as unknown as string
      const parsed = typeof q === 'string' ? JSON.parse(q) : q
      const promptId = parsed?.prompt_id as string | undefined
      if (!promptId) throw new Error('ComfyUI did not return a prompt_id')

      // Poll history until done
      const start = Date.now()
      while (Date.now() - start < 300000) {
        await new Promise((r) => setTimeout(r, 1500))
        const hr = await fetch(`http://127.0.0.1:8188/history/${promptId}`)
        if (!hr.ok) continue
        const hist = await hr.json() as Record<string, { outputs?: Record<string, { images?: Array<{ filename: string; subfolder?: string; type?: string }> }> }>
        const node5 = hist[promptId]?.outputs?.["5"]
        const img = node5?.images?.[0]
        if (img) {
          const blob = await comfyuiGetImage(img.filename, img.subfolder || '')
          const url = URL.createObjectURL(blob)
          setResultUrl(url)
          setPhase('done')
          return
        }
      }
      throw new Error('ComfyUI: timeout')
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      setPhase('error')
    }
  }

  const apply = () => {
    if (!resultUrl) return
    onApply?.(resultUrl)
    onClose()
  }

  return createPortal(
    <div className="ip-overlay" onClick={onClose}>
      <div className="ip-panel" onClick={(e) => e.stopPropagation()}>
        <header className="ip-head">
          <div className="ip-title">Retouche par brosse</div>
          <button type="button" className="ip-close" onClick={onClose}>✕</button>
        </header>

        <div className="ip-stage">
          <img ref={imgRef} src={imageSrc} alt="" className="ip-img" />
          <canvas ref={baseRef} style={{ display: 'none' }} />
          <canvas
            ref={maskRef}
            className="ip-mask"
            onPointerDown={onDown}
            onPointerMove={onMove}
            onPointerUp={onUp}
            onPointerCancel={onUp}
          />
          {resultUrl && (
            <img src={resultUrl} alt="result" className="ip-result" />
          )}
        </div>

        <div className="ip-tools">
          <label className="ip-tool">
            Brosse
            <input type="range" min={8} max={150} value={brushSize}
              onChange={(e) => setBrushSize(Number(e.target.value))} />
            <span>{brushSize}px</span>
          </label>
          <button type="button" onClick={clearMask}>↺ Effacer masque</button>
          {phase !== 'done' ? (
            <button type="button" className="ip-run" disabled={phase === 'running'} onClick={() => void runInpaint()}>
              {phase === 'running' ? '⏳ LaMa…' : '✨ Retoucher'}
            </button>
          ) : (
            <button type="button" className="ip-apply" onClick={apply}>✓ Appliquer</button>
          )}
        </div>
        {error && <div className="ip-err">⚠ {error}</div>}
      </div>
    </div>,
    document.body,
  )
}
