import { useEffect } from 'react'
import { useAppStore } from '../stores/appStore'
import { onRuntimeProgress, runtimeInspectServices } from './useTauri'
import { isTauriRuntime } from '../utils/runtime'

function mapRuntimeServices(
  services: Awaited<ReturnType<typeof runtimeInspectServices>>,
) {
  return services.reduce((accumulator, service) => {
    accumulator[service.id] = service
    return accumulator
  }, {} as Record<'ollama' | 'comfyui', (typeof services)[number]>)
}

export function useRuntimeTelemetry() {
  const { mergeRuntimeService, setRuntimeServices, setServices, setRuntimeTask } = useAppStore()

  useEffect(() => {
    let cancelled = false
    let unlisten: (() => void) | null = null

    async function refresh() {
      if (!isTauriRuntime()) {
        return
      }

      try {
        const services = await runtimeInspectServices()
        if (cancelled) return

        const mapped = mapRuntimeServices(services)
        setRuntimeServices(mapped)
        setServices({
          ollama: mapped.ollama?.running || false,
          comfyui: mapped.comfyui?.running || false,
        })
      } catch {
        // Ignore telemetry bootstrap failures and keep UI responsive.
      }
    }

    void refresh()

    onRuntimeProgress((payload) => {
      if (cancelled) return

      const nextRunning =
        payload.status === 'ready' ||
        payload.status === 'warming' ||
        payload.status === 'starting' ||
        payload.status === 'releasing'
          ? true
          : payload.status === 'stopped' || payload.status === 'error'
            ? false
            : undefined

      mergeRuntimeService(payload.service, {
        progress: payload.progress,
        detail: payload.detail,
        running: nextRunning,
      })

      const currentTask = useAppStore.getState().runtimeTask
      if (currentTask.active && currentTask.phase !== 'generate' && currentTask.phase !== 'done' && currentTask.phase !== 'error') {
        setRuntimeTask({
          detail: payload.detail,
          progress: Math.max(currentTask.progress, payload.progress),
        })
      }
    }).then((stop) => {
      if (!cancelled) {
        unlisten = stop
      }
    }).catch(() => {
      unlisten = null
    })

    const interval = window.setInterval(() => {
      void refresh()
    }, 15000)

    return () => {
      cancelled = true
      if (unlisten) {
        unlisten()
      }
      window.clearInterval(interval)
    }
  }, [mergeRuntimeService, setRuntimeServices, setServices, setRuntimeTask])
}
