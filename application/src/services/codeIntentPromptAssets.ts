// ---------------------------------------------------------------------------
// Asset and visual quality prompt sections
// Extracted from codeIntent.ts during WS1 modularisation.
// ---------------------------------------------------------------------------

import type { CodeIntent, PromptLanguage } from './codeIntentTypes.ts'

export function appendAssetPromptSections(lines: string[], intent: CodeIntent): void {
  // --- Asset plan & relative path discipline -----------------------------
  const ap = intent.assetPlan

  if (ap?.subject?.canonical) {
    const subj = ap.subject
    const brandNote = subj.source === 'brand' && subj.domain
      ? ` (marque reconnue — domaine: ${subj.domain})`
      : ''
    lines.push(
      '',
      '## FIDELITE AU SUJET — PRIORITE MAXIMALE',
      `- Sujet principal de la demande: **${subj.canonical}**${brandNote}.`,
      '- TOUT le contenu de la page DOIT parler de ce sujet exact. Pas de derive.',
      '- INTERDIT de generer un contenu sur un sujet adjacent ou "theme proche". Ex: si le sujet est Coca-Cola, NE JAMAIS inventer "culinary excellence" ou "pizzas italiennes" — la page doit parler de Coca-Cola et uniquement de Coca-Cola.',
      subj.source === 'brand'
        ? [
            `- C est une marque reelle: respecte son identite visuelle (couleurs officielles, typographie proche, tonalite de communication).`,
            `- Le logo, si tu le representes, doit etre un SVG inline stylise qui RESSEMBLE visuellement a la marque (forme, couleur), pas un logo generique.`,
            `- Les sections doivent parler de produits, valeurs et univers REELS de ${subj.canonical}.`,
          ].join('\n')
        : '- Respecte strictement le sujet meme s il est generique.',
      '- Si tu as peu d informations fiables sur le sujet, reste factuel et sobre plutot que d inventer.',
    )
  }

  if (ap?.language && ap.language !== 'unknown') {
    const labels: Record<PromptLanguage, string> = {
      fr: 'francais', en: 'anglais', es: 'espagnol', de: 'allemand', it: 'italien', pt: 'portugais', unknown: '',
    }
    lines.push(
      '',
      '## LANGUE DE L INTERFACE',
      `- L utilisateur a ecrit sa demande en **${labels[ap.language]}** — TOUS les textes visibles dans la page (titres, sous-titres, boutons, labels, placeholders, nav, footer, alt, aria-label, messages) doivent etre dans cette langue.`,
      '- NE traduis PAS automatiquement en anglais par defaut. Si l utilisateur a ecrit en francais, le site est en francais. Si en espagnol, en espagnol.',
      '- Si l utilisateur a explicitement demande un selecteur de langue ("language switcher", "multilang", "i18n"), alors ET SEULEMENT alors, prepare une UI multilingue avec la langue de depart = celle du prompt.',
      '- Les identifiants de code (variables, classes CSS, noms de fichiers) restent en anglais par convention. Seul le contenu visible suit la langue du prompt.',
    )
  }

  lines.push(
    '',
    '## CHEMINS RELATIFS — OBLIGATOIRE',
    '- TOUTE reference a une ressource locale (image, police, script, style, 3D, audio, video) doit utiliser un chemin RELATIF a la racine du projet.',
    '- Exemples valides: `./assets/hero.jpg`, `images/logo.svg`, `fonts/inter.woff2`, `models/bike.glb`.',
    '- INTERDIT: chemins absolus (`C:\\...`, `/home/...`, `/Users/...`), URLs `file://`, chemins qui font reference a un dossier parent imaginaire (`../../build`, `../some-project/...`).',
    '- Place TOUS les assets dans des dossiers standards: `assets/images/`, `assets/fonts/`, `assets/models/`, `assets/audio/`, `assets/videos/`, `assets/icons/`, `assets/data/`.',
    '- Si un asset n est PAS fourni mais est necessaire (ex: hero image), declare-le dans une note README + prevois un fallback visuel (gradient, SVG inline, placeholder propre).',
    '- Ne code JAMAIS en dur un chemin absolu qui casserait apres un telechargement/deplacement du projet.',
    '',
    '## PAS D IMAGES CASSEES — REGLE DURE',
    '- INTERDIT absolu de generer des balises `<img src="logo.png">` ou `<img src="hero.jpg">` qui pointent vers des fichiers que tu ne livres PAS.',
    '- Si tu n es pas en train d ecrire et fournir le fichier image, tu NE dois PAS reference une source externe ni un fichier inexistant.',
    '- Par defaut, remplace TOUTES les images decoratives (logo, hero, icone, avatar, illustration) par:',
    '  1. du **SVG inline** directement dans le HTML (path stylise du sujet, illustration geometrique coherente avec la palette),',
    '  2. OU un **gradient CSS** travaille (linear-gradient multi-stops, radial-gradient, mesh gradient via blobs blur),',
    '  3. OU un **pattern CSS** (grille de dots, lignes diagonales, noise via filter),',
    '  4. OU un `<img>` en `data:` URL avec un SVG data URL embarque.',
    '- Pour les photos realistes d un sujet concret (velo, iphone, cafe, etc.) qu il est impossible de remplacer par SVG:',
    '  - Genere une illustration SVG stylisee DU sujet (formes geometriques qui evoquent l objet), pas une photo.',
    '  - Explique dans le README section "Assets a fournir" le nom exact et la dimension attendue si l utilisateur veut plus tard une vraie photo.',
    '- INTERDIT d utiliser: via.placeholder.com, placehold.it, picsum.photos, unsplash.com/source, loremflickr, pravatar — ces services peuvent tomber et casser la page.',
    '- Pour un favicon, integre un SVG inline dans <link rel="icon" href="data:image/svg+xml,...">.',
    '- Aucun `<img>` ne doit rester "broken" (cercle avec croix) au chargement de la page. Test mental: je ferme internet et je ouvre index.html → tout doit s afficher impeccable.',
  )

  if (ap?.wantsImages || ap?.wants3D || (ap?.objectMentions.length ?? 0) > 0) {
    lines.push(
      '',
      '## ASSETS DEMANDES PAR L UTILISATEUR',
      ap.objectMentions.length > 0
        ? `- Objets / sujets detectes (probablement a visualiser): ${ap.objectMentions.slice(0, 6).join(', ')}`
        : '',
      ap.wantsImages
        ? '- Images requises: produis-les en SVG inline stylise (illustration travaillee). Si l image EST une photo specifique fournie par l utilisateur, alors et seulement alors utilise `<img src="./assets/images/<nom>.jpg" alt="..." loading="lazy" decoding="async">`.'
        : '',
      ap.wants3D ? '- 3D requis: utilise Three.js (CDN officiel jsdelivr ou unpkg, version figee) avec un <canvas> initialise au chargement, controles orbit, gestion redimensionnement, shadow toggle. Pour les meshes: utilise des primitives (BoxGeometry, SphereGeometry, IcosahedronGeometry, TorusKnotGeometry) plutot que charger un .glb externe qui n existe pas.' : '',
      '- Pour CHAQUE asset externe que tu ne peux pas inline toi-meme, ajoute au README.md une section "### Assets a fournir" listant le nom du fichier attendu, ses dimensions recommandees, et un exemple de source.',
    )
  }

  if (ap?.effectMentions.length) {
    lines.push(
      '',
      '## EFFETS / INTERACTIONS DEMANDES',
      `- Effets detectes: ${ap.effectMentions.slice(0, 8).join(', ')}`,
      '- Implemente-les sans librairie lourde quand c est faisable en CSS/JS pur (transitions, scroll-linked animations via IntersectionObserver, requestAnimationFrame).',
      '- Si une librairie est vraiment necessaire (three.js, gsap, lottie, rive), utilise-la via CDN officiel stable, et declare le script avant la fermeture </body>.',
      '- Les animations doivent respecter `prefers-reduced-motion: reduce` (fallback sobre).',
    )
  }

  if (ap?.paletteHints.length) {
    lines.push(
      '',
      '## PALETTE IMPOSEE PAR L UTILISATEUR',
      `- Couleurs a respecter EXACTEMENT: ${ap.paletteHints.join(', ')}`,
      '- Base toute la theme (primaire, accents, fonds, textes) sur cette palette. N invente pas d autres couleurs.',
    )
  }

  if (ap?.wantsPremiumLook || ap?.wantsResearch) {
    lines.push(
      '',
      '## NIVEAU DE QUALITE VISUELLE ATTENDU — PREMIUM, PAS SCOLAIRE',
      ap.wantsPremiumLook
        ? `- Styles cibles detectes: ${ap.styleHints.slice(0, 6).join(', ')}. Vise un rendu VRAIMENT travaille. Si le resultat ressemble a un tutoriel debutant, c est un echec.`
        : '',
      '',
      '### Baseline obligatoire d une page "professionnelle"',
      'La page DOIT avoir AU MOINS ces sections dans cet ordre (sauf si le prompt indique explicitement autre chose):',
      '1. Navigation fixed/sticky en haut (logo SVG inline + menu + CTA). Backdrop-filter blur 12px, fond semi-transparent.',
      '2. Hero full-height (min-height: 100vh) avec headline imposant (clamp(2.5rem, 6vw, 5rem), font-weight 700-800, line-height 1.05, tracking -0.02em), sous-titre lisible (clamp(1rem, 1.3vw, 1.2rem), line-height 1.6, opacity 0.7), 2 CTAs (primaire + ghost), et un visuel a droite (SVG inline stylise, canvas animated, ou gradient mesh).',
      '3. Section "features" ou "services" avec GRID 3 colonnes (2 colonnes tablet, 1 colonne mobile), chaque carte avec icone SVG inline, titre, 2-3 lignes de description, hover subtil (translateY(-4px), shadow).',
      '4. Section "showcase" / "gallery" / "work" / "products" (selon le sujet) — minimum 4 elements avec images (SVG inline stylises ou gradient mesh), legendes, hover zoom.',
      '5. Section "testimonials" ou "numbers" — chiffres animes au scroll (counter IntersectionObserver), ou citations design.',
      '6. Section CTA finale forte.',
      '7. Footer complet (4 colonnes: about, links, contact, newsletter).',
      '',
      '### Typographie premium (OBLIGATOIRE)',
      '- Heading: "Inter", "Manrope", "Satoshi", "DM Sans", "Space Grotesk" ou "Plus Jakarta Sans" via Google Fonts (preconnect + display=swap).',
      '- Body: meme famille ou pair compatible.',
      '- Echelle typographique: 12 / 14 / 16 / 18 / 20 / 24 / 32 / 40 / 56 / 72 / 96 px avec clamp() pour le responsive.',
      '- Letter-spacing: -0.02em sur les grands titres, 0 sur le corps, +0.1em uppercase eyebrow.',
      '',
      '### Couleurs premium (par defaut si non imposees par l utilisateur)',
      '- Fond principal tres sombre (#0a0a0b, #0d1117, #0e0e11) OU tres clair travaille (#fafafa + #ffffff cards).',
      '- Accent principal vibrant (violet electrique #7c3aed, bleu electrique #3b82f6, vert menthe #22c55e, orange ambre #f59e0b, rose #ec4899).',
      '- Text primary opacity 0.95, secondary 0.7, tertiary 0.5 sur fond sombre.',
      '- Mesh gradient subtil en fond de hero via 2-3 blobs `filter: blur(120px)` positionnes en absolute.',
      '',
      '### Espacement et rythme',
      '- Systeme 4/8/12/16/20/24/32/40/48/64/80/96/128.',
      '- Max-width container: 1200px ou 1280px, centre avec padding lateral responsive (clamp(1rem, 4vw, 3rem)).',
      '- Vertical rhythm: sections 80-128px padding vertical desktop, 48-64px mobile.',
      '',
      '### Micro-interactions et animations',
      '- Transitions fluides 200-350ms avec cubic-bezier(0.22, 1, 0.36, 1) sur hover, focus, state change.',
      '- Scroll reveal sur chaque section via IntersectionObserver (opacity + translateY 30px → 0).',
      '- Parallax leger sur le hero visual via translate3d.',
      '- Hover buttons: scale(1.02), shadow augmentee, couleur qui se decale.',
      '- Respecter `@media (prefers-reduced-motion: reduce)` — desactiver animations.',
      '',
      '### Accessibilite non negociable',
      '- Contraste WCAG AA minimum partout.',
      '- focus-visible avec outline 2px accent + offset 2px.',
      '- Balises semantiques: <header>, <nav>, <main>, <section>, <article>, <footer>.',
      '- Aria-labels sur toutes les icones/boutons sans texte.',
      '- Navigation clavier complete (tab order, skip link).',
      '',
      '### Details qui font la difference',
      '- Bordures subtiles (1px solid rgba(255,255,255,0.06)) plutot que bordures franches.',
      '- Shadows composites: `0 4px 12px rgba(0,0,0,.08), 0 16px 40px rgba(0,0,0,.12)`.',
      '- Rounded corners coherents: 8px petits elements, 16-20px cartes, 28-32px sections CTA.',
      '- Noise overlay leger sur le hero (SVG turbulence opacity 0.02-0.04) pour casser le lisse numerique.',
      '- Jamais de bouton "bleu 4285F4 default browser", jamais de font Arial/Times par defaut, jamais de `border: 1px solid black`.',
      '',
      '### Design tokens OBLIGATOIRES (CSS variables a declarer dans :root)',
      '- Couleurs: `--color-bg-primary, --color-bg-secondary, --color-surface, --color-surface-hover, --color-border, --color-border-strong, --color-accent, --color-accent-hover, --color-text-primary, --color-text-secondary, --color-text-tertiary, --color-success, --color-warning, --color-error`.',
      '- Echelle typographique: `--text-xs (12px), --text-sm (14px), --text-base (16px), --text-lg (18px), --text-xl (20px), --text-2xl (24px), --text-3xl (32px), --text-4xl (40px), --text-5xl (56px), --text-6xl (72px)`. Toutes les valeurs en clamp() responsive.',
      '- Echelle d espacement: `--space-1 (4px), --space-2 (8px), --space-3 (12px), --space-4 (16px), --space-5 (20px), --space-6 (24px), --space-8 (32px), --space-10 (40px), --space-12 (48px), --space-16 (64px), --space-20 (80px), --space-24 (96px), --space-32 (128px)`.',
      '- Radius: `--radius-sm (6px), --radius (10px), --radius-md (14px), --radius-lg (20px), --radius-xl (28px), --radius-pill (999px)`.',
      '- Shadows: `--shadow-sm, --shadow, --shadow-md, --shadow-lg, --shadow-xl, --shadow-glow` (composites multi-layer).',
      '- Transitions: `--ease-spring (cubic-bezier(0.22,1,0.36,1)), --ease-bounce, --ease-smooth, --duration-fast (150ms), --duration (250ms), --duration-slow (400ms)`.',
      '- Z-index: `--z-base, --z-overlay, --z-modal, --z-toast` (numeros tries: 1, 100, 1000, 9999).',
      '',
      '### Mode sombre / clair OBLIGATOIRE',
      '- Toggle visible (icone soleil/lune) qui bascule via `data-theme="light"|"dark"` sur `<html>`, persiste dans localStorage.',
      '- Tous les tokens couleurs ont une valeur differente dans `:root` (defaut sombre) et `[data-theme="light"]`.',
      '- `prefers-color-scheme` detecte au premier load et utilise comme defaut.',
      '- Les `<img>` qui contiennent du fond travaille (ex: SVG inline) doivent avoir leur `<style>` interne adaptable au theme.',
      '',
      '### Composants reutilisables (declarer comme classes CSS reutilisables, pas en inline)',
      '- `.btn`, `.btn-primary`, `.btn-ghost`, `.btn-icon` avec etats hover/focus/active/disabled.',
      '- `.card` avec hover lift et clearfix.',
      '- `.input`, `.input-icon`, etats focus avec ring + glow accent.',
      '- `.badge` (small pill), `.chip` (tag avec close icon).',
      '- `.section` avec padding-block consistent depuis tokens.',
      '- `.container` (max-width + auto margins + padding lateral responsive).',
      '- `.stack-N` (flex column gap variable), `.row-N` (flex row gap variable) — utilitaires.',
      '',
      '### Interdictions (renvoient a du scolaire)',
      '- Titre <h1>Bienvenue</h1> sans style.',
      '- Hero en simple `background: blue` uni sans nuance.',
      '- Boutons rectangulaires sans radius, sans hover.',
      '- Grille en tableau HTML.',
      '- Zero animation / zero transition.',
      '- Images placeholder grises ou emoji a la place du visuel.',
      '',
      '### Effets UX OBLIGATOIRES — le site DOIT bouger / reagir',
      'Tu DOIS implementer AU MOINS 6 des 10 effets suivants. Sans ces effets, le site est juge "amateur".',
      '1. **Scroll reveal par section** via IntersectionObserver: chaque <section> apparait en fondu + translation (opacity 0→1, translateY 32px→0), duree 700ms, easing cubic-bezier(0.22, 1, 0.36, 1), threshold 0.15.',
      '2. **Navigation qui change d apparence au scroll**: au-dela de 40px de scrollY, ajoute une classe `scrolled` qui reduit le padding vertical et rend le fond plus opaque avec backdrop-filter: blur(16px).',
      '3. **Hero visual parallax**: l element visuel principal (image, canvas, blob) se deplace a 40-60% de la vitesse du scroll via translate3d(0, calc(var(--s) * -0.5), 0) ou via requestAnimationFrame.',
      '4. **Hover revele** sur les cards: au survol, l image zoom (scale 1.05), un overlay gradient apparait, un label CTA glisse depuis le bas (translateY(10px → 0) + opacity 0 → 1).',
      '5. **Compteurs animes** sur la section "numbers": quand la section entre dans le viewport, chaque chiffre s anime de 0 a sa valeur cible en 1.5-2 s (via requestAnimationFrame ou animation-delay CSS steps).',
      '6. **Carousel / slider doux** (testimonials, products) — soit auto-scroll infini CSS (keyframes marquee), soit clic-controle avec boutons prev/next qui translate.',
      '7. **Boutons magnetiques** ou micro-shake sur hover (scale 1.02-1.04 + shadow qui s etend, transition cubic-bezier spring).',
      '8. **Curseur custom** (optionnel mais cool) ou blob gradient qui suit la souris via mousemove + translate3d (requestAnimationFrame throttled).',
      '9. **Fade-in stagger** sur les listes: chaque enfant apparait avec un delay incremental de 80-120ms pour creer un effet cascade.',
      '10. **Gradient mesh anime** en arriere-plan du hero: 2-3 blobs absolute avec filter: blur(140px) qui se deplacent lentement via @keyframes translate / scale infinite.',
      '',
      '### Architecture obligatoire AVANT de coder',
      '- Pense la page comme une SEQUENCE NARRATIVE: attirer (hero) → convaincre (features) → demontrer (showcase/numbers) → rassurer (testimonials) → conclure (CTA) → informer (footer).',
      '- Chaque section a une intention claire et un **focal point** visuel fort.',
      '- Le premier fold (au-dessus de la ligne de flottaison) doit pouvoir se suffire a lui-meme pour vendre le sujet.',
      '- N accepte PAS de "page basique en 3 divs". Si le brief est vague, ecris quand meme 7-10 sections riches et coherentes.',
      '- Chaque section doit respirer: `padding-block: clamp(4rem, 10vw, 8rem)`.',
      '- Les animations doivent servir la comprehension, pas decorer gratuitement.',
    )
  }

  if (ap?.researchQueries.length) {
    lines.push(
      '',
      '## RECHERCHE WEB (deja effectuee en amont par l orchestrateur)',
      '- Des recherches web ont ete faites sur les references visuelles attendues.',
      '- Le contenu trouve est integre dans le context bloc "RECHERCHE". Inspire-toi du vocabulaire, palettes et structures qui y apparaissent.',
      `- Requetes effectuees: ${ap.researchQueries.slice(0, 4).join(' | ')}.`,
    )
  }
}
