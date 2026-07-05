/**
 * buildRecovery — récupération automatique d'un build « périmé ».
 *
 * Symptôme : après un déploiement, le navigateur a un `index.html` en cache
 * (Service Worker ou cache HTTP) qui référence des chunks Vite dont le hash a
 * changé → `import()` renvoie 404 → le <Suspense> du shell tourne à l'infini
 * (« ça charge à l'infini en changeant d'interface »).
 *
 * Stratégie : dès qu'on détecte une erreur de chargement de chunk (ou que
 * l'app n'a pas monté du tout), on purge les caches + désinscrit les SW + on
 * recharge avec un cache-bust. Garde anti-boucle : 2 tentatives max par
 * session (compteur en sessionStorage), remis à zéro quand l'app tourne sainement.
 */
export const CHUNK_ERR_RE =
  /dynamically imported module|importing a module script failed|loading chunk|chunkloaderror|failed to fetch dynamically/i

const RECOVER_COUNT_KEY = 'aurora_recover_n'
let recovering = false

export function isChunkError(input: unknown): boolean {
  if (!input) return false
  const msg =
    typeof input === 'string'
      ? input
      : input instanceof Error
        ? input.message
        : ((input as { message?: unknown }).message != null ? String((input as { message?: unknown }).message) : String(input))
  return CHUNK_ERR_RE.test(msg)
}

export function recoverFromStaleBuild(why: string): void {
  if (recovering || typeof window === 'undefined') return
  let n = 0
  try { n = Number(window.sessionStorage.getItem(RECOVER_COUNT_KEY) || 0) } catch { /* private mode */ }
  if (n >= 2) {
    console.warn('[AuroraIA] recovery déjà tentée 2× cette session — abandon (' + why + ')')
    return
  }
  try { window.sessionStorage.setItem(RECOVER_COUNT_KEY, String(n + 1)) } catch { /* noop */ }
  recovering = true
  console.warn('[AuroraIA] stale-build recovery (' + why + ') — purge caches + SW + reload…')
  const jobs: Promise<unknown>[] = []
  try { if ('caches' in window) jobs.push(caches.keys().then((ks) => Promise.all(ks.map((k) => caches.delete(k))))) } catch { /* noop */ }
  try {
    if ('serviceWorker' in navigator) {
      jobs.push(navigator.serviceWorker.getRegistrations().then((regs) => Promise.all(regs.map((r) => r.unregister()))))
    }
  } catch { /* noop */ }
  Promise.allSettled(jobs).finally(() => {
    try {
      const u = new URL(window.location.href)
      u.searchParams.set('_r', String(Date.now()))
      window.location.replace(u.toString())
    } catch {
      window.location.reload()
    }
  })
}

/** Appelé une fois que l'app a monté et tourne depuis quelques secondes : le
 *  boot est sain → on désarme le compteur de recovery. */
export function markBootHealthy(): void {
  try { window.sessionStorage.removeItem(RECOVER_COUNT_KEY) } catch { /* noop */ }
}

/** Recharge la page en forçant un re-fetch de `index.html` (cache-buster `?_t`)
 *  et purge les caches API. À utiliser après un changement de skin pour que le
 *  navigateur récupère bien le nouvel index.html (et ses preloads de chunks)
 *  au lieu de servir un index.html périmé → « charge à l'infini ». */
export function reloadFresh(extraParams?: Record<string, string>): void {
  if (typeof window === 'undefined') return
  const go = () => {
    try {
      const u = new URL(window.location.href)
      if (extraParams) for (const [k, v] of Object.entries(extraParams)) u.searchParams.set(k, v)
      u.searchParams.set('_t', String(Date.now()))
      window.location.replace(u.toString())
    } catch {
      window.location.reload()
    }
  }
  try {
    if ('caches' in window) {
      caches.keys().then((ks) => Promise.all(ks.map((k) => caches.delete(k)))).finally(go)
      return
    }
  } catch { /* noop */ }
  go()
}

/** Installe les garde-fous globaux : erreurs de chunk + watchdog de boot. */
export function installBuildRecovery(): void {
  if (typeof window === 'undefined') return
  // Vite : module pré-chargé qui échoue (chunk 404 typiquement).
  window.addEventListener('vite:preloadError', () => recoverFromStaleBuild('vite:preloadError'))
  // Watchdog : si #root est vide après 20s → l'app n'a jamais monté → recovery.
  window.setTimeout(() => {
    const root = document.getElementById('root')
    if (!root || root.childElementCount === 0) recoverFromStaleBuild('boot-watchdog: #root vide après 20s')
  }, 20_000)
  // Boot sain après 5s → désarmer le compteur.
  window.setTimeout(() => {
    const root = document.getElementById('root')
    if (root && root.childElementCount > 0) markBootHealthy()
  }, 5_000)
}
