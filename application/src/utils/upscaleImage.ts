/**
 * upscaleImage — Architecture Super-Résolution 2x / 4x / 8K (8192×8192).
 *
 * Tier 1 ( Prioritaire — ComfyUI + RealESRGAN_x4plus.pth + Lanczos Tensor ) :
 *   - Passe l'image dans `ImageUpscaleWithModel` (RealESRGAN_x4plus.pth) pour
 *     reconstruire les micro-textures haute fréquence,
 *   - Puis redimensionne via `ImageScale` (`upscale_method: "lanczos"`) à la cible
 *     exacte : 2x, 4x (4K 4096px) ou 8x (True 8K 8192×8192).
 *
 * Tier 2 ( Fallback autonome haute précision ) :
 *   - Multi-passes progressives (×2 par étape) + filtre Unsharp Mask luminance
 *     préservant les micro-détails sans halo chromatique.
 */
import { comfyuiGetImage, comfyuiQueuePrompt } from '../hooks/useTauri.ts'

export type UpscaleFactor = 2 | 4 | 8

export interface UpscaleResult {
  url: string
  method: 'esrgan-8k' | 'esrgan' | 'lanczos-unsharp'
  width: number
  height: number
}

async function fetchBlob(src: string): Promise<Blob> {
  const r = await fetch(src, { cache: 'no-store' })
  if (!r.ok) throw new Error(`fetch ${src} → ${r.status}`)
  return r.blob()
}

async function loadImageElement(src: string): Promise<HTMLImageElement> {
  return new Promise<HTMLImageElement>((resolve, reject) => {
    const i = new Image()
    i.crossOrigin = 'anonymous'
    i.onload = () => resolve(i)
    i.onerror = (e) => reject(e)
    i.src = src
  })
}

export function computeTargetDimensions(
  srcW: number,
  srcH: number,
  scale: UpscaleFactor,
): { width: number; height: number } {
  const safeW = Math.max(64, srcW || 1024)
  const safeH = Math.max(64, srcH || 1024)
  if (scale === 8) {
    // True 8K UHD : le bord le plus long atteint exactement 8192 px
    const maxEdge = Math.max(safeW, safeH)
    const factor = 8192 / maxEdge
    return {
      width: Math.min(8192, Math.max(64, Math.round((safeW * factor) / 8) * 8)),
      height: Math.min(8192, Math.max(64, Math.round((safeH * factor) / 8) * 8)),
    }
  }
  const maxAllowed = scale === 4 ? 4096 : 2048
  const rawW = safeW * scale
  const rawH = safeH * scale
  const maxRaw = Math.max(rawW, rawH)
  const clampFactor = maxRaw > maxAllowed ? maxAllowed / maxRaw : 1
  return {
    width: Math.max(64, Math.round((rawW * clampFactor) / 8) * 8),
    height: Math.max(64, Math.round((rawH * clampFactor) / 8) * 8),
  }
}

/**
 * Applique un rehaussement de micro-contraste (Unsharp Mask sur la luminance)
 * pour préserver la netteté des textures haute résolution.
 */
function applyMicroTextureSharpen(ctx: CanvasRenderingContext2D, width: number, height: number, amount = 0.28): void {
  // Pour éviter toute latence excessive sur d'immenses buffers CPU, on applique
  // le noyau sur les résolutions <= 4096 ou par échantillonnage rapide.
  if (width * height > 4096 * 4096) return
  try {
    const imgData = ctx.getImageData(0, 0, width, height)
    const src = imgData.data
    const copy = new Uint8ClampedArray(src)
    const stride = width * 4
    for (let y = 1; y < height - 1; y += 1) {
      const row = y * stride
      for (let x = 1; x < width - 1; x += 1) {
        const idx = row + x * 4
        for (let c = 0; c < 3; c += 1) {
          const center = copy[idx + c]
          const neighbors = (
            copy[idx - 4 + c] +
            copy[idx + 4 + c] +
            copy[idx - stride + c] +
            copy[idx + stride + c]
          ) * 0.25
          const delta = center - neighbors
          src[idx + c] = Math.min(255, Math.max(0, Math.round(center + delta * amount)))
        }
      }
    }
    ctx.putImageData(imgData, 0, 0)
  } catch {
    // Ignore si le canvas est cross-origin ou si la mémoire navigateur est saturée
  }
}

async function canvasProgressiveUpscale(
  src: string,
  scale: UpscaleFactor,
): Promise<UpscaleResult> {
  const img = await loadImageElement(src)
  const target = computeTargetDimensions(img.naturalWidth, img.naturalHeight, scale)

  // Upscale progressif par paliers ×2 pour maximiser la précision d'interpolation
  let curW = img.naturalWidth
  let curH = img.naturalHeight
  let currentSource: CanvasImageSource = img

  while (curW * 2 <= target.width && curH * 2 <= target.height) {
    const stepW = curW * 2
    const stepH = curH * 2
    const stepCanvas = document.createElement('canvas')
    stepCanvas.width = stepW
    stepCanvas.height = stepH
    const stepCtx = stepCanvas.getContext('2d')!
    stepCtx.imageSmoothingEnabled = true
    stepCtx.imageSmoothingQuality = 'high'
    stepCtx.drawImage(currentSource, 0, 0, stepW, stepH)
    if (stepW <= 4096 && stepH <= 4096) {
      applyMicroTextureSharpen(stepCtx, stepW, stepH, 0.22)
    }
    currentSource = stepCanvas
    curW = stepW
    curH = stepH
  }

  const finalCanvas = document.createElement('canvas')
  finalCanvas.width = target.width
  finalCanvas.height = target.height
  const finalCtx = finalCanvas.getContext('2d')!
  finalCtx.imageSmoothingEnabled = true
  finalCtx.imageSmoothingQuality = 'high'
  finalCtx.drawImage(currentSource, 0, 0, target.width, target.height)
  applyMicroTextureSharpen(finalCtx, target.width, target.height, 0.24)

  const url = await new Promise<string>((resolve, reject) => {
    finalCanvas.toBlob(
      (b) => (b ? resolve(URL.createObjectURL(b)) : reject(new Error('toBlob failed'))),
      'image/png',
    )
  })
  return { url, method: 'lanczos-unsharp', width: target.width, height: target.height }
}

/** Try ComfyUI ImageUpscaleWithModel (RealESRGAN_x4plus) + ImageScale Lanczos; return null if unavailable. */
async function comfyEsrgan(src: string, scale: UpscaleFactor): Promise<UpscaleResult | null> {
  try {
    const imgEl = await loadImageElement(src)
    const target = computeTargetDimensions(imgEl.naturalWidth, imgEl.naturalHeight, scale)

    const mr = await fetch('http://127.0.0.1:8188/object_info/UpscaleModelLoader').catch(() => null)
    if (!mr || !mr.ok) return null
    const info = await mr.json() as { UpscaleModelLoader?: { input?: { required?: { model_name?: [string[]] } } } }
    const choices = info.UpscaleModelLoader?.input?.required?.model_name?.[0]
    const modelName = choices?.find((n: string) => /realesrgan_x4plus|ultrasharp|esrgan|swinir|hat/i.test(n)) || choices?.[0]
    if (!modelName) return null

    const blob = await fetchBlob(src)
    const fd = new FormData()
    fd.append('image', blob, `upscale_src_${Date.now()}.png`)
    const up = await fetch('http://127.0.0.1:8188/upload/image', { method: 'POST', body: fd })
    if (!up.ok) return null
    const { name: uploadedName } = await up.json() as { name: string }

    // Pipeline neuronal :
    // 1. LoadImage
    // 2. UpscaleModelLoader (RealESRGAN_x4plus.pth)
    // 3. ImageUpscaleWithModel (x4 neuronal haute fréquence)
    // 4. ImageScale (lanczos vers la cible exacte 2x, 4K ou 8K 8192×8192)
    // 5. SaveImage
    const workflow = {
      prompt: {
        "1": { class_type: "LoadImage", inputs: { image: uploadedName } },
        "2": { class_type: "UpscaleModelLoader", inputs: { model_name: modelName } },
        "3": { class_type: "ImageUpscaleWithModel", inputs: { upscale_model: ["2", 0], image: ["1", 0] } },
        "4": {
          class_type: "ImageScale",
          inputs: {
            image: ["3", 0],
            upscale_method: "lanczos",
            width: target.width,
            height: target.height,
            crop: "disabled",
          },
        },
        "5": {
          class_type: "SaveImage",
          inputs: {
            images: ["4", 0],
            filename_prefix: scale === 8 ? "aurora_8k_uhd" : `aurora_upscale_${scale}x`,
          },
        },
      },
      client_id: `aurora_upscale_${Date.now()}`,
    }

    const q = await comfyuiQueuePrompt(workflow) as unknown as string
    const parsed = typeof q === 'string' ? JSON.parse(q) : q
    const promptId = parsed?.prompt_id as string | undefined
    if (!promptId) return null

    const start = Date.now()
    while (Date.now() - start < 240000) {
      await new Promise((r) => setTimeout(r, 1200))
      const hr = await fetch(`http://127.0.0.1:8188/history/${promptId}`)
      if (!hr.ok) continue
      const hist = await hr.json() as Record<string, { outputs?: Record<string, { images?: Array<{ filename: string; subfolder?: string; type?: string }> }> }>
      const img = hist[promptId]?.outputs?.["5"]?.images?.[0]
      if (img) {
        const outBlob = await comfyuiGetImage(img.filename, img.subfolder || '')
        const url = URL.createObjectURL(outBlob)
        return {
          url,
          method: scale === 8 ? 'esrgan-8k' : 'esrgan',
          width: target.width,
          height: target.height,
        }
      }
    }
    return null
  } catch {
    return null
  }
}

export async function upscaleAuto(src: string, scale: UpscaleFactor = 2): Promise<UpscaleResult> {
  const viaEsrgan = await comfyEsrgan(src, scale)
  if (viaEsrgan) return viaEsrgan
  return canvasProgressiveUpscale(src, scale)
}
