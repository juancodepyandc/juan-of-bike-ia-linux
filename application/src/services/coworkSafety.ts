// Validation preventive des actions Cowork avant execution.

import type { CoworkAction, CoworkRuntime } from './coworkTypes'

export const SAFETY_LIMITS = {
  maxReadFileBytes: 5 * 1024 * 1024,
  maxWriteFileBytes: 5 * 1024 * 1024,
  maxFetchBytes: 10 * 1024 * 1024,
  maxShellTimeoutMs: 5 * 60 * 1000,
  defaultShellTimeoutMs: 60 * 1000,
  defaultFetchTimeoutMs: 30 * 1000,
  maxListDirEntries: 5000,
  maxPlanIterations: 8,
} as const

// Commandes executees sans confirmation.
const SHELL_ALLOWLIST: readonly string[] = [
  'git', 'gh', 'npm', 'pnpm', 'yarn', 'node', 'npx',
  'python', 'python3', 'pip', 'pip3', 'uv',
  'cargo', 'rustc', 'rustup',
  'go', 'tsc', 'eslint', 'prettier',
  'curl', 'wget', 'echo', 'printf',
  'ls', 'dir', 'pwd', 'whoami', 'where', 'which',
  'cat', 'head', 'tail', 'grep', 'rg', 'fd', 'find',
  'wc', 'sort', 'uniq', 'cut', 'awk', 'sed',
  'tar', 'unzip', 'zip', '7z',
  'docker', 'kubectl',
  'ollama', 'tauri',
]

// Commandes a risque majeur : en mode preventif elles demandent confirmation.
const SHELL_BLOCKLIST: readonly string[] = [
  'format', 'mkfs', 'mkfs.ext4', 'mkfs.ntfs', 'mkfs.fat',
  'fdisk', 'parted', 'diskpart',
  'dd',
  'shutdown', 'halt', 'poweroff', 'reboot', 'init',
  'sudo', 'su', 'doas',
  'runas',
  ':(){ :|:& };:',
]

// Arguments qui transforment une commande normale en action sensible.
const SHELL_DANGEROUS_ARG_PATTERNS: readonly RegExp[] = [
  /^-rf?$/i,
  /\/\s*$/,
  /^[a-z]:[\\/]+$/i,
  /\b(rm|del|erase|rmdir)\s+-rf?\s+\/?\s*$/i,
]

export type SafetyVerdict = {
  decision: 'allow' | 'confirm' | 'block'
  reason: string
  destructive: boolean
  normalized: CoworkAction
}

const sessionApprovedExternalPaths = new Set<string>()

export function approveExternalPath(path: string): void {
  sessionApprovedExternalPaths.add(normalizePath(path))
}

export function clearSessionApprovals(): void {
  sessionApprovedExternalPaths.clear()
}

function isSessionApprovedPath(path: string): boolean {
  const normalized = normalizePath(path).toLowerCase()
  for (const approvedRaw of sessionApprovedExternalPaths) {
    const approved = normalizePath(approvedRaw).toLowerCase()
    if (normalized === approved || normalized.startsWith(approved + '/')) return true
  }
  return false
}

export type ValidateOptions = {
  trustMode?: boolean
  dangerMode?: boolean
  fullyUnlocked?: boolean
}

export function validateAction(
  action: CoworkAction,
  runtime: CoworkRuntime,
  workspaceRoot: string,
  options: ValidateOptions = {},
): SafetyVerdict {
  if (options.fullyUnlocked) {
    return {
      decision: 'allow',
      reason: 'Deverrouille totalement - l utilisateur a accepte les risques.',
      destructive: isDestructive(action),
      normalized: action,
    }
  }
  // Le duo danger+trust lance sans confirmation logicielle.
  const noGuardrails = !!(options.dangerMode && options.trustMode)

  if (runtime === 'web-mobile' && isDestructive(action) && !noGuardrails) {
    if (options.dangerMode) {
      return {
        decision: 'confirm',
        reason: 'Mobile : action destructive demandee. Mode preventif : confirmation requise au lieu d un blocage.',
        destructive: true,
        normalized: action,
      }
    }
    return {
      decision: 'block',
      reason: 'Mobile : actions destructives interdites. Utilise l app PC ou l extension navigateur.',
      destructive: true,
      normalized: action,
    }
  }

  const verdict = computeBaseVerdict(action, runtime, workspaceRoot)

  if (noGuardrails) {
    if (verdict.decision === 'block' || verdict.decision === 'confirm') {
      return { ...verdict, decision: 'allow', reason: `${verdict.reason} (ZERO GARDE FOU - danger+trust)` }
    }
    return verdict
  }

  // Mode preventif : avertir et demander confirmation plutot que bloquer.
  if (options.dangerMode && verdict.decision === 'block' && isPreventableBlock(action, verdict.reason)) {
    return { ...verdict, decision: 'confirm', reason: `${verdict.reason} (mode preventif - confirmation requise, pas de blocage)` }
  }
  // Mode confiance : les confirmations preventives deviennent automatiques.
  if (options.trustMode && verdict.decision === 'confirm') {
    return { ...verdict, decision: 'allow', reason: `${verdict.reason} (trust mode)` }
  }
  return verdict
}

function computeBaseVerdict(
  action: CoworkAction,
  runtime: CoworkRuntime,
  workspaceRoot: string,
): SafetyVerdict {

  switch (action.kind) {
    case 'reply':
    case 'finish':
      return { decision: 'allow', reason: 'message', destructive: false, normalized: action }

    case 'read_file': {
      const resolved = resolvePath(action.path, workspaceRoot)
      const inWorkspace = isInsideWorkspace(resolved, workspaceRoot)
      const approved = isSessionApprovedPath(resolved)
      const standardUserRead = isInsideStandardUserReadPath(resolved, workspaceRoot)
      return {
        decision: inWorkspace || approved || standardUserRead ? 'allow' : 'confirm',
        reason: inWorkspace
          ? 'lecture workspace'
          : (standardUserRead ? 'lecture dossier utilisateur standard' : 'lecture hors workspace'),
        destructive: false,
        normalized: { ...action, path: resolved },
      }
    }

    case 'list_dir': {
      const resolved = resolvePath(action.path, workspaceRoot)
      const inWorkspace = isInsideWorkspace(resolved, workspaceRoot)
      const approved = isSessionApprovedPath(resolved)
      const standardUserRead = isInsideStandardUserReadPath(resolved, workspaceRoot)
      return {
        decision: inWorkspace || approved || standardUserRead ? 'allow' : 'confirm',
        reason: inWorkspace
          ? 'liste workspace'
          : (standardUserRead ? 'liste dossier utilisateur standard' : 'liste hors workspace'),
        destructive: false,
        normalized: { ...action, path: resolved },
      }
    }

    case 'write_file': {
      if (action.content.length > SAFETY_LIMITS.maxWriteFileBytes) {
        return {
          decision: 'block',
          reason: `Contenu trop volumineux (${action.content.length} > ${SAFETY_LIMITS.maxWriteFileBytes} octets).`,
          destructive: true,
          normalized: action,
        }
      }
      const resolved = resolvePath(action.path, workspaceRoot)
      const inWorkspace = isInsideWorkspace(resolved, workspaceRoot)
      const approved = isSessionApprovedPath(resolved)
      const sensitive = isSensitivePath(resolved)
      return {
        decision: (inWorkspace || approved) && !sensitive ? 'allow' : 'confirm',
        reason: inWorkspace
          ? (sensitive ? 'ecriture fichier sensible (workspace)' : 'ecriture fichier workspace')
          : (approved && !sensitive ? 'ecriture fichier dossier approuve' : 'ecriture fichier hors workspace'),
        destructive: true,
        normalized: { ...action, path: resolved },
      }
    }

    case 'edit_file': {
      if (action.newText.length > SAFETY_LIMITS.maxWriteFileBytes) {
        return {
          decision: 'block',
          reason: `Contenu trop volumineux (${action.newText.length} octets).`,
          destructive: true,
          normalized: action,
        }
      }
      const resolved = resolvePath(action.path, workspaceRoot)
      const inWorkspace = isInsideWorkspace(resolved, workspaceRoot)
      const approved = isSessionApprovedPath(resolved)
      const sensitive = isSensitivePath(resolved)
      return {
        decision: (inWorkspace || approved) && !sensitive ? 'allow' : 'confirm',
        reason: inWorkspace
          ? (sensitive ? 'modification fichier sensible (workspace)' : 'modification fichier workspace (replace exact-match)')
          : (approved && !sensitive ? 'modification fichier dossier approuve' : 'modification fichier hors workspace'),
        destructive: true,
        normalized: { ...action, path: resolved },
      }
    }

    case 'delete_file': {
      const resolved = resolvePath(action.path, workspaceRoot)
      if (
        resolved === workspaceRoot ||
        /^[/\\]$/.test(resolved) ||
        /^[a-z]:[/\\]?$/i.test(resolved)
      ) {
        return {
          decision: 'block',
          reason: `Suppression refusee : chemin protege (${resolved}).`,
          destructive: true,
          normalized: action,
        }
      }
      return {
        decision: 'confirm',
        reason: 'suppression fichier/dossier',
        destructive: true,
        normalized: { ...action, path: resolved },
      }
    }

    case 'shell': {
      const cmd = action.command.trim()
      if (!cmd) {
        return { decision: 'block', reason: 'Commande vide.', destructive: false, normalized: action }
      }
      const cmdBase = baseCommandName(cmd)
      if (SHELL_BLOCKLIST.includes(cmdBase.toLowerCase())) {
        return {
          decision: 'block',
          reason: `Commande interdite par la politique de securite : ${cmdBase}.`,
          destructive: true,
          normalized: action,
        }
      }
      const args = action.args ?? []
      for (const arg of args) {
        for (const pat of SHELL_DANGEROUS_ARG_PATTERNS) {
          if (pat.test(arg)) {
            return {
              decision: 'confirm',
              reason: `Argument potentiellement destructif : "${arg}". Confirme avant execution.`,
              destructive: true,
              normalized: { ...action, command: cmd, args },
            }
          }
        }
      }
      const isAllowlisted = SHELL_ALLOWLIST.includes(cmdBase.toLowerCase())
      return {
        decision: isAllowlisted ? 'allow' : 'confirm',
        reason: isAllowlisted
          ? `commande allowlist : ${cmdBase}`
          : `commande non allowlist : ${cmdBase}. Confirme avant execution.`,
        destructive: !isAllowlisted,
        normalized: { ...action, command: cmd, args },
      }
    }

    case 'web_search': {
      const query = action.query.trim()
      if (!query) {
        return { decision: 'block', reason: 'web_search.query vide', destructive: false, normalized: action }
      }
      return {
        decision: 'allow',
        reason: 'recherche web native',
        destructive: false,
        normalized: { ...action, query, limit: action.limit ? Math.max(1, Math.min(10, Math.round(action.limit))) : undefined },
      }
    }

    case 'fetch': {
      const url = (action.url || '').trim()
      try {
        const u = new URL(url)
        if (!['https:', 'http:'].includes(u.protocol)) {
          return {
            decision: 'block',
            reason: `Protocole non supporte : ${u.protocol}`,
            destructive: false,
            normalized: action,
          }
        }
        const isHttp = u.protocol === 'http:'
        const isLocal = u.hostname === 'localhost' || u.hostname === '127.0.0.1' || u.hostname.endsWith('.localhost')
        return {
          decision: isHttp && !isLocal ? 'confirm' : 'allow',
          reason: isHttp && !isLocal ? 'http non chiffre - confirmer' : 'fetch reseau',
          destructive: false,
          normalized: { ...action, url },
        }
      } catch {
        return { decision: 'block', reason: `URL invalide : ${url}`, destructive: false, normalized: action }
      }
    }

    case 'open_url': {
      const url = (action.url || '').trim()
      try {
        const u = new URL(url)
        if (!['https:', 'http:'].includes(u.protocol)) {
          return {
            decision: 'block',
            reason: `Protocole non supporte : ${u.protocol}`,
            destructive: false,
            normalized: action,
          }
        }
        return { decision: 'allow', reason: 'ouverture navigateur', destructive: false, normalized: { ...action, url } }
      } catch {
        return { decision: 'block', reason: `URL invalide : ${url}`, destructive: false, normalized: action }
      }
    }

    case 'clipboard_read':
      return { decision: 'allow', reason: 'lecture presse-papiers', destructive: false, normalized: action }

    case 'clipboard_write':
      return { decision: 'allow', reason: 'ecriture presse-papiers', destructive: false, normalized: action }

    case 'voice_speak': {
      const len = action.text?.length ?? 0
      if (!action.text) {
        return { decision: 'block', reason: 'voice_speak.text vide', destructive: false, normalized: action }
      }
      if (len > 4000) {
        return {
          decision: 'block',
          reason: `voice_speak.text trop long (${len} > 4000 caracteres).`,
          destructive: false,
          normalized: action,
        }
      }
      return { decision: 'allow', reason: 'TTS Kokoro', destructive: false, normalized: action }
    }

    case 'think': {
      if (!action.thought || !action.thought.trim()) {
        return { decision: 'block', reason: 'think.thought vide', destructive: false, normalized: action }
      }
      return { decision: 'allow', reason: 'reflexion', destructive: false, normalized: action }
    }

    case 'think_long': {
      if (!action.topic?.trim() || !action.prompt?.trim()) {
        return { decision: 'block', reason: 'think_long requiert topic + prompt non vides', destructive: false, normalized: action }
      }
      return { decision: 'allow', reason: 'reflexion longue (LLM local)', destructive: false, normalized: action }
    }

    case 'remember_fact': {
      if (!action.fact?.trim()) {
        return { decision: 'block', reason: 'remember_fact.fact vide', destructive: false, normalized: action }
      }
      return { decision: 'allow', reason: 'memoire user (localStorage)', destructive: false, normalized: action }
    }

    case 'forget_fact': {
      if (!action.id && !action.matching) {
        return { decision: 'block', reason: 'forget_fact requiert id ou matching', destructive: false, normalized: action }
      }
      return { decision: 'allow', reason: 'oubli memoire user', destructive: false, normalized: action }
    }

    case 'vision_describe': {
      if (!action.imageDataUrl || !action.imageDataUrl.startsWith('data:')) {
        return { decision: 'block', reason: 'vision_describe.imageDataUrl manquant ou format invalide (attendu data:...)', destructive: false, normalized: action }
      }
      return { decision: 'allow', reason: 'vision (qwen3-vl local)', destructive: false, normalized: action }
    }

    case 'screenshot_desktop': {
      return { decision: 'allow', reason: 'capture ecran systeme (Print Screen)', destructive: false, normalized: action }
    }

    case 'connector': {
      const id = (action.connector || '').trim()
      const op = (action.action || '').trim()
      if (!id) return { decision: 'block', reason: 'connector.connector vide', destructive: false, normalized: action }
      if (!op) return { decision: 'block', reason: 'connector.action vide', destructive: false, normalized: action }
      // Actions de connecteur qui changent un service externe.
      const destructiveOps = new Set([
        'create_issue', 'merge_pr', 'send_message', 'create_page',
        'create_deployment', 'create_design', 'update_issue',
        'play', 'pause', 'next', 'call_service', 'set_light',
      ])
      const destructive = destructiveOps.has(op)
      return {
        decision: destructive ? 'confirm' : 'allow',
        reason: destructive ? `connector ${id}.${op} - appel externe destructif` : `connector ${id}.${op}`,
        destructive,
        normalized: { ...action, connector: id, action: op, params: action.params ?? {} },
      }
    }

    case 'browser': {
      const op = action.operation
      const destructive = op === 'eval' || op === 'navigate'
      return {
        decision: destructive ? 'confirm' : 'allow',
        reason: destructive ? `browser ${op} (potentiellement destructif)` : `browser ${op}`,
        destructive,
        normalized: action,
      }
    }

    case 'dom_query': {
      if (runtime === 'tauri-desktop') {
        return {
          decision: 'block',
          reason: 'dom_query non disponible sur Tauri (le shell n a pas de DOM web a inspecter).',
          destructive: false,
          normalized: action,
        }
      }
      const sel = (action.selector || '').trim()
      if (!sel) {
        return { decision: 'block', reason: 'dom_query.selector vide', destructive: false, normalized: action }
      }
      if (/^\*+$/.test(sel)) {
        return { decision: 'block', reason: 'selecteur "*" interdit (trop large)', destructive: false, normalized: action }
      }
      return { decision: 'allow', reason: 'lecture DOM', destructive: false, normalized: action }
    }

    default: {
      const _exhaustive: never = action
      return {
        decision: 'block',
        reason: `Action inconnue : ${JSON.stringify(_exhaustive)}`,
        destructive: false,
        normalized: action as CoworkAction,
      }
    }
  }
}

function isDestructive(action: CoworkAction): boolean {
  return ['write_file', 'edit_file', 'delete_file', 'shell'].includes(action.kind)
}

function isPreventableBlock(action: CoworkAction, reason: string): boolean {
  if (action.kind === 'shell') return !!action.command?.trim()
  if (action.kind === 'write_file' || action.kind === 'edit_file' || action.kind === 'delete_file') return true
  if (action.kind === 'voice_speak') return /trop long/i.test(reason)
  if (action.kind === 'dom_query') return /trop large|interdit/i.test(reason)
  return false
}

function isSensitivePath(path: string): boolean {
  const normalized = normalizePath(path).toLowerCase()
  return /(^|\/)(\.env(\..*)?|id_rsa|id_dsa|id_ecdsa|id_ed25519|credentials(\..*)?|secrets?(\..*)?)$/.test(normalized)
    || /\.(pem|key|p12|pfx|crt)$/i.test(normalized)
}

function baseCommandName(command: string): string {
  const basename = command.split(/[\\/]/).pop() || command
  return basename.replace(/\.(exe|cmd|bat|sh|ps1)$/i, '')
}

export function resolvePath(input: string, workspaceRoot: string): string {
  if (!input) return workspaceRoot
  if (/^([a-z]:[\\/]|[\\/])/i.test(input)) {
    return normalizePath(input)
  }
  return normalizePath(joinPaths(workspaceRoot, input))
}

export function isInsideWorkspace(absolutePath: string, workspaceRoot: string): boolean {
  const root = normalizePath(workspaceRoot).toLowerCase()
  const path = normalizePath(absolutePath).toLowerCase()
  if (root === path) return true
  return path.startsWith(root + '/') || path.startsWith(root + '\\')
}

function isInsideStandardUserReadPath(absolutePath: string, workspaceRoot: string): boolean {
  const home = inferUserHomeFromWorkspace(workspaceRoot)
  if (!home) return false
  const path = normalizePath(absolutePath).toLowerCase()
  const allowedFolders = ['Desktop', 'Bureau', 'Documents', 'Downloads', 'Telechargements']
    .map((folder) => joinPaths(home, folder).toLowerCase())
  return allowedFolders.some((folder) => path === folder || path.startsWith(folder + '/'))
}

function inferUserHomeFromWorkspace(workspaceRoot: string): string | null {
  const normalized = normalizePath(workspaceRoot)
  const windows = normalized.match(/^([a-z]:\/Users\/[^/]+)/i)
    || normalized.match(/^(\/[a-z]\/Users\/[^/]+)/i)
  if (windows) return windows[1]
  const unix = normalized.match(/^(\/home\/[^/]+)/i)
    || normalized.match(/^(\/Users\/[^/]+)/i)
  return unix?.[1] || null
}

export function normalizePath(p: string): string {
  const sep = p.includes('\\') && !p.includes('/') ? '\\' : '/'
  const parts = p.replace(/\\/g, '/').split('/')
  const out: string[] = []
  for (const part of parts) {
    if (part === '' || part === '.') {
      if (out.length === 0) out.push(part)
      continue
    }
    if (part === '..') {
      if (out.length > 1) out.pop()
      continue
    }
    out.push(part)
  }
  return out.join(sep === '\\' ? '/' : '/')
    .replace(/\/+/g, '/')
    .replace(/\/$/, '') || '/'
}

function joinPaths(a: string, b: string): string {
  if (!a) return b
  if (!b) return a
  return a.replace(/[\\/]+$/, '') + '/' + b.replace(/^[\\/]+/, '')
}
