import { isHtmlLike, isPyLike, isTsLike, type StaticRule } from './codeStaticCriticShared.ts'


// --- 2. Security critic ----------------------------------------------------
// Pattern-matching on well-known anti-patterns. Source : OWASP Top 10 +
// Cyber lab du module cyber (cryptoVulnerabilities).

export const SECURITY_RULES: StaticRule[] = [
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
