// ---------------------------------------------------------------------------
// codeDesignDirectiveBlocks — static premium design directive blocks.
// Extracted from codeDesignDirectives so the public facade keeps one job:
// detect the archetype and compose the final block.
// ---------------------------------------------------------------------------

import type { CodeIntent } from './codeIntent'
import type { DesignArchetype } from './codeDesignDirectives.ts'

// ---------------------------------------------------------------------------
// Inspirations and CDN library hints — surfaced to the model so it knows what
// world-class output looks like and which libraries to wire in.
// ---------------------------------------------------------------------------

const CDN_LIBS = {
  three: 'https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js',
  threeOrbit: 'https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/controls/OrbitControls.js',
  threeGLTF: 'https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/loaders/GLTFLoader.js',
  threePostproc: 'https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/postprocessing/EffectComposer.js',
  gsap: 'https://cdn.jsdelivr.net/npm/gsap@3.12.5/dist/gsap.min.js',
  scrollTrigger: 'https://cdn.jsdelivr.net/npm/gsap@3.12.5/dist/ScrollTrigger.min.js',
  lenis: 'https://cdn.jsdelivr.net/npm/@studio-freight/lenis@1.0.42/dist/lenis.min.js',
  lottie: 'https://cdn.jsdelivr.net/npm/lottie-web@5.12.2/build/player/lottie.min.js',
  splitText: 'https://cdn.jsdelivr.net/npm/split-type@0.3.4/umd/index.min.js',
  d3: 'https://cdn.jsdelivr.net/npm/d3@7.8.5/dist/d3.min.js',
  chartjs: 'https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js',
  motionone: 'https://cdn.jsdelivr.net/npm/motion@10.18.0/dist/motion.min.js',
} as const

// ---------------------------------------------------------------------------
// Common premium baseline — applied on top of every visual archetype.
// ---------------------------------------------------------------------------

export function buildCommonPremiumBaseline(): string[] {
  // v82m7 — barre relevee au niveau ingenieur senior (Linear/Vercel/Arc/Stripe/Anthropic).
  // Avant: clamp() + accent vibrant + 7 micro-interactions = scolaire.
  // Apres: oklch palette restreinte, Instrument Serif italic display, motion tokens
  // explicites (cubic-bezier(0.32,0.72,0,1) spring), grille 12-col,
  // anti-patterns concrets, density rules, scroll-driven natif.
  return [
    '## NIVEAU INGENIEUR SENIOR — STANDARD AURORA v82m7 (toujours actif)',
    '',
    'Tu codes au niveau d un IC senior chez Linear / Vercel / Arc / Stripe / Anthropic / Apple. Brief court ne signifie pas rendu pauvre. Tutorial-ish = ECHEC peu importe le brief.',
    '',
    '### Type system editorial (NON NEGOCIABLE)',
    '- Display (hero, citations): "Instrument Serif" italic OU "Geist" / "Inter Tight" tres tendu. PAS Roboto, PAS Times defaut.',
    '- Body: "Inter Variable" / "Geist" 14-16px line-height 1.55-1.65, font-feature-settings "ss01" "cv11".',
    '- Mono kicker / labels / chiffres: "JetBrains Mono" / "Geist Mono" 11-13px uppercase letter-spacing 0.08em.',
    '- Echelle modulaire 1.25: 12 / 14 / 16 / 20 / 28 / 40 / 56 / 72 / 96.',
    '- Tracking: -0.04em sur display 56px+, -0.02em sur 32-40px, +0.08em sur eyebrows.',
    '- Line-height: 1.0 sur 72px+, 1.55-1.65 sur body. Mesure ligne 60-70 caracteres max.',
    '',
    '### Color system — palette restreinte oklch',
    '- UN SEUL accent (un 2e seulement pour focus state ou dataviz). 3 couleurs primary/secondary/tertiary = scolaire.',
    '- Couleurs en oklch() ou hsl(). PAS de red/blue/green nommes, PAS de #ff0000/#0000ff par defaut.',
    '- Neutres: rampe 11 etapes warm-tinted (slate / zinc / stone). Backgrounds oklch(0.13 0.012 252) sombre OU oklch(0.985 0.005 80) paper warm.',
    '- Surface elevation: 3 paliers max avec deltas 3-5%. Pas de cards Discord 2018.',
    '- Bordures: rgba subtiles 0.06-0.08. Text 0.95 / 0.62 / 0.42 (3 paliers, jamais plus).',
    '',
    '### Layout — grille editoriale density assumee',
    '- Grille 12-col explicite avec col-span asymetriques (hero copy span-7 / visual span-5). Pas auto-fit uniforme partout.',
    '- Container queries (@container) en complement des media queries.',
    '- Spacing tokens 4-base (4/8/12/16/20/24/32/40/48/64/80/96/128). PAS margin-top: 10px arbitraire — gap sur le parent.',
    '- Sections padding-block clamp(80px, 12vw, 160px). Whitespace alterne: titre+sub serres / blocs aeres.',
    '- Mosaique inegale obligatoire sur les listes (large/medium/small mix), pas grid auto-fit uniforme.',
    '',
    '### Motion — easing tokens explicites',
    '- Tokens CSS variables:',
    '    --ease-out-expo: cubic-bezier(0.16, 1, 0.3, 1)   /* hover / reveal */',
    '    --ease-spring: cubic-bezier(0.32, 0.72, 0, 1)    /* magnetic / drawer */',
    '    --ease-smooth: cubic-bezier(0.4, 0, 0.2, 1)',
    '- Durees: 120-180ms sur micro hover, 240-360ms sur reveal section, 600-800ms transitions de page.',
    '- Hover scale 1.02 max (1.04 sur grosse CTA). Magnetic max 6-8px. Au-dela = lourd.',
    '- Scroll-driven: @supports (animation-timeline: view()) + animation-range: entry 0% entry 60%. Fallback IntersectionObserver.',
    '- View Transitions API (document.startViewTransition) sur swap dark/light, route, filter.',
    '- Stagger 60-90ms entre items (pas 200ms scolaire).',
    '',
    '### Profondeur et matiere — mesuree, pas Discord 2018',
    '- Glass: backdrop-filter blur(16-24px) saturate(150-180%) + inset 0 1px 0 rgba(255,255,255,0.06) signature Apple/Linear.',
    '- Shadows composites 2-3 couches, jamais flat 0 0 10px black.',
    '- Mesh gradients oklch chroma 0.18-0.24 max (jamais le violet→cyan→ambre Bootstrap).',
    '- Noise overlay (SVG turbulence opacity 0.02-0.035 mix-blend overlay).',
    '- Radius: 4 chip / 8 input / 12 card / 18-22 section / 999 pill. Coherent.',
    '',
    '### Iconographie & details',
    '- Lucide / Phosphor / Radix Icons stroke 1.5 currentColor. PAS Font Awesome, PAS emoji a la place.',
    '- Boutons padding asymmetrique (px=18-24, py=10-12), font 13-14px medium, gap interne 8px.',
    '- Inputs: border-bottom-only OU subtle inset shadow. Pas border 2px solid blue HTML5.',
    '- Cursor follow subtil (14px outline mix-blend difference). Pas fleche custom mal scalee.',
    '',
    '### Anti-patterns INTERDITS (font scolaire)',
    '- margin-top: 10px isole (utilise gap sur parent).',
    '- Couleurs nommees CSS (red/blue/green/orange).',
    '- Hex flashy par defaut (#ff0000, #0000ff).',
    '- Bouton border-radius 50px ET shadow scolaire (0 4px 6px rgba(0,0,0,0.1)) ensemble.',
    '- Gradient banal sky-to-purple (#87ceeb → #c084fc).',
    '- font-weight: bold seul sans hierarchie de poids.',
    '- 3 couleurs primary/secondary/tertiary qui se battent.',
    '- Cards toutes meme taille en grid uniforme.',
    '- <h1>Bienvenue</h1>, <button>Click here</button>, <p>Lorem ipsum</p>.',
    '- Animation 800ms+ sur un hover (lourd).',
    '- box-shadow 0 0 20px rgba(0,255,0,0.5) neon multi-couleurs (Discord 2018).',
    '- Border-radius mixtes incoherents.',
    '- Hero `background: blue` uni.',
    '- Footer "© 2024" tout court.',
    '',
    '### Three.js — JAMAIS un cube qui tourne',
    '- 5+ lights typees, materials PBR (MeshPhysicalMaterial clearcoat/iridescence/transmission), PMREMGenerator + RoomEnvironment.',
    '- EffectComposer + UnrealBloomPass + OutputPass. composer.render() au lieu de renderer.render().',
    '- Au moins UN shader custom (fresnel halo, displacement noise, particles GPU).',
    '- Camera dolly piloté par scroll quand la composition le permet.',
    '- clock.getDelta() (pas Date.now()).',
    '',
    '### Accessibilite + perf',
    '- WCAG AA min, AAA sur body. focus-visible 2px outline + offset 2px.',
    '- Semantic HTML strict. Aria-labels sur boutons sans texte.',
    '- prefers-reduced-motion: animations off strict.',
    '- font-display: swap, preconnect Google Fonts, lazy-load images.',
    '',
    '### Test premier coup d oeil — mental check AVANT generation',
    '1. Screenshot post sur Twitter: "joli" ou "tutoriel" ? Si tutoriel, repense.',
    '2. UN accent oklch ou 3 couleurs scolaires ? Si 3, ramene a 1.',
    '3. Display utilise serif italic OU sans tendu different du body ? Si juste bold, change.',
    '4. Rythme: spacings serres + amples, mosaique de tailles ? Si tout uniforme, ajoute du contraste.',
    '5. Layout statique tient sans animation ? Si non, l animation cache un layout faible.',
  ]
}

// ---------------------------------------------------------------------------
// Archetype-specific blocks
// ---------------------------------------------------------------------------

function appleProductBlock(intent: CodeIntent): string[] {
  const subject = intent.assetPlan?.subject?.canonical || intent.assetPlan?.objectMentions?.[0] || 'le produit'
  return [
    '## ARCHETYPE: APPLE PRODUCT PAGE — page produit narrative et anatomique',
    '',
    `Le sujet principal est ${subject}. Tu produis une page qui rappelle apple.com/airpods, apple.com/iphone-15-pro, ou linear.app — froide, precise, hypnotique, narrative.`,
    '',
    '### Sections obligatoires (ordre imperatif)',
    '1. **Nav fixed/sticky** transparente -> opaque au scroll, blur backdrop, logo SVG inline + menu central + CTA a droite.',
    '2. **Hero cinematique full-height** (min-height: 100vh): titre majeur clamp(3rem, 9vw, 8rem) tres tracking serre (-0.04em), sous-titre court, et VISUEL CENTRAL EN GRAND. Le visuel doit etre soit un canvas/scene 3D, soit une SVG inline anatomiquement detaillee, soit un mesh gradient + ombre projetee tres travaillee. Eviter une simple photo plate.',
    '3. **Section "Compose / Anatomie / Inside"** EXPLODED VIEW. Affiche le produit avec ses composants annotes par des HOTSPOTS cliquables. Chaque hotspot revele une fiche flottante avec un descriptif (drivers, capteurs, materiaux, proc, batterie, etc.). Sur scroll, les pieces s ECARTENT lentement (translate3d sur chaque .part) pour montrer la decomposition.',
    '4. **Section "Materials / Finitions"** — galerie de matieres avec hover qui zoom et change l ambiance lumineuse autour (filter brightness/contrast).',
    '5. **Section "Specs"** — tableau comparatif premium avec colonnes alignees, valeurs en gros chiffre + unite small caps, separateurs subtils.',
    '6. **Section "Performance"** — chiffres animes (compteurs IntersectionObserver) + barres de progression, ou diagramme SVG anime au scroll.',
    '7. **Section "In motion"** — galerie ou marquee infinie de scenarios d usage. Si la stack le permet (game_web ou three.js inline), ajouter une mini scene 3D rotative scroll-driven.',
    '8. **Section "Compare"** — image-comparison slider entre 2 etats (avant/apres, surface mate/brillante, mode jour/nuit, etc.).',
    '9. **Section "Testimonials / Awards"** — citations design.',
    '10. **CTA final** (acheter, configurer, decouvrir) en pleine largeur, gradient.',
    '11. **Footer** complet 4 colonnes.',
    '',
    '### Effets cinematiques OBLIGATOIRES (mecaniques d Apple / Linear)',
    '- **Scroll scrub** sur le visuel hero: la rotation/translation du produit suit la position de scroll (via IntersectionObserver + scrollY ou via GSAP ScrollTrigger).',
    '- **Hotspots animes**: chaque hotspot a un point + cercle pulsant (@keyframes ping radial) + label flottant qui apparait au hover/click avec un slide doux.',
    '- **Decoupe/exploded animation**: les pieces se separent au scroll (chaque .part a un translate3d different relie au scroll progress de la section). Implementation simple: `IntersectionObserver` + variable CSS `--p` (0->1) reliee au scroll dans la section, puis chaque .part utilise `transform: translate3d(calc(var(--p) * Vx), calc(var(--p) * Vy), calc(var(--p) * Vz)) rotate3d(...)`.',
    '- **Image overlap stack**: empile 2-3 images/SVG du produit avec leger decalage et blur progressif pour creer une impression de profondeur (style fashion editorial).',
    '- **Smooth scroll** via Lenis (CDN) si l environnement le permet, sinon `scroll-behavior: smooth` + scrolling-perf optimise.',
    '- **Cinematic typography**: les titres apparaissent caractere par caractere via SplitType (CDN) ou un home-made char wrap. Les transitions sont longues (1.2-1.6s) avec stagger cubic-bezier.',
    '',
    '### Ressources / librairies recommandees (inclure via CDN dans le HTML)',
    `- Three.js: ${CDN_LIBS.three}`,
    `- OrbitControls (si rotation utilisateur): ${CDN_LIBS.threeOrbit}`,
    `- GSAP + ScrollTrigger (scroll scrub des hotspots / exploded view): ${CDN_LIBS.gsap}, ${CDN_LIBS.scrollTrigger}`,
    `- Lenis (smooth scroll): ${CDN_LIBS.lenis}`,
    `- SplitType (titres caractere par caractere): ${CDN_LIBS.splitText}`,
    '',
    '### Production de l asset principal',
    '- Si le produit existe et est connu, il doit etre dessine en SVG inline detaille (multi-path, gradients, light/shadow simules) ou modelise en three.js avec primitives composees (box + cylinder + sphere + lathe).',
    '- Aucun `<img>` qui pointe vers un fichier que tu ne livres pas.',
    '- Si tu utilises three.js, code une mini-scene avec lighting PBR (HemisphereLight + DirectionalLight + environnement reflechissant via PMREMGenerator si possible).',
    '',
    '### Le plus dur — narration scroll',
    '- Pense la page comme un STORY-BOARD vertical: quoi -> de quoi c est fait -> pour qui -> en action -> chiffres -> contre-arguments -> pour le commander.',
    '- Chaque section a un focal point unique. Aucune redite. Aucun bloc rempli "pour faire long".',
  ]
}

function narrativeLandingBlock(): string[] {
  return [
    '## ARCHETYPE: PREMIUM NARRATIVE LANDING — landing page editoriale (style Stripe / Linear / Vercel)',
    '',
    '### Sections obligatoires',
    '1. Nav fixed avec backdrop-filter blur, logo SVG inline, menu, CTA accent.',
    '2. Hero full-height avec headline imposante (clamp(2.5rem, 6.5vw, 5.5rem)), sous-titre, 2 CTAs (primary + ghost), visuel a droite (SVG anime / canvas / mesh gradient sophistique).',
    '3. Bandeau logos clients defilant (marquee CSS infinie, opacity 0.5).',
    '4. Section "Why" 3 colonnes ou bento (mix de cards de tailles differentes).',
    '5. Section "Showcase / Features" — grid 6-8 elements avec hover zoom + overlay gradient.',
    '6. Section "Numbers" — compteurs animes au scroll.',
    '7. Section "How it works" — etapes numerotees avec connecteurs SVG path animes au scroll.',
    '8. Section "Testimonials" — slider avec citations grandes, photos en cercle.',
    '9. CTA final immersif pleine largeur avec gradient.',
    '10. Footer 4 colonnes (about, links, contact, newsletter avec input style premium).',
    '',
    '### Effets recommandes',
    '- Mesh gradient anime en arriere-plan du hero (2-3 blobs filter blur 140px qui se deplacent en boucle).',
    '- SVG path animes (stroke-dasharray) sur les connecteurs entre sections.',
    '- Blob qui suit la souris dans le hero (mousemove + translate3d throttle).',
    '- Scroll reveal stagger sur chaque liste.',
    '- Counter animation IntersectionObserver.',
    `- GSAP ScrollTrigger (optionnel mais recommande): ${CDN_LIBS.gsap}, ${CDN_LIBS.scrollTrigger}.`,
  ]
}

function dashboardBlock(): string[] {
  return [
    '## ARCHETYPE: DASHBOARD / DATAVIZ PREMIUM — admin moderne style Linear / Vercel',
    '',
    '### Layout obligatoire',
    '- Sidebar gauche fixe (240-280px), couleur tres sombre, logo en haut, menu icones+labels, footer avec avatar + nom utilisateur, theme toggle.',
    '- Topbar avec breadcrumb, recherche command-palette (cmd+k), notifications, avatar dropdown.',
    '- Zone main fluide en grid bento (mix tailles, gap 16-24px).',
    '- Footer minimal.',
    '',
    '### Cartes / widgets',
    '- Glassmorphism: rgba(255,255,255,0.04) + backdrop-filter blur(24px) + border 1px rgba(255,255,255,0.08).',
    '- Chaque card: header (titre eyebrow + filter), zone data, footer (lien details).',
    '- Charts: courbe lissee SVG path (stroke-dasharray reveal), barchart avec barres animees au mount, donut SVG avec stroke-dasharray, sparkline en background des KPIs.',
    `- Librairie recommandee Chart.js (CDN): ${CDN_LIBS.chartjs} OU SVG home-made pour plus de finesse.`,
    `- Pour data tres complexe: D3 (CDN): ${CDN_LIBS.d3}.`,
    '',
    '### Interactions premium',
    '- Theme dark/light toggle persistant (localStorage), variables CSS `--bg`, `--fg`, `--accent`.',
    '- Command palette cmd+k qui apparait avec scale 0.96->1 + opacity 0->1.',
    '- Skeletons sur loading (background gradient anime).',
    '- Notifications toast (position top-right, slide-in + auto-dismiss 4s).',
    '- Filtres animes (chip qui change de couleur/border en cliquant).',
    '- Resize grid en drag & drop optionnel (Sortable.js si tu veux).',
    '',
    '### Visual cues',
    '- Status pill avec dot pulsant (online green / busy amber / offline gray).',
    '- Avatars circulaires avec ring couleur.',
    '- Iconographie Lucide (path SVG inline, pas de font icon).',
  ]
}

function portfolioBlock(): string[] {
  return [
    '## ARCHETYPE: PORTFOLIO IMMERSIF — agence creative / designer / studio',
    '',
    '### Direction artistique',
    '- Tres aere, palette monochrome avec un accent fort. Feel award-winning (Awwwards, Cssdesignawards).',
    '- Type display tres grand (clamp(4rem, 12vw, 12rem)) avec letter-spacing -0.04em.',
    '- Cursor custom (cercle qui suit la souris, change de taille au hover).',
    '',
    '### Sections',
    '1. Hero plein ecran avec marquee horizontal du nom/services + visuel central WebGL ou SVG anime.',
    '2. Section "Selected works" — grille bento avec 6-8 cas, hover qui agrandit l image (scale 1.06) + reveal label.',
    '3. Section "Approach / Manifesto" — texte editorial 2 colonnes, drop cap.',
    '4. Section "Clients" — marquee logos.',
    '5. Section "Awards / Press" — list typographique alignee.',
    '6. Section "Contact" — gros bouton mailto OU form premium avec floating labels.',
    '',
    '### Effets',
    '- WebGL en arriere-plan du hero: shader simple (noise + color cycle) OU particules three.js (Points + couleurs).',
    '- Images des projets en hover: distortion (RGB shift via SVG filter feColorMatrix) OU zoom + parallax.',
    '- Marquee infini (CSS @keyframes translateX).',
    '- Smooth scroll via Lenis si compatible (sinon scroll-behavior).',
    `- Three.js si stack le permet: ${CDN_LIBS.three}.`,
    `- GSAP pour les transitions complexes: ${CDN_LIBS.gsap}.`,
  ]
}

function ecommerceBlock(): string[] {
  return [
    '## ARCHETYPE: ECOMMERCE PREMIUM — store moderne style Aime Leon Dore / Bose',
    '',
    '### Sections obligatoires',
    '1. Nav avec logo + menu (hover dropdown methode mega-menu si applicable) + recherche + cart icon avec badge.',
    '2. Hero produit ou collection: image grande + titre editorial + CTA acheter.',
    '3. Section "Bestsellers" — grille de product cards.',
    '4. Section "Lookbook / Collection" — mosaique editoriale.',
    '5. Section "Story" — narration de la marque/produit.',
    '6. Section "Reviews" — etoiles + temoignages.',
    '7. Newsletter footer + footer 4 colonnes.',
    '',
    '### Product card premium',
    '- Image carre avec hover qui swap vers une autre vue ou applique zoom.',
    '- Color swatches sous l image (3-5 ronds couleur cliquables).',
    '- Tag badge (NEW, SALE -20%, SOLDOUT) en haut a gauche.',
    '- Hover affiche un quick-add CTA (translateY).',
    '',
    '### Page produit detaillee (si demandee)',
    '- Galerie verticale a gauche (thumbnails) + image principale large a droite.',
    '- Image zoom au hover (deplace selon position souris).',
    '- Sticky add-to-cart sidebar a droite (titre, prix, sizes, couleur, bouton CTA grand).',
    '- Tabs description / specs / care / reviews.',
    '- Section produits associes en bas.',
  ]
}

function saasMarketingBlock(): string[] {
  return [
    '## ARCHETYPE: SAAS MARKETING — page produit B2B style Linear / Notion / Vercel',
    '',
    '### Sections obligatoires',
    '1. Nav avec sous-menu "Product / Solutions / Pricing / Customers / Docs".',
    '2. Hero avec headline benefit-driven, eyebrow categorie produit, 2 CTAs, et un screenshot/illustration premium a droite.',
    '3. Logos clients en bandeau.',
    '4. Section "Features" — bento grid avec 6 features, chacune avec icone Lucide path, titre, 2-3 lignes, lien "Learn more".',
    '5. Section "Use cases" — slider/tabs des cas d usage avec illustration animée.',
    '6. Section "Pricing" — 3 plans avec mise en avant du plan central (border accent, badge "Recommended"), bouton CTA.',
    '7. Section "Testimonials" + section "Compare to competitors" tableau.',
    '8. Section "Numbers / Stats" — compteurs animes.',
    '9. CTA final + footer.',
    '',
    '### Pricing card detail',
    '- 3 colonnes egales sur desktop, stack mobile.',
    '- Plan central a une bordure colore et un badge "Most popular".',
    '- Liste de features avec icone check SVG inline.',
    '- Bouton CTA different par plan (primary / outline / outline).',
    '',
    '### Animations',
    '- Comparison table avec lignes qui se revelent au scroll.',
    '- Pricing toggle Monthly/Annual avec switch anime + recalcul des prix.',
    '- Feature illustrations animees (mini-loop SVG ou Lottie).',
    `- Lottie player pour les illustrations: ${CDN_LIBS.lottie}.`,
  ]
}

function editorialStoryBlock(): string[] {
  return [
    '## ARCHETYPE: EDITORIAL STORY — article long-form premium style The Verge / Pudding / NYT Magazine',
    '',
    '### Layout',
    '- Hero plein ecran avec image/illustration grande, eyebrow categorie, titre serif imposant (Playfair Display, GT Sectra, Spectral, Recoleta), sous-titre, byline + date + reading time.',
    '- Corps article max-width 680-720px centre, type tres lisible (16-18px, line-height 1.7).',
    '- Drop cap sur le 1er paragraphe.',
    '- Pull-quotes typographiques entre les sections (italique, tres grand, bordure gauche accent).',
    '- Callouts (citations, faits, schemas) qui debordent en marge a +50% de largeur.',
    '- Images plein-largeur entre les sections avec legende italique.',
    '- Charts ou data viz inline (SVG path animes au scroll).',
    '- Scroll progress bar fixe en haut.',
    '',
    '### Effets',
    '- Scroll progress bar (fixed top, height 3px, width = scrollProgress%).',
    '- Reading time estime affiche en haut.',
    '- Reveal au scroll de chaque image et figure.',
    '- Sticky aside avec table des matieres (chapitres cliquables, scroll-spy).',
    '- Image comparison sliders dans l article si pertinent.',
    `- SplitType pour titres caractere par caractere (optionnel): ${CDN_LIBS.splitText}.`,
  ]
}

function scroll3DJourneyBlock(): string[] {
  return [
    '## ARCHETYPE: SCROLL 3D JOURNEY — experience cinematique pinned (style Apple, Igloo Inc, Active Theory)',
    '',
    '### Principe',
    '- Une scene three.js en plein ecran (canvas absolute z-1) qui reagit au scroll: la camera, les positions, les rotations, les materiaux changent au fil de la timeline.',
    '- Le scroll de la page est REELLEMENT PINNE: la scene reste fixe pendant 5-7 chapitres, et chaque chapitre a son timing dans la timeline (0-15%, 15-35%, 35-55%, etc.).',
    '- Chaque chapitre ajoute des overlays HTML (titre, sous-titre, CTA) qui apparaissent et disparaissent au bon moment.',
    '',
    '### Implementation',
    `- Three.js: ${CDN_LIBS.three}.`,
    `- GSAP + ScrollTrigger (PINNED + scrub): ${CDN_LIBS.gsap}, ${CDN_LIBS.scrollTrigger}.`,
    `- Lenis pour smooth scroll: ${CDN_LIBS.lenis}.`,
    '- Structure HTML: section pin avec hauteur calculee (ex: 600vh), canvas fixed inside, et 5-7 .chapter overlays absolutely positioned by GSAP.',
    '- Eclairage PBR: HemisphereLight + DirectionalLight, MeshStandardMaterial / MeshPhysicalMaterial avec roughness/metalness/clearcoat.',
    '- Camera animee (position + lookAt) via tween scroll progress.',
    '- Geometrie principale: composer des primitives ou un .glb minimaliste fait main (sphere + box + lathe + extrude).',
    '- Postprocessing optionnel: Bloom + Vignette + ChromaticAberration via EffectComposer.',
    '',
    '### Garde-fous',
    '- Garder un mode degraded mobile: si window.innerWidth < 720, replier en mode statique (fond + sections classiques) plutot que faire ramer.',
    '- prefers-reduced-motion: desactiver scroll scrub.',
    '- Chargement: afficher un loader simple (logo SVG centre + barre progress) tant que three.js + textures pas pretes.',
  ]
}

function micrositeEventBlock(): string[] {
  return [
    '## ARCHETYPE: MICROSITE EVENT — landing evenement / festival / conference',
    '',
    '### Sections obligatoires',
    '1. Hero immersif: titre evenement tres grand, dates et lieu, CTA "Buy ticket" / "Register", visuel/affiche.',
    '2. Countdown live (jours / heures / minutes / secondes) avec ticking animation.',
    '3. Section "Lineup / Speakers" — grille de cartes (photo, nom, role, social).',
    '4. Section "Schedule / Agenda" — timeline jours (tabs Day 1 / Day 2 / Day 3) avec liste sessions horaire+titre+intervenant.',
    '5. Section "Venue" — carte interactive (Leaflet OSM optionnel ou SVG schematique), adresse, transport.',
    '6. Section "Sponsors" — grille logos.',
    '7. Section "FAQ" — accordeon.',
    '8. CTA final ticket + footer.',
    '',
    '### Effets',
    '- Countdown anime (recalcul chaque seconde, transitions sur les chiffres flip).',
    '- Tab schedule avec slider pile sur le tab actif (translateX selon index).',
    '- Cards lineup hover scale + reveal social icons.',
    '- Background hero avec mesh gradient ou particules soft.',
  ]
}

function brutalistBlock(): string[] {
  return [
    '## ARCHETYPE: MINIMAL BRUTALIST — typographie raw, palette monochrome, no-bullshit',
    '',
    '### Direction artistique',
    '- Typo display imposante (clamp(4rem, 14vw, 14rem)) en sans-serif geometrique (Helvetica, Neue Haas Grotesk, Inter Tight).',
    '- Palette: noir sur blanc OU blanc sur noir, avec UN accent rouge electrique #ff0000 ou jaune fluo #fff200.',
    '- Aucun radius sauf sur des elements specifiques. Aucun shadow. Aucun gradient.',
    '- Bordures franches 1-2px solid black/white.',
    '- Grid layout strict avec colonnes visibles (grid-template-columns repeat(12, 1fr) + gutters).',
    '',
    '### Effets autorises',
    '- Hover: invert couleurs ou fond change.',
    '- Marquee de texte (band horizontal qui defile).',
    '- Cursor underscore qui clignote sur certains elements.',
    '- Effet "glitch" tres ponctuel (translateX random + clip-path).',
    '',
    '### Anti-patterns interdits dans cet archetype',
    '- Pas de mesh gradient.',
    '- Pas de glassmorphism.',
    '- Pas de neumorphism.',
    '- Pas de pastels.',
    '- Pas de border-radius generique partout.',
  ]
}

function mobileNativePremiumBlock(intent: CodeIntent): string[] {
  const isFlutter = intent.projectType === 'mobile_flutter'
  return [
    `## ARCHETYPE: MOBILE NATIVE PREMIUM (${isFlutter ? 'Flutter' : 'React Native + Expo'})`,
    '',
    '### Visual quality',
    '- Theme dark + light avec switch persistant (AsyncStorage / SharedPreferences).',
    '- Typo: Inter / SF Pro / Plus Jakarta Sans. Echelle 12/14/16/20/28/40.',
    '- Palette systeme + accent unique vibrant.',
    '- Spacing 4/8/12/16/20/24/32.',
    '- Header avec blur (BlurView ou ImageFilter.blur Flutter).',
    '- Cards radius 16-20, ombre soft, padding genereux.',
    '',
    '### Interactions natives',
    '- Bottom sheet (gorhom/react-native-bottom-sheet OU showModalBottomSheet Flutter) pour les actions secondaires.',
    '- Swipe gestures (Gesture Handler / GestureDetector).',
    '- Haptic feedback sur les actions importantes (Haptics.impactAsync ou HapticFeedback.lightImpact).',
    '- Skeletons sur loading (Animated linear gradient).',
    '- Pull-to-refresh natif.',
    '- Tab bar bottom avec icones Lucide ou material symbols.',
    '',
    '### Pages obligatoires',
    '1. Splash screen (logo + spinner ou animation lottie).',
    '2. Onboarding 3 ecrans (carousel paginee).',
    '3. Home avec hero + sections.',
    '4. Detail page accessible par push.',
    '5. Profil / settings avec switch dark/light, language, notifications, sign out.',
    '',
    '### Production',
    isFlutter
      ? '- pubspec.yaml avec flutter, cupertino_icons, http, shared_preferences, google_fonts.'
      : '- package.json avec expo, react-native, react-navigation, expo-linear-gradient, lucide-react-native, react-native-reanimated.',
    '- README avec commandes lancement (expo start ou flutter run).',
  ]
}

function desktopAppBlock(intent: CodeIntent): string[] {
  const isTauri = intent.projectType === 'desktop_tauri'
  return [
    `## ARCHETYPE: DESKTOP APP (${isTauri ? 'Tauri' : 'Electron'})`,
    '',
    '### Visual quality',
    '- Title bar custom (cacher la title bar OS, dessiner une nous-meme avec drag region).',
    '- Sidebar gauche avec navigation, avatar/profile en bas.',
    '- Main panel scrollable. Optionnel: panel droite repliable (split-pane).',
    '- Theme follow systeme + override manuel.',
    '- Iconographie Lucide / Phosphor.',
    '',
    '### Patterns recommandes',
    '- Command palette cmd+k avec recherche actions.',
    '- Toast notifications discretes en bas a droite.',
    '- Settings page avec sections (General, Apparence, Raccourcis, A propos).',
    '- Onboarding au premier lancement.',
    '- Persistence d etat (Zustand + persist OU localStorage si frontend pur).',
    '',
    '### Tech stack',
    isTauri
      ? '- Frontend: Vite + React + TypeScript + Tailwind ou CSS module premium.\n- Backend: Tauri Rust pour acces fichier et commands IPC.'
      : '- Frontend Electron renderer + main process (electron 28+) + preload.',
  ]
}

function gamePremiumBlock(): string[] {
  return [
    '## ARCHETYPE: GAME WEB PREMIUM — visual juice maximum',
    '',
    '### Visual & juice obligatoire',
    '- Palette neon ou cinematique (cyber, retrowave, cyberpunk, vapor) avec un fond tres sombre.',
    '- Particules sur chaque action significative (explosion, score, dash, mort).',
    '- Screen shake (translation 2-6px aleatoire 80-150ms) sur impacts.',
    '- Trainees / motion blur sur projectiles ou personnages rapides.',
    '- Camera offset leger qui suit le joueur (smoothing 0.08).',
    '- Sons synthetises Web Audio (oscillator, noise, envelope ADSR) pour shoot/score/death/jump.',
    '- HUD propre: score top-left grand, vies/HP top-right en pictos, level center top.',
    '- Animations easing sur menus (ease-out spring).',
    '- Game over screen anime (flash + pulse texte score + bouton Rejouer).',
    '',
    '### Implementation',
    '- requestAnimationFrame avec delta time.',
    '- Boucle propre: input -> update -> draw, jamais setInterval.',
    '- localStorage best score.',
    '- Responsive canvas (resize listener) avec viewport scale uniforme.',
    '- prefers-reduced-motion: reduire screen shake et particules.',
  ]
}

function defaultPremiumBlock(): string[] {
  return [
    '## ARCHETYPE: DEFAULT PREMIUM — produit visuel polished generique',
    '',
    'Aucun archetype precis n a ete identifie. Tu produis un site/page premium standard avec:',
    '- Nav fixed blur + logo SVG.',
    '- Hero plein ecran avec mesh gradient + headline imposante + CTA + visuel.',
    '- 3-4 sections riches (features, showcase, numbers, testimonials).',
    '- CTA final + footer 4 colonnes.',
    '- Tous les effets baseline (scroll reveal, hover cards, counter, parallax leger).',
  ]
}

// ---------------------------------------------------------------------------
// Building block — assemble final directives
// ---------------------------------------------------------------------------

export function archetypeBlock(archetype: DesignArchetype, intent: CodeIntent): string[] {
  switch (archetype) {
    case 'apple_product': return appleProductBlock(intent)
    case 'narrative_landing': return narrativeLandingBlock()
    case 'dashboard_dataviz': return dashboardBlock()
    case 'portfolio_immersive': return portfolioBlock()
    case 'ecommerce_premium': return ecommerceBlock()
    case 'saas_marketing': return saasMarketingBlock()
    case 'editorial_story': return editorialStoryBlock()
    case 'scroll_3d_journey': return scroll3DJourneyBlock()
    case 'microsite_event': return micrositeEventBlock()
    case 'minimal_brutalist': return brutalistBlock()
    case 'mobile_native_premium': return mobileNativePremiumBlock(intent)
    case 'desktop_native_app': return desktopAppBlock(intent)
    case 'game_visual_premium': return gamePremiumBlock()
    default: return defaultPremiumBlock()
  }
}

export function depthDirectivesBlock(intent: CodeIntent): string[] {
  // Always-on depth/3D suggestions for visual web projects
  const wants3D = intent.assetPlan?.wants3D || intent.features.includes('3d')
  if (!wants3D && intent.projectType !== 'static_web' && !intent.projectType.startsWith('spa_') && !intent.projectType.startsWith('ssr_')) {
    return []
  }

  const lines = [
    '## PROFONDEUR ET 3D — toujours preferer la profondeur a la platitude',
    '- Aucun ecran ne doit etre 100% plat. Si la stack est web, ajoute au moins UN effet de profondeur:',
    '  1. Parallax sur 2-3 couches (translate3d en fonction du scroll).',
    '  2. Mesh gradient avec blobs blur en arriere-plan.',
    '  3. Layered z-index (cards qui se chevauchent legerement avec ombres composites).',
    '  4. Mini scene three.js (canvas inline) pour le hero ou une section dediee.',
    '- Si la stack permet WebGL et que le sujet le justifie, prefere une mini scene 3D meme courte (cube anime, sphere materielle, scrolling planet) plutot que des photos statiques.',
  ]

  if (wants3D) {
    lines.push(
      '',
      '### Three.js — implementation premium obligatoire (puisque 3D demande)',
      `- Importer via CDN module: ${CDN_LIBS.three}.`,
      `- OrbitControls si manipulation utilisateur: ${CDN_LIBS.threeOrbit}.`,
      `- GLTFLoader si modele externe: ${CDN_LIBS.threeGLTF}.`,
      '- Renderer: { antialias: true, alpha: true, powerPreference: "high-performance" }, shadowMap.enabled = true.',
      '- Camera PerspectiveCamera(45-60, aspect, 0.1, 1000) bien positionnee, jamais 0,0,0.',
      '- Lighting: HemisphereLight + DirectionalLight castShadow + (optionnel) PointLight colore.',
      '- Materials: MeshStandardMaterial avec metalness/roughness + envMap (PMREMGenerator) si possible.',
      '- Composition: minimum 1 mesh principal anime (rotation + flottement Math.sin(t)).',
      '- Postprocessing optionnel: Bloom, FXAA, ChromaticAberration via EffectComposer.',
      '- Cleanup: dispose() des geometries/materials/textures, cancelAnimationFrame au demontage, resize listener.',
      '- Performance: pixelRatio min(2, devicePixelRatio), pause scene si tab cache (visibilitychange).',
    )
  }

  return lines
}

export function autoDepsBlock(): string[] {
  return [
    '## DEPENDANCES — declaration ET livraison automatique',
    '- Si tu utilises GSAP / ScrollTrigger / Lenis / SplitType / Three.js / Lottie: ajoute le <script> CDN dans index.html (ou la ressource dans package.json si la stack est SPA bundler).',
    '- Pour SPA bundler: ajoute la lib dans dependencies du package.json avec une version stable (three@^0.160, gsap@^3.12, framer-motion@^11, react-three-fiber@^8, @react-three/drei@^9).',
    '- Verifie systematiquement que chaque lib utilisee dans ton code est bien declaree (import OK + dependance presente) — sinon le sandbox echouera.',
    '- Si une lib est lourde et qu une alternative CSS pure existe, prefere la version CSS (transition + @keyframes) pour un loading instantane.',
  ]
}
