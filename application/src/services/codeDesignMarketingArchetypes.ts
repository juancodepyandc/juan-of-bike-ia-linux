import type { CodeIntent } from './codeIntent.ts'
import type { DesignArchetype } from './codeDesignDirectives.ts'
import { CODE_DESIGN_CDN_LIBS as CDN_LIBS } from './codeDesignDirectiveLibraries.ts'

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

export function marketingArchetypeBlock(
  archetype: DesignArchetype,
  intent: CodeIntent,
): string[] | null {
  switch (archetype) {
    case 'apple_product': return appleProductBlock(intent)
    case 'narrative_landing': return narrativeLandingBlock()
    case 'dashboard_dataviz': return dashboardBlock()
    case 'portfolio_immersive': return portfolioBlock()
    case 'ecommerce_premium': return ecommerceBlock()
    case 'saas_marketing': return saasMarketingBlock()
    case 'editorial_story': return editorialStoryBlock()
    default: return null
  }
}
