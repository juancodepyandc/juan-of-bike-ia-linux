// ─── Shared Memory — Cross-module persistent storage ─────────────────────────
//
// Toutes les clés DOIVENT avoir un préfixe de module pour éviter les collisions.
// Format attendu : "<module>_<type>_<hash>" ou "<module>:<clé>".
// En développement, un warning est émis si la clé ne suit pas ce format.

const STORE_MAX_SIZE = 128
const store = new Map<string, unknown>()

function warnUnprefixedKey(key: string, caller: string) {
  // Sous Node (test runner), `import.meta.env` est undefined.
  // Sous Vite, `import.meta.env.DEV` existe. Utiliser ?. pour les deux.
  if (import.meta.env?.DEV && !/^[a-z_]+[_:]/.test(key)) {
    console.warn(
      `[sharedMemory.${caller}] Clé sans préfixe de module détectée: "${key}". `
      + 'Utiliser le format "<module>_<type>_<id>" pour éviter les collisions inter-modules.',
    )
  }
}

/** Éviction LRU: supprime l'entrée la plus ancienne quand la capacité est atteinte. */
function evictIfFull(key: string) {
  if (store.size >= STORE_MAX_SIZE && !store.has(key)) {
    const firstKey = store.keys().next().value
    if (firstKey !== undefined) store.delete(firstKey)
  }
}

export const sharedMemory = {
  get<T = unknown>(key: string): T | undefined {
    warnUnprefixedKey(key, 'get')
    return store.get(key) as T | undefined
  },

  set<T = unknown>(key: string, value: T): void {
    warnUnprefixedKey(key, 'set')
    evictIfFull(key)
    store.set(key, value)
  },

  has(key: string): boolean {
    return store.has(key)
  },

  delete(key: string): boolean {
    return store.delete(key)
  },

  keys(): string[] {
    return Array.from(store.keys())
  },

  /** Retourne toutes les clés appartenant à un module donné. */
  keysForModule(module: string): string[] {
    const prefix = `${module}_`
    const prefix2 = `${module}:`
    return Array.from(store.keys()).filter((k) => k.startsWith(prefix) || k.startsWith(prefix2))
  },

  /** Supprime toutes les entrées d'un module. Utile au démontage. */
  clearModule(module: string): void {
    for (const key of this.keysForModule(module)) {
      store.delete(key)
    }
  },

  clear(): void {
    store.clear()
  },

  // ── Helpers module-spécifiques ──────────────────────────────────────────

  setModuleResult(module: string, promptHash: string, result: unknown): void {
    const key = `${module}_result_${promptHash}`
    evictIfFull(key)
    store.set(key, result)
  },

  getModuleResult<T = unknown>(module: string, promptHash: string): T | undefined {
    return store.get(`${module}_result_${promptHash}`) as T | undefined
  },

  setRealityAnalysis(promptHash: string, analysis: unknown): void {
    const key = `reality_analysis_${promptHash}`
    evictIfFull(key)
    store.set(key, analysis)
  },

  getRealityAnalysis<T = unknown>(promptHash: string): T | undefined {
    return store.get(`reality_analysis_${promptHash}`) as T | undefined
  },

  /** Taille courante du store (pour monitoring). */
  get size(): number {
    return store.size
  },
}
