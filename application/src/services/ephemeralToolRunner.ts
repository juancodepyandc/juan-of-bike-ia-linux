import { runWorkspaceCommand, getWorkspacePath } from '../hooks/useTauri.ts'

export interface EphemeralToolRequest {
  name: string
  packages?: string[]
  scriptCode: string
  autoCleanup?: boolean
  timeoutSeconds?: number
  envVars?: Record<string, string>
}

export interface EphemeralToolFile {
  name: string
  relpath: string
  size: number
  path: string
}

export interface EphemeralToolResponse {
  ok: boolean
  stdout: string
  stderr: string
  producedFiles: EphemeralToolFile[]
  elapsedSeconds: number
  cleanedUp: boolean
  error?: string
}

/**
 * Exécute un outil ou script spécialisé dans un bac à sable éphémère.
 * Installe les dépendances nécessaires à la volée, exécute la charge utile,
 * extrait les artefacts produits et désinstalle / purge automatiquement
 * l'environnement pour préserver les ressources de la machine hôte.
 */
export async function runEphemeralToolSandbox(
  req: EphemeralToolRequest
): Promise<EphemeralToolResponse> {
  const workspace = await getWorkspacePath()
  const scriptArgs = [
    'python-services/ephemeral_tool_sandbox.py',
    '--name', req.name,
    '--timeout', String(req.timeoutSeconds || 180),
  ]

  if (req.autoCleanup === false) {
    scriptArgs.push('--no-cleanup')
  }

  if (req.packages && req.packages.length > 0) {
    scriptArgs.push('--packages', ...req.packages)
  }

  scriptArgs.push('--script', req.scriptCode)

  try {
    const output = await runWorkspaceCommand(
      'python3',
      scriptArgs,
      workspace
    )

    const rawText = typeof output === 'string' ? output : (output?.output || '')
    const parsed = JSON.parse(rawText.trim())
    return {
      ok: parsed.ok ?? false,
      stdout: parsed.stdout ?? '',
      stderr: parsed.stderr ?? '',
      producedFiles: (parsed.produced_files || []).map((f: Record<string, unknown>) => ({
        name: String(f.name || ''),
        relpath: String(f.relpath || ''),
        size: Number(f.size || 0),
        path: String(f.path || ''),
      })),
      elapsedSeconds: Number(parsed.elapsed_s || 0),
      cleanedUp: parsed.cleaned_up ?? true,
      error: parsed.error,
    }
  } catch (err) {
    return {
      ok: false,
      stdout: '',
      stderr: err instanceof Error ? err.message : String(err),
      producedFiles: [],
      elapsedSeconds: 0,
      cleanedUp: true,
      error: err instanceof Error ? err.message : String(err),
    }
  }
}
