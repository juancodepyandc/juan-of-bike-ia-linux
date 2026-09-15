/**
 * Construction des messages d'annonce TTS pour Aurora.
 *
 * Le pool persona-flavored par module évite les annonces robotiques répétitives.
 * Extrait d'auroraVoice pour pouvoir tester la logique de génération sans
 * dépendances DOM/Audio.
 */
import type { ModuleId } from '../types/app.ts'

export type AnnounceKind = 'started' | 'completed' | 'failed' | 'cancelled'

const MODULE_LABEL_FR: Record<ModuleId, string> = {
  conversation: 'le chat',
  image: 'ton image',
  code: 'ton projet de code',
  video: 'ta vidéo',
  drawing: 'ton dessin',
  '3d': 'ton modèle 3D',
  learning: 'ta leçon',
  voice: 'la voix',
  cyber: 'le challenge cyber',
}

/** Pool de phrases 'completed' par module — persona-flavored, anti-répétition. */
const COMPLETED_POOL_FR: Record<ModuleId, string[]> = {
  conversation: ['Voilà ma réponse.', 'C\'est dit.', 'Pris en compte.'],
  image: [
    'Iris a fini ton image.',
    'Image livrée — regarde la palette.',
    'Composition prête, jette un œil.',
  ],
  video: [
    'Cinéma a bouclé le plan.',
    'Storyboard rendu, c\'est dans la boîte.',
    'Coupez — ta vidéo est prête.',
  ],
  code: [
    'Glyph a livré le code.',
    'Build prêt, lance la preview.',
    'Projet compilé, regarde les fichiers.',
  ],
  drawing: [
    'Sumi a posé le trait.',
    'Croquis transformé, ton dessin t\'attend.',
    'Geste capté, rendu prêt.',
  ],
  '3d': [
    'Atlas a sculpté ton modèle.',
    'Mesh prêt — topologie propre.',
    'Volume livré, ouvre le viewer.',
  ],
  learning: [
    'Sage a préparé ta leçon.',
    'Contenu pédagogique prêt à étudier.',
    'Leçon montée, on enchaîne quand tu veux.',
  ],
  voice: ['Voix prête.'],
  cyber: [
    'Phantom a livré le rapport.',
    'Analyse cyber terminée.',
    'Challenge prêt — bonne chasse.',
  ],
}

/** Pool 'failed' (plus court — pas de personality push sur les erreurs). */
const FAILED_POOL_FR: Record<ModuleId, string[]> = {
  conversation: ['Le pipeline conversation a échoué.', 'Je n\'ai pas pu répondre.'],
  image: ['L\'image n\'a pas pu être générée.', 'Iris a buté sur ce prompt.'],
  video: ['La vidéo a planté.', 'Cinéma n\'a pas pu monter ce plan.'],
  code: ['La build a échoué.', 'Glyph signale un problème.'],
  drawing: ['Le rendu dessin a échoué.', 'Sumi n\'a pas pu finir.'],
  '3d': ['La génération 3D a échoué.', 'Atlas n\'a pas pu sculpter.'],
  learning: ['La leçon n\'a pas pu être générée.', 'Sage a buté sur ce sujet.'],
  voice: ['Le moteur vocal a échoué.'],
  cyber: ['L\'analyse cyber a échoué.', 'Phantom signale une erreur.'],
}

export interface AnnouncePayloadInput {
  module: ModuleId
  kind: AnnounceKind
  summary?: string
}

/**
 * Sélecteur dans un pool avec un index pré-calculé.
 * `index` doit être un entier ≥0 — modulo appliqué pour boucler.
 * Pool vide → string vide.
 */
export function pickFromPool(pool: string[], index: number): string {
  if (pool.length === 0) return ''
  const i = ((index % pool.length) + pool.length) % pool.length  // safe mod (négatifs ok)
  return pool[i]
}

/**
 * Construit le texte d'annonce. `poolIndex` permet au caller de gérer son
 * propre compteur pour éviter la répétition consécutive ; passé directement,
 * il est applique modulo la longueur du pool.
 */
export function buildAnnounceText(
  payload: AnnouncePayloadInput,
  lang: 'fr' | 'en',
  poolIndex: number,
): string {
  const summary = payload.summary ? ` ${payload.summary}` : ''
  if (lang === 'en') {
    const label = payload.module
    switch (payload.kind) {
      case 'started':   return `Starting ${label}.${summary}`
      case 'completed': return `${label} ready.${summary}`
      case 'failed':    return `${label} failed.${summary}`
      case 'cancelled': return `${label} cancelled.`
    }
  }
  const label = MODULE_LABEL_FR[payload.module] || payload.module
  switch (payload.kind) {
    case 'started':
      return `C'est parti pour ${label}.${summary}`
    case 'completed': {
      const base = pickFromPool(COMPLETED_POOL_FR[payload.module] || [], poolIndex)
      return base ? `${base}${summary}` : `${label.charAt(0).toUpperCase() + label.slice(1)} est prêt.${summary}`
    }
    case 'failed': {
      const base = pickFromPool(FAILED_POOL_FR[payload.module] || [], poolIndex)
      return base ? `${base}${summary}` : `Échec sur ${label}.${summary}`
    }
    case 'cancelled':
      return `${label.charAt(0).toUpperCase() + label.slice(1)} annulé.`
  }
}

/** Permet aux tests d'inspecter les pools. */
export const _internal = { MODULE_LABEL_FR, COMPLETED_POOL_FR, FAILED_POOL_FR }
