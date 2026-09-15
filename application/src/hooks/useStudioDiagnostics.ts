import { useEffect, useMemo, useState } from 'react'
import { useAppStore } from '../stores/appStore.ts'
import { fsExists, getWorkspacePath } from '../hooks/useTauri.ts'
import { getRuntimeLabel, isCloudRuntime, isTauriRuntime } from '../utils/runtime.ts'

export type StudioRequirementTone = 'good' | 'warn' | 'default'

export type StudioRequirement = {
  id: string
  label: string
  detail: string
  ready: boolean
  tone: StudioRequirementTone
}

type RequiredFile = {
  label: string
  relativePath: string
}

type StudioDiagnosticsOptions = {
  requiresTauri?: boolean
  requiresOllama?: boolean
  requiresComfyui?: boolean
  requiredFiles?: RequiredFile[]
}

export type StudioDiagnostics = {
  checking: boolean
  workspacePath: string | null
  readiness: number
  requirements: StudioRequirement[]
  summary: string
  blockingReason: string | null
  runtimeLabel: string
}

export function useStudioDiagnostics(options: StudioDiagnosticsOptions = {}): StudioDiagnostics {
  const { checkingConfig, installedModels, runtimeServices, services } = useAppStore()
  const [workspacePath, setWorkspacePath] = useState<string | null>(null)
  const [fileChecks, setFileChecks] = useState<Record<string, boolean>>({})
  const [checking, setChecking] = useState(false)
  const requiredFiles = options.requiredFiles ?? []
  const requiredFilesKey = JSON.stringify(requiredFiles)
  const tauriReady = isTauriRuntime() || isCloudRuntime()

  useEffect(() => {
    let cancelled = false

    async function inspectWorkspace() {
      if (!tauriReady) {
        setWorkspacePath(null)
        setFileChecks({})
        setChecking(false)
        return
      }

      setChecking(true)

      try {
        const nextWorkspacePath = await getWorkspacePath()
        if (cancelled) return

        setWorkspacePath(nextWorkspacePath)

        if (requiredFiles.length === 0) {
          setFileChecks({})
          return
        }

        const nextChecks = await Promise.all(
          requiredFiles.map(async (file) => {
            const absolutePath = `${nextWorkspacePath}/${file.relativePath}`
            const exists = await fsExists(absolutePath)
            return [file.relativePath, exists] as const
          }),
        )

        if (!cancelled) {
          setFileChecks(Object.fromEntries(nextChecks))
        }
      } catch {
        if (!cancelled) {
          setWorkspacePath(null)
          setFileChecks({})
        }
      } finally {
        if (!cancelled) {
          setChecking(false)
        }
      }
    }

    void inspectWorkspace()

    return () => {
      cancelled = true
    }
  }, [requiredFilesKey, tauriReady])

  const requirements = useMemo<StudioRequirement[]>(() => {
    const items: StudioRequirement[] = []

    if (options.requiresTauri) {
      const cloudReady = isCloudRuntime()
      items.push({
        id: 'runtime',
        label: 'Shell natif',
        detail: tauriReady
          ? cloudReady
            ? 'Cloud RunPod actif, acces distant disponible.'
            : 'Tauri natif actif, acces local disponible.'
          : 'Ce module attend le shell Tauri pour lire le disque et lancer les workflows lourds.',
        ready: tauriReady,
        tone: tauriReady ? 'good' : 'warn',
      })
    }

    if (options.requiresOllama) {
      const ollamaKnownAvailable = runtimeServices.ollama.available || installedModels.length > 0
      const ollamaReady = services.ollama || ollamaKnownAvailable
      items.push({
        id: 'ollama',
        label: 'Ollama',
        detail: checkingConfig
          ? 'Verification locale en cours avant de statuer sur l installation.'
          : services.ollama
            ? 'Le moteur local repond.'
            : ollamaKnownAvailable
              ? 'Installe et pret pour un demarrage a la demande.'
              : 'Non detecte sur ce poste. Ce module restera bloque tant qu il n est pas installe.',
        ready: ollamaReady,
        tone: services.ollama ? 'good' : ollamaKnownAvailable ? 'default' : checkingConfig ? 'default' : 'warn',
      })
    }

    if (options.requiresComfyui) {
      const comfyuiReady = services.comfyui || runtimeServices.comfyui.available
      items.push({
        id: 'comfyui',
        label: 'ComfyUI',
        detail: services.comfyui
          ? 'Le pipeline visuel est joignable.'
          : runtimeServices.comfyui.available
            ? 'Installe et pret pour un demarrage a la demande.'
            : 'Non detecte sur ce poste. Le rendu visuel restera bloque tant qu il n est pas installe.',
        ready: comfyuiReady,
        tone: services.comfyui ? 'good' : runtimeServices.comfyui.available ? 'default' : 'warn',
      })
    }

    for (const file of requiredFiles) {
      const exists = tauriReady ? fileChecks[file.relativePath] : false
      const ready = tauriReady ? Boolean(exists) : false
      items.push({
        id: `file:${file.relativePath}`,
        label: file.label,
        detail: tauriReady
          ? exists
            ? `${file.relativePath} est disponible dans le workspace.`
            : `${file.relativePath} est introuvable dans le workspace courant.`
          : 'Verification du fichier reservee au shell Tauri.',
        ready,
        tone: ready ? 'good' : tauriReady ? 'warn' : 'default',
      })
    }

    if (items.length === 0) {
      items.push({
        id: 'runtime-info',
        label: 'Runtime',
        detail: `Interface chargee sur ${getRuntimeLabel()}.`,
        ready: true,
        tone: 'good',
      })
    }

    return items
  }, [
    checkingConfig,
    fileChecks,
    installedModels.length,
    options.requiresComfyui,
    options.requiresOllama,
    options.requiresTauri,
    requiredFiles,
    services.comfyui,
    services.ollama,
    runtimeServices.comfyui.available,
    runtimeServices.ollama.available,
    tauriReady,
  ])

  const readiness = useMemo(() => {
    if (requirements.length === 0) return 100
    const readyCount = requirements.filter((item) => item.ready).length
    return Math.round((readyCount / requirements.length) * 100)
  }, [requirements])

  const blockingRequirement = requirements.find((item) => !item.ready)
  const blockingReason = checking || checkingConfig
    ? null
    : blockingRequirement ? `${blockingRequirement.label}: ${blockingRequirement.detail}` : null

  let summary = 'Module pret.'
  if (checking || checkingConfig) {
    summary = 'Verification du poste en cours.'
  } else if (blockingReason) {
    summary = `Preflight incomplet. ${blockingRequirement?.label} doit encore etre aligne.`
  }

  return {
    checking,
    workspacePath,
    readiness,
    requirements,
    summary,
    blockingReason,
    runtimeLabel: getRuntimeLabel(),
  }
}
