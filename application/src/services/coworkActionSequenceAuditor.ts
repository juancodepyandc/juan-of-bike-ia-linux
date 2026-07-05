// Détecteur de séquences d'actions dangereuses dans un plan Cowork.
// Au-delà de l'estimateur statique (qui regarde chaque action isolément),
// on cherche les COMBINAISONS problématiques :
//
//   - delete avant qu'un read sauvegardé ne soit fait
//   - write d'un fichier sensible (.env, .ssh/) sans confirmation user
//   - fetch externe puis exec d'un fichier reçu (RCE pattern)
//   - shell de commande avec argument provenant d'une réponse LLM
//
// Pure compute. Sortie : liste d'alertes avec niveau.

import type { CoworkAction, CoworkPlan } from './coworkTypes.ts'

export type SequenceAlert = {
  severity: 'info' | 'warn' | 'error' | 'critical'
  pattern: string
  message: string
  actionIndices: number[]
  recommendation: string
}

const SENSITIVE_PATHS = [
  /\.env$/i,
  /\.env\..+/i,
  /\.ssh\//,
  /id_rsa$/,
  /id_ed25519$/,
  /\.aws\//,
  /credentials/i,
  /secret[^/]*$/i,
  /\.npmrc$/,
  /\.git\//,
]

function pathIsSensitive(path: string): boolean {
  return SENSITIVE_PATHS.some((re) => re.test(path))
}

const DANGEROUS_SHELL_COMMANDS = [
  { pattern: /rm\s+-rf/, msg: 'rm -rf' },
  { pattern: /dd\s+if=/, msg: 'dd if=' },
  { pattern: /mkfs/, msg: 'mkfs' },
  { pattern: /chmod\s+(?:777|\+rwx)/, msg: 'chmod 777' },
  { pattern: /sudo\b/, msg: 'sudo' },
  { pattern: /eval\s+\$/, msg: 'eval $' },
  { pattern: /curl\s+[^|]+\|\s*(?:sh|bash|zsh|python)/, msg: 'curl pipe shell (RCE)' },
  { pattern: />\s*\/dev\/(?:sda|nvme|null)/, msg: 'overwrite raw device' },
]

/**
 * Audit complet du plan.
 */
export function auditActionSequence(plan: CoworkPlan): SequenceAlert[] {
  const alerts: SequenceAlert[] = []
  const actions = plan.actions

  // 1. Sensitive file write/delete.
  for (let i = 0; i < actions.length; i += 1) {
    const a = actions[i]
    if (a.kind === 'write_file' || a.kind === 'edit_file' || a.kind === 'delete_file') {
      if (pathIsSensitive(a.path)) {
        alerts.push({
          severity: 'critical',
          pattern: 'sensitive-file-mutation',
          message: `Modification d'un fichier sensible : ${a.path}`,
          actionIndices: [i],
          recommendation: 'Confirmer manuellement, vérifier qu\'aucun secret n\'est exfiltré.',
        })
      }
    }
  }

  // 2. Commandes shell dangereuses.
  for (let i = 0; i < actions.length; i += 1) {
    const a = actions[i]
    if (a.kind !== 'shell') continue
    const full = `${a.command} ${a.args.join(' ')}`
    for (const d of DANGEROUS_SHELL_COMMANDS) {
      if (d.pattern.test(full)) {
        alerts.push({
          severity: 'critical',
          pattern: 'dangerous-shell',
          message: `Commande shell dangereuse : ${d.msg}`,
          actionIndices: [i],
          recommendation: 'Vérifier que la cible est légitime + confirmation user.',
        })
      }
    }
  }

  // 3. Pattern : delete sans read préalable (data loss).
  const observedPaths: string[] = []
  for (let i = 0; i < actions.length; i += 1) {
    const a = actions[i]
    if (a.kind === 'read_file' || a.kind === 'list_dir') observedPaths.push(a.path)
    if (a.kind === 'delete_file' && !observedPaths.some((path) => pathCoversDelete(path, a.path))) {
      alerts.push({
        severity: 'error',
        pattern: 'delete-without-read',
        message: `Delete de ${a.path} sans backup préalable (read).`,
        actionIndices: [i],
        recommendation: 'Insérer un read_file avant pour permettre rollback.',
      })
    }
  }

  // 4. RCE pattern : fetch externe puis shell d'un fichier reçu.
  // 3b. Delete sans verification apres coup : l'action peut etre voulue, mais
  // Cowork doit verifier que l'ancienne sortie a vraiment disparu.
  for (let i = 0; i < actions.length; i += 1) {
    const a = actions[i]
    if (a.kind !== 'delete_file') continue
    const verifiedAfter = actions.slice(i + 1).some((next) => {
      if (next.kind === 'list_dir') return pathCoversDelete(next.path, a.path) || pathCoversDelete(parentPath(a.path), next.path)
      if (next.kind === 'read_file') return pathCoversDelete(parentPath(a.path), next.path)
      if (next.kind !== 'shell') return false
      return /\b(test|build|check|ls|dir|rg|find|exists|stat)\b/i.test(`${next.command} ${next.args.join(' ')}`)
    })
    if (!verifiedAfter) {
      alerts.push({
        severity: 'warn',
        pattern: 'delete-without-post-verification',
        message: `Delete de ${a.path} sans verification posterieure.`,
        actionIndices: [i],
        recommendation: 'Ajouter list_dir/read_file/shell check apres suppression pour confirmer l etat final.',
      })
    }
  }

  for (let i = 0; i < actions.length - 1; i += 1) {
    const a = actions[i]
    if (a.kind !== 'fetch') continue
    const isExternal = !/^https?:\/\/(localhost|127\.|192\.168\.|10\.|172\.(?:1[6-9]|2\d|3[01])\.)/.test(a.url)
    if (!isExternal) continue
    // Cherche un shell dans les 3 actions suivantes.
    for (let j = i + 1; j <= Math.min(i + 3, actions.length - 1); j += 1) {
      if (actions[j].kind === 'shell') {
        alerts.push({
          severity: 'critical',
          pattern: 'fetch-then-shell',
          message: `Fetch externe (${a.url}) suivi d'un shell — risque RCE.`,
          actionIndices: [i, j],
          recommendation: 'Vérifier l\'origine du fetch ; ne JAMAIS exec sans signature/hash.',
        })
        break
      }
    }
  }

  // 5. Write puis fetch (exfiltration potentielle de données écrites).
  for (let i = 0; i < actions.length - 1; i += 1) {
    const a = actions[i]
    if (a.kind !== 'write_file') continue
    if (!pathIsSensitive(a.path)) continue
    for (let j = i + 1; j <= Math.min(i + 5, actions.length - 1); j += 1) {
      const b = actions[j]
      if (b.kind === 'fetch' || b.kind === 'open_url') {
        alerts.push({
          severity: 'critical',
          pattern: 'sensitive-write-then-fetch',
          message: `Write sur fichier sensible suivi d'un fetch — risque exfiltration.`,
          actionIndices: [i, j],
          recommendation: 'Vérifier la destination du fetch.',
        })
        break
      }
    }
  }

  // 6. Trop de shell consécutives = scriptable risk.
  let consecShell = 0
  let firstShellIdx = -1
  for (let i = 0; i < actions.length; i += 1) {
    if (actions[i].kind === 'shell') {
      if (firstShellIdx === -1) firstShellIdx = i
      consecShell += 1
    } else {
      if (consecShell >= 4) {
        alerts.push({
          severity: 'warn',
          pattern: 'many-consecutive-shell',
          message: `${consecShell} commandes shell consécutives — wrap dans un script audité plutôt.`,
          actionIndices: Array.from({ length: consecShell }, (_, k) => firstShellIdx + k),
          recommendation: 'Écrire un script .sh isolé et l\'exécuter via un seul shell action.',
        })
      }
      consecShell = 0
      firstShellIdx = -1
    }
  }

  // 7. clipboard_write avec données qui peuvent venir d'un read_file sensible.
  // Heuristique : si on a write+sensitive ou read+sensitive avant un clipboard_write.
  for (let i = 0; i < actions.length; i += 1) {
    const a = actions[i]
    if (a.kind !== 'clipboard_write') continue
    // Look back 3 actions.
    for (let j = Math.max(0, i - 3); j < i; j += 1) {
      const b = actions[j]
      if ((b.kind === 'read_file' || b.kind === 'write_file') && pathIsSensitive(b.path)) {
        alerts.push({
          severity: 'warn',
          pattern: 'sensitive-then-clipboard',
          message: `Action sur fichier sensible suivie d'un clipboard_write — risque fuite.`,
          actionIndices: [j, i],
          recommendation: 'Vérifier le contenu mis dans le presse-papier.',
        })
        break
      }
    }
  }

  // 8. Projet genere trop superficiel : pour une demande qui promet un projet
  // ou une application, un seul fichier ou l'absence de test/build est une
  // fragilite. L'alerte ne bloque pas l'execution, elle pousse Cowork a
  // enrichir le livrable avant de le declarer stable.
  alerts.push(...auditProjectGenerationQuality(plan))

  return alerts
}

/**
 * Vérification rapide : true si au moins 1 critical, ou ≥ 2 errors.
 */
export function planRequiresHumanReview(alerts: SequenceAlert[]): boolean {
  const critical = alerts.filter((a) => a.severity === 'critical').length
  const errors = alerts.filter((a) => a.severity === 'error').length
  return critical >= 1 || errors >= 2
}

function auditProjectGenerationQuality(plan: CoworkPlan): SequenceAlert[] {
  const text = normalizeText(`${plan.reasoning} ${plan.expectedOutcome}`)
  const actions = plan.actions
  const writeIndices = actions
    .map((action, index) => ({ action, index }))
    .filter(({ action }) => action.kind === 'write_file' || action.kind === 'edit_file')
  const writePaths = writeIndices.map(({ action }) => action.kind === 'write_file' || action.kind === 'edit_file' ? action.path : '')

  const looksLikeProject = /\b(projet|application|app|codebase|starter|scaffold|base logicielle|logiciel)\b/.test(text)
    || writePaths.some((path) => /(^|\/)(package\.json|pyproject\.toml|cargo\.toml|vite\.config|tsconfig\.json)$/.test(normalizePath(path)))
  if (!looksLikeProject || writeIndices.length === 0) return []

  const hasManifest = writePaths.some((path) => /(^|\/)(package\.json|pyproject\.toml|cargo\.toml|vite\.config|tsconfig\.json)$/.test(normalizePath(path)))
  const hasSource = writePaths.some((path) => /(^|\/)(src|app|lib)\//.test(normalizePath(path)) || /\.(ts|tsx|js|jsx|mjs|py|rs|html|css)$/i.test(path))
  const hasTestFile = writePaths.some((path) => /(^|\/)(__tests__|tests?)\/|(\.test|\.spec)\.(ts|tsx|js|jsx|mjs|py|rs)$/i.test(normalizePath(path)))
  const hasExecutableCheck = actions.some((action) => {
    if (action.kind !== 'shell') return false
    return /\b(test|build|lint|check|typecheck|tsc|pytest|cargo test|node --test|npm test|pnpm test|yarn test)\b/i.test(`${action.command} ${action.args.join(' ')}`)
  })
  const lastWriteIndex = Math.max(...writeIndices.map((entry) => entry.index))
  const hasPostWriteObservation = actions.slice(lastWriteIndex + 1).some((action) => (
    action.kind === 'read_file'
    || action.kind === 'list_dir'
    || action.kind === 'shell'
  ))

  const alerts: SequenceAlert[] = []
  if (writeIndices.length < 3 || !hasManifest || !hasSource) {
    alerts.push({
      severity: 'error',
      pattern: 'project-generation-too-thin',
      message: 'Generation de projet trop superficielle : attendu manifest + source + plusieurs fichiers coherents.',
      actionIndices: writeIndices.map((entry) => entry.index),
      recommendation: 'Creer une base projet complete : manifest, src/, tests ou exemple d execution, README/config si utile.',
    })
  }
  if (!hasTestFile || !hasExecutableCheck || !hasPostWriteObservation) {
    alerts.push({
      severity: 'error',
      pattern: 'project-generation-without-verification',
      message: 'Projet genere sans preuve de stabilite suffisante.',
      actionIndices: actions.map((_, index) => index),
      recommendation: 'Ajouter un test/build/lint executable apres creation, puis relire ou lister la sortie avant finish.',
    })
  }
  return alerts
}

function pathCoversDelete(observedPath: string, deletedPath: string): boolean {
  const observed = normalizePath(observedPath)
  const deleted = normalizePath(deletedPath)
  if (!observed || !deleted) return false
  return observed === deleted || deleted.startsWith(`${observed}/`)
}

function parentPath(path: string): string {
  const normalized = normalizePath(path)
  const idx = normalized.lastIndexOf('/')
  return idx <= 0 ? normalized : normalized.slice(0, idx)
}

function normalizePath(path: string): string {
  return path.trim().replace(/\\/g, '/').replace(/\/+/g, '/').replace(/\/$/, '').toLowerCase()
}

function normalizeText(value: string): string {
  return value
    .toLowerCase()
    .normalize('NFD')
    .replace(/\p{Diacritic}/gu, '')
}
