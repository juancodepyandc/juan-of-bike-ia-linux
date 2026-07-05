/**
 * Pure helpers (no DOM, no store) du parser de commandes vocales Aurora.
 *
 * Isolés ici pour pouvoir être testés sous Node sans importer le store
 * zustand (qui dépend de browser globals via le middleware persist).
 *
 * Le wrapper public `tryHandleVoiceCommand` reste dans voiceCommands.ts
 * (avec les effets de bord setActiveModule / dispatchEvent).
 */
import type { ModuleId } from '../types/app'

export const MODULE_KEYWORDS: Array<{ id: ModuleId; words: string[] }> = [
  { id: 'conversation', words: ['chat', 'conversation', 'discussion', 'parle', 'discute'] },
  { id: 'image',        words: ['image', 'images', 'flux', 'dessin ia', 'photo', 'illustration'] },
  { id: 'code',         words: ['code', 'forge', 'programmation', 'developpement', 'dev'] },
  { id: 'video',        words: ['video', 'videos', 'wan', 'clip'] },
  { id: 'drawing',      words: ['dessin', 'dessine', 'pinceau', 'sumi', 'croquis'] },
  { id: '3d',           words: ['3d', 'mesh', 'hunyuan', 'modele 3d', 'volume'] },
  { id: 'learning',     words: ['academie', 'academy', 'apprentissage', 'apprendre', 'quiz', 'bac'] },
  { id: 'voice',        words: ['voix', 'voice', 'voxtral', 'copilote'] },
  { id: 'cyber',        words: ['cyber', 'cryptographie', 'crypto', 'securite', 'ctf', 'hacking'] },
]

/** Lowercase + strip diacritics + collapse whitespace + strip ponctuation. */
export function normalize(s: string): string {
  return s
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[^\w\s]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

/**
 * Détecte une intention de navigation parmi une chaîne déjà normalisée.
 * Renvoie le moduleId cible ou `null` si rien de reconnu.
 */
export function parseNavigation(norm: string): ModuleId | null {
  const NAV_VERBS = /\b(ouvre|ouvrir|va|passe|bascule|aller|affiche|montre|lance|demarre|rejoins)\b/
  if (!NAV_VERBS.test(norm)) return null
  for (const { id, words } of MODULE_KEYWORDS) {
    for (const w of words) {
      if (norm.includes(` ${w}`) || norm.endsWith(w) || norm === w) return id
    }
  }
  return null
}
