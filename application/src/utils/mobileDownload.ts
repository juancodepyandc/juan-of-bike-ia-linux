import { getBridgeUrl, isTauriRuntime } from './runtime.ts'
import { safeParseJson } from './errors.ts'

/**
 * Telecharge un fichier genere sur le telephone (ou PC en mode browser).
 * En mode Tauri, ouvre le fichier directement.
 * En mode cloud/browser, force le telechargement via le bridge.
 */
export async function downloadGeneratedFile(relativePath: string, filename?: string): Promise<void> {
  if (isTauriRuntime()) {
    // En mode Tauri, ouvrir via le shell
    try {
      const { invoke } = await import('@tauri-apps/api/core')
      await invoke('plugin:shell|open', { path: relativePath })
    } catch {
      // Fallback: ouvrir dans un nouvel onglet
      window.open(`asset://localhost/${relativePath}`, '_blank')
    }
    return
  }

  // Mode bridge (mobile/browser) — forcer le telechargement
  const base = getBridgeUrl()
  const url = `${base}/api/download/${encodeURIComponent(relativePath)}`

  const a = document.createElement('a')
  a.href = url
  a.download = filename || relativePath.split('/').pop() || 'download'
  a.style.display = 'none'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
}

/**
 * Liste les fichiers generes disponibles (images, videos, audio, 3D).
 */
export interface GeneratedFile {
  name: string
  path: string
  size: number
  modified: number
  type: string
}

export async function listGeneratedFiles(): Promise<GeneratedFile[]> {
  if (isTauriRuntime()) {
    // En mode Tauri, lister localement
    try {
      const { invoke } = await import('@tauri-apps/api/core')
      const workspacePath = await invoke<string>('get_workspace_path')
      // Fallback: retourner vide, le bridge n'est pas necessaire en Tauri
      return []
    } catch {
      return []
    }
  }

  const base = getBridgeUrl()
  try {
    const resp = await fetch(`${base}/api/generated-files`)
    if (!resp.ok) return []
    return await safeParseJson<GeneratedFile[]>(resp, 'Generated files')
  } catch {
    return []
  }
}

/**
 * Upload un fichier depuis le telephone vers le serveur.
 * Utilisable pour ajouter des fichiers contexte, des images reference, etc.
 */
export async function uploadFileFromMobile(file: File, targetDir: string = 'uploads'): Promise<string> {
  if (isTauriRuntime()) {
    throw new Error('Upload non necessaire en mode Tauri (acces direct au filesystem)')
  }

  const base = getBridgeUrl()
  const formData = new FormData()
  formData.append('file', file)
  formData.append('targetDir', targetDir)

  const resp = await fetch(`${base}/api/upload`, {
    method: 'POST',
    body: formData,
  })

  if (!resp.ok) throw new Error(`Upload echoue: ${resp.status}`)
  const data = await safeParseJson<{ path: string }>(resp, 'Upload')
  return data.path
}
