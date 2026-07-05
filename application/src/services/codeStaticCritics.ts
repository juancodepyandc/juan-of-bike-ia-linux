// Critics statiques qui s'exécutent SANS LLM sur du code généré.
// Chacun retourne un score [0..1] + des issues détaillées.
// Ils sont injectables dans runCritiqueLoop comme une étape déterministe
// AVANT de payer un round-trip LLM-critic.
//
// L'objectif est qu'un code clairement cassé (eval(), innerHTML d'input
// utilisateur, fonctions de 200 lignes, no-await sur promise) tombe à
// score < 0.5 sans appeler de modèle.

import type { CodeFile, CodeProject, CriticFn, CritiqueAxis, CritiqueIssue, CritiqueReport } from './codeMultiPassCritique.ts'
import { buildReport } from './codeMultiPassCritique.ts'
import type { CodeIntent } from './codeIntent.ts'

// --- Helpers ---------------------------------------------------------------

const TS_LIKE = ['ts', 'tsx', 'jsx', 'js', 'typescript', 'javascript']
const PY_LIKE = ['py', 'python']
const HTML_LIKE = ['html', 'htm']
const CSS_LIKE = ['css', 'scss']

function isTsLike(lang: string): boolean {
  return TS_LIKE.includes(lang.toLowerCase())
}
function isPyLike(lang: string): boolean {
  return PY_LIKE.includes(lang.toLowerCase())
}
function isHtmlLike(lang: string): boolean {
  return HTML_LIKE.includes(lang.toLowerCase())
}
function isCssLike(lang: string): boolean {
  return CSS_LIKE.includes(lang.toLowerCase())
}

function countLines(content: string): number {
  return content.split(/\r?\n/).length
}

function normalizedName(name: string): string {
  return name.replace(/\\/g, '/').replace(/^\.\//, '').toLowerCase()
}

// --- 1. Syntax sanity critic -----------------------------------------------
// Vrai parser : non. Mais on attrape les classes d'erreurs visibles
// (parenthèses non équilibrées, JSX mal fermé, indent Python brisé,
// imports incomplets).

function bracketBalance(content: string): { ok: boolean; diff: number; kind: string } {
  // Strip string literals + comments to avoid false positives.
  // ORDRE CRITIQUE :
  //   1. /* */ : retire les commentaires de bloc en premier (peuvent contenir
  //      // ou des strings imbriquées qui se feraient mal stripper sinon).
  //   2. //   : retire les commentaires de ligne AVANT les strings — sinon
  //      "Anki's" dans un commentaire fait que le regex single-quote attaque
  //      par "Anki" et mange jusqu'au prochain `'` n'importe où dans le code.
  //   3. backtick : retire les template literals avant les single/double
  //      pour la même raison côté FR ("l'attaque" dans une template).
  //   4. doubles, 5. singles : ordre classique en fin.
  //
  // Cet ordre est arrivé après 2 bugs réels successifs détectés sur de vrai
  // code Aurora (kdfCostAnalyzer + spacedRepetition). NE PAS le changer
  // sans relancer le test codeStaticCriticsRealWorld.
  const stripped = content
    .replace(/\/\*[\s\S]*?\*\//g, '')           // /* … */
    .replace(/\/\/[^\n]*/g, '')                 // // …
    .replace(/`(?:\\.|[^`\\])*`/g, '``')        // `template`
    .replace(/"(?:\\.|[^"\\])*"/g, '""')        // "string"
    .replace(/'(?:\\.|[^'\\])*'/g, "''")        // 'string'
  const pairs: Array<[string, string, string]> = [
    ['(', ')', 'parens'],
    ['[', ']', 'brackets'],
    ['{', '}', 'braces'],
  ]
  for (const [open, close, kind] of pairs) {
    let depth = 0
    for (const ch of stripped) {
      if (ch === open) depth += 1
      else if (ch === close) depth -= 1
      if (depth < 0) return { ok: false, diff: depth, kind }
    }
    if (depth !== 0) return { ok: false, diff: depth, kind }
  }
  return { ok: true, diff: 0, kind: '' }
}

function syntaxIssues(file: CodeFile): CritiqueIssue[] {
  const issues: CritiqueIssue[] = []
  if (isTsLike(file.language) || isHtmlLike(file.language)) {
    const bal = bracketBalance(file.content)
    if (!bal.ok) {
      issues.push({
        axis: 'compile',
        severity: 'block',
        message: `${file.name}: ${bal.kind} non équilibrés (diff ${bal.diff})`,
        location: { file: file.name },
        suggestion: 'Vérifie les blocs ouverts/fermés.',
      })
    }
  }
  // Empty file = suspect.
  if (file.content.trim().length === 0) {
    issues.push({
      axis: 'compile',
      severity: 'error',
      message: `${file.name}: fichier vide`,
      location: { file: file.name },
    })
  }
  // Incomplete imports / dangling commas at top-level (TS).
  if (isTsLike(file.language)) {
    if (/import\s*{\s*$/m.test(file.content) || /import\s+from\s+['"]/.test(file.content)) {
      issues.push({
        axis: 'compile',
        severity: 'error',
        message: `${file.name}: import incomplet détecté`,
        location: { file: file.name },
        suggestion: "Termine la déclaration d'import.",
      })
    }
  }
  // Python : indentation mixte tab/space.
  if (isPyLike(file.language)) {
    if (/^\t/m.test(file.content) && /^ {2,}/m.test(file.content)) {
      issues.push({
        axis: 'compile',
        severity: 'error',
        message: `${file.name}: mélange tab + espaces`,
        location: { file: file.name },
        suggestion: 'Choisis tabs OU espaces, pas les deux.',
      })
    }
  }
  return issues
}

export const syntaxCritic: CriticFn = async (project: CodeProject, _intent: CodeIntent): Promise<CritiqueReport> => {
  const issues = project.files.flatMap(syntaxIssues)
  const blockers = issues.filter((i) => i.severity === 'block').length
  const errors = issues.filter((i) => i.severity === 'error').length
  const filesChecked = project.files.length || 1
  // Score proportional to # of clean files.
  const score = blockers > 0 ? 0 : Math.max(0, 1 - (errors / filesChecked) * 0.5)
  return buildReport({ compile: score }, issues)
}

// --- 2. Security critic ----------------------------------------------------
// Pattern-matching on well-known anti-patterns. Source : OWASP Top 10 +
// Cyber lab du module cyber (cryptoVulnerabilities).

type SecurityRule = {
  pattern: RegExp
  message: string
  severity: CritiqueIssue['severity']
  suggestion: string
  appliesTo: (file: CodeFile) => boolean
}

const SECURITY_RULES: SecurityRule[] = [
  {
    pattern: /\beval\s*\(/,
    message: 'Usage de eval() — exécution arbitraire',
    severity: 'block',
    suggestion: 'Remplacer par JSON.parse, Function constructor avec input contrôlé, ou logic deterministe.',
    appliesTo: (f) => isTsLike(f.language) || isHtmlLike(f.language),
  },
  {
    pattern: /\bnew\s+Function\s*\(/,
    message: 'new Function() — équivalent à eval()',
    severity: 'error',
    suggestion: 'Remplacer par une logique deterministe.',
    appliesTo: (f) => isTsLike(f.language) || isHtmlLike(f.language),
  },
  {
    // Path traversal : ".." dans un literal concaténé à une variable (TS)
    // ou f-string Python. Détecte le pattern de construction de chemin
    // contenant ".." côté littéral, indépendamment de l'API utilisée.
    pattern: /[+,]\s*['"`f?]?\.\.[\/\\]/,
    message: 'Concaténation de chemin contenant ".." — risque path traversal',
    severity: 'error',
    suggestion: 'Utiliser path.resolve(workspace, segment), valider que le résultat est dans workspace.',
    appliesTo: (f) => isTsLike(f.language) || isPyLike(f.language),
  },
  {
    // SSRF : fetch URL avec concaténation d'input utilisateur
    pattern: /(?:fetch|axios|request|http\.get|requests\.get)\s*\([^)]*\+[^)]*(?:req\.|request\.|params\.|body\.|query\.|input)/,
    message: 'URL construite avec input utilisateur — risque SSRF',
    severity: 'error',
    suggestion: 'Whitelister les domaines autorisés avant fetch.',
    appliesTo: (f) => isTsLike(f.language) || isPyLike(f.language),
  },
  {
    // Prototype pollution : Object.assign({}, req.body)
    pattern: /Object\.assign\s*\(\s*(?:\{\}|target)\s*,\s*(?:req\.|request\.|params\.|body\.|query\.|input)/,
    message: 'Object.assign({}, input) — risque prototype pollution',
    severity: 'error',
    suggestion: 'Filtrer __proto__ et constructor des keys avant merge, ou utiliser Object.create(null).',
    appliesTo: (f) => isTsLike(f.language),
  },
  {
    // RegExp DoS : .* avec quantifieurs imbriqués
    pattern: /new RegExp\s*\(\s*[^)]*\+\s*(?:req\.|request\.|params\.|body\.|input)/,
    message: 'RegExp construite depuis input utilisateur — risque ReDoS',
    severity: 'warn',
    suggestion: 'Échapper les caractères regex de l\'input, ou limiter la complexité.',
    appliesTo: (f) => isTsLike(f.language),
  },
  {
    // Unsafe deserialization JSON.parse sans try/catch
    pattern: /JSON\.parse\s*\(\s*(?:localStorage|sessionStorage|atob)/,
    message: 'JSON.parse direct sur source potentiellement corrompue (localStorage/atob)',
    severity: 'warn',
    suggestion: 'Wrapper dans try/catch et valider le shape du résultat.',
    appliesTo: (f) => isTsLike(f.language),
  },
  {
    // Open redirect : window.location = paramètre direct
    pattern: /(?:window\.location|location\.href|location\.assign)\s*=\s*(?:req\.|request\.|params\.|query\.|input)/,
    message: 'Open redirect : location.href = input — un attaquant peut rediriger',
    severity: 'error',
    suggestion: 'Whitelister les destinations autorisées.',
    appliesTo: (f) => isTsLike(f.language),
  },
  {
    // Cookie sans HttpOnly/Secure
    pattern: /document\.cookie\s*=\s*['"`][^'"`]*=/,
    message: 'document.cookie assigné direct — préfère lib avec HttpOnly/Secure/SameSite',
    severity: 'warn',
    suggestion: 'Côté serveur, mettre HttpOnly + Secure + SameSite=Lax.',
    appliesTo: (f) => isTsLike(f.language),
  },
  {
    pattern: /\.innerHTML\s*=\s*[^'"][^;]*\+/,
    message: "Concaténation directe dans .innerHTML — risque XSS",
    severity: 'error',
    suggestion: 'Utiliser textContent, ou échapper via une lib de sanitisation (DOMPurify).',
    appliesTo: (f) => isTsLike(f.language) || isHtmlLike(f.language),
  },
  {
    pattern: /document\.write\s*\(/,
    message: 'document.write() — bloque le rendu et casse SSR',
    severity: 'error',
    suggestion: 'Construire des nodes via createElement / framework.',
    appliesTo: (f) => isTsLike(f.language) || isHtmlLike(f.language),
  },
  {
    pattern: /Math\.random\s*\(\)/,
    message: 'Math.random() — non cryptographique',
    severity: 'warn',
    suggestion: 'Pour les tokens/sels : crypto.getRandomValues. Sinon documenter.',
    appliesTo: (f) => isTsLike(f.language),
  },
  {
    pattern: /(?:password|api[_-]?key|token|secret)\s*[:=]\s*['"][^'"]{6,}['"]/i,
    message: 'Secret en dur dans le code',
    severity: 'block',
    suggestion: 'Déplacer vers .env / variable d\'environnement.',
    appliesTo: () => true,
  },
  {
    pattern: /\bexec\s*\(\s*[^)]*\+/,
    message: 'Concaténation dans exec()/subprocess — risque injection commande',
    severity: 'block',
    suggestion: 'Passer args en liste, sans shell=True.',
    appliesTo: (f) => isPyLike(f.language) || isTsLike(f.language),
  },
  {
    pattern: /\bshell\s*=\s*True/,
    message: 'subprocess avec shell=True — injection possible',
    severity: 'error',
    suggestion: 'Passer args en liste sans shell.',
    appliesTo: (f) => isPyLike(f.language),
  },
  {
    pattern: /pickle\.loads?\s*\(/,
    message: 'pickle.loads — exécution arbitraire si source non fiable',
    severity: 'error',
    suggestion: 'Utiliser json.loads ou un format sûr.',
    appliesTo: (f) => isPyLike(f.language),
  },
  {
    pattern: /verify\s*=\s*False/i,
    message: 'TLS verify=False — MITM possible',
    severity: 'error',
    suggestion: 'Garder la vérification TLS active.',
    appliesTo: () => true,
  },
  {
    pattern: /\bhashlib\.(md5|sha1)\s*\(/,
    message: 'MD5/SHA-1 pour mot de passe = banni (cf. module cyber)',
    severity: 'error',
    suggestion: 'argon2id ou bcrypt cost=12.',
    appliesTo: (f) => isPyLike(f.language),
  },
  {
    // SQL injection via concatenation dans une string SQL-ish
    pattern: /(?:execute|query|raw)\s*\(\s*[`'"][^`'"]*(?:SELECT|INSERT|UPDATE|DELETE|DROP)\b[^`'"]*['`"]\s*\+/i,
    message: 'Requête SQL construite par concaténation — risque SQL injection',
    severity: 'block',
    suggestion: 'Utiliser des prepared statements (paramètres bindés).',
    appliesTo: (f) => isTsLike(f.language) || isPyLike(f.language),
  },
  {
    // NoSQL injection : $where avec input direct
    pattern: /\$where\s*:\s*(?:['"`].*\+|req\.|input)/,
    message: '$where MongoDB avec input — risque NoSQL injection',
    severity: 'error',
    suggestion: 'Préférer les opérateurs typés ($eq, $gt, $regex échappé).',
    appliesTo: (f) => isTsLike(f.language),
  },
  {
    // CSRF : form POST sans token visible
    pattern: /method\s*=\s*['"]POST['"](?:(?![\s\S]*csrf|[\s\S]*_token).){0,400}<\/form>/i,
    message: 'Formulaire POST sans champ CSRF token apparent',
    severity: 'warn',
    suggestion: 'Ajouter un input hidden name="csrf_token" + validation serveur.',
    appliesTo: (f) => isHtmlLike(f.language) || isTsLike(f.language),
  },
  {
    // IDOR : route /:id sans contrôle d'autorisation
    pattern: /(?:app|router)\.(?:get|put|post|delete)\s*\(\s*['"`][^'"`]*:[a-zA-Z]+Id\b/,
    message: 'Route avec :id — vérifier l\'autorisation (IDOR possible)',
    severity: 'warn',
    suggestion: 'Vérifier que le user a accès à la ressource avant retour.',
    appliesTo: (f) => isTsLike(f.language) || isPyLike(f.language),
  },
  {
    // Response header injection
    pattern: /\.setHeader\s*\(\s*['"][^'"]+['"]\s*,\s*[^)]*(?:req\.|request\.|params\.|body\.)/,
    message: 'Header HTTP construit depuis input — risque header injection (CRLF)',
    severity: 'error',
    suggestion: 'Whitelister la valeur, refuser \\r\\n.',
    appliesTo: (f) => isTsLike(f.language),
  },
  {
    // CORS permissif : "Access-Control-Allow-Origin" suivi quelque part de "*"
    // entre quotes (header passé comme valeur ou comme objet).
    pattern: /Access-Control-Allow-Origin[^a-zA-Z0-9]{1,20}['"`]\*['"`]/,
    message: 'CORS Access-Control-Allow-Origin: * en code applicatif',
    severity: 'warn',
    suggestion: 'Whitelister les origins légitimes, pas *.',
    appliesTo: () => true,
  },
  {
    // LDAP injection : literal "cn=" / "uid=" / "ldap" suivi de + et d'un input.
    pattern: /(?:['"`](?:cn|uid|ou|dc)=[^'"`]*['"`]|ldap[a-zA-Z]*).{0,60}\+\s*(?:req\.|request\.|params\.|body\.|input)/i,
    message: 'Filtre LDAP construit avec input — risque LDAP injection',
    severity: 'error',
    suggestion: 'Échapper *()\\\\0 selon RFC 4515.',
    appliesTo: (f) => isTsLike(f.language) || isPyLike(f.language),
  },
  {
    // http:// sur endpoint sensible
    pattern: /\bhttp:\/\/[^\s'"]*(?:login|signup|auth|admin|password|token|api[\/_-])/i,
    message: 'URL http:// (non-TLS) sur endpoint sensible',
    severity: 'error',
    suggestion: 'Forcer https://.',
    appliesTo: () => true,
  },
  // --- Python-specific anti-patterns -------------------------------------
  {
    // Mutable default argument : def f(items=[])
    pattern: /^def\s+\w+\s*\([^)]*=\s*(?:\[\]|\{\}|set\(\))/m,
    message: 'Argument par défaut mutable — bug subtil partagé entre appels',
    severity: 'error',
    suggestion: 'Utiliser None et créer dans la fonction.',
    appliesTo: (f) => isPyLike(f.language),
  },
  {
    // bare except: pass
    pattern: /^\s*except\s*:\s*\n\s*pass\s*$/m,
    message: 'except: pass — silencie toutes les erreurs, debug impossible',
    severity: 'error',
    suggestion: 'Catcher l\'exception précise + log.',
    appliesTo: (f) => isPyLike(f.language),
  },
  {
    // bare except (sans Type)
    pattern: /^\s*except\s*:/m,
    message: 'bare except — catche aussi KeyboardInterrupt et SystemExit',
    severity: 'warn',
    suggestion: 'Utiliser except Exception: au minimum.',
    appliesTo: (f) => isPyLike(f.language),
  },
  {
    // assert dans du code production (peut être désactivé avec -O)
    pattern: /^\s*assert\s+.+\s*,\s*['"][^'"]+['"]\s*$/m,
    message: 'assert pour validation — désactivable avec python -O',
    severity: 'warn',
    suggestion: 'Pour la sécurité runtime, utiliser if + raise.',
    appliesTo: (f) => isPyLike(f.language),
  },
  {
    // os.system avec concat = shell injection
    pattern: /os\.system\s*\(\s*[^)]*\+/,
    message: 'os.system avec concaténation — injection de commande',
    severity: 'block',
    suggestion: 'subprocess.run([cmd, arg1, ...]) sans shell=True.',
    appliesTo: (f) => isPyLike(f.language),
  },
  {
    // yaml.load sans Loader= (CVE en série)
    pattern: /yaml\.load\s*\([^)]*\)(?![^\n]*Loader=)/,
    message: 'yaml.load sans Loader= — exécution arbitraire (CVE)',
    severity: 'error',
    suggestion: 'yaml.safe_load(s) ou yaml.load(s, Loader=yaml.SafeLoader).',
    appliesTo: (f) => isPyLike(f.language),
  },
  {
    // SQL Python : execute("SELECT ..." + var)
    pattern: /\.execute\s*\(\s*['"`][^'"`]*%s[^'"`]*['"`]\s*%\s*[a-zA-Z_]/,
    message: 'execute("...%s..." % var) — SQL injection Python old-style',
    severity: 'block',
    suggestion: 'execute("... %s ...", (var,)) — paramètres en tuple.',
    appliesTo: (f) => isPyLike(f.language),
  },
  {
    // print() laissé en debug
    pattern: /^\s*print\s*\(\s*['"`](?:debug|TODO|XXX|DEBUG|FIXME)/m,
    message: 'print() debug oublié',
    severity: 'warn',
    suggestion: 'Utiliser logging.debug ou supprimer.',
    appliesTo: (f) => isPyLike(f.language),
  },
]

function fileSecurityIssues(file: CodeFile): CritiqueIssue[] {
  const issues: CritiqueIssue[] = []
  for (const rule of SECURITY_RULES) {
    if (!rule.appliesTo(file)) continue
    // Match sur le contenu complet — gère les patterns multi-lignes
    // (except:\npass, CSRF cross-form). Le numéro de ligne est calculé
    // depuis l'index du match dans le contenu.
    const m = rule.pattern.exec(file.content)
    if (!m) continue
    const before = file.content.slice(0, m.index)
    const lineNum = before.split(/\r?\n/).length
    issues.push({
      axis: 'security',
      severity: rule.severity,
      message: `${file.name}:${lineNum} — ${rule.message}`,
      location: { file: file.name, line: lineNum },
      suggestion: rule.suggestion,
    })
  }
  return issues
}

export const securityCritic: CriticFn = async (project: CodeProject, _intent: CodeIntent): Promise<CritiqueReport> => {
  const issues = project.files.flatMap(fileSecurityIssues)
  const blockers = issues.filter((i) => i.severity === 'block').length
  const errors = issues.filter((i) => i.severity === 'error').length
  const warns = issues.filter((i) => i.severity === 'warn').length
  let score = 1
  if (blockers > 0) score = 0
  else score = Math.max(0, 1 - errors * 0.2 - warns * 0.05)
  return buildReport({ security: score }, issues)
}

// --- 3. Structure critic ---------------------------------------------------
// Fonctions trop longues, fichier énorme, callback hell, magic numbers
// répétés — indicateurs structurels d'une génération mal pensée.

function countFunctions(content: string, lang: string): { count: number; maxLength: number } {
  if (isTsLike(lang)) {
    const declRe = /\b(?:function\s+\w+|const\s+\w+\s*=\s*(?:async\s+)?\([^)]*\)\s*=>|\w+\s*\([^)]*\)\s*{)/g
    const matches = content.match(declRe) ?? []
    // Approximation : taille = total / count.
    const lines = countLines(content)
    return { count: matches.length, maxLength: matches.length > 0 ? Math.round(lines / matches.length) : lines }
  }
  if (isPyLike(lang)) {
    const lines = content.split(/\r?\n/)
    const defs: number[] = []
    for (let i = 0; i < lines.length; i += 1) {
      if (/^def\s+\w+/.test(lines[i])) defs.push(i)
    }
    if (defs.length === 0) return { count: 0, maxLength: lines.length }
    const gaps: number[] = []
    for (let i = 0; i < defs.length - 1; i += 1) gaps.push(defs[i + 1] - defs[i])
    gaps.push(lines.length - defs[defs.length - 1])
    return { count: defs.length, maxLength: Math.max(...gaps) }
  }
  return { count: 1, maxLength: countLines(content) }
}

function fileStructureIssues(file: CodeFile): CritiqueIssue[] {
  const issues: CritiqueIssue[] = []
  const lines = countLines(file.content)
  if (lines > 1500) {
    issues.push({
      axis: 'lint',
      severity: 'error',
      message: `${file.name}: fichier énorme (${lines} lignes)`,
      location: { file: file.name },
      suggestion: 'Découper en plusieurs modules.',
    })
  } else if (lines > 600) {
    issues.push({
      axis: 'lint',
      severity: 'warn',
      message: `${file.name}: fichier long (${lines} lignes)`,
      location: { file: file.name },
      suggestion: 'Envisager un découpage.',
    })
  }
  if (isTsLike(file.language) || isPyLike(file.language)) {
    const fn = countFunctions(file.content, file.language)
    if (fn.maxLength > 200) {
      issues.push({
        axis: 'lint',
        severity: 'warn',
        message: `${file.name}: fonction de plus de 200 lignes`,
        location: { file: file.name },
        suggestion: 'Extraire des helpers ou des sous-fonctions.',
      })
    }
  }
  // TS : promesses non-await suspectes
  if (isTsLike(file.language)) {
    const fetchOrphan = /^(?!\s*(?:await|return|void)\s)(?:\s*)fetch\s*\(/m
    if (fetchOrphan.test(file.content) && !/\.then\s*\(/.test(file.content)) {
      issues.push({
        axis: 'runtime',
        severity: 'warn',
        message: `${file.name}: fetch() sans await ni .then`,
        location: { file: file.name },
        suggestion: 'Préfixer par await ou void si fire-and-forget intentionnel.',
      })
    }
  }
  return issues
}

export const structureCritic: CriticFn = async (project: CodeProject, _intent: CodeIntent): Promise<CritiqueReport> => {
  const issues = project.files.flatMap(fileStructureIssues)
  const errors = issues.filter((i) => i.severity === 'error').length
  const warns = issues.filter((i) => i.severity === 'warn').length
  const score = Math.max(0, 1 - errors * 0.15 - warns * 0.05)
  return buildReport({ lint: score }, issues)
}

// --- 4. Accessibility critic (HTML / JSX) -----------------------------------

const A11Y_RULES: SecurityRule[] = [
  {
    pattern: /<img\b(?![^>]*\balt\s*=)[^>]*>/i,
    message: 'Image sans attribut alt',
    severity: 'error',
    suggestion: 'Ajouter alt="" si décoratif, sinon une description.',
    appliesTo: (f) => isTsLike(f.language) || isHtmlLike(f.language),
  },
  {
    pattern: /<button\b(?![^>]*aria-label)[^>]*>\s*<(?:svg|i)\b/i,
    message: 'Bouton icon-only sans aria-label',
    severity: 'warn',
    suggestion: 'Ajouter aria-label décrivant l\'action.',
    appliesTo: (f) => isTsLike(f.language) || isHtmlLike(f.language),
  },
  {
    pattern: /<a\b(?![^>]*href)[^>]*onClick/i,
    message: '<a> sans href + onClick = pas accessible clavier',
    severity: 'error',
    suggestion: 'Utiliser <button> pour les actions, garder <a> pour la navigation.',
    appliesTo: (f) => isTsLike(f.language) || isHtmlLike(f.language),
  },
  {
    pattern: /<input\b(?![^>]*(?:aria-label|aria-labelledby|placeholder))[^>]*>/i,
    message: 'Input sans label ni aria-label ni placeholder',
    severity: 'warn',
    suggestion: 'Associer un <label htmlFor> ou ajouter aria-label.',
    appliesTo: (f) => isTsLike(f.language) || isHtmlLike(f.language),
  },
]

function fileA11yIssues(file: CodeFile): CritiqueIssue[] {
  const out: CritiqueIssue[] = []
  for (const rule of A11Y_RULES) {
    if (!rule.appliesTo(file)) continue
    const lines = file.content.split(/\r?\n/)
    for (let i = 0; i < lines.length; i += 1) {
      if (rule.pattern.test(lines[i])) {
        out.push({
          axis: 'accessibility',
          severity: rule.severity,
          message: `${file.name}:${i + 1} — ${rule.message}`,
          location: { file: file.name, line: i + 1 },
          suggestion: rule.suggestion,
        })
        break
      }
    }
  }
  return out
}

export const accessibilityCritic: CriticFn = async (project: CodeProject, _intent: CodeIntent): Promise<CritiqueReport> => {
  const issues = project.files.flatMap(fileA11yIssues)
  const errors = issues.filter((i) => i.severity === 'error').length
  const warns = issues.filter((i) => i.severity === 'warn').length
  const score = Math.max(0, 1 - errors * 0.15 - warns * 0.05)
  return buildReport({ accessibility: score }, issues)
}

// --- 5. Deliverable completeness critic ------------------------------------

function normalizedProjectPaths(project: CodeProject): string[] {
  return project.files.map((f) => f.name.replace(/\\/g, '/').toLowerCase())
}

function isCliLikeIntent(intent: CodeIntent): boolean {
  if (!intent.projectType) return false
  return intent.projectType.startsWith('cli_')
    || intent.projectType.startsWith('system_')
    || intent.projectType === 'script'
    || intent.projectType === 'data_python'
}

function isStaticUiIntent(intent: CodeIntent): boolean {
  if (!intent.projectType) return false
  return intent.projectType === 'static_web' || intent.projectType === 'game_web'
}

function minimumConcreteFiles(intent: CodeIntent): number {
  const expected = Math.max(1, intent.estimatedFileCount || 1)
  if (isStaticUiIntent(intent)) return expected >= 4 ? 3 : Math.min(3, expected)
  if (isCliLikeIntent(intent)) return expected >= 5 ? 4 : Math.min(3, expected)
  if (intent.needsDevServer || intent.needsBundling || intent.projectType.startsWith('spa_')) {
    return expected >= 10 ? Math.max(6, Math.min(8, Math.floor(expected * 0.35))) : Math.min(6, expected)
  }
  return expected >= 10 ? Math.max(5, Math.min(8, Math.floor(expected * 0.35))) : Math.min(4, expected)
}

function deliverableCompletenessIssues(project: CodeProject, intent: CodeIntent): CritiqueIssue[] {
  const issues: CritiqueIssue[] = []
  if (!intent.projectType || !intent.estimatedFileCount) return issues
  const paths = normalizedProjectPaths(project)
  const fileCount = project.files.length
  const minFiles = minimumConcreteFiles(intent)
  const expected = Math.max(1, intent.estimatedFileCount || 1)

  if (expected >= 5 && fileCount < minFiles) {
    issues.push({
      axis: 'fidelity',
      severity: fileCount <= 1 ? 'block' : 'error',
      message: `Livrable trop petit: ${fileCount} fichier(s) pour environ ${expected} attendus par l'intention ${intent.projectType}`,
      suggestion: `Generer au moins ${minFiles} fichiers reels: point d'entree, configuration, styles, logique metier, donnees/services et verification locale.`,
    })
  }

  if ((intent.needsDevServer || intent.needsBundling || intent.projectType.startsWith('spa_'))
      && !paths.some((p) => p.endsWith('package.json'))) {
    issues.push({
      axis: 'runtime',
      severity: 'block',
      message: `${intent.projectType}: package.json manquant pour une livraison dev-server/tunnel`,
      suggestion: 'Ajouter package.json avec scripts dev/build/preview et dependances declarees.',
    })
  }

  if (intent.projectType === 'desktop_tauri') {
    const hasTauriShell = paths.some((p) => p === 'src-tauri/cargo.toml' || p.endsWith('/src-tauri/cargo.toml'))
      && paths.some((p) => p === 'src-tauri/tauri.conf.json' || p.endsWith('/src-tauri/tauri.conf.json'))
      && paths.some((p) => p === 'src-tauri/src/main.rs' || p.endsWith('/src-tauri/src/main.rs'))
    if (!hasTauriShell) {
      issues.push({
        axis: 'runtime',
        severity: 'block',
        message: 'Application Tauri incomplete: shell Rust/config Tauri manquant',
        suggestion: 'Ajouter src-tauri/Cargo.toml, src-tauri/tauri.conf.json et src-tauri/src/main.rs.',
      })
    }
  }

  if (isCliLikeIntent(intent) && expected >= 5) {
    const joined = project.files.map((f) => f.content).join('\n')
    const hasCliParser = /argparse|click\.|commander|yargs|clap::|cobra\.Command|flag\.|--help/i.test(joined)
    const hasVerification = paths.some((p) => /(^|\/)(test|tests|__tests__)\//.test(p) || /\.test\./.test(p))
      || /pytest|node --test|cargo test|go test|unittest/i.test(joined)
    if (!hasCliParser) {
      issues.push({
        axis: 'fidelity',
        severity: 'error',
        message: 'CLI complete sans parser d arguments / --help detectable',
        suggestion: 'Ajouter un parser CLI, --help, erreurs lisibles et codes de sortie coherents.',
      })
    }
    if (!hasVerification) {
      issues.push({
        axis: 'tests',
        severity: 'warn',
        message: 'CLI complete sans test ni script de verification local detectable',
        suggestion: 'Ajouter tests ou script de verification reproductible.',
      })
    }
  }

  return issues
}

export const deliverableCompletenessCritic: CriticFn = async (project: CodeProject, intent: CodeIntent): Promise<CritiqueReport> => {
  const issues = deliverableCompletenessIssues(project, intent)
  const blockers = issues.filter((i) => i.severity === 'block').length
  const errors = issues.filter((i) => i.severity === 'error').length
  const warns = issues.filter((i) => i.severity === 'warn').length
  return buildReport({
    fidelity: Math.max(0, 1 - blockers * 0.5 - errors * 0.25 - warns * 0.05),
    runtime: blockers > 0 ? 0 : 1,
    tests: Math.max(0, 1 - warns * 0.1),
  }, issues)
}

// --- 6. Project integrity critic ------------------------------------------
// Catches cross-file failures that a single-file syntax regex cannot see:
// missing local imports, missing linked assets, and Tailwind utility markup
// generated without Tailwind or matching CSS. These are common "looks like a
// project" failures that compile/run checks may find late after npm install.

const RESOLVABLE_EXTENSIONS = [
  '.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs',
  '.json', '.css', '.scss', '.sass', '.less',
  '.html', '.htm', '.svg',
]

function dirnameOf(name: string): string {
  const normalized = normalizedName(name)
  const slash = normalized.lastIndexOf('/')
  return slash >= 0 ? normalized.slice(0, slash) : ''
}

function joinProjectPath(baseDir: string, specifier: string): string {
  const raw = `${baseDir ? `${baseDir}/` : ''}${specifier}`.replace(/\\/g, '/')
  const parts: string[] = []
  for (const part of raw.split('/')) {
    if (!part || part === '.') continue
    if (part === '..') {
      parts.pop()
      continue
    }
    parts.push(part)
  }
  return parts.join('/').toLowerCase()
}

function hasExplicitExtension(path: string): boolean {
  return /\.[a-z0-9]+$/i.test(path.split('/').pop() || '')
}

function resolveProjectImport(paths: Set<string>, fromFile: string, specifier: string): string | null {
  const requested = joinProjectPath(dirnameOf(fromFile), specifier)
  if (paths.has(requested)) return requested
  if (hasExplicitExtension(requested)) return null

  for (const ext of RESOLVABLE_EXTENSIONS) {
    const candidate = `${requested}${ext}`
    if (paths.has(candidate)) return candidate
  }
  for (const ext of RESOLVABLE_EXTENSIONS) {
    const candidate = `${requested}/index${ext}`
    if (paths.has(candidate)) return candidate
  }
  return null
}

function collectLocalSpecifiers(content: string): string[] {
  const specs: string[] = []
  const patterns = [
    /\bimport\s+(?:type\s+)?(?:[\s\S]*?\s+from\s+)?['"](\.[^'"]+)['"]/g,
    /\bexport\s+(?:type\s+)?[\s\S]*?\s+from\s+['"](\.[^'"]+)['"]/g,
    /\bimport\s*\(\s*['"](\.[^'"]+)['"]\s*\)/g,
    /\brequire\s*\(\s*['"](\.[^'"]+)['"]\s*\)/g,
  ]
  for (const pattern of patterns) {
    let match: RegExpExecArray | null
    while ((match = pattern.exec(content)) !== null) {
      specs.push(match[1])
    }
  }
  return specs
}

const NODE_BUILTIN_IMPORTS = new Set([
  'assert', 'buffer', 'child_process', 'cluster', 'crypto', 'dns', 'events', 'fs',
  'http', 'https', 'net', 'os', 'path', 'process', 'querystring', 'readline',
  'stream', 'string_decoder', 'timers', 'tls', 'tty', 'url', 'util', 'vm', 'zlib',
])

function packageNameFromImportSpecifier(specifier: string): string | null {
  if (!specifier || specifier.startsWith('.') || specifier.startsWith('/') || specifier.startsWith('#')) return null
  if (specifier.startsWith('node:')) return null
  const parts = specifier.split('/')
  const packageName = specifier.startsWith('@') && parts.length >= 2
    ? `${parts[0]}/${parts[1]}`
    : parts[0]
  if (NODE_BUILTIN_IMPORTS.has(packageName)) return null
  return packageName
}

function collectBarePackageSpecifiers(content: string): string[] {
  const specs: string[] = []
  const patterns = [
    /\bimport\s+(?:type\s+)?(?:[\s\S]*?\s+from\s+)?['"]([^.'"/][^'"]*|@[^'"]+)['"]/g,
    /\bexport\s+(?:type\s+)?[\s\S]*?\s+from\s+['"]([^.'"/][^'"]*|@[^'"]+)['"]/g,
    /\bimport\s*\(\s*['"]([^.'"/][^'"]*|@[^'"]+)['"]\s*\)/g,
    /\brequire\s*\(\s*['"]([^.'"/][^'"]*|@[^'"]+)['"]\s*\)/g,
  ]
  for (const pattern of patterns) {
    let match: RegExpExecArray | null
    while ((match = pattern.exec(content)) !== null) {
      const packageName = packageNameFromImportSpecifier(match[1])
      if (packageName) specs.push(packageName)
    }
  }
  return specs
}

function readManifestDependencyNames(project: CodeProject): Set<string> | null {
  const packageFile = project.files.find((f) => normalizedName(f.name) === 'package.json')
  if (!packageFile) return null
  try {
    const manifest = JSON.parse(packageFile.content) as Record<string, unknown>
    const names = new Set<string>()
    for (const section of ['dependencies', 'devDependencies', 'optionalDependencies', 'peerDependencies'] as const) {
      const deps = manifest[section]
      if (!deps || typeof deps !== 'object' || Array.isArray(deps)) continue
      for (const name of Object.keys(deps as Record<string, unknown>)) names.add(name)
    }
    return names
  } catch {
    return null
  }
}

function missingPackageDependencyIssues(project: CodeProject): CritiqueIssue[] {
  const declared = readManifestDependencyNames(project)
  if (!declared) return []
  const issues: CritiqueIssue[] = []
  const seen = new Set<string>()

  for (const file of project.files) {
    if (!isTsLike(file.language) && !/\.[cm]?[jt]sx?$/i.test(file.name)) continue
    for (const packageName of collectBarePackageSpecifiers(file.content)) {
      if (declared.has(packageName) || seen.has(packageName)) continue
      seen.add(packageName)
      issues.push({
        axis: 'compile',
        severity: 'block',
        message: `${file.name}: dependance npm importee mais absente du package.json (${packageName})`,
        location: { file: file.name },
        suggestion: `Ajouter ${packageName} dans dependencies/devDependencies ou remplacer l import par du code local livre.`,
      })
    }
  }

  return issues
}

function hasTailwindSetup(project: CodeProject): boolean {
  const paths = normalizedProjectPaths(project)
  if (paths.some((p) => /(^|\/)(tailwind\.config\.(?:js|cjs|mjs|ts)|postcss\.config\.(?:js|cjs|mjs|ts))$/.test(p))) {
    return true
  }
  const all = project.files.map((f) => f.content).join('\n')
  if (/cdn\.tailwindcss\.com/i.test(all)) {
    return true
  }
  const packageFile = project.files.find((f) => normalizedName(f.name) === 'package.json')
  if (!packageFile) return false
  try {
    const manifest = JSON.parse(packageFile.content) as {
      dependencies?: Record<string, unknown>
      devDependencies?: Record<string, unknown>
    }
    return Boolean(manifest.dependencies?.tailwindcss || manifest.devDependencies?.tailwindcss)
  } catch {
    return false
  }
}

function extractClassTokens(content: string): string[] {
  const tokens: string[] = []
  const classAttr = /\bclass(?:Name)?\s*=\s*["']([^"']+)["']/g
  let match: RegExpExecArray | null
  while ((match = classAttr.exec(content)) !== null) {
    tokens.push(...match[1].split(/\s+/).filter(Boolean))
  }
  return tokens
}

function isLikelyTailwindUtility(token: string): boolean {
  const normalized = token.replace(/^(?:sm|md|lg|xl|2xl|dark|hover|focus|active|disabled|group-hover|motion-safe|motion-reduce):/g, '')
  return /^(?:container|sr-only|flex|inline-flex|grid|hidden|block|relative|absolute|fixed|sticky|inset-|top-|right-|bottom-|left-|z-\d+|min-h-|max-w-|w-(?:\d|full|screen)|h-(?:\d|full|screen)|p[trblxy]?-\d+|m[trblxy]?-\d+|mx-auto|gap-\d+|space-[xy]-\d+|items-|justify-|content-|rounded(?:-|$)|border(?:-|$)|shadow(?:-|$)|bg-|text-|font-|leading-|tracking-|opacity-|transition|duration-|ease-|overflow-|object-|aspect-|scale-|translate-|rotate-|transform|from-|via-|to-|backdrop-|dark:bg-|dark:text-|dark:border-)/.test(normalized)
}

function linkedLocalAssetsMissing(project: CodeProject, paths: Set<string>): CritiqueIssue[] {
  const issues: CritiqueIssue[] = []
  const linkedFile = project.files.filter((file) => isHtmlLike(file.language) || isCssLike(file.language) || /\.(html?|css|scss)$/i.test(file.name))
  const refPattern = /(?:\b(?:src|href)\s*=\s*["']([^"']+)["']|url\(\s*["']?([^"')]+)["']?\s*\))/gi
  const localAsset = /\.(?:css|m?js|jsx|tsx|png|jpe?g|webp|gif|svg|ico|woff2?|ttf|otf|mp3|wav|mp4|webm|glb|gltf)$/i

  for (const file of linkedFile) {
    let match: RegExpExecArray | null
    while ((match = refPattern.exec(file.content)) !== null) {
      const rawUrl = (match[1] || match[2] || '').trim()
      if (!rawUrl || /^(?:https?:)?\/\//i.test(rawUrl) || /^(?:data:|mailto:|tel:|#)/i.test(rawUrl)) continue
      const cleanUrl = rawUrl.split(/[?#]/)[0]
      if (!localAsset.test(cleanUrl)) continue
      if (!resolveProjectImport(paths, file.name, cleanUrl)) {
        issues.push({
          axis: 'runtime',
          severity: 'error',
          message: `${file.name}: ressource locale referencee mais absente (${rawUrl})`,
          location: { file: file.name },
          suggestion: 'Livrer le fichier reference ou remplacer par un SVG/data URL inline verifie.',
        })
      }
    }
  }
  return issues
}

function projectIntegrityIssues(project: CodeProject, intent: CodeIntent): CritiqueIssue[] {
  const issues: CritiqueIssue[] = []
  const paths = new Set(normalizedProjectPaths(project))

  for (const file of project.files) {
    if (!isTsLike(file.language) && !/\.[cm]?[jt]sx?$/i.test(file.name)) continue
    for (const specifier of collectLocalSpecifiers(file.content)) {
      if (!resolveProjectImport(paths, file.name, specifier)) {
        issues.push({
          axis: 'compile',
          severity: 'block',
          message: `${file.name}: import local introuvable (${specifier})`,
          location: { file: file.name },
          suggestion: `Ajouter le fichier ${specifier} ou corriger le chemin d import.`,
        })
      }
    }
  }

  issues.push(...linkedLocalAssetsMissing(project, paths))
  issues.push(...missingPackageDependencyIssues(project))

  const projectType = intent.projectType || 'unknown'
  const visualProject = projectType === 'static_web'
    || projectType.startsWith('spa_')
    || projectType.startsWith('ssr_')
    || projectType.startsWith('fullstack_')
    || projectType === 'game_web'
  if (visualProject && !hasTailwindSetup(project)) {
    let utilityCount = 0
    const examples = new Set<string>()
    for (const file of project.files) {
      if (!isTsLike(file.language) && !isHtmlLike(file.language) && !/\.(tsx|jsx|html?)$/i.test(file.name)) continue
      for (const token of extractClassTokens(file.content)) {
        if (!isLikelyTailwindUtility(token)) continue
        utilityCount += 1
        if (examples.size < 6) examples.add(token)
      }
    }
    if (utilityCount >= 8) {
      issues.push({
        axis: 'preview',
        severity: 'error',
        message: `Classes Tailwind detectees sans configuration Tailwind (${utilityCount} utilities, ex: ${[...examples].join(', ')})`,
        suggestion: 'Ajouter tailwindcss + config/postcss et @tailwind utilities, ou remplacer par du CSS livre dans le projet.',
      })
    }
  }

  return issues
}

export const projectIntegrityCritic: CriticFn = async (project: CodeProject, intent: CodeIntent): Promise<CritiqueReport> => {
  const issues = projectIntegrityIssues(project, intent)
  const blockers = issues.filter((i) => i.severity === 'block').length
  const errors = issues.filter((i) => i.severity === 'error').length
  const warns = issues.filter((i) => i.severity === 'warn').length
  return buildReport({
    compile: blockers > 0 ? 0 : 1,
    runtime: Math.max(0, 1 - blockers * 0.6 - errors * 0.25),
    preview: Math.max(0, 1 - errors * 0.25 - warns * 0.05),
    fidelity: Math.max(0, 1 - errors * 0.15 - warns * 0.05),
  }, issues)
}

// --- Cyclomatic complexity critic (wraps codeStructuralAnalysis) -----------

/**
 * Critic qui pénalise les fonctions trop complexes (CC > 20). Permet de
 * bloquer une PR sur du code "complexity bomb" qu'un humain ne pourra pas
 * réviser.
 */
export const complexityCritic: CriticFn = async (project: CodeProject, _intent: CodeIntent): Promise<CritiqueReport> => {
  const { analyzeCyclomaticComplexity } = await import('./codeStructuralAnalysis.ts')
  const issues: CritiqueIssue[] = []
  let totalFns = 0
  let badFns = 0
  for (const file of project.files) {
    const fns = analyzeCyclomaticComplexity(file.content, file.language)
    totalFns += fns.length
    for (const fn of fns) {
      if (fn.rating === 'ingérable') {
        badFns += 1
        issues.push({
          axis: 'lint',
          severity: 'block',
          message: `${file.name}: fonction ${fn.name} CC=${fn.cyclomaticComplexity} ingérable`,
          location: { file: file.name, line: fn.startLine },
          suggestion: 'Découper la fonction en sous-fonctions (< 10 branches par fonction).',
        })
      } else if (fn.rating === 'très-complexe') {
        badFns += 1
        issues.push({
          axis: 'lint',
          severity: 'error',
          message: `${file.name}: fonction ${fn.name} CC=${fn.cyclomaticComplexity} très complexe`,
          location: { file: file.name, line: fn.startLine },
          suggestion: 'Visez CC < 20.',
        })
      } else if (fn.rating === 'complexe') {
        issues.push({
          axis: 'lint',
          severity: 'warn',
          message: `${file.name}: fonction ${fn.name} CC=${fn.cyclomaticComplexity} complexe`,
          location: { file: file.name, line: fn.startLine },
          suggestion: 'Envisager un découpage.',
        })
      }
    }
  }
  const ratio = totalFns === 0 ? 0 : badFns / totalFns
  const score = Math.max(0, 1 - ratio)
  return buildReport({ lint: score }, issues)
}

// --- Composite critic ------------------------------------------------------
// Combines the 4 static critics into one report. Useful as a stand-in for
// the "first cheap pass" before paying the LLM critic.

export const compositeStaticCritic: CriticFn = async (project: CodeProject, intent: CodeIntent): Promise<CritiqueReport> => {
  const reports = await Promise.all([
    syntaxCritic(project, intent),
    securityCritic(project, intent),
    structureCritic(project, intent),
    deliverableCompletenessCritic(project, intent),
    projectIntegrityCritic(project, intent),
    complexityCritic(project, intent),
    accessibilityCritic(project, intent),
  ])
  const mergedScores: Partial<Record<CritiqueAxis, number>> = {}
  const allIssues: CritiqueIssue[] = []
  for (const r of reports) {
    for (const key of Object.keys(r.scores) as CritiqueAxis[]) {
      // Take the min across critics that scored the same axis (be strict).
      const prev = mergedScores[key]
      const next = r.scores[key]
      if (prev == null || next < prev) mergedScores[key] = next
    }
    allIssues.push(...r.issues)
  }
  return buildReport(mergedScores, allIssues)
}
