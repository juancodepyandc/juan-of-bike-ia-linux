/**
 * Tracker de coalescing — utilitaire pour ignorer des événements rapprochés
 * (même clé) dans une fenêtre de temps donnée.
 *
 * Usage type : éviter qu'une avalanche d'annonces TTS sur le même module
 * en moins de 2.5s déclenche autant d'utterances.
 *
 * Implémentation : `Map<key, lastTimestampMs>`. La fonction `shouldAllow`
 * retourne `false` si la clé a été acceptée récemment, `true` sinon
 * (et enregistre la date d'acceptation).
 */
export class CoalesceTracker {
  private readonly windowMs: number
  private readonly lastAcceptedAt: Map<string, number> = new Map()

  constructor(windowMs: number) {
    this.windowMs = windowMs
  }

  /**
   * Renvoie true si l'événement peut être joué (et enregistre l'horodatage).
   * Renvoie false s'il y a eu un événement de même clé il y a < windowMs.
   *
   * Le `now` est paramétrable pour faciliter les tests.
   */
  shouldAllow(key: string, now: number = Date.now()): boolean {
    const last = this.lastAcceptedAt.get(key)
    // Première occurrence (jamais vue) → toujours acceptée.
    if (last === undefined) {
      this.lastAcceptedAt.set(key, now)
      return true
    }
    if (now - last < this.windowMs) return false
    this.lastAcceptedAt.set(key, now)
    return true
  }

  /** Réinitialise le tracker (ex : changement d'utilisateur). */
  reset(): void {
    this.lastAcceptedAt.clear()
  }

  /** Pour debug / inspection. */
  size(): number {
    return this.lastAcceptedAt.size
  }
}
