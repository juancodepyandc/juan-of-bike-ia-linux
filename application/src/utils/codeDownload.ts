/**
 * codeDownload — client-side ZIP export of a generated project.
 *
 * Keeps the "download as currently" behaviour the user asked to preserve,
 * but bundles the WHOLE project tree (every file, nested paths intact)
 * into a single .zip instead of one file at a time. JSZip is already a
 * project dependency.
 */
import type { CodeFile } from '../services/codeOrchestrator'
import {
  collectAssetExportEntries,
  rewriteAssetUrlsForExport,
} from '../services/codeInterModuleAssetIntegration.ts'

function slugify(input: string): string {
  const base = (input || 'aurora-projet')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 48)
  return base || 'aurora-projet'
}

/**
 * Build a .zip from the project files and trigger a browser download.
 * `nameHint` seeds the archive filename (e.g. the prompt or repo label).
 */
export async function downloadProjectZip(files: CodeFile[], nameHint = 'aurora-projet'): Promise<void> {
  if (!files || files.length === 0) return
  const blob = await buildProjectZipBlob(files)
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${slugify(nameHint)}.zip`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  // Revoke a tick later so the download has a chance to start.
  setTimeout(() => URL.revokeObjectURL(url), 4000)
}

export async function buildProjectZipBlob(
  files: CodeFile[],
  fetchImpl: typeof fetch = globalThis.fetch.bind(globalThis),
): Promise<Blob> {
  const { default: JSZip } = await import('jszip')
  const zip = new JSZip()
  const assets = collectAssetExportEntries(files)
  for (const f of files) {
    const rel = (f.name || 'fichier.txt').replace(/^\.\//, '').replace(/^\/+/, '')
    zip.file(rel, rewriteAssetUrlsForExport(f.content ?? '', assets))
  }
  for (const asset of assets) {
    const response = await fetchImpl(asset.url)
    if (!response.ok) {
      throw new Error(`Export asset impossible (${response.status}) : ${asset.path}`)
    }
    zip.file(asset.path, await response.arrayBuffer(), { binary: true })
  }
  return zip.generateAsync({ type: 'blob', compression: 'DEFLATE' })
}

/** Format a seconds count as a compact "m min s s" / "s s" ETA label. */
export function formatEta(seconds: number | null): string {
  if (seconds === null || !Number.isFinite(seconds)) return '—'
  const s = Math.max(0, Math.round(seconds))
  if (s < 60) return `${s} s`
  const m = Math.floor(s / 60)
  const rem = s % 60
  return rem === 0 ? `${m} min` : `${m} min ${rem.toString().padStart(2, '0')} s`
}
