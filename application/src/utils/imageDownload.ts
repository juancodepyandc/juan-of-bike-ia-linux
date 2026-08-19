import { loadBlob } from './blobStore.ts'

export type ImageDownloadFormat = 'png' | 'jpeg' | 'webp'

export interface UniversalDownloadItem {
  id?: string
  url: string
  prompt?: string
  style?: string
  timestamp?: number
}

export interface UniversalDownloadOptions {
  filename?: string
  format?: ImageDownloadFormat
  quality?: number
  preferShareOnMobile?: boolean
}

/**
 * Resolves a Blob from various possible sources:
 * - Direct Blob instance
 * - Stored IndexedDB Blob via card ID
 * - Remote URL / Proxy / Object URL via fetch
 * - Fallback through HTML Canvas if necessary
 */
export async function resolveImageBlob(
  source: string | Blob | UniversalDownloadItem,
  cardIdHint?: string,
): Promise<Blob | null> {
  if (source instanceof Blob) {
    return source
  }

  const id = typeof source === 'object' ? source.id : cardIdHint
  const url = typeof source === 'object' ? source.url : source

  if (id) {
    const idbBlob = await loadBlob(id)
    if (idbBlob && idbBlob.size > 0) {
      return idbBlob
    }
  }

  if (!url || typeof url !== 'string') return null

  // 1. Direct fetch attempt
  try {
    const resp = await fetch(url, { mode: 'cors' })
    if (resp.ok) {
      const b = await resp.blob()
      if (b && b.size > 0) return b
    }
  } catch {
    // Continue to canvas fallback
  }

  // 2. Canvas fallback for cross-origin / taint-safe extraction
  try {
    return await new Promise<Blob | null>((resolve) => {
      const img = new Image()
      img.crossOrigin = 'anonymous'
      img.onload = () => {
        try {
          const canvas = document.createElement('canvas')
          canvas.width = img.naturalWidth || img.width
          canvas.height = img.naturalHeight || img.height
          const ctx = canvas.getContext('2d')
          if (!ctx) return resolve(null)
          ctx.drawImage(img, 0, 0)
          canvas.toBlob((blob) => resolve(blob), 'image/png')
        } catch {
          resolve(null)
        }
      }
      img.onerror = () => resolve(null)
      img.src = url
    })
  } catch {
    return null
  }
}

/**
 * Converts a blob to the desired image format (png, jpeg, webp) if needed.
 */
export async function convertBlobFormat(
  blob: Blob,
  format: ImageDownloadFormat = 'png',
  quality = 0.92,
): Promise<Blob> {
  const targetMime = format === 'jpeg' ? 'image/jpeg' : format === 'webp' ? 'image/webp' : 'image/png'
  if (blob.type === targetMime) return blob

  try {
    const bitmap = typeof createImageBitmap === 'function' ? await createImageBitmap(blob) : null
    const canvas = document.createElement('canvas')
    const ctx = canvas.getContext('2d')
    if (!ctx) return blob

    if (bitmap) {
      canvas.width = bitmap.width
      canvas.height = bitmap.height
      if (format === 'jpeg') {
        ctx.fillStyle = '#ffffff'
        ctx.fillRect(0, 0, canvas.width, canvas.height)
      }
      ctx.drawImage(bitmap, 0, 0)
      bitmap.close()
    } else {
      const img = await new Promise<HTMLImageElement>((resolve, reject) => {
        const i = new Image()
        const objectUrl = URL.createObjectURL(blob)
        i.onload = () => { URL.revokeObjectURL(objectUrl); resolve(i) }
        i.onerror = () => { URL.revokeObjectURL(objectUrl); reject(new Error('Image decode error')) }
        i.src = objectUrl
      })
      canvas.width = img.naturalWidth || img.width
      canvas.height = img.naturalHeight || img.height
      if (format === 'jpeg') {
        ctx.fillStyle = '#ffffff'
        ctx.fillRect(0, 0, canvas.width, canvas.height)
      }
      ctx.drawImage(img, 0, 0)
    }

    const converted = await new Promise<Blob | null>((resolve) => {
      canvas.toBlob((b) => resolve(b), targetMime, format === 'png' ? undefined : quality)
    })

    return converted || blob
  } catch {
    return blob
  }
}

/**
 * Builds an organized path and filename reflecting user intent and environment:
 * Structure: output/image/<context>/<session>/<mode>_<prompt_slug>_<timestamp>.<ext>
 * where context is 'cli' | 'ui' | 'tunnel'.
 */
export function buildIntentFilename(
  source: string | Blob | UniversalDownloadItem,
  options: {
    format?: ImageDownloadFormat
    context?: 'cli' | 'ui' | 'tunnel'
    sessionId?: string
    intentMode?: string
  } = {},
): { filename: string; relativeDir: string; fullPath: string } {
  const format = options.format || 'png'
  const ext = format === 'jpeg' ? 'jpg' : format
  const isObj = typeof source === 'object' && !(source instanceof Blob)
  const prompt = isObj ? (source as UniversalDownloadItem).prompt || '' : ''
  const mode = options.intentMode || (isObj ? ((source as any).editMode || (source as any).mode) : null) || 'creation'
  const modeSlug = String(mode).toLowerCase().replace(/[^a-z0-9]+/g, '_').slice(0, 16) || 'creation'

  const promptSlug = prompt
    ? prompt
        .toLowerCase()
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .replace(/[^a-z0-9]+/g, '_')
        .replace(/^_+|_+$/g, '')
        .slice(0, 32)
    : 'image'

  const ts = (isObj ? (source as UniversalDownloadItem).timestamp : null) || Date.now()
  const filename = `${modeSlug}_${promptSlug}_${ts}.${ext}`

  const isTunnel = typeof window !== 'undefined' && (
    window.location.hostname.includes('trycloudflare.com') ||
    window.location.hostname.includes('ngrok') ||
    window.location.hostname.includes('loca.lt')
  )
  const context = options.context || (isTunnel ? 'tunnel' : 'ui')
  const sessionFolder = (options.sessionId || (isObj ? ((source as any).sessionId) : null) || new Date(ts).toISOString().slice(0, 10)).replace(/[^a-z0-9_.-]+/gi, '_')
  const relativeDir = `output/image/${context}/${sessionFolder}`
  const fullPath = `${relativeDir}/${filename}`

  return { filename, relativeDir, fullPath }
}

function buildDefaultFilename(source: string | Blob | UniversalDownloadItem, format: ImageDownloadFormat): string {
  return buildIntentFilename(source, { format }).filename
}

function isMobileDevice(): boolean {
  if (typeof navigator === 'undefined') return false
  const ua = navigator.userAgent || ''
  return /android|iphone|ipad|ipod|windows phone|mobile/i.test(ua)
}

/**
 * Universal image download function that works on:
 * - PC (Tauri desktop app, localhost, Cloudflare / ngrok tunnel)
 * - Mobile (iOS Safari, Android Chrome, WebViews, mobile browsers via tunnel)
 */
export async function downloadImageUniversal(
  source: string | Blob | UniversalDownloadItem,
  options: UniversalDownloadOptions = {},
): Promise<{ ok: boolean; method: string; filename: string }> {
  const format = options.format || 'png'
  const filename = options.filename || buildDefaultFilename(source, format)

  // 1. Resolve raw binary blob
  const rawBlob = await resolveImageBlob(source)

  if (typeof document === 'undefined') {
    return { ok: true, method: rawBlob ? 'blob-ready' : 'url-ready', filename }
  }

  if (!rawBlob) {
    // Fallback: if we only have a URL and blob resolution failed, try opening or direct anchor
    const url = typeof source === 'string' ? source : typeof source === 'object' && !(source instanceof Blob) ? source.url : null
    if (url) {
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      a.target = '_blank'
      document.body.appendChild(a)
      a.click()
      setTimeout(() => a.remove(), 1000)
      return { ok: true, method: 'direct-url', filename }
    }
    return { ok: false, method: 'none', filename }
  }

  // 2. Convert format if requested
  const finalBlob = await convertBlobFormat(rawBlob, format, options.quality)
  const mime = finalBlob.type || 'image/png'

  // 3. On mobile: try Web Share API with File payload (allows saving directly to Photos / Gallery)
  if (isMobileDevice() && options.preferShareOnMobile !== false) {
    try {
      const file = new File([finalBlob], filename, { type: mime })
      if (typeof navigator !== 'undefined' && navigator.canShare && navigator.canShare({ files: [file] })) {
        await navigator.share({
          files: [file],
          title: filename,
        })
        return { ok: true, method: 'web-share', filename }
      }
    } catch (shareErr) {
      // If user dismissed share or platform failed, fallback to direct download anchor
      if ((shareErr as Error)?.name === 'AbortError') {
        return { ok: true, method: 'web-share-cancelled', filename }
      }
    }
  }

  // 4. Standard Blob Object URL download anchor
  try {
    const objectUrl = URL.createObjectURL(finalBlob)
    const anchor = document.createElement('a')
    anchor.style.display = 'none'
    anchor.href = objectUrl
    anchor.download = filename
    document.body.appendChild(anchor)
    anchor.click()

    // Clean up after small delay to let download start
    setTimeout(() => {
      anchor.remove()
      URL.revokeObjectURL(objectUrl)
    }, 2500)

    return { ok: true, method: 'object-url', filename }
  } catch {
    // 5. Data URL fallback (useful for iOS Safari or restricted webviews)
    try {
      const dataUrl = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader()
        reader.onloadend = () => resolve(reader.result as string)
        reader.onerror = () => reject(new Error('FileReader failed'))
        reader.readAsDataURL(finalBlob)
      })

      const anchor = document.createElement('a')
      anchor.style.display = 'none'
      anchor.href = dataUrl
      anchor.download = filename
      document.body.appendChild(anchor)
      anchor.click()
      setTimeout(() => anchor.remove(), 2500)

      return { ok: true, method: 'data-url', filename }
    } catch {
      return { ok: false, method: 'failed', filename }
    }
  }
}

/**
 * Downloads multiple generated images as a single ZIP archive.
 */
export async function downloadImagesAsZip(
  images: UniversalDownloadItem[],
  zipFilename = `aurora-images-${Date.now()}.zip`,
): Promise<boolean> {
  if (!images || images.length === 0) return false

  try {
    const { default: JSZip } = await import('jszip')
    const zip = new JSZip()

    await Promise.all(
      images.map(async (item, index) => {
        const blob = await resolveImageBlob(item)
        if (!blob) return
        const ext = blob.type === 'image/jpeg' ? 'jpg' : blob.type === 'image/webp' ? 'webp' : 'png'
        const rank = String(index + 1).padStart(2, '0')
        const slug = item.prompt ? item.prompt.toLowerCase().replace(/[^a-z0-9]+/g, '_').slice(0, 30) : 'image'
        const name = `${rank}_${slug}_${item.id || item.timestamp || Date.now()}.${ext}`
        zip.file(name, blob)
      }),
    )

    const zipBlob = await zip.generateAsync({ type: 'blob' })
    const zipUrl = URL.createObjectURL(zipBlob)
    const anchor = document.createElement('a')
    anchor.style.display = 'none'
    anchor.href = zipUrl
    anchor.download = zipFilename
    document.body.appendChild(anchor)
    anchor.click()

    setTimeout(() => {
      anchor.remove()
      URL.revokeObjectURL(zipUrl)
    }, 3000)

    return true
  } catch (err) {
    console.warn('[imageDownload] ZIP export failed:', err)
    return false
  }
}
