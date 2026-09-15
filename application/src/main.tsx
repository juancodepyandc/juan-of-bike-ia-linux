import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App.tsx'
import AppErrorBoundary from './components/AppErrorBoundary.tsx'
import { installDeviceAttribute } from './utils/device.ts'
import { registerNotificationWorker } from './utils/notificationBus.ts'
import { attachForgeQueueBootstrap } from './stores/forgeQueueStore.ts'
import { installTabLifecycleGuards } from './utils/tabLifecycle.ts'
import { installTheme } from './utils/theme.ts'
import { installUiSkin, readUiSkin } from './utils/uiSkin.ts'
import { installQuickNav } from './utils/quickNav.ts'
import { installBuildRecovery, isChunkError, recoverFromStaleBuild } from './utils/buildRecovery.ts'
import './styles/globals.css'
// v81q: Aurora Editorial design tokens — scoped to html[data-ui-skin="aurora_v1"]
// so they only apply when the user picks Editorial in Settings → UI complète.
// Manga and Ricochet skins are unaffected.
import './styles/aurora-skin.css'

// v82l2 : auto-cleanup au boot pour balayer SW + caches stale d'une
// version antérieure. Quand le user voit "page noire" après un déploiement,
// c'est presque toujours un SW qui sert un vieux chunk d'avant le fix.
// On compare la build version avec celle stockée ; si différente, on
// unregister tous les SW + clear toutes les caches puis reload UNE fois.
;(function autoCleanupStaleCache() {
  if (typeof window === 'undefined') return
  // BUILD_ID = timestamp injecté à chaque deploy (ou hash chunk Vite).
  // En dev, on prend une string fixe pour pas reload en boucle.
  const BUILD_ID = '__BUILD_v82l5_' + (import.meta.env.MODE || 'dev')
  const KEY = 'aurora_build_id'
  try {
    const last = window.localStorage.getItem(KEY)
    if (last && last !== BUILD_ID) {
      console.info('[aurora] new build detected, clearing caches + SW...')
      // Clear toutes caches HTTP.
      if ('caches' in window) {
        void caches.keys().then((keys) => Promise.all(keys.map((k) => caches.delete(k))))
      }
      // Unregister tous les SW.
      if ('serviceWorker' in navigator) {
        void navigator.serviceWorker.getRegistrations().then((regs) => {
          for (const r of regs) void r.unregister()
        })
      }
      // Reload UNE fois après cleanup.
      window.localStorage.setItem(KEY, BUILD_ID)
      window.location.reload()
      return
    }
    if (!last) window.localStorage.setItem(KEY, BUILD_ID)
  } catch { /* private mode / quota */ }
})()

installDeviceAttribute()
installTheme()
installUiSkin()
// v82k0 : load manga-theme.css UNIQUEMENT si l'utilisateur est sur le
// skin manga. Pour aurora_v1 / aurora_v3 le navigateur ne télécharge
// même pas le chunk (60KB+ de !important sur tokens paper/ink + Bangers
// font). Avant cette passe, manga-theme était importé globalement et
// polluait les surfaces aurora même pour les skins éditoriaux.
if (readUiSkin() === 'manga') {
  void import('./styles/manga-theme.css')
}
installQuickNav()
void registerNotificationWorker()
installTabLifecycleGuards()
// Drain any in-flight forge jobs persisted from a previous session
setTimeout(() => { try { attachForgeQueueBootstrap() } catch { /* ignore */ } }, 400)

// ---------------------------------------------------------------------------
// v82s-studio iter14 : "charge à l'infini" en changeant d'interface.
// Cause : après un déploiement, un `index.html` en cache (SW / HTTP) référence
// des chunks Vite dont le hash a changé → import() 404 → le <Suspense> du shell
// tourne pour toujours, et le crash-guard global avalait l'erreur en silence.
// → installBuildRecovery() installe : détection d'erreur de chunk + watchdog
//   de boot + reload dur (caches purgées, SW désinscrits) une seule fois.
installBuildRecovery()

// ---------------------------------------------------------------------------
// Global crash guard — prevent unhandled rejections from killing the app
// React error boundaries cannot catch async errors or promise rejections,
// so this is the LAST line of defense. Without this, any uncaught promise
// rejection restarts the entire app, losing all generation progress.
// ---------------------------------------------------------------------------
window.addEventListener('unhandledrejection', (event) => {
  if (isChunkError(event.reason)) {
    recoverFromStaleBuild('unhandledrejection: ' + (event.reason instanceof Error ? event.reason.message : String(event.reason)))
    return
  }
  event.preventDefault()
  const reason = event.reason instanceof Error ? event.reason.message : String(event.reason)
  console.error('[AuroraIA] Unhandled rejection intercepted (app NOT crashed):', reason)
})

window.addEventListener('error', (event) => {
  if (isChunkError(event.message) || isChunkError(event.error)) {
    recoverFromStaleBuild('error: ' + (event.message || ''))
    return
  }
  // Only intercept non-fatal errors — let critical ones through
  if (event.message?.includes('ResizeObserver') || event.message?.includes('Script error')) {
    event.preventDefault()
    return
  }
  console.error('[AuroraIA] Global error intercepted:', event.message)
})

ReactDOM.createRoot(document.getElementById('root')!).render(
  <AppErrorBoundary>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </AppErrorBoundary>,
)
