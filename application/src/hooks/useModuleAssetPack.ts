import { useCallback, useEffect, useMemo, useRef } from 'react'
import { useAppStore } from '../stores/appStore.ts'
import type {
  ModuleAssetDefinition,
  ModuleAssetPackState,
  ModuleAssetStatus,
  ModuleId,
  RuntimeProgressEvent,
} from '../types/app.ts'
import {
  fsExists,
  getWorkspacePath,
  ollamaListModels,
  onPythonProgress,
  onRuntimeProgress,
  runPythonScript,
  runtimeEnsureOllamaModelAvailable,
} from './useTauri.ts'
import { getErrorMessage } from '../utils/errors.ts'
import { resolveConfiguredModel } from '../config/models.ts'
import { isTauriRuntime } from '../utils/runtime.ts'

function parseLastJsonObject(text: string) {
  const lines = text.split('\n').map((line) => line.trim()).filter(Boolean)
  for (let index = lines.length - 1; index >= 0; index -= 1) {
    try {
      return JSON.parse(lines[index]) as { ok?: boolean; path?: string; error?: string }
    } catch {
      // Keep scanning until the last valid JSON line.
    }
  }

  return null
}

function parsePercent(detail: string) {
  const match = detail.match(/(\d{1,3})%/)
  return match ? Math.max(0, Math.min(100, Number(match[1]))) : null
}

function inferPythonStatus(detail: string): ModuleAssetStatus {
  const lower = detail.toLowerCase()
  if (lower.includes('verification') || lower.includes('scan')) {
    return 'scanning'
  }

  if (lower.includes('telechargement') || lower.includes('download')) {
    return 'downloading'
  }

  if (lower.includes('pret')) {
    return 'ready'
  }

  return 'warming'
}

function resolveAssetDestination(destination: string | null | undefined) {
  if (!destination) {
    return null
  }

  const normalized = destination.replace(/\\/g, '/')
  if (/^[a-zA-Z]:\//.test(normalized) || normalized.startsWith('/')) {
    return normalized
  }

  if (isTauriRuntime()) {
    const comfyuiPath = useAppStore.getState().runtimeServices.comfyui.path
    if (!comfyuiPath) {
      return null
    }
    return `${comfyuiPath.replace(/\\/g, '/')}/${normalized.replace(/^\/+/, '')}`
  }

  // Cloud/tunnel/browser: pass relative path as-is — the bridge resolves server-side
  return normalized
}

function mapOllamaProgress(payload: RuntimeProgressEvent) {
  const lowerDetail = payload.detail.toLowerCase()
  const status: ModuleAssetStatus =
    payload.status === 'checking'
      ? 'scanning'
      : payload.status === 'error'
        ? 'error'
        : lowerDetail.includes('telechargement')
          ? 'downloading'
          : payload.status === 'ready'
            ? 'ready'
            : 'warming'

  return {
    status,
    progress: payload.status === 'ready' ? 100 : payload.progress,
    detail: payload.detail,
  }
}

function buildAssetsKey(assets: ModuleAssetDefinition[]) {
  return JSON.stringify(
    assets.map((asset) => ({
      id: asset.id,
      target: asset.target,
      destination: asset.destination || null,
      repoId: asset.repoId || null,
      filename: asset.filename || null,
      prepareMode: asset.prepareMode || null,
    })),
  )
}

export function useModuleAssetPack({
  module,
  title,
  assets,
}: {
  module: ModuleId
  title: string
  assets: ModuleAssetDefinition[]
}) {
  const assetPack = useAppStore((state) => state.moduleAssetPacks[module])
  const hydrateModuleAssetPack = useAppStore((state) => state.hydrateModuleAssetPack)
  const setModuleAssetPack = useAppStore((state) => state.setModuleAssetPack)
  const setModuleAssetState = useAppStore((state) => state.setModuleAssetState)
  const setInstalledModels = useAppStore((state) => state.setInstalledModels)
  const assetsKey = useMemo(() => buildAssetsKey(assets), [assets])
  const stableAssets = useMemo(() => assets, [assetsKey])
  const activeOllamaAssetRef = useRef<string | null>(null)

  const refreshPackProgress = useCallback((detail?: string, status?: ModuleAssetPackState['status']) => {
    const currentPack = useAppStore.getState().moduleAssetPacks[module]
    const progress = currentPack.assets.length > 0
      ? Math.round(currentPack.assets.reduce((sum, asset) => sum + asset.progress, 0) / currentPack.assets.length)
      : 0

    setModuleAssetPack(module, {
      progress,
      detail: detail ?? currentPack.detail,
      status: status ?? currentPack.status,
    })
  }, [module, setModuleAssetPack])

  useEffect(() => {
    hydrateModuleAssetPack(module, title, stableAssets)
  }, [assetsKey, hydrateModuleAssetPack, module, stableAssets, title])

  useEffect(() => {
    let cancelled = false
    let unlisten: (() => void) | null = null

    onRuntimeProgress((payload) => {
      if (cancelled || payload.service !== 'ollama') {
        return
      }

      const assetId = activeOllamaAssetRef.current
      if (!assetId) {
        return
      }

      const mapped = mapOllamaProgress(payload)
      setModuleAssetState(module, assetId, mapped)
      refreshPackProgress(mapped.detail, mapped.status === 'error' ? 'error' : 'running')
    }).then((stop) => {
      if (!cancelled) {
        unlisten = stop
      }
    }).catch(() => {
      unlisten = null
    })

    return () => {
      cancelled = true
      if (unlisten) {
        unlisten()
      }
    }
  }, [module, refreshPackProgress, setModuleAssetState])

  const prepareOllamaAsset = useCallback(async (
    asset: ModuleAssetDefinition,
    setPhase?: (detail: string, progress: number) => void,
    phaseProgress = 28,
  ) => {
    // Auto-correction: resout les noms legacy avant d'appeler le backend Rust
    const resolvedTarget = resolveConfiguredModel(asset.target, asset.target)

    activeOllamaAssetRef.current = asset.id
    setModuleAssetState(module, asset.id, {
      status: 'scanning',
      progress: 6,
      detail: `Verification locale de ${asset.label}...`,
      error: null,
    })
    refreshPackProgress(`Verification de ${asset.label}...`, 'running')
    setPhase?.(`Verification de ${asset.label}...`, phaseProgress)

    await runtimeEnsureOllamaModelAvailable(resolvedTarget)

    const modelsResp = await ollamaListModels().catch(() => null)
    if (modelsResp?.models) {
      setInstalledModels(modelsResp.models.map((modelEntry: { name: string }) => modelEntry.name))
    }

    const ollamaPath = useAppStore.getState().runtimeServices.ollama.path
    setModuleAssetState(module, asset.id, {
      status: 'ready',
      progress: 100,
      detail: `${asset.label} disponible pour cette session.`,
      path: ollamaPath,
      lastCheckedAt: Date.now(),
      error: null,
    })
    refreshPackProgress(`${asset.label} disponible localement.`, 'running')
    activeOllamaAssetRef.current = null
  }, [module, refreshPackProgress, setInstalledModels, setModuleAssetState])

  const preparePythonAsset = useCallback(async (
    asset: ModuleAssetDefinition,
    setPhase?: (detail: string, progress: number) => void,
    phaseProgress = 28,
  ) => {
    const workspacePath = await getWorkspacePath()
    const scriptPath = `${workspacePath}/python-services/model_prepare.py`
    const scriptExists = await fsExists(scriptPath)

    if (!scriptExists) {
      throw new Error('python-services/model_prepare.py est introuvable dans le workspace.')
    }

    const resolvedDestination = asset.kind === 'hf_file'
      ? resolveAssetDestination(asset.destination)
      : null

    if (asset.kind === 'hf_file') {
      if (!asset.filename) {
        throw new Error(`${asset.label}: fichier cible non specifie (filename manquant).`)
      }
      if (!resolvedDestination && !asset.destination) {
        throw new Error(`${asset.label}: destination non configuree (aucun chemin disponible).`)
      }
    }

    // Use resolved absolute path when available; otherwise pass the raw relative destination
    // so the server can resolve it via COMFYUI_DIR env var (injected by bridge_server.py).
    const effectiveDestination = resolvedDestination ?? asset.destination ?? ''

    const args = asset.kind === 'hf_file'
      ? [
          '--mode',
          'hf-file',
          '--repo-id',
          asset.repoId || '',
          '--filename',
          asset.filename!, // validated non-empty above
          '--destination',
          effectiveDestination,
        ]
      : [
          '--mode',
          'hf-snapshot',
          '--repo-id',
          asset.repoId || asset.target,
        ]

    for (const pattern of asset.allowPatterns || []) {
      args.push('--allow-pattern', pattern)
    }

    setModuleAssetState(module, asset.id, {
      status: 'scanning',
      progress: 8,
      detail: `Verification locale de ${asset.label}...`,
      error: null,
    })
    refreshPackProgress(`Verification de ${asset.label}...`, 'running')
    setPhase?.(`Verification de ${asset.label}...`, phaseProgress)

    let stopListening: (() => void) | null = null
    try {
      stopListening = await onPythonProgress((message) => {
        if (!message.startsWith('PROGRESS:')) {
          return
        }

        const detail = message.split(':').slice(2).join(':') || message
        const progress = parsePercent(detail)
        const status = inferPythonStatus(detail)

        setModuleAssetState(module, asset.id, {
          status,
          progress: progress ?? (status === 'scanning' ? 18 : status === 'downloading' ? 54 : status === 'ready' ? 100 : 72),
          detail,
        })
        refreshPackProgress(detail, status === 'error' ? 'error' : 'running')
      })

      const output = await runPythonScript(scriptPath, args)
      const result = parseLastJsonObject(output)

      if (!result?.ok || !result.path) {
        throw new Error(result?.error || `${asset.label} n a pas pu etre prepare localement.`)
      }

      setModuleAssetState(module, asset.id, {
        status: 'ready',
        progress: 100,
        detail: `${asset.label} disponible pour cette session.`,
        path: result.path,
        lastCheckedAt: Date.now(),
        error: null,
      })
      refreshPackProgress(`${asset.label} disponible localement.`, 'running')
    } finally {
      stopListening?.()
    }
  }, [module, refreshPackProgress, setModuleAssetState])

  const preparePythonRuntimeAsset = useCallback(async (
    asset: ModuleAssetDefinition,
    setPhase?: (detail: string, progress: number) => void,
    phaseProgress = 28,
  ) => {
    const workspacePath = await getWorkspacePath()
    const scriptPath = `${workspacePath}/python-services/runtime_prepare.py`
    const scriptExists = await fsExists(scriptPath)

    if (!scriptExists) {
      throw new Error('python-services/runtime_prepare.py est introuvable dans le workspace.')
    }

    const prepareMode = asset.prepareMode || module
    const args = ['--module', prepareMode]

    setModuleAssetState(module, asset.id, {
      status: 'scanning',
      progress: 8,
      detail: `Verification locale de ${asset.label}...`,
      error: null,
    })
    refreshPackProgress(`Verification de ${asset.label}...`, 'running')
    setPhase?.(`Verification de ${asset.label}...`, phaseProgress)

    let stopListening: (() => void) | null = null
    try {
      stopListening = await onPythonProgress((message) => {
        if (!message.startsWith('PROGRESS:')) {
          return
        }

        const detail = message.split(':').slice(2).join(':') || message
        const progress = parsePercent(detail)
        const status = inferPythonStatus(detail)

        setModuleAssetState(module, asset.id, {
          status,
          progress: progress ?? (status === 'scanning' ? 18 : status === 'downloading' ? 54 : status === 'ready' ? 100 : 72),
          detail,
        })
        refreshPackProgress(detail, status === 'error' ? 'error' : 'running')
      })

      const output = await runPythonScript(scriptPath, args)
      const result = parseLastJsonObject(output)

      if (!result?.ok || !result.path) {
        throw new Error(result?.error || `${asset.label} n a pas pu etre prepare localement.`)
      }

      setModuleAssetState(module, asset.id, {
        status: 'ready',
        progress: 100,
        detail: `${asset.label} disponible pour cette session.`,
        path: result.path,
        lastCheckedAt: Date.now(),
        error: null,
      })
      refreshPackProgress(`${asset.label} disponible localement.`, 'running')
    } finally {
      stopListening?.()
    }
  }, [module, refreshPackProgress, setModuleAssetState])

  const preparePack = useCallback(async (setPhase?: (detail: string, progress: number) => void) => {
    const currentPack = useAppStore.getState().moduleAssetPacks[module]
    const packAlreadyReady =
      currentPack.assets.length === stableAssets.length
      && currentPack.assets.every((asset) => asset.status === 'ready')

    if (packAlreadyReady) {
      setModuleAssetPack(module, {
        status: 'ready',
        progress: 100,
        detail: 'Pack modele deja verifie pour cette session.',
        lastError: null,
      })
      setPhase?.('Pack modele deja valide pour cette session.', 36)
      return
    }

    setModuleAssetPack(module, {
      title,
      status: 'running',
      progress: 2,
      detail: 'Scan local du pack modele en cours...',
      lastError: null,
    })

    for (let index = 0; index < stableAssets.length; index += 1) {
      const asset = stableAssets[index]
      const phaseProgress = 18 + Math.round(((index + 1) / Math.max(1, stableAssets.length)) * 18)

      try {
        if (asset.kind === 'ollama_model') {
          await prepareOllamaAsset(asset, setPhase, phaseProgress)
        } else if (asset.kind === 'python_runtime') {
          await preparePythonRuntimeAsset(asset, setPhase, phaseProgress)
        } else {
          // In Tauri mode, the local ComfyUI path must be known before attempting downloads.
          // In cloud/browser mode, the server-side path comes from the bridge (runtimeServices),
          // so we skip this early guard and let preparePythonAsset proceed.
          if (asset.kind === 'hf_file' && isTauriRuntime() && !resolveAssetDestination(asset.destination)) {
            throw new Error(`${asset.label}: chemin cible introuvable, verifie le dossier ComfyUI local.`)
          }

          await preparePythonAsset(asset, setPhase, phaseProgress)
        }
      } catch (error) {
        const message = getErrorMessage(error, `Erreur inconnue sur ${asset.label}.`)
        setModuleAssetState(module, asset.id, {
          status: 'error',
          progress: 100,
          detail: message,
          error: message,
          lastCheckedAt: Date.now(),
        })
        setModuleAssetPack(module, {
          status: 'error',
          detail: message,
          lastError: message,
          lastCheckedAt: Date.now(),
        })
        refreshPackProgress(message, 'error')
        activeOllamaAssetRef.current = null
        throw error
      }
    }

    setModuleAssetPack(module, {
      status: 'ready',
      progress: 100,
      detail: 'Pack modele verifie et disponible pour cette session.',
      lastCheckedAt: Date.now(),
      lastError: null,
    })
  }, [
    module,
    prepareOllamaAsset,
    preparePythonAsset,
    preparePythonRuntimeAsset,
    refreshPackProgress,
    setModuleAssetPack,
    setModuleAssetState,
    stableAssets,
    title,
  ])

  return {
    pack: assetPack,
    preparePack,
  }
}
