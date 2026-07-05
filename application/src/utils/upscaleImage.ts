/**
 * upscaleImage — two-tier image upscaling.
 *
 * Tier 1 (fast, always works) : canvas bicubic — 2x or 4x client-side.
 * Tier 2 (needs ComfyUI + ESRGAN weight) : `ImageUpscaleWithModel` if a
 * .pth/.safetensors weight is present in ComfyUI/models/upscale_models.
 * Falls back to tier 1 transparently.
 *
 * The image module calls `upscaleAuto(dataUrl, scale)` and gets a new URL.
 */
import { comfyuiGetImage, comfyuiQueuePrompt } from '../hooks/useTauri'

async function fetchBlob(src: string): Promise<Blob> {
  const r = await fetch(src, { cache: 'no-store' })
  if (!r.ok) throw new Error(`fetch ${src} → ${r.status}`)
  return r.blob()
}

async function canvasUpscale(src: string, scale: 2 | 4): Promise<string> {
  const img = await new Promise<HTMLImageElement>((resolve, reject) => {
    const i = new Image()
    i.crossOrigin = 'anonymous'
    i.onload = () => resolve(i)
    i.onerror = (e) => reject(e)
    i.src = src
  })
  const w = img.naturalWidth * scale
  const h = img.naturalHeight * scale
  const c = document.createElement('canvas')
  c.width = w; c.height = h
  const ctx = c.getContext('2d')!
  ctx.imageSmoothingEnabled = true
  ctx.imageSmoothingQuality = 'high'
  ctx.drawImage(img, 0, 0, w, h)
  return new Promise<string>((resolve, reject) => {
    c.toBlob((b) => b ? resolve(URL.createObjectURL(b)) : reject(new Error('toBlob failed')), 'image/png')
  })
}

/** Try ComfyUI ImageUpscaleWithModel; return null if unavailable. */
async function comfyEsrgan(src: string, scale: 2 | 4): Promise<string | null> {
  try {
    // Probe for any upscale model in models/upscale_models via /models endpoint
    const mr = await fetch('http://127.0.0.1:8188/object_info/UpscaleModelLoader').catch(() => null)
    if (!mr || !mr.ok) return null
    const info = await mr.json() as { UpscaleModelLoader?: { input?: { required?: { model_name?: [string[]] } } } }
    const choices = info.UpscaleModelLoader?.input?.required?.model_name?.[0]
    const modelName = choices?.find((n: string) => /esrgan|ultrasharp|realesr/i.test(n)) || choices?.[0]
    if (!modelName) return null

    // Upload the source image to ComfyUI
    const blob = await fetchBlob(src)
    const fd = new FormData()
    fd.append('image', blob, `upscale_src_${Date.now()}.png`)
    const up = await fetch('http://127.0.0.1:8188/upload/image', { method: 'POST', body: fd })
    if (!up.ok) return null
    const { name: uploadedName } = await up.json() as { name: string }

    const workflow = {
      prompt: {
        "1": { class_type: "LoadImage", inputs: { image: uploadedName } },
        "2": { class_type: "UpscaleModelLoader", inputs: { model_name: modelName } },
        "3": { class_type: "ImageUpscaleWithModel", inputs: { upscale_model: ["2", 0], image: ["1", 0] } },
        // Many ESRGAN weights scale 4x; scale down to the requested ratio
        "4": { class_type: "ImageScale", inputs: {
          image: ["3", 0], upscale_method: "lanczos",
          width: 0, height: 0, crop: "disabled",
        } },
        "5": { class_type: "SaveImage", inputs: { images: ["3", 0], filename_prefix: "aurora_upscale" } },
      },
      client_id: `aurora_upscale_${Date.now()}`,
    }
    // Simpler: always save node 3 (the ESRGAN output directly, whatever its scale)
    const q = await comfyuiQueuePrompt(workflow) as unknown as string
    const parsed = typeof q === 'string' ? JSON.parse(q) : q
    const promptId = parsed?.prompt_id as string | undefined
    if (!promptId) return null

    const start = Date.now()
    while (Date.now() - start < 180000) {
      await new Promise((r) => setTimeout(r, 1200))
      const hr = await fetch(`http://127.0.0.1:8188/history/${promptId}`)
      if (!hr.ok) continue
      const hist = await hr.json() as Record<string, { outputs?: Record<string, { images?: Array<{ filename: string; subfolder?: string; type?: string }> }> }>
      const img = hist[promptId]?.outputs?.["5"]?.images?.[0]
      if (img) {
        const outBlob = await comfyuiGetImage(img.filename, img.subfolder || '')
        // If the requested scale is 2x but the model is 4x, scale down client-side
        const url = URL.createObjectURL(outBlob)
        if (scale === 4) return url
        try { return await canvasUpscale(url, scale === 2 ? 2 : 4) } catch { return url }
      }
    }
    return null
  } catch {
    return null
  }
}

export async function upscaleAuto(src: string, scale: 2 | 4 = 2): Promise<{ url: string; method: 'esrgan' | 'bicubic' }> {
  const viaEsrgan = await comfyEsrgan(src, scale)
  if (viaEsrgan) return { url: viaEsrgan, method: 'esrgan' }
  const viaCanvas = await canvasUpscale(src, scale)
  return { url: viaCanvas, method: 'bicubic' }
}
