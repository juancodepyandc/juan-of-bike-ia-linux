// Detecteurs du juge visuel source-statique.
//
// Extrait de codeVisualFidelity pour tenir la limite de 400 lignes par unite de
// production. Aucune logique de notation ici: uniquement les motifs qui disent
// « ce trait est present dans le markup / le CSS livre ».

export const PREMIUM_FONTS = /Inter|Manrope|Satoshi|DM\s*Sans|Space\s*Grotesk|Plus\s*Jakarta|Poppins|Outfit|Sora|Bungee/i
export const SCOLAIRE_TITLES = /<h1[^>]*>\s*Bienvenue\b|<h1[^>]*>\s*Welcome\b/i
export const FLAT_BG_COLORS = /background\s*:\s*(red|blue|green|yellow|orange|purple|pink|#[0-9a-f]{3,6})\s*[;}"]|background-color\s*:\s*(red|blue|green|yellow|orange|purple|pink)\b/i
export const PLAIN_LIST = /<ul[^>]*>(?:\s*<li[^>]*>[^<]{0,80}<\/li>\s*){2,8}\s*<\/ul>/i
// Le pipeline INJECTE Tailwind lui-meme (`ensureTailwindCDN`): mesurer un
// projet Tailwind sur des noms de proprietes CSS revenait a chercher le degrade
// la ou il n est jamais ecrit. `bg-gradient-to-br from-amber-900` EST un
// degrade dans la page rendue; `backdrop-blur-md` EST de la profondeur.
export const HAS_GRADIENT = /linear-gradient|radial-gradient|conic-gradient|\bbg-gradient-to-[a-z]{1,2}\b|\bbg-\[(?:linear|radial|conic)-gradient/i
export const HAS_MESH_BLUR = /filter\s*:\s*blur\(\s*[8-9]\d|filter\s*:\s*blur\(\s*1\d{2,}|\bblur-(?:2xl|3xl)\b|\bblur-\[\s*(?:[8-9]\d|1\d{2,})px\]/i
export const HAS_KEYFRAMES = /@keyframes/i
export const HAS_TRANSITION = /transition\s*:|transition:/i
export const HAS_INTERSECTION_OBSERVER = /IntersectionObserver/i
export const HAS_RAF = /requestAnimationFrame/i
export const HAS_INLINE_SVG = /<svg\b[^>]*>[\s\S]{120,}?<\/svg>/i
// Tailwind: `flex`/`grid` sont des classes, jamais des declarations CSS. On ne
// les cherche QUE dans un attribut de classe, pour ne pas confondre avec de la
// prose ou un identifiant.
export const HAS_FLEX_OR_GRID = /display\s*:\s*(flex|grid|inline-flex|inline-grid)|class(?:Name)?\s*=\s*[{"'`][^"'`}]*\b(?:inline-)?(?:flex|grid)\b/i
export const HAS_BACKDROP_FILTER = /backdrop-filter\s*:|-webkit-backdrop-filter\s*:|\bbackdrop-blur(?:-\w+)?\b/i
export const HAS_BORDER_RADIUS_LARGE = /border-radius\s*:\s*([1-9]\d|1\.|2\.|3\.)/i
export const HAS_CSS_VARS = /var\(\s*--/i
export const HAS_CLAMP = /clamp\s*\(/i
export const HAS_HOVER = /:hover/i
export const HAS_FONT_LINK_PRECONNECT = /fonts\.googleapis\.com|fonts\.gstatic\.com/i
export const HAS_TRANSFORM_3D = /transform\s*:[^;]*(?:rotate3d|rotateX|rotateY|rotateZ|perspective|translate3d|preserve-3d)/i
export const HAS_PARALLAX = /scroll-driven|sticky|IntersectionObserver|ScrollTrigger|--p\s*\)/i
export const HAS_MULTI_GRADIENTS = /linear-gradient[\s\S]*linear-gradient|radial-gradient[\s\S]*radial-gradient/i

