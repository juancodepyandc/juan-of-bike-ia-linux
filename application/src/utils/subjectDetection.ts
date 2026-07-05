/**
 * Pure utility: detect academic subject kind from a string.
 * No external dependencies — fully testable in Node.js.
 */

export type SubjectKind =
  | 'philo'
  | 'histoire'
  | 'geo'
  | 'maths'
  | 'science'
  | 'langue'
  | 'litterature'
  | 'informatique'
  | 'economie'
  | 'art'
  | 'general'

export const SUBJECT_HINTS: Record<SubjectKind, string> = {
  philo: 'philosophie, dissertations, auteurs, citations, thèses',
  histoire: 'chronologie, dates, personnages, causes/conséquences',
  geo: 'régions, territoires, enjeux, populations, climats',
  maths: 'formules, démonstrations, propriétés, théorèmes',
  science: 'définitions, mécanismes, lois, expériences, schémas',
  langue: 'vocabulaire, grammaire, conjugaison, traductions',
  litterature: 'auteurs, œuvres, courants, citations',
  informatique: 'concepts, algorithmes, syntaxes, patterns',
  economie: 'concepts, indicateurs, mécanismes, acteurs',
  art: 'courants, artistes, techniques, œuvres',
  general: 'synthèse structurée et mémorisable',
}

function stripAccents(input: string): string {
  return input
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
}

export function detectSubjectKind(subject: string, theme?: string): SubjectKind {
  const source = stripAccents(`${subject} ${theme ?? ''}`)
  const buckets: Array<[SubjectKind, RegExp]> = [
    ['philo', /\b(philo|philosophie|descartes|kant|nietzsche|sartre|stoic|stoicien|ethique|metaphysique|dissertation|morale|liberte|existentialisme|epictete|marc aurele)\b/],
    ['histoire', /\b(histoire|guerre|revolution|napoleon|empire|antiquite|medieval|xix|xx|epoque|chronologie|dynastie|president|roi|reine|1789|1945|moyen age|renaissance|antiquite)\b/],
    ['geo', /\b(geographie|pays|continent|region|capitale|climat|population|urbanisation|mondialisation|carte|territoire)\b/],
    ['maths', /\b(math|maths|algebre|calcul|integrale|derivee|fonction|theoreme|geometrie|probabilite|statistique|equation|trigonometrie|trigo|vecteur|matrice|pythagore)\b/],
    ['science', /\b(physique|chimie|biologie|svt|cellule|atome|molecule|force|energie|reaction|evolution|anatomie|photosynthese|ecosysteme|genetique|adn)\b/],
    ['langue', /\b(anglais|espagnol|allemand|italien|vocabulaire|grammaire|conjugaison|verbe|traduction|phonetic|langue)\b/],
    ['litterature', /\b(litterature|roman|poeme|poesie|theatre|hugo|moliere|baudelaire|zola|camus|proust|auteur|oeuvre|courant litteraire)\b/],
    ['informatique', /\b(informatique|code|algorithme|python|javascript|typescript|java|c\+\+|reseau|systeme|base de donnees|sql|programmation|git|docker|api|framework)\b/],
    ['economie', /\b(economie|inflation|pib|marche|monnaie|banque|bourse|fiscalite|entreprise|commerce|keynes|smith)\b/],
    ['art', /\b(peinture|sculpture|impressionnisme|renaissance|baroque|cubisme|artiste|picasso|monet|van ?gogh|musee)\b/],
  ]

  for (const [kind, regex] of buckets) {
    if (regex.test(source)) return kind
  }
  return 'general'
}
