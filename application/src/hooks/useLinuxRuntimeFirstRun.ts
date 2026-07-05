import { useEffect } from 'react'
import { linuxRuntimeCheck, linuxRuntimeInstallMissing } from './useTauri'
import { isTauriRuntime } from '../utils/runtime'

let installStarted = false

export function useLinuxRuntimeFirstRun() {
  useEffect(() => {
    if (!isTauriRuntime() || installStarted) return

    let cancelled = false

    void (async () => {
      const report = await linuxRuntimeCheck()
      if (cancelled || !report.isLinux || !report.needsInstall || installStarted) return

      installStarted = true
      const needsNvidia = report.items.some((item) => item.id === 'nvidia-smi' && !item.ready)
      console.info('[Aurora Linux] Runtime incomplet, lancement du first-run:', report.detail)
      await linuxRuntimeInstallMissing({
        maxQuality: true,
        installNvidiaDriver: needsNvidia,
      })
    })().catch((error) => {
      installStarted = false
      console.warn('[Aurora Linux] First-run non lance:', error)
    })

    return () => {
      cancelled = true
    }
  }, [])
}
