/**
 * v82fe : pool partagé de conversation starters pour les boutons
 * "⚡ surprise" V1 / V3 / Manga ChatView. Mutualisé pour avoir une
 * source unique et permettre des extensions futures (catégories,
 * pondération par profil utilisateur, etc.).
 */

export const RANDOM_CHAT_STARTERS: string[] = [
  'Explique-moi un concept de physique quantique de manière intuitive',
  'Quelle est l\'invention scientifique la plus sous-estimée du 20e siècle ?',
  'Donne-moi une recette de pâtes simple mais raffinée',
  'Quel livre devrais-je lire pour comprendre l\'histoire de la France ?',
  'Explique-moi le théorème de Gödel sans jargon mathématique',
  'Quelles sont les meilleures pratiques pour apprendre une nouvelle langue ?',
  'Aide-moi à planifier une routine matinale productive',
  'Compare-moi 3 styles musicaux que je devrais explorer',
  'Quelles séries SF récentes valent vraiment le coup ?',
  'Explique le fonctionnement d\'un réseau de neurones avec une analogie simple',
  'Donne-moi 5 anecdotes historiques peu connues mais fascinantes',
  'Comment structurer une présentation orale percutante en 10 minutes ?',
]

/** Pioche un starter au hasard. */
export function pickRandomStarter(): string {
  return RANDOM_CHAT_STARTERS[Math.floor(Math.random() * RANDOM_CHAT_STARTERS.length)]
}
