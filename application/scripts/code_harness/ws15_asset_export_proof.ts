import { createHash } from 'node:crypto'
import { readFile, writeFile } from 'node:fs/promises'
import path from 'node:path'
import JSZip from 'jszip'
import { CODE_ASSET_MANIFEST_PATH, type CodeAssetBundle } from '../../src/services/codeInterModuleAssets.ts'
import { buildProjectZipBlob } from '../../src/utils/codeDownload.ts'

const root = process.cwd()
const runId = process.argv[2] || 'ws15-live-selected-v6'
const bridgeUrl = (process.argv[3] || 'http://127.0.0.1:3001').replace(/\/$/, '')
const bundlePath = path.join(root, 'output', 'code_assets', runId, 'asset-bundle.json')
const proofDir = path.join(root, 'output', 'ws15_inter_module_proof')
const zipPath = path.join(proofDir, `${runId}_project_export.zip`)
const bundle = JSON.parse(await readFile(bundlePath, 'utf8')) as CodeAssetBundle

function absoluteUrl(value?: string) {
  return value && /^https?:\/\//i.test(value)
    ? value
    : `${bridgeUrl}/${String(value || '').replace(/^\//, '')}`
}

const manifestAssets = bundle.assets.map((asset) => ({
  ...asset,
  previewUrl: absoluteUrl(asset.previewUrl),
  variants: asset.variants?.map((variant) => ({
    ...variant,
    previewUrl: absoluteUrl(variant.previewUrl),
  })),
}))
const previewUrls = manifestAssets.map((asset) => asset.previewUrl)
const files = [
  {
    name: 'src/assets.ts',
    language: 'ts',
    content: previewUrls.map((url, index) => `export const asset${index} = ${JSON.stringify(url)}`).join('\n'),
  },
  {
    name: CODE_ASSET_MANIFEST_PATH,
    language: 'json',
    content: JSON.stringify({
      schemaVersion: bundle.schemaVersion,
      runId: bundle.runId,
      assets: manifestAssets,
    }, null, 2),
  },
]

const blob = await buildProjectZipBlob(files)
const zipBytes = Buffer.from(await blob.arrayBuffer())
await writeFile(zipPath, zipBytes)
const zip = await JSZip.loadAsync(zipBytes)
const checks: Array<{ path: string; bytes: number; sha256: string; sourceMatch: boolean }> = []
const checkedPaths = new Set<string>()

for (const asset of bundle.assets) {
  const entries = [asset, ...(asset.variants || [])]
  for (const entry of entries) {
    if (checkedPaths.has(entry.path)) continue
    checkedPaths.add(entry.path)
    const archived = await zip.file(entry.path)?.async('uint8array')
    if (!archived) throw new Error(`asset absent du ZIP: ${entry.path}`)
    const sourcePath = entry.storagePath
    if (!sourcePath) throw new Error(`storagePath absent: ${entry.path}`)
    const source = await readFile(path.join(root, sourcePath))
    const archivedHash = createHash('sha256').update(archived).digest('hex')
    const sourceHash = createHash('sha256').update(source).digest('hex')
    checks.push({
      path: entry.path,
      bytes: archived.byteLength,
      sha256: archivedHash,
      sourceMatch: archivedHash === sourceHash,
    })
  }
}

const exportedSource = await zip.file('src/assets.ts')?.async('string')
const report = {
  schemaVersion: 'aurora.code.ws15-export-proof/1',
  ok: checks.every((check) => check.sourceMatch) && !exportedSource?.includes(bridgeUrl),
  runId,
  zipPath: path.relative(root, zipPath),
  zipBytes: zipBytes.byteLength,
  archiveEntries: Object.keys(zip.files).filter((name) => !zip.files[name].dir).sort(),
  bridgeUrlsRemaining: exportedSource?.includes(bridgeUrl) ?? false,
  checks,
}

process.stdout.write(`${JSON.stringify(report, null, 2)}\n`)
if (!report.ok) process.exitCode = 1
