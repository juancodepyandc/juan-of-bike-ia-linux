import type { FollowUpKind } from '../services/codeOrchestrator.ts'
import type { CodeStreamState } from './codeStreamTypes.ts'

const NARRATE_VOICE_KEY = 'aurora.code.narrateVoice'

export function readNarrateVoice(): boolean {
  try { return localStorage.getItem(NARRATE_VOICE_KEY) === '1' } catch { return false }
}

/**
 * v85e : friendly FIRST-PERSON French narration of what the module is doing
 * right now — "je fais ceci, puis je vais m'attaquer à ça". This is what the
 * UI shows (and optionally speaks). Phase-based so it changes a handful of
 * times per run, not per token.
 */
export function narrate(
  phase: CodeStreamState['phase'],
  detail: string,
  ctx: { followUp: FollowUpKind | null; repo: boolean; brand: string | null; correction: boolean },
): string {
  const where = ctx.repo ? 'ton dépôt' : 'le projet'
  // v85f : a CORRECTION ("corrige le bug / écran noir") is a surgical fix, not
  // an addition. The wording must say "je corrige", never "j'ajoute".
  if (ctx.correction) {
    switch (phase) {
      case 'research':
      case 'brand':
      case 'planning':
        return `Je relis ${where} pour localiser le problème, ensuite je le corrige.`
      case 'streaming':
        return 'Je corrige uniquement ce qui ne marche pas, sans toucher au reste.'
      case 'validation':
        return 'Je vérifie que la correction règle bien le souci et ne casse rien d’autre.'
      case 'done':
        return 'C’est corrigé — je viens de te livrer la version réparée.'
      case 'error':
        return 'Je n’ai pas pu corriger automatiquement, je t’explique pourquoi juste en dessous.'
      default:
        return detail || 'Je prépare la correction…'
    }
  }
  switch (phase) {
    case 'research':
      return 'Je cherche des références de design en ligne, ensuite je conçois l’architecture.'
    case 'brand':
      return `J’étudie l’identité de ${ctx.brand || 'la marque'} pour rester fidèle, ensuite je passe à la conception.`
    case 'planning':
      return ctx.followUp === 'increment'
        ? `Je relis ${where} existant pour bien comprendre, ensuite j’applique ta demande.`
        : 'Je conçois l’architecture du projet, ensuite j’écris le code.'
    case 'streaming':
      return ctx.followUp === 'increment'
        ? 'J’applique ta demande au code, puis je vérifierai que tout tient toujours.'
        : `J’écris le code de ${where} maintenant, puis je vérifierai qu’il fonctionne.`
    case 'validation':
      return 'Je teste et je corrige le code généré, puis je te livre le résultat.'
    case 'done':
      return 'C’est prêt — je viens de te livrer le projet.'
    case 'error':
      return 'J’ai rencontré un souci pendant la tâche, je te l’explique juste en dessous.'
    default:
      return detail || 'Je prépare la tâche…'
  }
}

export function writeNarrateVoice(on: boolean) {
  try { localStorage.setItem(NARRATE_VOICE_KEY, on ? '1' : '0') } catch { /* ignore */ }
}
