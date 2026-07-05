/**
 * pdfExtract — client-side PDF → plain text via pdfjs-dist.
 *
 * We dynamically import pdfjs-dist and its worker so the bundle stays small
 * when no one ever imports a PDF. The worker is loaded via `?url` so Vite
 * serves it as a standalone asset.
 */

export async function extractPdfText(file: File, maxPages = 20): Promise<string> {
  const [{ getDocument, GlobalWorkerOptions }, workerUrlMod] = await Promise.all([
    import('pdfjs-dist'),
    // @ts-ignore — Vite ?url import returns a string
    import('pdfjs-dist/build/pdf.worker.mjs?url'),
  ])
  GlobalWorkerOptions.workerSrc = (workerUrlMod as { default: string }).default

  const buf = await file.arrayBuffer()
  const pdf = await getDocument({ data: buf }).promise
  const pages = Math.min(pdf.numPages, maxPages)
  const chunks: string[] = []
  for (let p = 1; p <= pages; p++) {
    const page = await pdf.getPage(p)
    const content = await page.getTextContent()
    const text = content.items
      .map((it: any) => ('str' in it ? it.str : ''))
      .join(' ')
      .replace(/[ \t]+/g, ' ')
      .trim()
    if (text) chunks.push(text)
  }
  return chunks.join('\n\n')
}

/**
 * v82cj : render chaque page d'un PDF en File image PNG. Utilisé en
 * fallback automatique pour les PDF scannés (sans texte extractible)
 * → l'user upload un PDF photographié, on rend les pages, et la
 * vision multimodale (qwen3-vl) fait l'OCR + l'analyse.
 *
 * Limite stricte (maxPages = 6) pour ne pas saturer le contexte
 * vision et garder un temps de génération raisonnable. Scale 1.5
 * équivalent à 144 dpi pour un A4 standard — suffisant pour OCR.
 */
export async function renderPdfPagesToImages(
  file: File,
  maxPages = 6,
  scale = 1.5,
): Promise<File[]> {
  const [{ getDocument, GlobalWorkerOptions }, workerUrlMod] = await Promise.all([
    import('pdfjs-dist'),
    // @ts-ignore — Vite ?url import returns a string
    import('pdfjs-dist/build/pdf.worker.mjs?url'),
  ])
  GlobalWorkerOptions.workerSrc = (workerUrlMod as { default: string }).default

  const buf = await file.arrayBuffer()
  const pdf = await getDocument({ data: buf }).promise
  const pages = Math.min(pdf.numPages, maxPages)
  const out: File[] = []
  for (let p = 1; p <= pages; p++) {
    const page = await pdf.getPage(p)
    const viewport = page.getViewport({ scale })
    const canvas = document.createElement('canvas')
    canvas.width = Math.ceil(viewport.width)
    canvas.height = Math.ceil(viewport.height)
    const ctx = canvas.getContext('2d')
    if (!ctx) continue
    await page.render({ canvasContext: ctx, viewport, canvas }).promise
    const blob: Blob | null = await new Promise((resolve) =>
      canvas.toBlob((b) => resolve(b), 'image/png', 0.92),
    )
    if (!blob) continue
    const safe = (file.name || 'page').replace(/\.[^.]+$/, '').replace(/[^a-zA-Z0-9_-]+/g, '_')
    out.push(new File([blob], `${safe}_p${p}.png`, { type: 'image/png' }))
  }
  return out
}
