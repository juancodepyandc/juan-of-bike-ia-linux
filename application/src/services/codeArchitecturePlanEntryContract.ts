// ---------------------------------------------------------------------------
// codeArchitecturePlanEntryContract — garantit que le plan contient la porte
// d entree du type de projet.
//
// Observe en run reel, deux fois. L intention est bien `static_web`, mais
// l architecte produit un plan Next.js (`src/app/layout.tsx`, `next.config.js`,
// `tailwind.config.ts`) sans `index.html`. Ensuite :
//
//  - le contrat plan/livraison passe (les fichiers livres correspondent au plan) ;
//  - la porte de livraison, elle, refuse: « Page web statique detectee mais
//    `index.html` est absent » ;
//  - la boucle de sortie regenere... le meme plan, donc le meme manque.
//
// Le run brule ainsi ses passes jusqu a epuisement du budget sur un defaut que
// personne ne corrige, parce que l executor ne peut ecrire QUE les fichiers de
// la file issue du plan: dire au codeur « index.html est obligatoire » ne sert a
// rien si le plan ne le contient pas.
//
// La reparation est DETERMINISTE et sans appel modele supplementaire: chaque
// passe de replanification couterait un chargement de modele, ce que le budget
// VRAM de la machine ne supporte pas.
// ---------------------------------------------------------------------------

import type { CodeIntent, CodeProjectType } from './codeIntentTypes.ts'

export type ArchitecturePlanEntryRepair = {
  /** Plan serialise, repare si necessaire. */
  plan: string
  /** Fichiers d entree ajoutes au plan (vide si le plan etait deja conforme). */
  added: string[]
}

type PlanFile = {
  path: string
  role?: string
  language?: string
  required?: boolean
  imports?: string[]
  exports?: string[]
  notes?: string[]
}

/**
 * Porte d entree non negociable par type de projet. Source de verite unique,
 * partagee avec le contrat qualite envoye au codeur: deux listes divergentes
 * produiraient un plan et un contrat qui se contredisent.
 */
export function requiredEntryFilesForProject(projectType: CodeProjectType): string[] {
  switch (projectType) {
    case 'static_web':
    case 'game_web':
      return ['index.html']
    case 'spa_react':
    case 'spa_vue':
    case 'spa_angular':
    case 'spa_svelte':
      return ['index.html', 'package.json']
    case 'ssr_nextjs':
    case 'fullstack_nextjs':
      return ['package.json']
    default:
      return []
  }
}

function normalize(path: string) {
  return path.replace(/\\/g, '/').replace(/^\.\/+/, '').toLowerCase()
}

function entryFileSpec(path: string): PlanFile {
  const isHtml = /\.html?$/i.test(path)
  return {
    path,
    role: isHtml ? 'page' : 'manifest',
    language: isHtml ? 'html' : 'json',
    required: true,
    imports: [],
    exports: [],
    notes: [
      isHtml
        ? 'Page d entree du projet: charge reellement les styles et scripts produits (<link>/<script> vers les chemins existants).'
        : 'Manifeste du projet.',
    ],
  }
}

/**
 * Ajoute au plan les fichiers d entree manquants pour le type de projet.
 *
 * Ne touche a rien quand le plan est deja conforme, et rend le plan d origine
 * tel quel si le JSON est inexploitable (la validation en amont s en charge).
 */
export function ensureArchitecturePlanEntryFiles(
  serializedPlan: string,
  intent: CodeIntent,
): ArchitecturePlanEntryRepair {
  const required = requiredEntryFilesForProject(intent.projectType)
  if (required.length === 0) return { plan: serializedPlan, added: [] }

  let parsed: Record<string, unknown>
  try {
    parsed = JSON.parse(serializedPlan) as Record<string, unknown>
  } catch {
    return { plan: serializedPlan, added: [] }
  }
  if (!parsed || typeof parsed !== 'object' || !Array.isArray(parsed.files)) {
    return { plan: serializedPlan, added: [] }
  }

  const files = parsed.files as PlanFile[]
  const present = new Set(
    files
      .map((file) => (typeof file?.path === 'string' ? normalize(file.path) : ''))
      .filter(Boolean),
  )

  const added: string[] = []
  for (const entry of required) {
    if (present.has(normalize(entry))) continue
    files.unshift(entryFileSpec(entry))
    added.push(entry)
  }
  if (added.length === 0) return { plan: serializedPlan, added: [] }

  // La porte d entree se genere en premier: les autres fichiers s y raccrochent.
  if (Array.isArray(parsed.generationOrder)) {
    const order = (parsed.generationOrder as unknown[]).filter(
      (value): value is string => typeof value === 'string',
    )
    parsed.generationOrder = [...added, ...order.filter((path) => !added.some((a) => normalize(a) === normalize(path)))]
  }

  return { plan: JSON.stringify(parsed), added }
}
