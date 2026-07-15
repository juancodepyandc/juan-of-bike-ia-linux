import type { CodeIntent } from './codeIntent.ts'
import type { CodeFile } from './codeOrchestrator.ts'
import { isLLMRefusal } from './codeLLMRefusal.ts'

const DOCUMENTATION_EXTENSIONS_EARLY = new Set(['md', 'txt', 'doc', 'docx', 'pdf', 'rtf'])

/**
 * Deterministic playability check for a generated web game. Looks at the actual
 * HTML/JS for the essentials any playable game must have, cross-referenced with
 * what the brief asked for (keyboard vs pointer controls). Returns the missing
 * essentials plus a correction hint the auto-correction pass can act on.
 */
export function checkGamePlayability(
  files: CodeFile[],
  prompt: string,
): { ok: boolean; missing: string[]; hint: string } {
  const code = files
    .filter((f) => /\.(html?|m?[jt]sx?)$/i.test(f.name))
    .map((f) => f.content)
    .join('\n')
  if (!code.trim()) return { ok: true, missing: [], hint: '' }
  const lc = code.toLowerCase()
  const promptL = prompt.toLowerCase()
  const missing: string[] = []

  // 1) Game loop.
  const hasLoop = /requestanimationframe/i.test(code) || /setinterval\s*\(/i.test(code)
  if (!hasLoop) missing.push('boucle de jeu (requestAnimationFrame)')

  // 2) Keyboard controls when the brief asks for them.
  const wantsKeyboard =
    /\b(clavier|fl[eè]ches?|touche|touches|espace|wasd|arrow|keyboard|spacebar|saut|sauter|jump|d[eé]plac)/i.test(
      promptL,
    )
  const hasKeyboard =
    /addeventlistener\s*\(\s*['"]key(down|up|press)['"]/i.test(code) ||
    /on(keydown|keyup|keypress)\s*=/i.test(lc) ||
    /\.onkey(down|up|press)\b/i.test(lc)
  if (wantsKeyboard && !hasKeyboard) missing.push('gestion clavier (addEventListener keydown/keyup)')

  // 3) Pointer/touch controls when the brief asks for them and there is no keyboard.
  const wantsPointer = /\b(souris|clic|cliquer|tap|toucher|tactile|mouse|click|pointer)\b/i.test(promptL)
  const hasPointer =
    /addeventlistener\s*\(\s*['"](click|mousedown|mousemove|mouseup|pointerdown|pointermove|touchstart|touchmove)['"]/i.test(
      code,
    )
  if (wantsPointer && !wantsKeyboard && !hasPointer) missing.push('gestion souris/tactile')

  // 4) A canvas game must actually obtain a drawing context.
  if (/<canvas/i.test(code) && !/getcontext\s*\(/i.test(lc)) missing.push('rendu canvas (getContext)')

  // 5) A self-rescheduling game loop must actually be kicked off, not just
  // defined. Weak models routinely write
  //   function gameLoop(){ … requestAnimationFrame(gameLoop) }
  // but never call it → the canvas stays frozen/blank. Detect the loop function
  // by its self-reschedule, then require it to be invoked at least once more
  // (a direct call OR a second requestAnimationFrame(name) that kicks it off).
  const loopFn = code.match(/function\s+([A-Za-z_$][\w$]*)\s*\([^)]*\)\s*\{[\s\S]*?requestAnimationFrame\s*\(\s*\1\b/)
  if (loopFn) {
    const name = loopFn[1]
    const directCalls = (code.match(new RegExp(`\\b${name}\\s*\\(`, 'g')) || []).length // includes the declaration
    const rafKicks = (code.match(new RegExp(`requestAnimationFrame\\s*\\(\\s*${name}\\b`, 'g')) || []).length
    if (directCalls <= 1 && rafKicks <= 1) missing.push("démarrage de la boucle (la fonction de boucle n'est jamais appelée)")
  }

  // 6) Features explicitly named in the brief must actually appear in the code.
  if (/particule|particle/i.test(promptL) && !/particule|particle/i.test(lc)) missing.push('effets de particules')
  // Named collectibles (coins / pièces / gems …) — a frequent omission: the
  // brief asks for coins to collect but the game ships without any. Require an
  // actual collection STRUCTURE (array or iteration), not just the substring —
  // a leftover `allCoinsCollected` boolean must not count as "coins present".
  const wantsCollectibles = /\b(pi[eè]ces?|coins?|gemmes?|gems?|[eé]toiles?|stars?)\b|\bcollect|\bramass/i.test(promptL)
  const COLLECTIBLE = '(?:coins?|pi[eè]ces?|gemmes?|gems?|[eé]toiles?|stars?|collectibles?|pickups?)'
  const hasCollectibles =
    new RegExp(`\\b${COLLECTIBLE}\\s*[=:]\\s*\\[`, 'i').test(code) ||
    new RegExp(`\\b${COLLECTIBLE}\\s*\\.\\s*(?:forEach|map|filter|length|push|splice|some|every)`, 'i').test(code) ||
    new RegExp(`\\b${COLLECTIBLE}\\s*\\[`, 'i').test(code)
  if (wantsCollectibles && !hasCollectibles) missing.push('objets à collecter (pièces/coins)')

  if (missing.length === 0) return { ok: true, missing: [], hint: '' }

  const hint = [
    'JEU NON JOUABLE — ajoute ces éléments ESSENTIELS sans rien retirer du reste :',
    ...missing.map((m) => `- ${m}`),
    '',
    'Le joueur DOIT pouvoir contrôler le jeu immédiatement avec les contrôles demandés :',
    "- clavier : addEventListener('keydown'/'keyup') qui met à jour l'état du joueur, avec",
    '  preventDefault() sur les flèches et la barre d\'espace pour ne pas scroller la page ;',
    '- une boucle requestAnimationFrame avec delta-time (60 FPS) ;',
    '- un HUD qui affiche en continu le score et les vies ;',
    '- des collisions réellement résolues (repositionner le joueur sur la plateforme, pas un simple flag) ;',
    '- les écrans démarrage / game over / victoire câblés aux vraies conditions de jeu.',
  ].join('\n')
  return { ok: false, missing, hint }
}

/**
 * v89b: conservative bracket-balance scanner for JavaScript. Skips string
 * literals (', ", `) and comments so brackets inside them don't count. A
 * truncated file ("... for (let i = 0; i") ends with unclosed brackets → not
 * balanced. Used to catch JS that was cut off mid-generation (num_predict
 * budget) and would throw "Unexpected end of input" at load, killing the page.
 * Returns true when balanced (or trivially empty) — only a CLEAR imbalance is a
 * signal, to avoid false-positives on otherwise-valid code.
 */
function jsBracketsBalanced(code: string): boolean {
  if (!code.trim()) return true
  let paren = 0
  let brace = 0
  let bracket = 0
  let str: string | null = null
  let lineComment = false
  let blockComment = false
  for (let i = 0; i < code.length; i++) {
    const c = code[i]
    const next = code[i + 1]
    if (lineComment) {
      if (c === '\n') lineComment = false
      continue
    }
    if (blockComment) {
      if (c === '*' && next === '/') {
        blockComment = false
        i++
      }
      continue
    }
    if (str) {
      if (c === '\\') {
        i++
      } else if (c === str) {
        str = null
      }
      continue
    }
    if (c === '/' && next === '/') {
      lineComment = true
      i++
      continue
    }
    if (c === '/' && next === '*') {
      blockComment = true
      i++
      continue
    }
    if (c === '"' || c === "'" || c === '`') {
      str = c
      continue
    }
    if (c === '(') paren++
    else if (c === ')') paren--
    else if (c === '{') brace++
    else if (c === '}') brace--
    else if (c === '[') bracket++
    else if (c === ']') bracket--
    if (paren < 0 || brace < 0 || bracket < 0) return false
  }
  return paren === 0 && brace === 0 && bracket === 0 && !str && !blockComment
}

/**
 * v89b: deterministic integrity gate for a static_web page, mirroring
 * checkGamePlayability. A page can be "substantial" in bytes (>= 4000 chars of
 * HTML+CSS) yet be a NON-FUNCTIONAL SHELL — e.g. <script src="script.js"> with
 * no script.js in the file set, a <canvas> with no getContext anywhere, a
 * <tbody> "populated by JS" with no JS at all. The accept-after-1-pass shortcut
 * used to ship exactly that. This gate detects the hard, unambiguous failures
 * and surfaces them so the correction pass generates the missing logic.
 */
export function checkWebPageIntegrity(
  files: CodeFile[],
  prompt: string,
): { ok: boolean; missing: string[]; hint: string } {
  const htmlFiles = files.filter((f) => /\.html?$/i.test(f.name))
  if (htmlFiles.length === 0) return { ok: true, missing: [], hint: '' }
  const html = htmlFiles.map((f) => f.content).join('\n')

  // Basenames of every file we actually shipped (path-insensitive lookup).
  const shipped = new Set(
    files.map((f) => f.name.replace(/\\/g, '/').split('/').pop()?.toLowerCase()).filter(Boolean) as string[],
  )
  const missing: string[] = []

  // 1) Local <script src>/<link href> that points at a file we DIDN'T ship.
  //    External (http/protocol-relative/data) and in-page anchors are ignored.
  const refRe = /<(?:script\b[^>]*\bsrc|link\b[^>]*\bhref)\s*=\s*["']([^"']+)["']/gi
  let m: RegExpExecArray | null
  const danglingRefs: string[] = []
  while ((m = refRe.exec(html)) !== null) {
    const url = m[1].trim()
    if (/^(?:https?:)?\/\//i.test(url) || url.startsWith('data:') || url.startsWith('#') || url.startsWith('mailto:')) continue
    const base = url.split(/[?#]/)[0].split('/').pop()?.toLowerCase() || ''
    if (!/\.(?:m?js|css)$/i.test(base)) continue
    if (!shipped.has(base)) danglingRefs.push(url)
  }
  for (const r of danglingRefs) missing.push(`fichier local référencé mais absent du projet : ${r}`)

  // All application JS actually present = external .js files + inline <script>
  // bodies, MINUS the Tailwind config object (config, not app logic).
  const externalJs = files.filter((f) => /\.m?js$/i.test(f.name)).map((f) => f.content).join('\n')
  const inlineJs = Array.from(html.matchAll(/<script\b(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/gi))
    .map((x) => x[1])
    .join('\n')
  const appJs = `${externalJs}\n${inlineJs}`.replace(/tailwind\.config\s*=\s*\{[\s\S]*?\}\s*;?/i, '')
  const hasRealJs =
    /\b(?:function\b|=>|addEventListener|querySelector|getElementById|setInterval|setTimeout|requestAnimationFrame|getContext|fetch\s*\(|new\s+\w|class\s+\w)\b/i.test(appJs)

  // 1b) Referenced/shipped JS that is truncated or syntactically broken
  //     (unbalanced brackets) → the page throws at load and nothing runs.
  //     This is the num_predict-truncation failure mode ("...for (let i = 0; i").
  for (const f of files.filter((x) => /\.m?js$/i.test(x.name))) {
    if (!jsBracketsBalanced(f.content)) {
      missing.push(`JavaScript tronqué ou invalide (${f.name} — parenthèses/accolades non équilibrées) : la page plantera au chargement`)
    }
  }
  if (inlineJs.trim() && !jsBracketsBalanced(inlineJs)) {
    missing.push('script inline tronqué ou invalide (parenthèses/accolades non équilibrées)')
  }

  // 2) A <canvas> that never obtains a drawing context → blank chart.
  if (/<canvas/i.test(html) && !/getContext\s*\(/i.test(appJs)) {
    missing.push('canvas sans rendu (aucun getContext) — le(s) graphique(s) restent blancs')
  }

  // 3) A container explicitly waiting for JS injection, with no JS present.
  const hasEmptyDynamicContainer =
    /populated?\s+by\s+js|rempli\s+par\s+js|will\s+be\s+(?:populated|added|generated)|injected?\s+by\s+js/i.test(html) ||
    /<tbody\b[^>]*>\s*(?:<!--[\s\S]*?-->)?\s*<\/tbody>/i.test(html)
  if (hasEmptyDynamicContainer && !hasRealJs) {
    missing.push("contenu dynamique jamais injecté (table/liste vide) — aucune logique JavaScript présente")
  }

  // 4) The brief demands interactivity but the page ships zero application JS.
  const wantsInteractivity =
    /\b(setinterval|temps\s*r[eé]el|live|interactif|tri(?:able|er)?|filtr|recherche|toggle|bascul|convertisseur|calcul|graphique|chart|dashboard|tableau\s+de\s+bord|anim)\b/i.test(
      prompt.toLowerCase(),
    )
  if (wantsInteractivity && !hasRealJs) {
    missing.push("logique JavaScript applicative absente alors que le brief exige de l'interactivité")
  }

  // 5) JS that targets element ids ABSENT from the HTML (and not created by JS)
  //    → getElementById(...) returns null and the feature silently dies (blank
  //    chart, dead control). Real failure: JS read #today-pnl-chart while the
  //    canvas was id="pnl-chart" → initCharts threw → every chart stayed blank.
  //    Only static string-literal ids are checked; concatenated/dynamic ids
  //    (getElementById('row-' + i)) never match and are never flagged.
  const knownIds = new Set<string>()
  for (const m of html.matchAll(/\bid\s*=\s*["']([^"']+)["']/gi)) knownIds.add(m[1])
  // ids the JS itself creates (innerHTML templates, .id =, setAttribute('id',…)).
  for (const m of appJs.matchAll(/\bid\s*=\s*["']([^"'\s]+)["']/gi)) knownIds.add(m[1])
  for (const m of appJs.matchAll(/\.id\s*=\s*["']([^"'\s]+)["']/g)) knownIds.add(m[1])
  for (const m of appJs.matchAll(/setAttribute\(\s*["']id["']\s*,\s*["']([^"'\s]+)["']/g)) knownIds.add(m[1])
  const referencedIds = new Set<string>()
  for (const m of appJs.matchAll(/getElementById\(\s*["']([A-Za-z][\w-]*)["']\s*\)/g)) referencedIds.add(m[1])
  for (const m of appJs.matchAll(/querySelector(?:All)?\(\s*["']#([A-Za-z][\w-]*)["']\s*\)/g)) referencedIds.add(m[1])
  const danglingIds = [...referencedIds].filter((id) => !knownIds.has(id))
  if (danglingIds.length > 0) {
    missing.push(
      `le JavaScript cible des éléments inexistants dans le HTML (#${danglingIds.slice(0, 6).join(', #')}) — corrige les id pour que ces fonctionnalités (graphiques/contrôles) marchent`,
    )
  }

  if (missing.length === 0) return { ok: true, missing: [], hint: '' }

  const hint = [
    'PAGE NON FONCTIONNELLE — la structure HTML est là mais la logique manque. Corrige SANS rien retirer du HTML/CSS existant :',
    ...missing.map((x) => `- ${x}`),
    '',
    "Génère le fichier JavaScript référencé (ex: script.js) — ou intègre le <script> inline dans index.html — avec TOUTE la logique attendue :",
    "- remplir et mettre à jour le DOM (peupler chaque <tbody>/liste vide, pas de placeholder) ;",
    "- chaque <canvas> doit obtenir son contexte (getContext) et être DESSINÉ (graphique + donut) ;",
    "- les mises à jour temps réel via setInterval (cours qui bougent) ;",
    "- tri des colonnes au clic, recherche/filtre, convertisseur de devises, toggle de thème persistant (localStorage), calcul du P&L ;",
    "- toutes les données simulées en JavaScript pur, aucune dépendance réseau.",
    "Le fichier doit RÉELLEMENT exister dans le projet et être chargé par index.html.",
  ].join('\n')
  return { ok: false, missing, hint }
}

export function checkInteractive3DFidelity(
  files: CodeFile[],
  prompt: string,
  intent?: CodeIntent,
): { ok: boolean; missing: string[]; hint: string } {
  const code = files
    .filter((file) => /\.(html?|css|m?[jt]sx?|vue|svelte)$/i.test(file.name))
    .map((file) => file.content)
    .join('\n')
  if (!code.trim()) return { ok: true, missing: [], hint: '' }

  const codeLower = code.toLowerCase()
  const promptLower = prompt.toLowerCase()
  const missing: string[] = []

  const wants3D =
    intent?.features.includes('3d')
    || intent?.assetPlan?.wants3D
    || /\b(3d|three\.?js|r3f|webgl|space|spaceship|vaisseau|station spatiale|asteroid|planet|orbital|cockpit|simulateur|simulator)\b/i.test(promptLower)
  const has3D =
    /@react-three\/fiber|@react-three\/drei|<Canvas\b|new\s+THREE\.|WebGLRenderer|three\/examples/i.test(code)

  if (!wants3D && !has3D) return { ok: true, missing: [], hint: '' }

  const wantsKeyboard =
    /\b(wasd|clavier|keyboard|key(?:down|up)|touches?|fleches?|arrows?|shift|boost|espace|space|pilotage|piloter|fly|voler|thrust|propulsion)\b/i.test(promptLower)
  const hasKeyboard =
    /\baddEventListener\s*\(\s*['"]key(?:down|up|press)['"]|onKeyDown|onKeyUp|KeyboardControls|useKeyboardControls|\.onkey(?:down|up|press)\b/i.test(code)
  const hasFrameMovement =
    /\b(useFrame|requestAnimationFrame|setInterval)\b/i.test(code)
    && /\b(position\.(?:x|y|z|set)|camera\.position|velocity|speed|thrust|boost|acceleration|delta)\b/i.test(code)
  if (wantsKeyboard && (!hasKeyboard || !hasFrameMovement)) {
    missing.push('pilotage clavier/WASD relie a un mouvement 3D par frame')
  }

  const wantsMinimap = /\b(minimap|mini-map|radar|scanner map|carte tactique)\b/i.test(promptLower)
  const radarLooksRandom =
    /\bradar[\s\S]{0,900}\bMath\.random\s*\(/i.test(code)
    || /\bblip[\s\S]{0,400}\bMath\.random\s*\(/i.test(code)
  const hasMinimap =
    /\b(minimap|mini-map|radar|blip|scanline|tactical-map|tacticalMap)\b/i.test(code)
    && /<svg\b|<canvas\b|\.map\s*\(|position/i.test(code)
  if (wantsMinimap && (!hasMinimap || radarLooksRandom)) {
    missing.push('minimap/radar avec positions ou blips reels, pas des points aleatoires')
  }

  const wantsWorldInteractions =
    /\b(collect|collecter|resource|ressource|resources|minerai|mineral|minerals|dock|docking|scanner?|scan|mission|objectif|objective)\b/i.test(promptLower)
  const hasSpatialCheck =
    /\b(distanceTo|raycaster|intersect|intersectsSphere|collision|collid|Math\.hypot|Vector3|Box3|Sphere)\b/i.test(code)
  const hasDomainAction =
    /\b(collect|resource|ressource|minerai|mineral|dock|docking|scan|scanner|mission|objective|cargo|inventory)\b/i.test(code)
  if (wantsWorldInteractions && (!hasSpatialCheck || !hasDomainAction)) {
    missing.push('collecte/scan/docking relies a des tests spatiaux, pas seulement a du texte HUD')
  }

  const wantsDynamicHud =
    /\b(hud|energy|energie|shield|fuel|minerals|resources|mission|score|cargo|inventory)\b/i.test(promptLower)
    || wantsWorldInteractions
  const hasDynamicHud =
    /\bset(?:Energy|Fuel|Shield|Minerals|Resources|Score|Mission|Cargo|Inventory)\s*\(|useReducer\s*\(|dispatch\s*\(/.test(code)
  if (wantsDynamicHud && wantsWorldInteractions && !hasDynamicHud) {
    missing.push('HUD dynamique mis a jour par les interactions')
  }

  if (missing.length === 0) return { ok: true, missing: [], hint: '' }

  return {
    ok: false,
    missing,
    hint: [
      'FIDELITE 3D INTERACTIVE INSUFFISANTE - la scene compile peut-etre, mais elle ne realise pas le brief.',
      ...missing.map((item) => `- ${item}`),
      '',
      'Correction attendue:',
      "- ajouter un etat de vaisseau/joueur (position, velocity, fuel/energy, cargo) pilote par keydown/keyup et useFrame(delta) ;",
      '- afficher une minimap/radar derivee des positions reelles des objets si le brief la demande ;',
      '- implementer scan/collect/docking avec distanceTo, raycaster, collision ou volumes 3D ;',
      '- connecter ces interactions au HUD et aux objectifs de mission ;',
      '- garder le rendu React Three Fiber propre, avec HUD HTML hors Canvas ou via Html de drei.',
    ].join('\n'),
  }
}

// ---------------------------------------------------------------------------
// LLM Refusal Detection — catches when model refuses instead of generating code
// ---------------------------------------------------------------------------

/**
 * Computes a content quality score independent of sandbox results.
 * Penalizes: refusals, too-short files, placeholder content, missing structure.
 */
export function computeContentQualityScore(files: CodeFile[], intent: CodeIntent): number {
  if (files.length === 0) return 0

  // Check for refusal in any file
  const refusalFile = files.find((f) => isLLMRefusal(f.content))
  if (refusalFile) return 0

  // Check for generic fallback files (reponse.txt)
  const allGeneric = files.every((f) => /^(reponse|bloc-\d+)\.(txt|text)$/i.test(f.name))
  if (allGeneric) return 5

  // Check for actual code files
  const codeFiles = files.filter((f) => {
    const ext = f.name.split('.').pop()?.toLowerCase() || ''
    return !DOCUMENTATION_EXTENSIONS_EARLY.has(ext)
  })
  if (codeFiles.length === 0) return 10

  // Average content length check
  const avgLen = codeFiles.reduce((sum, f) => sum + f.content.length, 0) / codeFiles.length
  if (avgLen < 50) return 20

  // Basic structure check for web projects
  if (intent.projectType === 'static_web' || intent.projectType === 'game_web') {
    const hasHtml = files.some((f) => /\.html?$/i.test(f.name))
    if (!hasHtml) return 40
  }

  // Design polish gate: pour les projets visibles (web/UI), penaliser quand le
  // CSS+HTML produit ne respecte pas le design contract (pas de variables CSS,
  // pas de gradients, pas de transitions, pas de Google Fonts premium, pas
  // d animations). Le user a explicitement dit "designs pousses tout le temps"
  // donc une UI scolaire = score plafonne a 60 = trigger correction loop.
  if (isVisualProjectType(intent.projectType)) {
    const designScore = computeDesignPolishScore(files)
    if (designScore < 50) return 55
    if (designScore < 70) return 75
  }

  return 100 // Content looks structurally valid
}

export function isVisualProjectType(type: string): boolean {
  return type === 'static_web'
    || type === 'spa_react'
    || type === 'spa_vue'
    || type === 'spa_angular'
    || type === 'spa_svelte'
    || type === 'ssr_nextjs'
    || type === 'ssr_nuxt'
    || type === 'ssr_remix'
    || type === 'fullstack_mern'
    || type === 'fullstack_nextjs'
    || type === 'fullstack_django'
    || type === 'fullstack_rails'
    || type === 'desktop_electron'
    || type === 'desktop_tauri'
    || type === 'mobile_rn'
    || type === 'mobile_flutter'
    || type === 'game_web'
}

/**
 * Score 0-100 of how "premium" the generated visual code looks. Pure
 * heuristic — checks for the design tokens / patterns the design contract
 * demands. Used to gate the auto-correction loop: a < 70 score triggers
 * a regeneration with explicit "ce que tu as fait est trop scolaire" hint.
 */
function computeDesignPolishScore(files: CodeFile[]): number {
  return computeDesignPolishReport(files).score
}

/**
 * v66: returns BOTH the numerical score AND the list of premium signals
 * that the LLM did not include. Used by the correction loop to send a
 * targeted retry instruction ("ajoute @keyframes + backdrop-filter +
 * clamp()") instead of a vague "fais un design plus pousse".
 */
export type DesignPolishReport = {
  score: number
  missing: string[]
  penalties: string[]
}

export function computeDesignPolishReportPublic(files: CodeFile[]): DesignPolishReport {
  return computeDesignPolishReport(files)
}

export function computeDesignPolishReport(files: CodeFile[]): DesignPolishReport {
  const visualBlob = files
    .filter((f) => /\.(html?|css|s?css|less|tsx?|jsx?|vue|svelte|astro)$/i.test(f.name)) // v85d : +astro
    .map((f) => f.content)
    .join('\n')
    .toLowerCase()

  if (visualBlob.length < 200) {
    return {
      score: 30,
      missing: ['contenu visuel insuffisant — moins de 200 caracteres de CSS/HTML detectes'],
      penalties: [],
    }
  }

  let score = 0
  const missing: string[] = []
  // Premium signals (label, regex, points)
  const checks: Array<{ label: string; pattern: RegExp; points: number }> = [
    { label: 'CSS variables / design tokens (--color-*, --space-*, etc.)', pattern: /--[a-z-]+:\s*/i, points: 12 },
    { label: 'police premium Google Fonts (Inter / Manrope / Satoshi / DM Sans / Space Grotesk / Plus Jakarta)', pattern: /inter|manrope|satoshi|dm sans|space grotesk|plus jakarta|bricolage|bangers/i, points: 10 },
    { label: 'gradients (linear-gradient / radial-gradient / conic-gradient)', pattern: /(linear|radial|conic)-gradient/i, points: 12 },
    { label: 'transitions explicites (transition: ... 250ms cubic-bezier)', pattern: /transition:\s*[^;]+\d+ms/i, points: 8 },
    { label: '@keyframes (animations CSS)', pattern: /@keyframes\s+\w+/i, points: 10 },
    { label: 'backdrop-filter blur (glassmorphism)', pattern: /backdrop-filter\s*:\s*blur/i, points: 10 },
    { label: 'clamp() pour les tailles responsive', pattern: /clamp\s*\(/i, points: 8 },
    { label: 'box-shadow multi-layer composite', pattern: /box-shadow\s*:[^;]*,[^;]*\d/i, points: 8 },
    { label: 'utilisation de var(--*) (variables CSS appliquees)', pattern: /var\(--[a-z]/i, points: 6 },
    { label: 'layout moderne grid ou flex', pattern: /display\s*:\s*(grid|flex)/i, points: 6 },
    { label: 'hover states (:hover {)', pattern: /:hover\s*\{/i, points: 5 },
  ]

  for (const { label, pattern, points } of checks) {
    if (pattern.test(visualBlob)) {
      score += points
    } else {
      missing.push(`${label} (${points} pts manquants)`)
    }
  }

  // Palette richness bonus: count distinct hex colors
  const hexes = new Set((visualBlob.match(/#[0-9a-f]{6}/g) || []))
  if (hexes.size >= 5) score += 5
  else if (hexes.size >= 3) score += 3
  else missing.push(`palette riche (${hexes.size} couleurs hex distinctes seulement, vise 5+)`)

  // Penalties: scolaire markers
  const penalties: string[] = []
  if (/font-family\s*:\s*["']?(arial|times new roman|sans-serif)\s*[;,"']/i.test(visualBlob)) {
    score -= 15
    penalties.push('police par defaut (Arial / Times / sans-serif) — utilise une Google Fonts premium')
  }
  if (/<table[^>]*>\s*<tr/i.test(visualBlob) && !/role="grid"/i.test(visualBlob)) {
    score -= 10
    penalties.push('layout en <table> — utilise CSS grid ou flexbox')
  }
  if (/(background|color)\s*:\s*(blue|red|green|yellow|black|white)\s*;/i.test(visualBlob)) {
    score -= 5
    penalties.push('couleur basique (blue/red/green) — utilise un hex code premium ou une variable CSS')
  }
  if (/<button[^>]*>(?:[^<]*?)<\/button>/.test(visualBlob)
    && !/button\s*\{[\s\S]*?(background|border-radius|transition)/i.test(visualBlob)) {
    score -= 8
    penalties.push('bouton sans style (pas de background, border-radius, ou transition) — restyle-le')
  }

  return {
    score: Math.max(0, Math.min(100, score)),
    missing,
    penalties,
  }
}

/**
 * v66: build a targeted retry prompt that tells the LLM exactly what was
 * missing in the previous output. Used when computeDesignPolishReport
 * reports a score < 70 — the orchestrator can re-stream with this added
 * to the user prompt to push the LLM in the right direction.
 */
export function buildDesignRetryHint(report: DesignPolishReport): string {
  const lines: string[] = [
    '═══════════════════════════════════════════════════════════',
    'AUDIT DESIGN — ton output precedent est ENCORE TROP SCOLAIRE',
    `Score: ${report.score}/100 (seuil minimum: 70)`,
    '═══════════════════════════════════════════════════════════',
    '',
  ]
  if (report.missing.length > 0) {
    lines.push('Ce que tu as OUBLIE (a ajouter imperativement):')
    for (const item of report.missing.slice(0, 8)) {
      lines.push(`  ✗ ${item}`)
    }
    lines.push('')
  }
  if (report.penalties.length > 0) {
    lines.push('Ce que tu as MAL FAIT (a corriger):')
    for (const item of report.penalties) {
      lines.push(`  ⚠ ${item}`)
    }
    lines.push('')
  }
  lines.push(
    'Refais le projet COMPLET avec TOUS ces points corriges.',
    'INTERDICTION absolue de relivrer du HTML qui ressemblerait a un tutoriel debutant.',
    '═══════════════════════════════════════════════════════════',
  )
  return lines.join('\n')
}
