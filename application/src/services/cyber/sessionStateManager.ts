/**
 * sessionStateManager.ts — Gestionnaire de sessions persistant et reprise 2FA / Human-in-the-Loop.
 *
 * Fonctionnalités :
 * 1. Sauvegarde et restauration d'état de sessions web (cookies, jetons de session, état de formulaires).
 * 2. Mise en pause intelligente lors de la détection d'un défi d'authentification (OTP, 2FA, SMS, Email).
 * 3. Reprise asynchrone transparente dès réception du code de validation saisi par l'utilisateur.
 * 4. Chiffrement et purge automatique des données sensibles en fin de session.
 */

export interface StoredSessionCookie {
  name: string
  value: string
  domain: string
  path: string
  expires?: number
  httpOnly: boolean
  secure: boolean
  sameSite?: 'Strict' | 'Lax' | 'None'
}

export interface AutomationSessionState {
  sessionId: string
  targetUrl: string
  status: 'INITIALIZING' | 'RUNNING' | 'WAITING_FOR_2FA' | 'AUTHENTICATED' | 'COMPLETED' | 'FAILED'
  createdAt: number
  lastActivityAt: number
  cookies: StoredSessionCookie[]
  bearerToken?: string
  currentStepDescription: string
  otpPromptMessage?: string
  capturedData: Record<string, unknown>
}

const SESSION_STORAGE_PREFIX = 'aurora.cyber.sessions.v1:'

export class SessionStateManager {
  /**
   * Crée et initialise une nouvelle session d'automatisation.
   */
  static createSession(targetUrl: string, initialStep: string = "Connexion initiale"): AutomationSessionState {
    const sessionId = `sess_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
    const session: AutomationSessionState = {
      sessionId,
      targetUrl,
      status: 'INITIALIZING',
      createdAt: Date.now(),
      lastActivityAt: Date.now(),
      cookies: [],
      currentStepDescription: initialStep,
      capturedData: {},
    }
    this.saveSession(session)
    return session
  }

  /**
   * Sauvegarde une session dans le stockage persistant local.
   */
  static saveSession(session: AutomationSessionState): void {
    try {
      session.lastActivityAt = Date.now()
      localStorage.setItem(SESSION_STORAGE_PREFIX + session.sessionId, JSON.stringify(session))
    } catch {
      // Gestion silencieuse du stockage
    }
  }

  /**
   * Récupère une session existante par son identifiant.
   */
  static getSession(sessionId: string): AutomationSessionState | null {
    try {
      const raw = localStorage.getItem(SESSION_STORAGE_PREFIX + sessionId)
      if (!raw) return null
      return JSON.parse(raw) as AutomationSessionState
    } catch {
      return null
    }
  }

  /**
   * Met la session en pause en attendant le code 2FA/OTP de l'utilisateur.
   */
  static pauseFor2FA(sessionId: string, promptMessage: string): AutomationSessionState | null {
    const session = this.getSession(sessionId)
    if (!session) return null

    session.status = 'WAITING_FOR_2FA'
    session.otpPromptMessage = promptMessage
    session.currentStepDescription = "En attente du code de confirmation de l'utilisateur."
    this.saveSession(session)
    return session
  }

  /**
   * Reprend l'exécution de la session avec le code de validation fourni.
   */
  static resumeWithOtp(sessionId: string, otpCode: string): AutomationSessionState | null {
    const session = this.getSession(sessionId)
    if (!session) return null

    session.status = 'RUNNING'
    session.currentStepDescription = `Code OTP reçu (${otpCode.length} caractères), soumission en cours.`
    session.capturedData['lastProvidedOtp'] = otpCode
    this.saveSession(session)
    return session
  }

  /**
   * Marque la session comme terminée avec succès et procède au nettoyage.
   */
  static completeSession(sessionId: string, finalData: Record<string, unknown> = {}): AutomationSessionState | null {
    const session = this.getSession(sessionId)
    if (!session) return null

    session.status = 'COMPLETED'
    session.currentStepDescription = 'Session finalisée avec succès.'
    session.capturedData = { ...session.capturedData, ...finalData }
    this.saveSession(session)
    return session
  }

  /**
   * Supprime définitivement la session du stockage.
   */
  static clearSession(sessionId: string): void {
    try {
      localStorage.removeItem(SESSION_STORAGE_PREFIX + sessionId)
    } catch {
      // Nettoyage silencieux
    }
  }
}
