// ---------------------------------------------------------------------------
// codeSystemPromptContracts — generation contracts used by Codeur prompts.
// ---------------------------------------------------------------------------

import type { CodeIntent } from './codeIntent.ts'
import { buildPremiumDesignReferenceBlock as _buildPremiumDesignReferenceBlock } from './codeDesignReference.ts'
import { CODE_REACT_THREE_COMPATIBILITY } from './codeRuntimeDependencies.ts'

export { buildLauncherInstructionBlock } from './codeLauncherPromptContract.ts'
export { buildSubjectLockBlock } from './codeSubjectPromptContract.ts'

// Build quality contract per language family: systems, backend, data, CLI, library, devops, mobile.
function buildNonVisualQualityContract(intent: CodeIntent): string {
  const lines: string[] = [
    '## QUALITE OUTPUT — PROJET NON-VISUEL (REGLE ZERO)',
    '',
    `Type detecte: ${intent.projectType} (${intent.complexity}). Tu es expert dans ce domaine, pas dans le HTML.`,
    'Le code que tu produis DOIT etre celui d un senior dans ce langage / cette stack, PAS un tutoriel debutant.',
    '',
    '### REGLES UNIVERSELLES (tous projets non-visuels)',
    '- Code lisible mais pas naif: nommage semantique (verbes pour fonctions, noms pour types), pas d abreviations cryptiques.',
    '- Gestion d erreur explicite aux frontieres: parse JSON / fichiers / args utilisateur retourne un Result / Option / Either, pas un crash.',
    '- Pas de print debug oublie en production. Si du logging est utile, utilise la lib standard (logging Python, log/slog Go, tracing Rust, java.util.logging Java).',
    '- README.md OBLIGATOIRE avec: description en 2 lignes, install (commande exacte), usage (exemple --help ou flag minimal), license (MIT default).',
    '- Tests si la stack en a une: cargo test pour Rust, go test pour Go, pytest pour Python, npm test pour Node, dotnet test pour C#. AU MOINS un test par fonction publique.',
    '',
  ]

  const family = classifyNonVisualFamily(intent)
  switch (family) {
    case 'systems':
      lines.push('### SYSTEMS (Rust / C / C++ / Zig / Go bas-niveau)')
      lines.push('- Memory safety obligatoire: pas de unsafe sans commentaire SAFETY explicite, pas de raw pointers Rust sans wrapper, pas de strcpy/strcat C, prefere std::string en C++, defer en Go.')
      lines.push('- Error handling: Result<T,E> en Rust avec thiserror/anyhow, errno + return codes en C, std::expected/exceptions structurees en C++, error wrap en Go.')
      lines.push('- Pas de panic / abort sur les hot paths. Gestion gracieuse des cas limites (overflow, division par zero, allocation failure).')
      lines.push('- Build deterministe: lockfile (Cargo.lock, go.sum), version compiler dans la doc.')
      lines.push('- Performance: profile avant d optimiser, mais zero allocation dans les boucles chaudes par defaut.')
      lines.push('- Tests unitaires + au moins UN test d integration qui exerce le binaire complet.')
      break
    case 'backend_api':
      lines.push('### BACKEND / API (Express / FastAPI / Django / Flask / Spring / Gin / Actix / .NET / Rails)')
      lines.push('- Endpoints typed: Pydantic / TypeBox / DTO Java, schemas validates, status codes corrects (200/201/204/400/401/403/404/409/422/500).')
      lines.push('- Authentification quand le prompt user le suggere: JWT signed, sessions secure cookies httpOnly secure sameSite=lax, pas de tokens en localStorage exposes.')
      lines.push('- Gestion d erreur: middleware ou interceptor unique qui transforme exceptions -> reponses JSON {code, message, details}, pas de stack trace expose au client.')
      lines.push('- Logging structure (JSON ou key=value), correlation id propage, pas de print/console.log.')
      lines.push('- Pagination, filtering, sorting sur les endpoints de listing. Limites par defaut explicites (page_size <= 100).')
      lines.push('- CORS configure mais pas wide-open. Rate limiting pour les endpoints sensibles.')
      lines.push('- Tests: au moins UN test integration qui hit chaque endpoint. Mock les services externes.')
      break
    case 'data_ml':
      lines.push('### DATA / ML (pandas / numpy / scikit / pytorch / tensorflow / R)')
      lines.push('- Reproducibilite: seed RNG fixe au top du script (numpy.random.seed, torch.manual_seed, set.seed en R).')
      lines.push('- DataFrames: assertions de shape apres chaque transformation critique. Documenter les colonnes attendues.')
      lines.push('- Charts saves en fichier (PNG/SVG dans ./output/), pas plt.show() qui bloque.')
      lines.push('- Modeles: separer fit / predict, sauver le modele entraine (pickle, joblib, .pt, .h5) avec version.')
      lines.push('- Pas de notebook .ipynb sauf si demande explicitement. Prefere des scripts .py modulaires.')
      lines.push('- Requirements gele (pip freeze > requirements.txt) ou environment.yml pour conda.')
      lines.push('- Validation: train/val/test split explicite, metrics report (accuracy + precision + recall + F1), matrix de confusion plot.')
      break
    case 'cli_script':
      lines.push('### CLI / SCRIPT (Rust clap / Go cobra / Python argparse-typer / Node yargs / Bash)')
      lines.push('- argparse / clap / yargs / cobra: chaque flag documente, --help genere automatiquement, exit codes (0=ok, 1=user error, 2=system error).')
      lines.push('- Idempotence: le meme appel deux fois doit donner le meme resultat. Pas d effet de bord cache.')
      lines.push('- Stderr pour les logs / progress, stdout pour le resultat (JSON parsable si applicable). Permet le pipe.')
      lines.push('- Atomic writes pour les fichiers de sortie: ecris dans un tmp puis rename.')
      lines.push('- Detection signal interrupt (Ctrl+C) avec cleanup.')
      lines.push('- Tests: au moins UN test qui invoque le binaire avec --help et verifie l exit code.')
      break
    case 'library':
      lines.push('### LIBRARY (npm package / pypi package / crate)')
      lines.push('- API publique designee en premier (top-down), implementations privees ensuite.')
      lines.push('- Versioning semver: changes breaking -> major bump. CHANGELOG.md tenu a jour.')
      lines.push('- Doc: README avec installation + usage minimal + lien vers la reference complete (TSDoc / pydoc / rustdoc).')
      lines.push('- Tests pour 100% des points d entree publics. Snapshots si applicable.')
      lines.push('- Build outputs propres: ESM + CJS pour npm, sdist + wheel pour pypi, lib.rs sans cfg(test) leak.')
      lines.push('- Aucun import de node:fs / std::env dans une lib pure (pas de side effects).')
      break
    case 'devops':
      lines.push('### DEVOPS (Docker / Kubernetes / Compose)')
      lines.push('- Dockerfile multistage: stage builder (deps + compile) puis stage runtime (image distroless ou alpine, USER non-root).')
      lines.push('- Pas de secrets dans les layers (RUN echo $TOKEN... INTERDIT). Use BuildKit secrets ou env vars runtime.')
      lines.push('- HEALTHCHECK explicite. EXPOSE le port utilise. CMD / ENTRYPOINT clair.')
      lines.push('- Kubernetes: requests/limits CPU/RAM definis, livenessProbe + readinessProbe, securityContext runAsNonRoot, ServiceAccount minimal.')
      lines.push('- docker-compose.yml: depends_on avec condition: service_healthy quand applicable, volumes nommes.')
      break
    default:
      lines.push('### DEFAULT')
      lines.push('- Pour ce type de projet specifique, applique les conventions de la stack: voir doc officielle pour structure de dossiers et best practices.')
  }

  lines.push('')
  lines.push('### INTERDICTIONS ABSOLUES (output rejete automatiquement)')
  lines.push('- "TODO: implementer plus tard" / "/// NOT IMPLEMENTED" / "raise NotImplementedError" / "panic!(\\"todo\\")".')
  lines.push('- print/console.log de debug oublie. Stack trace expose en production.')
  lines.push('- Hardcoded credentials (API keys, mots de passe en dur).')
  lines.push('- Catch-all silent (try/except: pass / catch (e) {}).')
  lines.push('- Globals mutables sans verrouillage explicite.')
  lines.push('- Single-letter variables hors compteurs de boucle.')

  return lines.join('\n')
}

/**
 * Map a CodeProjectType to one of the non-visual language families used by
 * `buildNonVisualQualityContract`. Returns 'default' for project types that
 * don't map cleanly (e.g. games, mobile — those are visual and don't reach
 * this branch).
 */
type NonVisualFamily = 'systems' | 'backend_api' | 'data_ml' | 'cli_script' | 'library' | 'devops' | 'default'

function classifyNonVisualFamily(intent: CodeIntent): NonVisualFamily {
  const t = intent.projectType
  if (t === 'system_c' || t === 'system_cpp' || t === 'system_rust' || t === 'cli_rust' || t === 'cli_cpp' || t === 'cli_go') return 'systems'
  if (t === 'api_express' || t === 'api_fastapi' || t === 'api_django' || t === 'api_flask' || t === 'api_spring' || t === 'api_gin' || t === 'api_actix' || t === 'api_dotnet') return 'backend_api'
  if (t === 'data_python') return 'data_ml'
  if (t === 'cli_node' || t === 'cli_python' || t === 'script') return 'cli_script'
  if (t === 'library_npm' || t === 'library_pypi' || t === 'library_crate') return 'library'
  if (t === 'devops_docker') return 'devops'
  return 'default'
}

export function isVisualProject(projectType: CodeIntent['projectType']): boolean {
  return projectType === 'static_web'
    || projectType === 'spa_react'
    || projectType === 'spa_vue'
    || projectType === 'spa_angular'
    || projectType === 'spa_svelte'
    || projectType === 'ssr_nextjs'
    || projectType === 'ssr_nuxt'
    || projectType === 'ssr_remix'
    || projectType === 'fullstack_mern'
    || projectType === 'fullstack_nextjs'
    || projectType === 'fullstack_django'
    || projectType === 'fullstack_rails'
    || projectType === 'desktop_electron'
    || projectType === 'desktop_tauri'
    || projectType === 'mobile_rn'
    || projectType === 'mobile_flutter'
    || projectType === 'game_web'
}

export function buildDeliveryContractBlock(intent: CodeIntent): string {
  const expectedFiles = Math.max(1, intent.estimatedFileCount || 1)
  const isCli = intent.projectType.startsWith('cli_')
    || intent.projectType.startsWith('system_')
    || intent.projectType === 'script'
    || intent.projectType === 'data_python'
  const isStatic = intent.projectType === 'static_web' || intent.projectType === 'game_web'
  const isServer = intent.previewType === 'dev_server' || intent.needsDevServer || intent.needsBundling

  const mode = isCli
    ? 'CLI_CONSOLE'
    : isServer
      ? 'UI_DEV_SERVER_OU_TUNNEL'
      : isStatic
        ? 'UI_STATIQUE_OUVRABLE'
        : 'UI_APP'

  const lines = [
    '## CONTRAT LIVRABLE — CLI OU UI OU TUNNEL, PAS DE DEMO ISOLEE',
    `- Mode de livraison retenu: ${mode}. Respecte ce mode jusqu au bout.`,
    `- Nombre de fichiers attendu par l orchestrateur: environ ${expectedFiles} fichiers. Ce nombre sert a eviter les mini-demos; il peut varier seulement si la demande explicite "un seul fichier".`,
    '- Interdit de livrer un fichier independant minimal quand la demande implique une app, un outil client, un dashboard, un studio, une plateforme, un module complet ou un workflow.',
    '- Le livrable doit contenir le point d entree, la configuration, les styles, les composants/services, les donnees d exemple utiles et au moins un chemin de test ou verification locale.',
    '- Toute fonctionnalite promise dans l interface doit avoir une logique reliee: pas de boutons decoratifs, pas de formulaires sans state, pas de vues vides.',
  ]

  if (isCli) {
    lines.push(
      '- Pour CLI: fournis parser d arguments, --help, erreurs lisibles, code de sortie coherent, README usage, et tests ou script de verification.',
      '- Pour CLI: pas d UI web decorative et pas de tunnel inutile. La console est le produit.',
    )
  } else if (isServer) {
    lines.push(
      '- Pour UI avec dev-server/tunnel: package.json + scripts dev/build/preview, config bundler, entree UI, composants, styles, et README de lancement.',
      '- Si tunnel/cloud preview est vise: l app doit ecouter sur host/port configurables et ne pas dependre de chemins absolus locaux.',
    )
  } else {
    lines.push(
      '- Pour UI statique: index.html + style.css + script.js minimum, tous relies entre eux. Le double-clic sur index.html doit afficher l experience complete.',
      '- Pour UI statique: si le brief demande un outil complet, segmente le JS en modules uniquement si tu livres tous les fichiers importes.',
    )
  }

  return lines.join('\n')
}

export function buildExpertEngineeringContractBlock(intent: CodeIntent): string {
  const isComplex = intent.complexity === 'complex' || intent.complexity === 'enterprise'
  const isVisual = isVisualProject(intent.projectType)
  const isSystem = intent.projectType.startsWith('system_')
    || intent.projectType.startsWith('cli_')
    || intent.projectType === 'script'
  const is3D = intent.features.includes('3d') || intent.assetPlan?.wants3D || intent.projectType === 'game_web'

  const lines = [
    '## CONTRAT INGENIEUR EXPERT',
    '- Livre une implementation complete et coherente avec le niveau de la demande. Une UI jolie sans logique reliee est un echec.',
    '- Ne reduis pas le scope en MVP si la demande parle de projet complet, complexe, multipage, simulateur, OS, tunnel, UI, CLI ou rendu premium.',
    '- Chaque fonctionnalite visible doit avoir une implementation mesurable: etat, donnees, validation, erreurs, feedback utilisateur et persistance quand pertinent.',
    '- Ajoute un chemin de verification local: test, smoke script, build command ou instructions README executables.',
    '- Gere les erreurs comme un produit reel: empty states, loading states, permissions/refus, donnees invalides, echec reseau, restart/retry quand utile.',
    '- Securite par defaut: pas de eval/new Function, pas de secrets en dur, pas de HTML utilisateur injecte sans sanitization, validation cote client ET cote serveur quand serveur il y a.',
  ]

  if (isComplex) {
    lines.push(
      '- Projet complexe: decompose en modules, routes/pages ou services reels; evite le fichier monolithe si la stack attend une architecture modulaire.',
      '- Projet complexe: inclus donnees d exemple riches, scenarios principaux, au moins un test/smoke couvrant le workflow central et un README de lancement.',
      '- Projet complexe: si une dependance lourde est choisie, declare-la et configure-la; sinon implemente une alternative stable sans casser le scope fonctionnel.',
    )
  }

  if (isVisual) {
    lines.push(
      '- UI/web/app: design adapte au sujet exact, pas de template generique; navigation claire, responsive mobile/desktop, states hover/focus, accessibilite minimale.',
      '- UI/web/app: les formulaires, filtres, favoris, toggles, recherches, cartes, dashboards et boutons doivent modifier reellement l etat affiche.',
      '- UI/web/app: evite les images cassees; si une image locale ou externe est referencee, elle doit exister ou avoir un fallback visuel propre.',
    )
  }

  if (is3D) {
    lines.push(
      '- 3D/simulateur: pas de simple vitrine. Il faut une boucle render/update, camera controlee, HUD, interactions, et au moins une mecanique ou mesure reactive.',
      '- 3D/simulateur: protege les performances avec resize handler, pixelRatio borne, cleanup listeners/timers, fallback si WebGL ou asset charge mal.',
    )
  }

  if (isSystem) {
    lines.push(
      '- CLI/system/OS: privilegie dry-run, confirmation explicite pour actions destructrices, chemins normalises, erreurs lisibles, logs utiles et rollback si possible.',
      '- CLI/system/OS: ne suppose jamais les privileges admin; detecte plateforme/permissions et degrade proprement quand une operation est interdite.',
    )
  }

  return lines.join('\n')
}

/**
 * Pull premium HTML reference into codeur prompt with optional forced variant (brand_landing for brands).
 */
export function buildDesignReferenceImport(promptHint?: string, forcedVariant?: string): string {
  return _buildPremiumDesignReferenceBlock(promptHint, forcedVariant)
}

export function buildMachineFileContractBlock(intent: CodeIntent): string {
  const lines = [
    '## CONTRAT FICHIERS MACHINE ET DEPENDANCES',
    '- Tous les fichiers `.json` doivent etre du JSON strict parseable par JSON.parse: doubles quotes, aucune virgule finale, aucun commentaire `//` ou `/* */`, aucun markdown fence dans le contenu.',
    '- `package.json`, `tsconfig.json`, `tsconfig.node.json`, `manifest.json` et configs similaires ne doivent contenir QUE leur objet JSON, pas de notes autour.',
    '- Si tu utilises Vite + TypeScript, `tsconfig.json` reste JSON strict meme si TypeScript accepte le JSONC.',
    '- Si tu utilises des classes Tailwind (`bg-`, `text-`, `flex`, `h-screen`, etc.), tu dois declarer et configurer Tailwind dans le projet. Sinon, ecris du CSS reel dans un fichier importe.',
    '- Ne declare jamais une dependance npm avec un nom non valide ou non officiel.',
  ]

  const wantsReact3D =
    intent.frameworks.includes('react')
    && (intent.features.includes('3d') || intent.assetPlan?.wants3D || intent.projectType === 'game_web')

  if (wantsReact3D) {
    lines.push(
      `- React 19 + 3D: utilise la matrice compatible ${CODE_REACT_THREE_COMPATIBILITY}.`,
      '- React 18 + 3D: utilise plutot `@react-three/fiber@^8.18.0` et `@react-three/drei@^9.122.0`.',
      '- Interdit: `react-three-fiber`, `react-three/drei`, `react-three/postprocessing` dans package.json. Ces noms cassent `npm install`.',
      '- Si tu importes `@react-spring/three`, declare aussi `@react-spring/three` dans `dependencies`; sinon n importe pas ce package.',
      '- Les overlays HUD HTML ne vont pas directement comme `<div>` enfant de `<Canvas>`: place-les hors Canvas ou via `<Html>` de drei.',
      '- Pour les refs R3F modifiees dans le code, ecris `useRef<THREE.Mesh | null>(null)` / `Group | null`, jamais `useRef<THREE.Mesh>(null)` si tu assignes a `.current`.',
      '- Si un store Zustand expose un setter appele avec `setX(prev => ...)`, type ce setter pour accepter une fonction et implemente `set((state) => ({ x: typeof value === "function" ? value(state.x) : value }))`.',
      '- Pour une simulation/projet 3D interactif, ne livre jamais une simple vitrine OrbitControls: code les controles demandes, les objectifs, les interactions spatiales et le HUD dynamique.',
      '- Pilotage/WASD/shift/espace = keydown/keyup + etat position/velocity + `useFrame(delta)`. Minimap/radar = positions reelles. Collecte/scan/docking = `distanceTo`, raycaster, collisions ou volumes 3D + mise a jour HUD.',
    )
  }

  return lines.join('\n')
}

/**
 * Hard design contract injected at the top of the codeur system prompt for
 * every web / app / UI project. The user explicitly demanded "designs pousses
 * tout le temps" on every output. This block makes design quality
 * NON-NEGOCIABLE so the LLM can no longer return scolaire HTML.
 */
export function buildDesignContractBlock(intent: CodeIntent): string {
  if (!isVisualProject(intent.projectType)) {
    return buildNonVisualQualityContract(intent)
  }

  // Raise bar to senior product engineer level: oklch palette, 12-col grid, display serif, motion tokens, density rules.
  return [
    '## DESIGN CONTRACT — NIVEAU INGENIEUR PRODUIT SENIOR (REGLE ZERO)',
    '',
    'Tu codes au niveau d un IC senior chez Linear / Vercel / Arc / Stripe / Anthropic / Apple.',
    'Tu N AS PAS le droit de livrer un visuel scolaire. Le test: un designer de Linear qui ouvre la page doit penser "ok, c est pro" en moins de 2 secondes. Si ca ressemble a un site Bootstrap, a un theme WordPress, a un kit Tailwind UI default, a un tutoriel YouTube, c est un ECHEC TOTAL et le pipeline rejette la livraison.',
    '',
    '### 1. SYSTEME DE COULEURS — palette restreinte, oklch, jamais hex flashy',
    '- UN SEUL accent (deux maximum, mais le second sert SEULEMENT en focus state ou dataviz). Le scolaire = "primary blue + secondary green + tertiary purple".',
    '- Couleurs en `oklch()` ou `hsl()` quand c est possible, JAMAIS en `red`/`blue`/`green` nommes. `oklch(0.62 0.22 264)` plutot que `#7c3aed`.',
    '- Neutres: une rampe 11 etapes (50,100,200,300,400,500,600,700,800,900,950) construite avec une seule teinte (ex: zinc-tinted, slate-tinted, warm-gray). PAS du noir #000 ni du blanc #fff purs sur les surfaces.',
    '- Backgrounds: deep neutral (oklch(0.13 0.01 240) ≈ #0a0a0c) OU paper warm (oklch(0.98 0.005 80) ≈ #faf9f7). Eviter le pur #fafafa Bootstrap-ish.',
    '- Surface elevation: 3 paliers max (`bg`, `surface`, `surface-elevated`) avec deltas de luminosite faibles (~3-5%). PAS de cards ombrees Discord 2018.',
    '- Bordures: rgba(255,255,255,0.06) en sombre, rgba(0,0,0,0.07) en clair. JAMAIS `1px solid #ddd`.',
    '- Text: 3 paliers (primary 0.95 / secondary 0.62 / tertiary 0.42). Pas plus.',
    '',
    '### 2. TYPOGRAPHIE — hierarchie editoriale, pas un h1/h2/h3 generique',
    '- Display (hero, citations): SERIF ITALIC quand le ton le permet ("Instrument Serif", "GT Sectra Display", "Cormorant", "Fraunces wonky") OU sans-serif tres tendu ("Geist", "Inter Tight", "Söhne", "PP Neue Montreal"). Italic display = 2026 senior signature. PAS Comic Sans, PAS Roboto par defaut, PAS Times.',
    '- Body: "Inter Variable" / "Geist" / "Söhne" — 14-16px, line-height 1.55-1.65.',
    '- Mono kicker / labels / chiffres precis: "JetBrains Mono" / "Geist Mono" / "IBM Plex Mono". Echelle 11-13px, uppercase, letter-spacing 0.08em.',
    '- Echelle modulaire (ratio ~1.25): 12 / 14 / 16 / 20 / 28 / 40 / 56 / 72 / 96. Pas d echelles fantaisie.',
    '- Tracking: -0.04em sur display 56px+, -0.02em sur 32-40px, normal sur body, +0.08em sur eyebrows uppercase.',
    '- Line-height: 1.0 sur display 72px+, 1.1 sur 40-56px, 1.4-1.5 sur sub-headings, 1.55-1.65 sur body. Mesure ligne 60-70 caracteres max sur prose.',
    '',
    '### 3. LAYOUT — grille editoriale, density assumee',
    '- Grille 12 colonnes avec `grid-template-columns: repeat(12, minmax(0, 1fr))` + gap clamp(16px, 1.4vw, 24px). Les sections importantes utilisent col-span explicite (ex: hero copy span-7, hero visual span-5 + offset 1).',
    '- Container: max-width 1280-1440px, padding lateral clamp(20px, 5vw, 56px).',
    '- Spacing tokens (4, 8, 12, 16, 20, 24, 32, 40, 48, 64, 80, 96, 128). Sections: padding-block clamp(80px, 12vw, 160px). PAS de `margin-top: 10px` arbitraire — utilise `gap` sur le parent.',
    '- Whitespace assumee: titre + sous-titre serres (gap 16-20px), block + block aere (gap 64-96px). Le scolaire = tout au meme spacing.',
    '- Container queries quand le composant doit s adapter a son parent (`@container (min-width: 32rem)`), pas seulement media queries.',
    '',
    '### 4. MOTION — easing tokens, timings serres, scroll-driven',
    '- Easing tokens (declare en CSS variables):',
    '    --ease-out-expo: cubic-bezier(0.16, 1, 0.3, 1)   /* hover, reveal */',
    '    --ease-spring: cubic-bezier(0.32, 0.72, 0, 1)    /* magnetic, drawer */',
    '    --ease-smooth: cubic-bezier(0.4, 0, 0.2, 1)      /* generic */',
    '- Durees: 120-180ms sur micro hover, 240-360ms sur reveal/transition section, 600-800ms sur transitions de page. Tout au-dela = lourd.',
    '- Hover scale: 1.02 max (1.04 sur grosse CTA). Au-dela ca ressemble a Discord 2018.',
    '- Scroll-driven: prefere `animation-timeline: scroll()` ou `animation-timeline: view()` quand supporte (avec fallback IntersectionObserver). Le scrub manuel via scrollY est l ancien monde.',
    '- View Transitions API (`document.startViewTransition`) pour les changements d etat majeurs (filter, route, theme).',
    '- Stagger: delay 60-90ms entre items (pas 200ms). Le scolaire stagger trop lent.',
    '- prefers-reduced-motion: respect strict, pas un afterthought.',
    '',
    '### 5. PROFONDEUR ET MATIERE — mesuree, pas Discord 2018',
    '- Glassmorphism utilise: `backdrop-filter: blur(16-24px) saturate(150-180%)` + `border: 1px solid rgba(255,255,255,0.08)` + `box-shadow: inset 0 1px 0 rgba(255,255,255,0.06)`. Le inset 1px white du haut est la signature Apple/Linear.',
    '- Shadows: composites a 2-3 couches (`0 1px 2px rgba(0,0,0,.08), 0 8px 24px -4px rgba(0,0,0,.12), 0 24px 48px -12px rgba(0,0,0,.16)`). JAMAIS `box-shadow: 0 0 10px black`.',
    '- Mesh gradients: blobs en oklch, blur 120-180px, saturation moderee (0.18-0.24 chroma max). PAS le gradient violet→cyan→ambre du tutoriel Bootstrap.',
    '- Noise overlay (SVG turbulence opacity 0.02-0.035 mix-blend overlay) sur les zones plates pour casser le flat numerique.',
    '- Radius: 4 (chip), 8 (input), 12 (card), 18-22 (section), 999 (pill). Coherent dans tout le doc.',
    '',
    '### 6. ICONOGRAPHIE & DETAILS',
    '- Icones Lucide / Phosphor / Radix Icons en SVG inline (stroke 1.5, currentColor). PAS Font Awesome, PAS emoji a la place d une icone.',
    '- Logos / SVG inline retravailles, pas un emoji.',
    '- Boutons: padding asymmetrique (px=20-24, py=10-12), font 14px medium, gap interne 8px. Primary = surface inversee + shadow inset blanc subtil. PAS le bouton bleu Bootstrap rond avec border-radius 50px.',
    '- Inputs: border-bottom-only OU subtle inset shadow. PAS le `border: 2px solid blue` HTML5 default.',
    '- Cursor follow: subtil (cercle 14px outline, mix-blend difference). Pas une fleche custom mal scalee.',
    '',
    '### 7. ANTI-PATTERNS QUI FONT SCOLAIRE — INTERDITS ABSOLUS',
    '- `margin-top: 10px` en isole (utilise `gap` sur le parent ou des tokens d espacement).',
    '- Couleurs nommees CSS (`color: red/blue/green/orange`).',
    '- Hex flashy par defaut (`#ff0000`, `#0000ff`, `#00ff00`).',
    '- Un bouton avec `border-radius: 50px` ET un drop-shadow scolaire (`0 4px 6px rgba(0,0,0,0.1)`) en meme temps.',
    '- Gradient banal `linear-gradient(135deg, #87ceeb, #c084fc)` (sky → purple) — c est le signe d un dev qui ne sait pas choisir.',
    '- Police par defaut Roboto sans variant, sans tracking, sans hierarchie de poids.',
    '- `font-weight: bold` en seul recours (utilise des poids precis: 400 / 500 / 600 / 700, et alterne avec italic display ou tracking).',
    '- 3 couleurs primary/secondary/tertiary qui se battent pour l attention.',
    '- Cards toutes a la meme taille en grid uniforme (utilise une mosaique inegale, sauf si la donnee impose la regularite).',
    '- `<h1>Bienvenue</h1>`, `<button>Click here</button>`, `<p>Lorem ipsum</p>` literalement.',
    '- Animation 800ms+ sur un hover (lourd, lent, scolaire).',
    '- Box-shadow `0 0 20px rgba(0,255,0,0.5)` neon glow pleins de couleurs (Discord 2018).',
    '- Border-radius mixtes incoherents (`8px` + `50px` + `4px` dans la meme card).',
    '- Hero `background: blue` uni, ou un seul gradient sky-to-pink banal.',
    '- Footer "© 2024" tout court — un footer senior a 3-4 colonnes denses.',
    '',
    '### 8. THREE.JS / WEBGL — JAMAIS un cube qui tourne',
    '- Si tu utilises Three.js, le minimum est: 5+ lights typees, materials PBR (MeshPhysicalMaterial avec clearcoat/iridescence/transmission), PMREMGenerator + RoomEnvironment, EffectComposer + UnrealBloomPass + OutputPass.',
    '- Plus: au moins UN shader custom (fresnel halo, displacement noise, particles GPU). MeshBasicMaterial = banni sauf pour billboards.',
    '- Camera dolly piloté par scroll quand la composition le permet.',
    '- Toujours `clock.getDelta()` (pas `Date.now()`).',
    '',
    '### 9. ACCESSIBILITE + PERF — non-negociable',
    '- Contraste WCAG AA min, AAA sur le body. focus-visible 2px outline accent + offset 2px.',
    '- Semantic HTML strict (`<header>`, `<nav>`, `<main>`, `<section>`, `<article>`, `<footer>`). Aria-labels sur tout bouton sans texte.',
    '- `prefers-reduced-motion: reduce` → animations off.',
    '- Lazy-load images, font-display: swap, preconnect Google Fonts.',
    '',
    '### TEST DE PREMIER COUP D OEIL — REPONDS MENTALEMENT AVANT DE GENERER',
    '1. Si je screenshot la page et la post sur Twitter, est-ce qu un dev senior dit "joli" ou "tutoriel" ? Si "tutoriel", repense.',
    '2. Ma palette utilise UN accent, ou je suis en mode 3 couleurs primary/secondary/tertiary scolaire ? Si 3 couleurs, ramene a 1.',
    '3. Mon display utilise une typo (serif italic OU sans-serif tendu type Geist/Inter Tight) qui differe du body, OU j ai juste mis le body en bold ? Si bold, change pour une vraie hierarchie.',
    '4. J ai un sens du rythme: spacings serres + spacings amples, cards de tailles inegales, ou tout est a 16px de gap uniforme ? Si uniforme, ajoute du contraste.',
    '5. Si j enleve toutes les animations, le layout statique tient-il deja ? (s il tient pas, c est qu il repose sur la sauce. Sinon, l animation est la cerise.)',
    '',
    'Une seule reponse "scolaire" = tu repenses AVANT le code. Pas apres.',
  ].join('\n')
}
