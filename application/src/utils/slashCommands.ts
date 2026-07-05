/**
 * Slash-command library — rewrites a user-typed command into a richer prompt
 * before it reaches the LLM. Keeps the chat composer honest: the user sees
 * their /explain, the model gets a full instruction set.
 *
 * Matching is case-insensitive, takes the command + optional argument string.
 *   /explain quantum entanglement → triggers the `explain` pattern
 *   /fiche  Algèbre linéaire     → triggers the `fiche` pattern
 *   /summary                      → no arg, summarizes the current thread
 */
export interface SlashCommand {
  name: string
  aliases: string[]
  description: string
  /** Build the actual prompt that will be sent. `arg` is everything after the command. */
  transform: (arg: string) => string
  /** Shown in the popup menu. */
  example: string
}

export const SLASH_COMMANDS: SlashCommand[] = [
  {
    name: 'fiche',
    aliases: ['fiche', 'revision'],
    description: 'Fiche de révision complète sur un sujet',
    example: '/fiche Dérivées',
    transform: (arg) => `Génère une FICHE DE RÉVISION dense et organisée sur « ${arg.trim() || '(précise le sujet)'} » — définitions, propriétés, formules, méthode pas-à-pas, pièges fréquents, exemple traité. Structure markdown avec ##, listes, formules $...$.`,
  },
  {
    name: 'explain',
    aliases: ['explain', 'explique'],
    description: 'Explique un concept comme à un débutant',
    example: '/explain entropie',
    transform: (arg) => `Explique « ${arg.trim() || '(précise le concept)'} » comme à un élève de lycée, en 3-5 paragraphes : intuition → définition précise → exemple concret → erreurs classiques → lien avec d'autres notions.`,
  },
  {
    name: 'translate',
    aliases: ['translate', 'traduis', 'tr'],
    description: 'Traduis du français vers une autre langue',
    example: '/translate en Bonjour comment ça va',
    transform: (arg) => {
      const match = arg.trim().match(/^(\S+)\s+(.+)$/)
      if (match) {
        const [, lang, text] = match
        return `Traduis le texte suivant en ${lang}, donne UNIQUEMENT la traduction sans explication :\n\n${text}`
      }
      return `Traduis le texte suivant (précise la langue cible en premier) : ${arg}`
    },
  },
  {
    name: 'code',
    aliases: ['code', 'dev', 'implement'],
    description: 'Écris du code à partir d\'une spec',
    example: '/code python fonction qui lit un CSV',
    transform: (arg) => `Écris du CODE propre et commenté pour : « ${arg.trim() || '(précise la tâche)'} ».
Rends uniquement un bloc \`\`\`<langage> de code prêt à exécuter. Ajoute 1-2 lignes d'explication après si nécessaire, pas plus.`,
  },
  {
    name: 'summary',
    aliases: ['summary', 'resume', 'tldr'],
    description: 'Résume la conversation ou un texte',
    example: '/summary (résume la conversation)',
    transform: (arg) => arg.trim()
      ? `Résume le texte suivant en 5 points-clés, concis :\n\n${arg}`
      : `Fais un résumé en 5 points-clés de NOTRE conversation depuis le début. Pas de méta-commentaire, juste les points. Chiffres et références concrètes conservés.`,
  },
  {
    name: 'quiz',
    aliases: ['quiz', 'qcm'],
    description: 'Quiz QCM de 5 questions sur un sujet',
    example: '/quiz Guerre froide',
    transform: (arg) => `Génère un quiz QCM de 5 questions sur « ${arg.trim() || '(précise le sujet)'} » avec 4 choix chacune. Numérote les questions, liste les choix A/B/C/D, mets la bonne réponse + une explication d'une phrase à la fin.`,
  },
  {
    name: 'plan',
    aliases: ['plan', 'dissert'],
    description: 'Plan de dissertation / exposé',
    example: '/plan la liberté est-elle une illusion ?',
    transform: (arg) => `Construis un PLAN DÉTAILLÉ (I / II / III + sous-parties A B C) pour traiter la question : « ${arg.trim() || '(précise le sujet)'} ». Problématique, thèse/antithèse/synthèse si pertinent, 1 exemple concret par sous-partie.`,
  },
  {
    name: 'proof',
    aliases: ['proof', 'preuve', 'demo'],
    description: 'Démonstration mathématique pas-à-pas',
    example: '/proof théorème de Pythagore',
    transform: (arg) => `Démontre pas-à-pas « ${arg.trim() || '(précise le théorème)'} » avec rigueur universitaire : énoncé, hypothèses, démonstration numérotée (1. 2. 3. ...), conclusion. Formules LaTeX en $$.`,
  },
  {
    name: 'debug',
    aliases: ['debug', 'fix'],
    description: 'Diagnostique un bug à partir d\'un message d\'erreur',
    example: '/debug <stack trace>',
    transform: (arg) => `Diagnostique le problème suivant : donne la cause racine en 1 phrase, puis la solution concrète (patch, commande, config). Pas de disclaimer.\n\n${arg}`,
  },
  {
    name: 'citations',
    aliases: ['cite', 'sources'],
    description: 'Cite des sources vérifiables sur un sujet',
    example: '/cite chiffres du chômage France 2025',
    transform: (arg) => `Donne 5 références vérifiables (livre, article, site institutionnel, étude) sur : « ${arg.trim() || '(précise le sujet)'} ». Format : titre · auteur/institution · année · URL si connue. Si tu n'es pas sûr d'une référence, ne l'invente pas — écris « à vérifier ».`,
  },
]

export function findCommand(input: string): { cmd: SlashCommand; arg: string } | null {
  if (!input.startsWith('/')) return null
  const m = input.slice(1).match(/^(\w+)\s*(.*)$/s)
  if (!m) return null
  const [, word, arg] = m
  const lw = word.toLowerCase()
  for (const cmd of SLASH_COMMANDS) {
    if (cmd.aliases.includes(lw)) return { cmd, arg: arg || '' }
  }
  return null
}

export function applySlashCommand(input: string): string {
  const match = findCommand(input)
  if (!match) return input
  // v82ej : track la commande dans le LRU dès qu'elle est exécutée.
  recordSlashUsage(match.cmd.name)
  return match.cmd.transform(match.arg)
}

/** v82ej : LRU des dernières commandes utilisées (cap 3). */
const SLASH_RECENT_KEY = 'aurora-slash-recent-v1'
const SLASH_RECENT_MAX = 3
export function getRecentSlash(): string[] {
  if (typeof window === 'undefined') return []
  try {
    const raw = window.localStorage.getItem(SLASH_RECENT_KEY)
    if (!raw) return []
    const arr = JSON.parse(raw)
    return Array.isArray(arr) ? arr.filter((s) => typeof s === 'string').slice(0, SLASH_RECENT_MAX) : []
  } catch { return [] }
}
export function recordSlashUsage(name: string): void {
  if (typeof window === 'undefined' || !name) return
  try {
    const cur = getRecentSlash().filter((n) => n !== name)
    const next = [name, ...cur].slice(0, SLASH_RECENT_MAX)
    window.localStorage.setItem(SLASH_RECENT_KEY, JSON.stringify(next))
  } catch { /* ignore */ }
}

/** Filter the library by the current typed prefix, for autocomplete menus.
 *  v82ej : si prefix === '/', prepend les commandes récentes (LRU). */
export function suggestCommands(prefix: string): SlashCommand[] {
  if (!prefix.startsWith('/')) return []
  const q = prefix.slice(1).toLowerCase().trim()
  if (!q) {
    const recent = getRecentSlash()
    if (recent.length === 0) return SLASH_COMMANDS
    const recentCmds = recent
      .map((n) => SLASH_COMMANDS.find((c) => c.name === n))
      .filter((c): c is SlashCommand => !!c)
    const recentNames = new Set(recentCmds.map((c) => c.name))
    const rest = SLASH_COMMANDS.filter((c) => !recentNames.has(c.name))
    return [...recentCmds, ...rest]
  }
  return SLASH_COMMANDS.filter((c) =>
    c.aliases.some((a) => a.startsWith(q)) || c.description.toLowerCase().includes(q),
  )
}
