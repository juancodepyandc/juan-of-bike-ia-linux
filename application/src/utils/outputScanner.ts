import { getBridgeUrl, isTauriRuntime } from './runtime.ts'
import { safeParseJson } from './errors.ts'

export interface ScannedFile {
  name: string
  path: string
  modified: number // epoch ms
  size: number
}

/**
 * Scanne un repertoire de sortie pour trouver des fichiers generes.
 * Fonctionne en Tauri (fs_list_dir), cloud/browser (bridge /api/generated-files).
 */
export async function scanOutputFiles(
  dir: string,
  afterTimestamp: number,
  pattern?: string,
): Promise<ScannedFile[]> {
  try {
    if (isTauriRuntime()) {
      return await scanViaTauri(dir, afterTimestamp, pattern)
    }
    return await scanViaBridge(afterTimestamp, pattern)
  } catch {
    return []
  }
}

async function scanViaTauri(
  dir: string,
  afterTimestamp: number,
  pattern?: string,
): Promise<ScannedFile[]> {
  try {
    const { runWorkspaceCommand } = await import('../hooks/useTauri')

    const result = await runWorkspaceCommand(
      'powershell',
      [
        '-NoProfile', '-Command',
        `Get-ChildItem -Path '${dir.replace(/'/g, "''")}' -File -Recurse | ` +
        `Where-Object { $_.LastWriteTime -gt (Get-Date '${new Date(afterTimestamp).toISOString()}') } | ` +
        `ForEach-Object { @{ name=$_.Name; path=$_.FullName; modified=[long]($_.LastWriteTimeUtc - [datetime]'1970-01-01').TotalMilliseconds; size=$_.Length } } | ` +
        `ConvertTo-Json -Compress`,
      ],
      dir,
      5000,
    )

    if (!result.ok || !result.output.trim()) return []

    const parsed = JSON.parse(result.output)
    const files: ScannedFile[] = Array.isArray(parsed) ? parsed : [parsed]

    return files
      .filter(f => f.modified > afterTimestamp)
      .filter(f => !pattern || new RegExp(pattern, 'i').test(f.name))
      .sort((a, b) => b.modified - a.modified)
  } catch {
    return []
  }
}

async function scanViaBridge(
  afterTimestamp: number,
  pattern?: string,
): Promise<ScannedFile[]> {
  try {
    const base = getBridgeUrl()
    const resp = await fetch(`${base}/api/generated-files`, {
      signal: AbortSignal.timeout(4000),
    })
    if (!resp.ok) return []

    const files = await safeParseJson<Array<{
      name: string
      path: string
      modified: number // epoch seconds from bridge
      size: number
    }>>(resp, 'Generated files scan')

    return files
      .filter(f => (f.modified * 1000) > afterTimestamp) // bridge retourne en secondes
      .filter(f => !pattern || new RegExp(pattern, 'i').test(f.name))
      .map(f => ({ ...f, modified: f.modified * 1000 }))
      .sort((a, b) => b.modified - a.modified)
  } catch {
    return []
  }
}
