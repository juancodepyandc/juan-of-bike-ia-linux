/**
 * Voice commands — intercepts specific spoken phrases and routes to app
 * navigation/actions BEFORE they reach the LLM. Keeps the response snappy
 * ("Aurora, ouvre le code" → instant module switch, no 8-second Ollama wait).
 *
 * Patterns are intentionally loose: we strip accents/punctuation and match on
 * verb+noun keywords so users can phrase however feels natural.
 *
 * Les helpers purs (`normalize`, `parseNavigation`, `MODULE_KEYWORDS`) sont
 * extraits dans voiceCommandsCore.ts pour être testables sans dépendance
 * sur le store / window.
 */
import { useAppStore } from '../stores/appStore.ts'
import type { ModuleId } from '../types/app.ts'
import { normalize, parseNavigation } from './voiceCommandsCore.ts'

// Re-exports pour ne pas casser les callers existants qui importent depuis ici.
export { normalize, parseNavigation } from './voiceCommandsCore.ts'

type VoiceCommandResult =
  | { handled: true; reply: string }
  | { handled: false }

const MODULE_LABELS: Record<ModuleId, string> = {
  conversation: 'Chat',
  image: 'Image',
  code: 'Forge de code',
  video: 'Vidéo',
  drawing: 'Dessin',
  '3d': 'Atelier 3D',
  learning: 'Académie',
  voice: 'Voix',
  cyber: 'Cyber',
}

/**
 * Try to handle a spoken phrase as a voice command.
 * Returns `{ handled: true, reply }` if the utterance matched a command —
 * the caller should use `reply` as the spoken feedback and SKIP sending the
 * text to the LLM. Returns `{ handled: false }` otherwise.
 */
export function tryHandleVoiceCommand(raw: string): VoiceCommandResult {
  const norm = normalize(raw)
  if (!norm) return { handled: false }

  // Navigation: ouvre le chat / va dans la forge / passe en cyber
  const nav = parseNavigation(norm)
  if (nav) {
    useAppStore.getState().setActiveModule(nav)
    return { handled: true, reply: `OK, je passe au module ${MODULE_LABELS[nav]}.` }
  }

  // Focus toggles
  if (/\b(focus|plein ecran|distraction|zen)\b/.test(norm) && /\b(active|lance|demarre|mode)\b/.test(norm)) {
    useAppStore.getState().setFocusMode(true)
    return { handled: true, reply: 'Mode focus activé.' }
  }
  if (/\b(sors|quitte|desactive|arrete|stop)\b/.test(norm) && /\b(focus|zen)\b/.test(norm)) {
    useAppStore.getState().setFocusMode(false)
    return { handled: true, reply: 'Mode focus désactivé.' }
  }

  // Global search
  if (/\b(recherche|cherche|trouve|search)\b/.test(norm) && norm.length < 40) {
    window.dispatchEvent(new CustomEvent('aurora:open-global-search'))
    return { handled: true, reply: 'Recherche ouverte.' }
  }

  // Settings
  if (/\b(reglages?|parametres?|settings|preferences)\b/.test(norm) && /\b(ouvre|montre|affiche)\b/.test(norm)) {
    window.dispatchEvent(new CustomEvent('aurora:open-settings'))
    return { handled: true, reply: 'Panneau de réglages ouvert.' }
  }

  return { handled: false }
}
