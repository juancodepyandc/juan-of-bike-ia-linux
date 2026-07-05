// Génère un plan de rollback à partir d'un plan exécuté + ses résultats.
// Inverse les actions destructives quand c'est possible :
//   - write_file (création) → delete_file
//   - write_file (overwrite) → write_file avec le contenu original
//   - delete_file → write_file avec le contenu sauvegardé
//   - edit_file → edit_file inverse (newText devient oldText)
//   - shell (irrécupérable) → action 'reply' qui prévient
//   - remember_fact → forget_fact
//
// Pré-requis : pour reconstituer le contenu original, l'orchestrateur doit
// faire un read_file AVANT chaque write/edit/delete et stocker le résultat.
// Cette structure est attendue dans `executionRecord.preActionStates`.

import type { CoworkAction, CoworkActionResult, CoworkPlan } from './coworkTypes.ts'

export type ActionResultPair = {
  action: CoworkAction
  result: CoworkActionResult
}

export type ExecutionRecord = {
  pairs: ActionResultPair[]
  /** État du fichier AVANT chaque action ayant pu le modifier. Clé = path. */
  preActionStates?: Record<string, { content: string; existed: boolean }>
}

export type RollbackPlan = {
  actions: CoworkAction[]
  /** Actions qui n'ont PAS pu être inversées (rollback partiel). */
  irreversible: Array<{ index: number; reason: string; original: CoworkAction }>
  /** Plan totalement réversible (irreversible empty). */
  fullyReversible: boolean
}

/**
 * Construit le plan inverse en marche-arrière (LIFO) — on rollback la
 * dernière action en premier.
 */
export function generateRollbackPlan(record: ExecutionRecord): RollbackPlan {
  const actions: CoworkAction[] = []
  const irreversible: RollbackPlan['irreversible'] = []
  const states = record.preActionStates ?? {}

  for (let i = record.pairs.length - 1; i >= 0; i -= 1) {
    const { action, result } = record.pairs[i]
    if (!result.ok) continue // une action qui a échoué n'a rien modifié → skip

    switch (action.kind) {
      case 'write_file': {
        const prior = states[action.path]
        if (!prior || !prior.existed) {
          // Le fichier n'existait pas avant → suppression.
          actions.push({ kind: 'delete_file', path: action.path })
        } else {
          // Existait → restaure le contenu original.
          actions.push({ kind: 'write_file', path: action.path, content: prior.content })
        }
        break
      }
      case 'edit_file': {
        // Edit inverse : oldText et newText swappés.
        actions.push({ kind: 'edit_file', path: action.path, oldText: action.newText, newText: action.oldText })
        break
      }
      case 'delete_file': {
        const prior = states[action.path]
        if (!prior) {
          irreversible.push({ index: i, reason: `Contenu original de ${action.path} non sauvegardé.`, original: action })
        } else {
          actions.push({ kind: 'write_file', path: action.path, content: prior.content })
        }
        break
      }
      case 'remember_fact': {
        actions.push({ kind: 'forget_fact', matching: action.fact })
        break
      }
      case 'forget_fact': {
        // Pas d'inverse sans le texte original — qui n'est pas dans l'action.
        irreversible.push({ index: i, reason: 'Fact oublié non récupérable.', original: action })
        break
      }
      case 'shell': {
        // Shell est généralement irréversible. On émet un reply d'alerte.
        irreversible.push({
          index: i,
          reason: 'Shell : effet de bord non automatiquement inversable.',
          original: action,
        })
        actions.push({
          kind: 'reply',
          message: `⚠️ La commande shell "${action.command} ${action.args.join(' ')}" a été exécutée. Effet non automatiquement annulable — vérifier manuellement.`,
        })
        break
      }
      case 'fetch':
      case 'web_search':
      case 'open_url':
      case 'clipboard_write': {
        irreversible.push({
          index: i,
          reason: `${action.kind} : effet observable côté serveur/utilisateur.`,
          original: action,
        })
        break
      }
      case 'voice_speak':
      case 'reply':
      case 'think':
      case 'think_long':
      case 'read_file':
      case 'list_dir':
      case 'dom_query':
      case 'clipboard_read':
      case 'vision_describe':
      case 'finish':
      case 'browser':
        // Read-only : rien à rollback.
        break
      default:
        irreversible.push({
          index: i,
          reason: `Type d'action ${(action as { kind: string }).kind} non géré.`,
          original: action,
        })
    }
  }

  return {
    actions,
    irreversible,
    fullyReversible: irreversible.length === 0,
  }
}

/**
 * Validation du plan original avant exec : vérifie que toutes les actions
 * destructives ont un read_file préalable (pour permettre rollback). Sinon
 * retourne les warnings à signaler à l'orchestrateur.
 */
export type RollbackReadinessCheck = {
  rollbackReady: boolean
  warnings: Array<{ actionIndex: number; path: string; warning: string }>
}

export function checkRollbackReadiness(plan: CoworkPlan): RollbackReadinessCheck {
  const warnings: RollbackReadinessCheck['warnings'] = []
  const readPaths = new Set<string>()
  for (let i = 0; i < plan.actions.length; i += 1) {
    const a = plan.actions[i]
    if (a.kind === 'read_file' || a.kind === 'list_dir') {
      readPaths.add(a.path)
      continue
    }
    if (a.kind === 'write_file' || a.kind === 'edit_file' || a.kind === 'delete_file') {
      if (!readPaths.has(a.path)) {
        warnings.push({
          actionIndex: i,
          path: a.path,
          warning: `Modifie ${a.path} sans read_file préalable → rollback impossible.`,
        })
      }
    }
  }
  return { rollbackReady: warnings.length === 0, warnings }
}
