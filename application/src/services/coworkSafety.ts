// Validation preventive des actions Cowork avant execution.

import type { CoworkAction, CoworkRuntime } from './coworkTypes.ts'

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

export type ReversibilityClass =
  | 'pure_read'
  | 'idempotent'
  | 'snapshot_reversible'
  | 'compensatable'
  | 'irreversible'

export type BlastRadiusScope =
  | 'none'
  | 'single_file'
  | 'workspace_subtree'
  | 'user_profile'
  | 'system_wide'
  | 'external_network'

export type ReversibilityAssessment = {
  classification: ReversibilityClass
  reversible: boolean
  requiresPreSnapshot: boolean
  inverseStrategy: string
  rollbackConfidence: number
}

export type BlastRadiusAssessment = {
  scope: BlastRadiusScope
  /** Score continu normalise dans [0, 1] mesurant l ampleur potentielle de l impact. */
  score: number
  affectedTargets: string[]
  recursiveOrWildcard: boolean
  crossesWorkspaceBoundary: boolean
  touchesSensitiveTarget: boolean
}

export type SafetyVerdict = {
  decision: 'allow' | 'confirm' | 'block'
  reason: string
  destructive: boolean
  normalized: CoworkAction
  reversibility: ReversibilityAssessment
  blastRadius: BlastRadiusAssessment
}

export type PlanSafetyEnvelope = {
  verdicts: SafetyVerdict[]
  overallDecision: 'allow' | 'confirm' | 'block'
  maxBlastRadiusScore: number
  cumulativeBlastScore: number
  dominantScope: BlastRadiusScope
  fullyReversible: boolean
  unguardedMutations: Array<{ index: number; target: string; kind: CoworkAction['kind']; reason: string }>
  irreversibleIndices: number[]
}

const sessionApprovedExternalPaths = new Set<string>()

export function approveExternalPath(path: string): void {
  sessionApprovedExternalPaths.add(normalizePath(path))
}

export function clearSessionApprovals(): void {
  sessionApprovedExternalPaths.clear()
}

function isSessionApprovedPath(path: string): boolean {
  for (const approved of sessionApprovedExternalPaths) {
    if (isInsideWorkspace(path, approved)) return true
  }
  return false
}

export type ValidateOptions = {
  trustMode?: boolean
  dangerMode?: boolean
  fullyUnlocked?: boolean
  hasPreSnapshot?: boolean
}

function attachFormalSafetyMetrics(
  base: Omit<SafetyVerdict, 'reversibility' | 'blastRadius'>,
  workspaceRoot: string,
  hasPreSnapshot = false,
): SafetyVerdict {
  const normalized = base.normalized
  const blastRadius = assessActionBlastRadius(normalized, workspaceRoot)
  const reversibility = assessActionReversibility(normalized, workspaceRoot, hasPreSnapshot)
  return {
    ...base,
    reversibility,
    blastRadius,
  }
}

export function validateAction(
  action: CoworkAction,
  runtime: CoworkRuntime,
  workspaceRoot: string,
  options: ValidateOptions = {},
): SafetyVerdict {
  // Un chemin porteur d un caractere de controle est MALFORME, pas risque:
  // ce n est pas une question de permission, et le deverrouillage total ne
  // doit pas le laisser passer. On refuse avant tout autre arbitrage.
  const rawPath = (action as { path?: unknown }).path
  if (typeof rawPath === 'string' && pathHasControlChars(rawPath)) {
    return attachFormalSafetyMetrics({
      decision: 'block',
      reason: 'Chemin malforme: caractere de controle (NUL / saut de ligne) interdit.',
      destructive: false,
      normalized: action,
    }, workspaceRoot, options.hasPreSnapshot)
  }

  if (options.fullyUnlocked) {
    return attachFormalSafetyMetrics({
      decision: 'allow',
      reason: 'Deverrouille totalement - l utilisateur a accepte les risques.',
      destructive: isDestructive(action),
      normalized: action,
    }, workspaceRoot, options.hasPreSnapshot)
  }
  // Le duo danger+trust lance sans confirmation logicielle.
  const noGuardrails = !!(options.dangerMode && options.trustMode)

  if (runtime === 'web-mobile' && isDestructive(action) && !noGuardrails) {
    if (options.dangerMode) {
      return attachFormalSafetyMetrics({
        decision: 'confirm',
        reason: 'Mobile : action destructive demandee. Mode preventif : confirmation requise au lieu d un blocage.',
        destructive: true,
        normalized: action,
      }, workspaceRoot, options.hasPreSnapshot)
    }
    return attachFormalSafetyMetrics({
      decision: 'block',
      reason: 'Mobile : actions destructives interdites. Utilise l app PC ou l extension navigateur.',
      destructive: true,
      normalized: action,
    }, workspaceRoot, options.hasPreSnapshot)
  }

  const baseVerdict = computeBaseVerdict(action, runtime, workspaceRoot)
  const verdict = attachFormalSafetyMetrics(baseVerdict, workspaceRoot, options.hasPreSnapshot)

  // Escalade formelle par rayon d impact : si une action "allow" presente un
  // blastRadius critique (>= 0.80) ou est irreversible avec mutation systeme,
  // on force une confirmation humaine hors mode sans garde-fou.
  if (
    verdict.decision === 'allow' &&
    verdict.destructive &&
    (verdict.blastRadius.score >= 0.80 || verdict.blastRadius.scope === 'system_wide')
  ) {
    verdict.decision = 'confirm'
    verdict.reason = `${verdict.reason} (escalade blastRadius=${verdict.blastRadius.score.toFixed(2)}, scope=${verdict.blastRadius.scope})`
  }

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
): Omit<SafetyVerdict, 'reversibility' | 'blastRadius'> {

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
      const byteLength = new TextEncoder().encode(action.content).byteLength
      if (byteLength > SAFETY_LIMITS.maxWriteFileBytes) {
        return {
          decision: 'block',
          reason: `Contenu trop volumineux (${byteLength} > ${SAFETY_LIMITS.maxWriteFileBytes} octets).`,
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
      const byteLength = new TextEncoder().encode(action.newText).byteLength
      if (byteLength > SAFETY_LIMITS.maxWriteFileBytes) {
        return {
          decision: 'block',
          reason: `Contenu trop volumineux (${byteLength} octets).`,
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
        normalizePath(resolved) === normalizePath(workspaceRoot) ||
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

    case 'ephemeral_tool': {
      const toolName = (action.toolName || '').trim()
      const scriptCode = action.scriptCode || ''
      if (!toolName || !scriptCode.trim()) {
        return {
          decision: 'block',
          reason: 'ephemeral_tool requiert toolName et scriptCode non vides.',
          destructive: true,
          normalized: action,
        }
      }
      const byteLength = new TextEncoder().encode(scriptCode).byteLength
      if (byteLength > SAFETY_LIMITS.maxWriteFileBytes) {
        return {
          decision: 'block',
          reason: `ephemeral_tool.scriptCode trop volumineux (${byteLength} octets).`,
          destructive: true,
          normalized: action,
        }
      }
      return {
        decision: 'confirm',
        reason: `outil ephemere sandbox (${toolName})`,
        destructive: true,
        normalized: { ...action, toolName },
      }
    }

    case 'file_bundle': {
      const files = action.files ?? []
      if (files.length === 0) {
        return {
          decision: 'block',
          reason: 'file_bundle.files vide.',
          destructive: true,
          normalized: action,
        }
      }
      for (const f of files) {
        if (!f.filename?.trim() || pathHasControlChars(f.filename) || /(^|[\\/])\.\.([\\/]|$)/.test(f.filename)) {
          return {
            decision: 'block',
            reason: `file_bundle filename invalide ou traversee de chemin : "${f.filename || ''}".`,
            destructive: true,
            normalized: action,
          }
        }
      }
      return {
        decision: 'confirm',
        reason: `emission de ${files.length} fichier(s) vers le module ${action.moduleTarget}`,
        destructive: true,
        normalized: action,
      }
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

/**
 * Analyse formelle par premiers principes du rayon d impact (blastRadius)
 * d une action Cowork avant son execution.
 */
export function assessActionBlastRadius(
  action: CoworkAction,
  workspaceRoot: string,
): BlastRadiusAssessment {
  switch (action.kind) {
    case 'reply':
    case 'finish':
    case 'think':
    case 'think_long':
    case 'voice_speak':
    case 'clipboard_read':
    case 'dom_query':
    case 'vision_describe':
    case 'screenshot_desktop':
      return {
        scope: 'none',
        score: 0.0,
        affectedTargets: [],
        recursiveOrWildcard: false,
        crossesWorkspaceBoundary: false,
        touchesSensitiveTarget: false,
      }

    case 'read_file':
    case 'list_dir': {
      const resolved = resolvePath(action.path, workspaceRoot)
      const inWs = isInsideWorkspace(resolved, workspaceRoot)
      const sensitive = isSensitivePath(resolved)
      const isRecursive = action.kind === 'list_dir' && (action.depth ?? 1) > 2
      return {
        scope: inWs ? (action.kind === 'list_dir' ? 'workspace_subtree' : 'single_file') : 'user_profile',
        score: clamp01((inWs ? 0.05 : 0.20) + (sensitive ? 0.25 : 0) + (isRecursive ? 0.05 : 0)),
        affectedTargets: [resolved],
        recursiveOrWildcard: isRecursive,
        crossesWorkspaceBoundary: !inWs,
        touchesSensitiveTarget: sensitive,
      }
    }

    case 'write_file':
    case 'edit_file': {
      const resolved = resolvePath(action.path, workspaceRoot)
      const inWs = isInsideWorkspace(resolved, workspaceRoot)
      const sensitive = isSensitivePath(resolved)
      const payload = action.kind === 'write_file' ? action.content : action.newText
      const byteLen = new TextEncoder().encode(payload || '').byteLength
      const sizeFactor = Math.min(0.15, (byteLen / SAFETY_LIMITS.maxWriteFileBytes) * 0.15)
      const base = action.kind === 'edit_file' ? 0.22 : 0.30
      const score = clamp01(base + (inWs ? 0 : 0.30) + (sensitive ? 0.30 : 0) + sizeFactor)
      return {
        scope: inWs ? 'single_file' : (isInsideStandardUserReadPath(resolved, workspaceRoot) ? 'user_profile' : 'system_wide'),
        score,
        affectedTargets: [resolved],
        recursiveOrWildcard: false,
        crossesWorkspaceBoundary: !inWs,
        touchesSensitiveTarget: sensitive,
      }
    }

    case 'delete_file': {
      const resolved = resolvePath(action.path, workspaceRoot)
      const inWs = isInsideWorkspace(resolved, workspaceRoot)
      const sensitive = isSensitivePath(resolved)
      const isRootLike = normalizePath(resolved) === normalizePath(workspaceRoot)
        || /^[/\\]$/.test(resolved)
        || /^[a-z]:[/\\]?$/i.test(resolved)
      const looksLikeDir = !/\.[a-z0-9]{1,8}$/i.test(resolved.split(/[\\/]/).pop() || '')
      const score = clamp01(0.55 + (inWs ? 0 : 0.25) + (sensitive ? 0.15 : 0) + (looksLikeDir ? 0.15 : 0) + (isRootLike ? 0.45 : 0))
      return {
        scope: isRootLike ? 'system_wide' : (inWs ? (looksLikeDir ? 'workspace_subtree' : 'single_file') : 'system_wide'),
        score,
        affectedTargets: [resolved],
        recursiveOrWildcard: looksLikeDir || isRootLike,
        crossesWorkspaceBoundary: !inWs,
        touchesSensitiveTarget: sensitive || isRootLike,
      }
    }

    case 'shell': {
      const cmd = (action.command || '').trim()
      const cmdBase = baseCommandName(cmd).toLowerCase()
      const args = action.args ?? []
      const joined = `${cmd} ${args.join(' ')}`
      const isBlocked = SHELL_BLOCKLIST.includes(cmdBase)
      const hasRecursiveFlag = args.some((a) => /^(-rf|-fr|--recursive|-r|-f|--hard|--force|-fdx)$/i.test(a.trim()))
        || /\b(rm\s+-rf|git\s+reset\s+--hard|git\s+clean\s+-fd|find\s+.*-delete)\b/i.test(joined)
      const hasWildcard = args.some((a) => /[*?]/.test(a))
      const pathArgs = args.filter((a) => !a.startsWith('-') && (a.includes('/') || a.includes('\\') || /\.[a-z0-9]{1,6}$/i.test(a)))
      const resolvedTargets = pathArgs.map((p) => resolvePath(p, action.cwd || workspaceRoot))
      const crossesWs = resolvedTargets.some((t) => !isInsideWorkspace(t, workspaceRoot))
      const touchesSensitive = resolvedTargets.some(isSensitivePath)
      const isReadOnlyShell = ['ls', 'dir', 'pwd', 'whoami', 'where', 'which', 'cat', 'head', 'tail', 'grep', 'rg', 'fd', 'find', 'wc', 'sort', 'uniq', 'cut', 'echo', 'printf'].includes(cmdBase)
        && !/\b(-delete|-exec|-i|--in-place|>\s*)\b/i.test(joined)
      if (isReadOnlyShell) {
        return {
          scope: crossesWs ? 'user_profile' : 'workspace_subtree',
          score: clamp01(crossesWs ? 0.15 : 0.08),
          affectedTargets: resolvedTargets,
          recursiveOrWildcard: hasWildcard,
          crossesWorkspaceBoundary: crossesWs,
          touchesSensitiveTarget: touchesSensitive,
        }
      }
      let score = SHELL_ALLOWLIST.includes(cmdBase) ? 0.35 : 0.60
      if (isBlocked) score = 0.98
      if (hasRecursiveFlag) score += 0.30
      if (hasWildcard) score += 0.10
      if (crossesWs) score += 0.20
      if (touchesSensitive) score += 0.15
      const scope: BlastRadiusScope = isBlocked || (crossesWs && hasRecursiveFlag)
        ? 'system_wide'
        : (crossesWs ? 'user_profile' : 'workspace_subtree')
      return {
        scope,
        score: clamp01(score),
        affectedTargets: resolvedTargets.length > 0 ? resolvedTargets : [cmdBase || 'shell'],
        recursiveOrWildcard: hasRecursiveFlag || hasWildcard,
        crossesWorkspaceBoundary: crossesWs || isBlocked,
        touchesSensitiveTarget: touchesSensitive || isBlocked,
      }
    }

    case 'web_search':
    case 'open_url':
      return {
        scope: 'external_network',
        score: 0.10,
        affectedTargets: [action.kind === 'web_search' ? action.query : action.url],
        recursiveOrWildcard: false,
        crossesWorkspaceBoundary: true,
        touchesSensitiveTarget: false,
      }

    case 'fetch': {
      const method = (action.method || 'GET').toUpperCase()
      const isMutatingHttp = method !== 'GET' && method !== 'HEAD'
      return {
        scope: 'external_network',
        score: isMutatingHttp ? 0.55 : 0.12,
        affectedTargets: [action.url],
        recursiveOrWildcard: false,
        crossesWorkspaceBoundary: true,
        touchesSensitiveTarget: isMutatingHttp,
      }
    }

    case 'clipboard_write':
    case 'remember_fact':
    case 'forget_fact':
      return {
        scope: 'user_profile',
        score: action.kind === 'forget_fact' ? 0.25 : 0.12,
        affectedTargets: [action.kind],
        recursiveOrWildcard: false,
        crossesWorkspaceBoundary: false,
        touchesSensitiveTarget: false,
      }

    case 'connector': {
      const op = (action.action || '').trim()
      const isRead = /^(get_|list_|search|check|probe|read|status)/i.test(op)
      return {
        scope: 'external_network',
        score: isRead ? 0.15 : 0.65,
        affectedTargets: [`${action.connector}.${op}`],
        recursiveOrWildcard: false,
        crossesWorkspaceBoundary: true,
        touchesSensitiveTarget: !isRead,
      }
    }

    case 'browser': {
      const readOps = new Set(['list_tabs', 'get_active_tab', 'read_dom', 'read_html', 'screenshot', 'analyze_page', 'extract_structured'])
      const isRead = readOps.has(action.operation)
      return {
        scope: 'external_network',
        score: isRead ? 0.08 : (action.operation === 'eval' ? 0.72 : 0.45),
        affectedTargets: [`browser.${action.operation}`],
        recursiveOrWildcard: false,
        crossesWorkspaceBoundary: !isRead,
        touchesSensitiveTarget: action.operation === 'eval',
      }
    }

    case 'ephemeral_tool':
      return {
        scope: 'workspace_subtree',
        score: action.autoCleanup === false ? 0.65 : 0.48,
        affectedTargets: [`ephemeral:${action.toolName}`],
        recursiveOrWildcard: false,
        crossesWorkspaceBoundary: false,
        touchesSensitiveTarget: false,
      }

    case 'file_bundle':
      return {
        scope: 'workspace_subtree',
        score: clamp01(0.30 + Math.min(0.30, (action.files?.length ?? 0) * 0.05)),
        affectedTargets: (action.files ?? []).map((f) => f.filename),
        recursiveOrWildcard: (action.files?.length ?? 0) > 1,
        crossesWorkspaceBoundary: false,
        touchesSensitiveTarget: (action.files ?? []).some((f) => isSensitivePath(f.filename)),
      }
  }
}

/**
 * Analyse formelle de la reversibilite transactionnelle d une action Cowork.
 */
export function assessActionReversibility(
  action: CoworkAction,
  workspaceRoot: string,
  hasPreSnapshot = false,
): ReversibilityAssessment {
  switch (action.kind) {
    case 'reply':
    case 'finish':
    case 'think':
    case 'think_long':
    case 'read_file':
    case 'list_dir':
    case 'web_search':
    case 'clipboard_read':
    case 'dom_query':
    case 'vision_describe':
    case 'screenshot_desktop':
      return {
        classification: 'pure_read',
        reversible: true,
        requiresPreSnapshot: false,
        inverseStrategy: 'none_required',
        rollbackConfidence: 1.0,
      }

    case 'voice_speak':
    case 'open_url':
      return {
        classification: 'idempotent',
        reversible: true,
        requiresPreSnapshot: false,
        inverseStrategy: 'none_required_ephemeral_ui',
        rollbackConfidence: 1.0,
      }

    case 'edit_file':
      return {
        classification: 'snapshot_reversible',
        reversible: true,
        requiresPreSnapshot: false,
        inverseStrategy: 'inverse_edit_swap_oldText_newText_or_restore_snapshot',
        rollbackConfidence: 0.98,
      }

    case 'write_file':
      return {
        classification: 'snapshot_reversible',
        reversible: true,
        requiresPreSnapshot: true,
        inverseStrategy: hasPreSnapshot
          ? 'restore_pre_write_snapshot_bytes'
          : 'capture_pre_image_snapshot_before_write_or_unlink_if_created',
        rollbackConfidence: hasPreSnapshot ? 0.99 : 0.92,
      }

    case 'delete_file': {
      const resolved = resolvePath(action.path, workspaceRoot)
      const looksLikeDir = !/\.[a-z0-9]{1,8}$/i.test(resolved.split(/[\\/]/).pop() || '')
      return {
        classification: looksLikeDir ? 'irreversible' : 'snapshot_reversible',
        reversible: !looksLikeDir || hasPreSnapshot,
        requiresPreSnapshot: true,
        inverseStrategy: looksLikeDir && !hasPreSnapshot
          ? 'irreversible_directory_tree_deletion_without_archive'
          : 'restore_deleted_file_from_pre_image_journal',
        rollbackConfidence: looksLikeDir ? (hasPreSnapshot ? 0.75 : 0.0) : (hasPreSnapshot ? 0.98 : 0.85),
      }
    }

    case 'remember_fact':
      return {
        classification: 'compensatable',
        reversible: true,
        requiresPreSnapshot: false,
        inverseStrategy: 'forget_fact_by_exact_fact_match',
        rollbackConfidence: 0.99,
      }

    case 'forget_fact':
    case 'clipboard_write':
      return {
        classification: 'snapshot_reversible',
        reversible: hasPreSnapshot,
        requiresPreSnapshot: true,
        inverseStrategy: hasPreSnapshot ? 'restore_previous_state' : 'previous_value_overwritten_without_snapshot',
        rollbackConfidence: hasPreSnapshot ? 0.95 : 0.30,
      }

    case 'fetch': {
      const method = (action.method || 'GET').toUpperCase()
      if (method === 'GET' || method === 'HEAD') {
        return {
          classification: 'pure_read',
          reversible: true,
          requiresPreSnapshot: false,
          inverseStrategy: 'none_required',
          rollbackConfidence: 1.0,
        }
      }
      return {
        classification: 'irreversible',
        reversible: false,
        requiresPreSnapshot: false,
        inverseStrategy: 'external_http_mutation_not_automatically_reversible',
        rollbackConfidence: 0.0,
      }
    }

    case 'shell': {
      const cmdBase = baseCommandName((action.command || '').trim()).toLowerCase()
      const joined = `${action.command} ${(action.args ?? []).join(' ')}`
      const isReadOnly = ['ls', 'dir', 'pwd', 'whoami', 'where', 'which', 'cat', 'head', 'tail', 'grep', 'rg', 'fd', 'find', 'wc', 'sort', 'uniq', 'cut', 'echo', 'printf'].includes(cmdBase)
        && !/\b(-delete|-exec|-i|--in-place|>\s*)\b/i.test(joined)
      if (isReadOnly) {
        return {
          classification: 'pure_read',
          reversible: true,
          requiresPreSnapshot: false,
          inverseStrategy: 'none_required',
          rollbackConfidence: 1.0,
        }
      }
      if (cmdBase === 'mkdir') {
        return {
          classification: 'compensatable',
          reversible: true,
          requiresPreSnapshot: false,
          inverseStrategy: 'rmdir_created_directory',
          rollbackConfidence: 0.85,
        }
      }
      return {
        classification: 'irreversible',
        reversible: false,
        requiresPreSnapshot: true,
        inverseStrategy: 'shell_side_effects_require_manual_or_git_compensation',
        rollbackConfidence: 0.10,
      }
    }

    case 'connector': {
      const op = (action.action || '').trim()
      const isRead = /^(get_|list_|search|check|probe|read|status)/i.test(op)
      if (isRead) {
        return {
          classification: 'pure_read',
          reversible: true,
          requiresPreSnapshot: false,
          inverseStrategy: 'none_required',
          rollbackConfidence: 1.0,
        }
      }
      return {
        classification: 'irreversible',
        reversible: false,
        requiresPreSnapshot: false,
        inverseStrategy: 'external_connector_side_effect',
        rollbackConfidence: 0.0,
      }
    }

    case 'browser': {
      const readOps = new Set(['list_tabs', 'get_active_tab', 'read_dom', 'read_html', 'screenshot', 'analyze_page', 'extract_structured'])
      if (readOps.has(action.operation)) {
        return {
          classification: 'pure_read',
          reversible: true,
          requiresPreSnapshot: false,
          inverseStrategy: 'none_required',
          rollbackConfidence: 1.0,
        }
      }
      return {
        classification: action.operation === 'eval' ? 'irreversible' : 'compensatable',
        reversible: action.operation !== 'eval',
        requiresPreSnapshot: false,
        inverseStrategy: action.operation === 'eval' ? 'dom_js_eval_arbitrary_mutation' : 'browser_history_back_or_clear_field',
        rollbackConfidence: action.operation === 'eval' ? 0.15 : 0.65,
      }
    }

    case 'ephemeral_tool':
      return {
        classification: action.autoCleanup !== false ? 'compensatable' : 'snapshot_reversible',
        reversible: true,
        requiresPreSnapshot: false,
        inverseStrategy: 'cleanup_ephemeral_sandbox_directory',
        rollbackConfidence: 0.90,
      }

    case 'file_bundle':
      return {
        classification: 'compensatable',
        reversible: true,
        requiresPreSnapshot: false,
        inverseStrategy: 'remove_emitted_bundle_files',
        rollbackConfidence: 0.90,
      }
  }
}

/**
 * Evalue l enveloppe de securite formelle d une sequence d actions (plan complet) :
 * - calcule le blastRadius maximal et cumule
 * - verifie si chaque mutation de fichier dispose d une lecture/snapshot prealable
 * - identifie toutes les etapes irreversibles avant execution.
 */
export function evaluatePlanSafetyEnvelope(
  actions: CoworkAction[],
  runtime: CoworkRuntime,
  workspaceRoot: string,
  options: ValidateOptions = {},
): PlanSafetyEnvelope {
  const observedPaths = new Set<string>()
  const verdicts: SafetyVerdict[] = []
  const unguardedMutations: PlanSafetyEnvelope['unguardedMutations'] = []
  const irreversibleIndices: number[] = []
  let maxBlastRadiusScore = 0
  let cumulativeBlastScore = 0
  let dominantScope: BlastRadiusScope = 'none'

  const scopeRank: Record<BlastRadiusScope, number> = {
    none: 0,
    single_file: 1,
    workspace_subtree: 2,
    user_profile: 3,
    external_network: 4,
    system_wide: 5,
  }

  for (let i = 0; i < actions.length; i += 1) {
    const a = actions[i]
    let hasPreSnapshot = Boolean(options.hasPreSnapshot)
    if ('path' in a && typeof a.path === 'string') {
      const resolved = resolvePath(a.path, workspaceRoot)
      if (a.kind === 'read_file' || a.kind === 'list_dir') {
        observedPaths.add(resolved)
      } else if (observedPaths.has(resolved)) {
        hasPreSnapshot = true
      }
    }

    const v = validateAction(a, runtime, workspaceRoot, { ...options, hasPreSnapshot })
    verdicts.push(v)

    if (v.blastRadius.score > maxBlastRadiusScore) {
      maxBlastRadiusScore = v.blastRadius.score
    }
    cumulativeBlastScore = clamp01(1 - (1 - cumulativeBlastScore) * (1 - v.blastRadius.score * 0.5))

    if (scopeRank[v.blastRadius.scope] > scopeRank[dominantScope]) {
      dominantScope = v.blastRadius.scope
    }

    if (v.reversibility.requiresPreSnapshot && !hasPreSnapshot && ('path' in a) && typeof a.path === 'string') {
      const resolved = resolvePath(a.path, workspaceRoot)
      unguardedMutations.push({
        index: i,
        target: resolved,
        kind: a.kind,
        reason: `Mutation ${a.kind} sur ${resolved} sans read_file/snapshot prealable dans le plan.`,
      })
    }

    if (!v.reversibility.reversible || v.reversibility.classification === 'irreversible') {
      irreversibleIndices.push(i)
    }
  }

  let overallDecision: 'allow' | 'confirm' | 'block' = 'allow'
  for (const v of verdicts) {
    if (v.decision === 'block') {
      overallDecision = 'block'
      break
    }
    if (v.decision === 'confirm') {
      overallDecision = 'confirm'
    }
  }

  return {
    verdicts,
    overallDecision,
    maxBlastRadiusScore,
    cumulativeBlastScore,
    dominantScope,
    fullyReversible: irreversibleIndices.length === 0,
    unguardedMutations,
    irreversibleIndices,
  }
}

function clamp01(v: number): number {
  if (!Number.isFinite(v)) return 0
  return Math.max(0, Math.min(1, Number(v.toFixed(4))))
}

function isDestructive(action: CoworkAction): boolean {
  return ['write_file', 'edit_file', 'delete_file', 'shell', 'ephemeral_tool', 'file_bundle'].includes(action.kind)
}

function isPreventableBlock(action: CoworkAction, reason: string): boolean {
  if (action.kind === 'shell') return !!action.command?.trim()
  if (action.kind === 'write_file' || action.kind === 'edit_file' || action.kind === 'delete_file') return true
  if (action.kind === 'ephemeral_tool' || action.kind === 'file_bundle') return !/vide|invalide|traversee/i.test(reason)
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

/**
 * Caracteres de controle interdits dans un chemin.
 *
 * `\0` d abord: un chemin qui en contient n est jamais legitime, et les
 * couches sous-jacentes le TRONQUENT au premier octet nul. Un chemin
 * `<workspace>/\0/../../etc/passwd` passait la cloture — il commence bien par
 * la racine du workspace — et ressortait en `allow` sans confirmation.
 *
 * `\r` et `\n` ensuite: l executeur interpole les chemins dans des lignes de
 * commande PowerShell; un saut de ligne y injecte une commande.
 */
const PATH_CONTROL_CHARS_RE = /[\u0000-\u001F\u007F]/

/** Le chemin porte-t-il un caractere de controle ? (jamais legitime) */
export function pathHasControlChars(path: string): boolean {
  return PATH_CONTROL_CHARS_RE.test(path)
}

export function isInsideWorkspace(absolutePath: string, workspaceRoot: string): boolean {
  // Un chemin malforme n est DANS rien: on refuse avant de comparer les prefixes.
  if (pathHasControlChars(absolutePath) || pathHasControlChars(workspaceRoot)) return false
  const windowsPath = /^(?:[a-z]:|\/[a-z]\/Users(?:\/|$))/i.test(normalizePath(workspaceRoot))
  const root = windowsPath ? normalizePath(workspaceRoot).toLowerCase() : normalizePath(workspaceRoot)
  const path = windowsPath ? normalizePath(absolutePath).toLowerCase() : normalizePath(absolutePath)
  if (root === path) return true
  return path.startsWith(root === '/' ? '/' : root + '/')
}

function isInsideStandardUserReadPath(absolutePath: string, workspaceRoot: string): boolean {
  const home = inferUserHomeFromWorkspace(workspaceRoot)
  if (!home) return false
  const allowedFolders = ['Desktop', 'Bureau', 'Documents', 'Downloads', 'Telechargements']
    .map((folder) => joinPaths(home, folder))
  return allowedFolders.some((folder) => isInsideWorkspace(absolutePath, folder))
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
