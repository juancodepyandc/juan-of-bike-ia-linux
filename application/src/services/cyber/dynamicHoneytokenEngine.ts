/**
 * dynamicHoneytokenEngine.ts — Moteur de déception défensive, micro-leurres et jetons canaris.
 *
 * Fonctionnalités :
 * 1. Synthèse dynamique de jetons pièges (Honeytokens, fausses clés d'API, JWT canaris, tables d'appât).
 * 2. Détection en temps réel de toute tentative d'accès non autorisé à ces ressources leurres.
 * 3. Génération d'alertes instantanées avec traçage de la chaîne de compromission (IP source, horodatage, action).
 * 4. Déploiement proactif dans le code source ou la configuration pour piéger les attaquants en reconnaissance.
 */

export type HoneytokenType = 'API_KEY' | 'JWT_TOKEN' | 'DATABASE_RECORD' | 'CONFIG_ENV_SECRET' | 'CANARY_FILE'

export interface HoneytokenDefinition {
  tokenId: string
  name: string
  type: HoneytokenType
  tokenValue: string
  decoyLocation: string
  createdAt: number
  triggerCount: number
  isActive: boolean
}

export interface HoneytokenTriggerAlert {
  alertId: string
  tokenId: string
  tokenName: string
  triggeredAt: number
  sourceIp: string
  userAgent: string
  attemptedAction: string
  severity: 'CRITICAL'
  recommendedImmediateAction: string
}

const HONEYTOKEN_STORAGE_KEY = 'aurora.cyber.honeytokens.v1'

export class DynamicHoneytokenEngine {
  /**
   * Génère un nouveau jeton d'appât (Honeytoken) hautement attractif.
   */
  static generateHoneytoken(type: HoneytokenType, label: string, location: string): HoneytokenDefinition {
    const tokenId = `ht_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`
    let fakeSecret = ''

    switch (type) {
      case 'API_KEY':
        fakeSecret = `ak_live_aurora_${Math.random().toString(36).slice(2, 10)}_decoy`
        break
      case 'JWT_TOKEN':
        fakeSecret = `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhZG1pbi1kZWNveSIsImlzcyI6ImF1cm9yYS1jYW5hcnkiLCJpYXQiOjE3ODgyMTM4OTN9.decoy_signature_hash`
        break
      case 'DATABASE_RECORD':
        fakeSecret = `user_admin_backup_secret_hash_9941`
        break
      default:
        fakeSecret = `CANARY_SECRET_PAYLOAD_${Math.random().toString(36).toUpperCase().slice(2, 12)}`
    }

    const tokenDef: HoneytokenDefinition = {
      tokenId,
      name: label,
      type,
      tokenValue: fakeSecret,
      decoyLocation: location,
      createdAt: Date.now(),
      triggerCount: 0,
      isActive: true,
    }

    this.saveHoneytoken(tokenDef)
    return tokenDef
  }

  /**
   * Vérifie si une valeur soumise correspond à un jeton d'appât et génère une alerte de compromission immédiate.
   */
  static evaluateAccessAttempt(
    candidateValue: string,
    sourceIp: string = '127.0.0.1',
    userAgent: string = 'Unknown Scanner'
  ): HoneytokenTriggerAlert | null {
    const tokens = this.listHoneytokens()
    const match = tokens.find((t) => t.tokenValue === candidateValue && t.isActive)

    if (!match) return null

    // Incrément du compteur de déclenchement
    match.triggerCount++
    this.saveHoneytoken(match)

    return {
      alertId: `ALERT-CANARY-${Date.now()}`,
      tokenId: match.tokenId,
      tokenName: match.name,
      triggeredAt: Date.now(),
      sourceIp,
      userAgent,
      attemptedAction: `Tentative d'utilisation du jeton piège [${match.name}] localisé dans [${match.decoyLocation}].`,
      severity: 'CRITICAL',
      recommendedImmediateAction: `Isoler immédiatement l'IP ${sourceIp} et révoquer les accès de session associés.`,
    }
  }

  static listHoneytokens(): HoneytokenDefinition[] {
    try {
      const raw = localStorage.getItem(HONEYTOKEN_STORAGE_KEY)
      if (!raw) return []
      return JSON.parse(raw) as HoneytokenDefinition[]
    } catch {
      return []
    }
  }

  static saveHoneytoken(token: HoneytokenDefinition): void {
    try {
      const all = this.listHoneytokens().filter((t) => t.tokenId !== token.tokenId)
      all.unshift(token)
      localStorage.setItem(HONEYTOKEN_STORAGE_KEY, JSON.stringify(all.slice(0, 40)))
    } catch {
      // Gestion silencieuse du stockage local
    }
  }

  static clearHoneytokens(): void {
    try {
      localStorage.removeItem(HONEYTOKEN_STORAGE_KEY)
    } catch {
      // Nettoyage silencieux
    }
  }
}
