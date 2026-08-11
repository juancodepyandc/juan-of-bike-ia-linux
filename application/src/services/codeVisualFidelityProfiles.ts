// Ce que « excellent » veut dire, PAR NATURE DE PROJET.
//
// Mesure reelle (run 971): un convertisseur Celsius/Fahrenheit demande pour une
// collegienne — « un petit truc tout simple », conversion en direct, sans
// bouton — a ete livre exactement comme demande: HTML semantique, conversion a
// la frappe, Inter, variables CSS, clamp(), ombre douce. Le pipeline l a
// declare INSUFFISANT (53/100) et a exige:
//
//     - Au moins 6 sections (hero / galerie / specs / KPIs / testimonials...)
//     - Au moins 2 images (trouve: 0)
//     - Transformations 3D (rotateY/X, perspective, preserve-3d)
//     - Animation pilotee par scroll
//     - Au moins 2 gradients layered
//     - HTML > 6 ko (trouve: 1 ko)
//
// C est le gabarit d une landing marketing premium, applique tel quel a un
// outil a une page. Les satisfaire aurait activement DEGRADE le produit: un
// convertisseur avec un hero, une galerie et une rotation 3D au scroll est un
// convertisseur moins bon. Un seuil universel ne mesure pas la qualite, il
// mesure la ressemblance a UN genre.
//
// La barre reste a 70. Ce qui change, c est la LISTE des criteres qui comptent.

import type { CodeIntent } from './codeIntent.ts'

export type VisualAmbition = 'showcase' | 'application' | 'utility'

type CodeFileLike = { name: string; content: string }

// Vocabulaire de vitrine: on VEND quelque chose, l apparence est le produit.
const SHOWCASE_RE = /\b(?:landing|vitrine|marque|brand|portfolio|e-?commerce|boutique|showroom|site\s+(?:web\s+)?(?:pour|de|d[eu])|page\s+d[e']\s*accueil|promou|marketing|agence|startup|presenter?\s+(?:notre|mon|ma|nos|mes))\b/i

// Vocabulaire d application: on FAIT quelque chose, l ecran est un poste de travail.
const APPLICATION_RE = /\b(?:dashboard|tableau\s+de\s+bord|admin|back-?office|crm|erp|saas|editeur|editor|ide|console|panneau|gestion|kanban|analytics|statistiques)\b/i

// Vocabulaire d outil: une tache, un ecran, zero ceremonie.
const UTILITY_RE = /\b(?:convertisseur|convertir|calculatrice|calculette|minuteur|chronom|compteur|generateur\s+de|todo|to-?do|pense-?bete|memo|bloc-?notes|quiz|tirage|aleatoire|comparateur\s+simple|petit\s+(?:truc|outil|script|utilitaire)|simple\s+(?:outil|page|script)|utilitaire)\b/i

const SIMPLICITY_RE = /\b(?:tout\s+simple|tres\s+simple|rien\s+d[e']\s*autre|juste\s+(?:la\s+page|une\s+page|un\s+truc)|pas\s+besoin\s+de\s+(?:compte|base)|minimaliste|epure)\b/i

/**
 * Criteres qui ne s appliquent PAS a une ambition donnee.
 *
 * On ne baisse jamais la barre: on retire du calcul ce qui n a aucun sens pour
 * le genre. Un outil qui n a pas de galerie n est pas un outil rate.
 */
export const AMBITION_EXCLUDED_CHECKS: Record<VisualAmbition, readonly string[]> = {
  // La vitrine est jugee sur tout: son apparence EST le produit livre.
  showcase: [],
  // Un poste de travail n est pas une page qui se scrolle: pas de sections
  // narratives, pas de parallaxe, pas de photos d ambiance imposees.
  application: [
    'min_sections',
    'has_images',
    'has_3d_transforms',
    'has_scroll_driven',
    'has_layered_gradients',
  ],
  // Un outil a une tache: on juge la clarte, la finition et la vie de l
  // interface, jamais la richesse editoriale.
  utility: [
    'min_sections',
    'has_images',
    'has_inline_svg',
    'has_3d_transforms',
    'has_scroll_driven',
    'has_layered_gradients',
    'has_gradient',
    'has_depth',
    'has_animations',
    'html_size',
  ],
}

/** Ce qui reste exige, en clair — sert la critique ET la documentation. */
export const AMBITION_BAR: Record<VisualAmbition, string> = {
  showcase: 'vitrine: richesse editoriale, profondeur, mouvement et iconographie travaillee',
  application: 'application: densite lisible, hierarchie, etats interactifs et finition, sans habillage narratif',
  utility: 'outil: clarte, typographie soignee, finition (rayons, ombres, survol) et interface vivante — ni hero, ni galerie, ni parallaxe',
}

function projectIsSmall(files: CodeFileLike[]): boolean {
  const codeFiles = files.filter((file) => !/^(?:readme\.md|start\.sh)$/i.test(file.name)
    && !/aurora-asset-bundle\.json$/i.test(file.name))
  const bytes = codeFiles.reduce((sum, file) => sum + file.content.length, 0)
  return codeFiles.length <= 5 && bytes < 24_000
}

/**
 * Nature visuelle du projet, deduite du brief ET de ce qui a ete livre.
 *
 * L intention prime quand elle est explicite; la taille reelle du livrable
 * tranche les cas muets (un projet de 3 fichiers et 5 ko n est pas une vitrine
 * de marque, quoi qu en dise un classifieur).
 */
export function resolveVisualAmbition(
  prompt: string,
  intent: CodeIntent,
  files: CodeFileLike[] = [],
): VisualAmbition {
  const text = prompt || ''
  const hasBrandSubject = intent.assetPlan?.subject?.source === 'brand'
    || intent.assetPlan?.subject?.source === 'inferred_brand'

  // Une marque a vendre l emporte: c est une vitrine, meme courte.
  if (hasBrandSubject && SHOWCASE_RE.test(text)) return 'showcase'

  const utility = UTILITY_RE.test(text)
  const simplicity = SIMPLICITY_RE.test(text)
  const showcase = SHOWCASE_RE.test(text) || hasBrandSubject
  const application = APPLICATION_RE.test(text)

  if (utility && !showcase) return 'utility'
  if (showcase) return 'showcase'
  if (application) return 'application'
  // Muet: c est le livrable qui parle. Trois fichiers et 5 ko ne sont pas une
  // vitrine — les juger comme telle est ce qui a coute le run 971.
  if ((simplicity || projectIsSmall(files)) && intent.projectType === 'static_web') return 'utility'
  if (intent.projectType.startsWith('spa_') || intent.projectType.startsWith('fullstack_')) return 'application'
  return 'showcase'
}
