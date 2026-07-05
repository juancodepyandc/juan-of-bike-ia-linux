// SQL injection sandbox — simule une vraie injection sur une table fake
// users, montre la query générée, et révèle le bypass quand le payload
// contient des patterns SQL injection classiques.
//
// Pédagogie pure : la query est analysée par regex (pas executée), donc
// pas de SGBD réel — l'utilisateur voit (1) la requête vulnérable
// reconstituée, (2) le set de lignes qui MATCHERAIT logiquement,
// (3) la version prepared statement qui empêche l'injection.

export type FakeUser = {
  id: number
  username: string
  password: string  // demo — en réel : hash bcrypt/argon2
  role: 'admin' | 'user' | 'guest'
}

// Table fake — pédagogie. Mots de passe en clair POUR LE LABO, à ne pas
// reproduire en réel.
const USERS: readonly FakeUser[] = [
  { id: 1, username: 'admin',  password: 'admin123',     role: 'admin' },
  { id: 2, username: 'alice',  password: 'wonderland42', role: 'user' },
  { id: 3, username: 'bob',    password: 'builder99',    role: 'user' },
  { id: 4, username: 'guest',  password: 'guest',        role: 'guest' },
]

export type InjectionVerdict =
  | 'safe'           // pas d'injection détectée, query normale
  | 'auth-bypass'    // bypass auth (OR '1'='1', comment, etc.)
  | 'union-leak'     // UNION SELECT pour leak data
  | 'comment-trick'  // commentaire utilisé pour neutraliser
  | 'destructive'    // tentative DROP/DELETE/UPDATE

export type SqlInjectionResult = {
  /** Query reconstituée (mode vulnérable). */
  vulnerableQuery: string
  /** Query prepared statement équivalente. */
  preparedQuery: string
  /** Verdict de l'analyse. */
  verdict: InjectionVerdict
  /** Patterns suspects détectés. */
  detectedPatterns: string[]
  /** Lignes que la query vulnérable retournerait. */
  rowsLeaked: FakeUser[]
  /** Explication pédagogique. */
  explanation: string
  /** Severity 0..1. */
  severity: number
}

const PATTERNS: Array<{ name: string; re: RegExp; verdict: InjectionVerdict; severity: number }> = [
  { name: "Tautology (OR '1'='1')",   re: /'\s*(?:OR|AND)\s*['"]?1['"]?\s*=\s*['"]?1['"]?/i, verdict: 'auth-bypass', severity: 0.95 },
  { name: "Always true (OR 1=1)",     re: /\b(?:OR|AND)\s*1\s*=\s*1\b/i,                     verdict: 'auth-bypass', severity: 0.9 },
  { name: 'Comment terminator (--)',  re: /--/,                                                verdict: 'comment-trick', severity: 0.75 },
  { name: 'Block comment (/* */)',    re: /\/\*|\*\//,                                         verdict: 'comment-trick', severity: 0.7 },
  { name: 'UNION SELECT',             re: /\bUNION\s+SELECT\b/i,                              verdict: 'union-leak', severity: 1 },
  { name: 'DROP/DELETE/UPDATE',       re: /\b(DROP|DELETE\s+FROM|UPDATE\s+\w+\s+SET|TRUNCATE)\b/i, verdict: 'destructive', severity: 1 },
  { name: 'Stacked query (;)',        re: /;\s*(?:DROP|INSERT|UPDATE|DELETE)/i,               verdict: 'destructive', severity: 1 },
  { name: "Single quote unbalanced",  re: /'/,                                                  verdict: 'comment-trick', severity: 0.45 },
]

/**
 * Construit la query vulnérable.
 */
function buildVulnerableQuery(username: string, password: string): string {
  return `SELECT id, username, role FROM users WHERE username = '${username}' AND password = '${password}'`
}

/**
 * Construit l'équivalent prepared statement.
 */
function buildPreparedQuery(): string {
  return [
    "SELECT id, username, role FROM users",
    "WHERE username = ?",
    "  AND password = ?",
    '-- bindings: [username, password]',
  ].join('\n')
}

/**
 * Détecte si une query construite via string-concat aboutirait à une
 * auth-bypass : on regarde si la query inclut un pattern qui rend le WHERE
 * toujours vrai (OR '1'='1', --, etc.).
 *
 * Pour pédagogie, on simule l'exécution :
 *   - Si auth-bypass → retourne TOUTES les lignes (comme un vrai SGBD).
 *   - Si union-leak → retourne aussi toutes les lignes (l'union expose tout).
 *   - Sinon, on cherche un user dont le username/password match littéralement.
 */
export function tryInject(username: string, password: string): SqlInjectionResult {
  const vulnerableQuery = buildVulnerableQuery(username, password)
  const preparedQuery = buildPreparedQuery()

  const detected: string[] = []
  let worst: { verdict: InjectionVerdict; severity: number } = { verdict: 'safe', severity: 0 }
  for (const p of PATTERNS) {
    if (p.re.test(username) || p.re.test(password)) {
      detected.push(p.name)
      if (p.severity > worst.severity) worst = { verdict: p.verdict, severity: p.severity }
    }
  }

  let rowsLeaked: FakeUser[] = []
  let explanation = ''
  if (worst.verdict === 'auth-bypass' || worst.verdict === 'comment-trick') {
    rowsLeaked = [...USERS]
    explanation =
      `Le payload « ${username} » contient un fragment SQL qui rend la condition WHERE toujours vraie.\n` +
      `Le SGBD renvoie TOUTES les lignes de la table users — souvent le 1er = admin → bypass.\n` +
      `Fix : prepared statement (placeholder ?, binding séparé). Le SGBD ne ré-interprète plus les quotes.`
  } else if (worst.verdict === 'union-leak') {
    rowsLeaked = [...USERS]
    explanation =
      `UNION SELECT permet de fusionner les résultats avec une autre table.\n` +
      `Avec le bon nombre de colonnes alignées, l'attaquant lit n'importe quelle table accessible.\n` +
      `Fix : prepared statements + principe du moindre privilège côté DB user.`
  } else if (worst.verdict === 'destructive') {
    explanation =
      `Le payload contient une commande destructive (DROP/DELETE/UPDATE).\n` +
      `Sur un SGBD qui accepte les stacked queries (MS SQL), ça aurait passé.\n` +
      `Fix : prepared statements + multi-statement désactivé + droits restreints.`
  } else {
    // Auth normal
    const match = USERS.find((u) => u.username === username && u.password === password)
    if (match) {
      rowsLeaked = [match]
      explanation = `Authentification normale réussie pour ${match.username} (rôle ${match.role}).`
    } else {
      explanation = `Aucun match · username/password invalides.`
    }
  }

  return {
    vulnerableQuery,
    preparedQuery,
    verdict: worst.verdict,
    detectedPatterns: detected,
    rowsLeaked,
    explanation,
    severity: worst.severity,
  }
}

/** Exports pour UI. */
export const SQL_DEMO_USERS = USERS
export const SQL_DEMO_PAYLOADS = [
  { label: "Auth bypass classique", username: "admin' --", password: "anything" },
  { label: "Tautology OR 1=1",       username: "' OR '1'='1", password: "x" },
  { label: "UNION leak",             username: "' UNION SELECT * FROM users --", password: "x" },
  { label: "Destructive",            username: "x'; DROP TABLE users; --", password: "" },
  { label: "Auth normale",           username: "alice", password: "wonderland42" },
] as const
