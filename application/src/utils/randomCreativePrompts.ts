/**
 * v82fg : pools mutualisés de prompts créatifs aléatoires pour les
 * boutons "⚡ surprise · go" Image / Video / Drawing / Code / 3D V1.
 *
 * Source de vérité unique — permet d'enrichir un seul fichier pour
 * tous les modules concernés. Chaque pool reste typé string[] pour
 * laisser l'appelant gérer le random index lui-même (et utiliser
 * une éventuelle stratégie anti-répétition contextuelle).
 */

export const RANDOM_IMAGE_PROMPTS: string[] = [
  'a serene Japanese garden at dawn with cherry blossoms',
  'futuristic cyberpunk Tokyo street, neon rain, 35mm',
  'mediterranean village at golden hour, watercolor',
  'a wolf howling at the moon, charcoal sketch',
  'space station orbiting Saturn, hyperdetailed',
  'old library with floating books, magical light',
  'aurora borealis over Iceland glacier',
  'steampunk airship in cloudy sky, sepia',
  'samurai warrior in bamboo forest, ink wash',
  'underwater coral reef city, bioluminescent',
  'autumn forest path with morning mist',
  'desert oasis at twilight, ancient ruins',
  'snow-capped mountains reflected in alpine lake',
  'medieval marketplace, oil painting',
  'spaceship cockpit view of nebula',
  'art deco hotel lobby, 1920s elegance',
  'tropical beach hut on stilts, sunset',
  'Viking longhouse in stormy fjord',
  'ballerina mid-leap in spotlight, dramatic',
  'lighthouse on cliff during thunderstorm',
]

export const RANDOM_VIDEO_PROMPTS: string[] = [
  'a chase scene through a futuristic Tokyo, neon lights reflecting in puddles',
  'a quiet morning in a Parisian café, espresso cup steaming',
  'a documentary on the deep sea, bioluminescent creatures',
  'a samurai duel at dawn in a bamboo forest',
  'a time-lapse of a flower blooming over four seasons',
  'a heist crew planning in an abandoned warehouse',
  'a mountain expedition, climber roping a vertical wall',
  'a chef preparing sushi, hands moving precisely, close-ups',
  'a streetwear photoshoot in a graffiti alley',
  'a violin recital under spotlight, audience in shadow',
  'a vintage train rolling through autumn countryside',
  'a child discovering a secret garden behind a hidden door',
]

export const RANDOM_VIDEO_STYLES: string[] = [
  'cinematic', 'documentary', 'anime', 'noir', 'pastel', 'gritty',
]

export const RANDOM_DRAW_PROMPTS: string[] = [
  'a heron standing in shallow water at dawn',
  'a wise old monk meditating under a pine tree',
  'a koi fish leaping above a still pond',
  'cherry blossom branch, single bird',
  'a samurai walking through misty bamboo',
  'a calligraphy master writing on rice paper',
  'a wolf howling on a mountain peak',
  'a single perfect chrysanthemum',
  'a tea master pouring matcha, calm hands',
  'a dragon coiling around a moon',
  'a cat curled by a window, raindrops',
  'a tiger crouching in tall grass',
]

export const RANDOM_CODE_IDEAS: string[] = [
  'Une fonction TypeScript qui parse un CSV avec headers et renvoie un array d\'objets typés',
  'Un hook React useDebouncedValue<T>(value, delay) avec cleanup',
  'Un small Express middleware Node.js qui logge le temps de chaque requête',
  'Une fonction Python qui télécharge un PDF, extrait le texte avec pdfplumber et le clean',
  'Un service Rust qui sert un fichier statique avec axum + tower-http',
  'Une CLI Go qui surveille un dossier et déclenche un build au moindre changement',
  'Un component React + Three.js qui affiche un cube 3D animé en lévitation',
  'Une fonction SQL CTE récursive pour calculer une hiérarchie d\'employés',
  'Un script bash qui sauvegarde un dossier en .tar.gz horodaté + rotation 7 derniers',
  'Une regex Python pour extraire toutes les emails et téléphones d\'un texte',
  'Un component Vue 3 avec composition API qui fait un infinite scroll',
  'Une fonction Rust qui parse un fichier JSON via serde_json avec error handling',
]

export const RANDOM_3D_PROMPTS: string[] = [
  'a stylized fantasy dragon with iridescent scales, low-poly',
  'a small robot companion with antennas and treads',
  'a medieval castle on a rocky cliff, hand-painted texture',
  'a futuristic spaceship, cyberpunk hull plating',
  'a samurai katana with engraved hilt and gold guard',
  'a low-poly fox in autumn leaves',
  'a crystalline mineral cluster, glowing core',
  'a steampunk pocket watch with exposed gears',
  'a cute chibi cat with big eyes, low-poly',
  'a sci-fi turret on a hexagonal base',
  'an ancient stone monolith with runes',
  'a tropical low-poly tree with hammock',
]

/** Helpers de pioche (avec retry anti-répétition optionnel). */
export function pickRandom<T>(pool: T[], avoid?: T): T {
  if (pool.length === 0) throw new Error('pool empty')
  if (pool.length === 1 || avoid === undefined) {
    return pool[Math.floor(Math.random() * pool.length)]
  }
  let next = pool[Math.floor(Math.random() * pool.length)]
  let tries = 0
  while (next === avoid && tries < 5) {
    next = pool[Math.floor(Math.random() * pool.length)]
    tries++
  }
  return next
}
