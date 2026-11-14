/**
 * AuroraIA Cognitive Prompt & Ontology Director (TypeScript / Frontend + Node Engine)
 *
 * Implements genuine ontological & semantic prompt intelligence across Image (FLUX.2-dev),
 * 3D (TRELLIS.2-4B / Hunyuan3D / Blender), Video (Wan2.2), and Animation (UniRig / HY-Motion):
 *
 * 1. Subject Ontology Reasoning (`subjectOntology`):
 *    Understands whether a requested character/object is intrinsically from an anime/manga/stylized
 *    universe (e.g. Natsu, Goku, Luffy, Naruto, Gojo, Tanjiro, Frieren, "un perso animé", "un mage shonen"),
 *    a video game asset, a mechanical CAD part, or a real-world human/object/landscape.
 *
 * 2. Native Style Fidelity & Explicit Override Rule (`effectiveRenderMode`):
 *    - If the subject is intrinsically anime/stylized: renders DIRECTLY in its authentic native anime/stylized
 *      aesthetic (cel-shading, anime facial proportions, sculpted hair locks, ZERO realistic skin pores),
 *      UNLESS the user explicitly requests real human skin textures (`explicitRealTexturesOverride = true`,
 *      e.g. "avec des textures de personne réelle", "en live-action", "peau humaine réelle").
 *    - If the subject is intrinsically real-world (human portrait, real object, landscape): renders DIRECTLY
 *      in physical photorealism (real skin pores, natural lens physics, PBR materials), UNLESS the user
 *      explicitly requests stylization (`explicitStylizedOverride = true`, e.g. "en style animé", "en manga").
 *
 * 3. Creation vs Modification Delta Lock (`operationMode`):
 *    - When `operationMode === 'modification'` (or `'reproduction'`), locks 100% of the existing subject's
 *      native ontology, style, identity, pose, and unmentioned attributes, applying ONLY the requested delta.
 *
 * 4. Deep French -> Fluent English Translation & Artistic/3D Expansion (`englishExpandedPrompt`):
 *    - Humans naturally write concise requests in French; diffusion & 3D backbones require rich, coherent
 *      English descriptions. Translates and expands short human ideas into complete English production briefs.
 */

export type SubjectOntology =
  | 'anime_manga_character'
  | 'game_character_or_asset'
  | 'mechanical_cad_engineering'
  | 'real_human_subject'
  | 'real_world_object_or_scene'

export type EffectiveRenderMode =
  | 'native_anime_stylized'
  | 'hybrid_anime_with_real_textures'
  | 'native_photorealistic'
  | 'hybrid_real_to_stylized'
  | 'native_game_stylized'
  | 'native_engineering_pbr'

export type PromptOperationMode = 'creation' | 'modification' | 'reproduction'

export type StrictPromptConstraints = {
  positiveTextClean: string
  excludedItemsEn: string[]
  affirmativeReplacementsEn: string[]
  mandatoryAttributesEn: string[]
}

export type StylizedSubmode =
  | 'cartoon_figurine'
  | 'figurine_toy'
  | 'clay_or_plush'
  | 'lowpoly_voxel'
  | 'cartoon_3d'
  | 'anime_cel'

export type CognitivePromptDecision = {
  rawPrompt: string
  targetModule: 'image' | '3d' | 'video' | 'drawing'
  operationMode: PromptOperationMode
  subjectOntology: SubjectOntology
  nativeOntology: 'anime_stylized' | 'real_photorealistic' | 'game_stylized' | 'engineering_cad'
  canonicalSubjectName: string | null
  effectiveRenderMode: EffectiveRenderMode
  stylizedSubmode?: StylizedSubmode | null
  explicitRealTexturesOverride: boolean
  explicitStylizedOverride: boolean
  preserveNativeAnimeStyle: boolean
  preserveNativeRealStyle: boolean
  lockUnmentionedAttributes: boolean
  englishSubject: string
  englishExpandedPrompt: string
  styleDirectiveEn: string
  negativePrompt: string
  negativeDirectivesEn: string[]
  strictConstraints?: StrictPromptConstraints
  modificationDeltaEn: string | null
  reasoningFr: string
  explanationFr: string
  badgeLabelFr: string
  wasLlmRefined: boolean
  openWorldEntity?: {
    title: string
    description: string
    source: string
  } | null
}

function stripAccents(text: string): string {
  return (text || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '')
}

function normalize(text: string): string {
  return stripAccents(text).toLowerCase().replace(/\s+/g, ' ').trim()
}

export const ANIME_ONTOLOGY_RE = new RegExp(
  String.raw`\b(` +
    [
      'anime', 'animé', 'manga', 'manhwa', 'webtoon', 'shonen', 'shojo', 'seinen', 'isekai', 'chibi',
      'cel[- ]?shad(?:ed|ing)', 'ghibli', 'makoto\\s*shinkai', 'ufotable', 'mappa', 'toei', 'kyoani',
      'pixar', 'disney', 'cartoon', 'dessin\\s*anime', 'toon', 'looney\\s*tunes', 'tex\\s*avery',
      'hanna[- ]?barbera', 'dreamworks', 'illumination', 'aardman', 'claymation', 'pate\\s*a\\s*modeler',
      'stop[- ]?motion', 'nickelodeon', 'cartoon\\s*network', 'xilam', 'bande\\s*dessinee', 'franco[- ]?belge',
      'funko\\s*pop', 'funko', 'nendoroid', 'figurine\\s*cartoon', 'jouet\\s*cartoon', 'peluche\\s*cartoon',
      'natsu', 'lucy\\s*heartfilia', 'erza', 'gray\\s*fullbuster', 'happy\\s*exceed', 'wendy\\s*marvell', 'fairy\\s*tail',
      'goku', 'son\\s*goku', 'sangoku', 'san\\s*goku', 'kakarot', 'kakarotto',
      'vegeta', 'gohan', 'sangohan', 'san\\s*gohan', 'goten', 'sangoten', 'trunks', 'piccolo', 'frieza', 'freezer', 'cell', 'majin\\s*buu', 'broly', 'beerus', 'whis', 'bulma', 'krillin', 'krilin', 'saiyan', 'super\\s*saiyan', 'ultra\\s*instinct', 'dragon\\s*ball',
      'luffy', 'monkey\\s*d', 'zoro', 'zorro', 'roronoa', 'sanji', 'nami', 'robin', 'chopper', 'usopp', 'brook', 'franky', 'jinbe', 'shanks', 'ace', 'sabo', 'trafalgar\\s*law', 'kaido', 'katakuri', 'gear\\s*5', 'one\\s*piece',
      'naruto', 'sasuke', 'sakura', 'kakashi', 'itachi', 'madara', 'obito', 'hinata', 'gaara', 'jiraiya', 'minato', 'pain', 'tsunade', 'orochimaru', 'akatsuki', 'sharingan', 'byakugan', 'konoha',
      'ichigo', 'rukia', 'aizen', 'byakuya', 'kenpachi', 'ulquiorra', 'grimmjow', 'yoruichi', 'urahara', 'bleach', 'bankai', 'shinigami',
      'tanjiro', 'nezuko', 'zenitsu', 'inosuke', 'rengoku', 'giyu', 'muzan', 'shinobu', 'mitsuri', 'tengen', 'akaza', 'kokushibo', 'hashira', 'demon\\s*slayer', 'kimetsu',
      'gojo', 'satoru\\s*gojo', 'sukuna', 'yuji\\s*itadori', 'megumi', 'nobara', 'toji', 'geto', 'yuta', 'maki', 'nanami', 'choso', 'mahoraga', 'jujutsu\\s*kaisen',
      'eren', 'mikasa', 'levi', 'livai', 'armin', 'reiner', 'erwin', 'zeke', 'attaque\\s*des\\s*titans', 'attack\\s*on\\s*titan', 'shingeki',
      'saitama', 'genos', 'tatsumaki', 'garou', 'fubuki', 'one\\s*punch',
      'gon', 'killua', 'kirua', 'kurapika', 'hisoka', 'meruem', 'chrollo', 'neferpitou', 'hunter\\s*x\\s*hunter',
      'deku', 'midoriya', 'bakugo', 'todoroki', 'all\\s*might', 'shigaraki', 'dabi', 'my\\s*hero\\s*academia',
      'asta', 'yuno', 'yami', 'noelle', 'black\\s*clover',
      'denji', 'makima', 'power', 'aki', 'pochita', 'reze', 'chainsaw\\s*man',
      'frieren', 'fern', 'stark', 'himmel',
      'anya', 'yor\\s*forger', 'loid\\s*forger', 'spy\\s*x\\s*family',
      'sung\\s*jin[- ]?woo', 'solo\\s*leveling', 'igris', 'beru',
      'edward\\s*elric', 'alphonse\\s*elric', 'roy\\s*mustang', 'fullmetal',
      'light\\s*yagami', 'ryuk', 'l\\s*lawliet', 'death\\s*note',
      'lelouch', 'code\\s*geass', 'rem', 'emilia', 'subaru', 're\\s*zero',
      'kirito', 'asuna', 'sword\\s*art\\s*online', 'rimuru', 'tensura', 'ainz', 'overlord',
      'jotaro', 'dio\\s*brando', 'giorno', 'josuke', 'jolyne', 'jojo',
      'guts', 'griffith', 'casca', 'berserk', 'baki', 'yujiro\\s*hanma',
      'seiya', 'chevaliers\\s*du\\s*zodiaque', 'saint\\s*seiya', 'goldorak', 'grendizer', 'albator', 'astro\\s*boy', 'akira', 'kaneda', 'inuyasha', 'sesshomaru', 'kenshin', 'alucard', 'hellsing', 'mob\\s*psycho', 'thorfinn', 'vinland\\s*saga', 'violet\\s*evergarden', 'maomao',
      'pikachu', 'charizard', 'dracaufeu', 'mewtwo', 'lucario', 'eevee', 'gengar', 'ectoplasma', 'tortank', 'blastoise', 'florizarre', 'venusaur', 'rayquaza', 'greninja', 'amphinobi', 'pokemon',
      'hatsune\\s*miku', 'vocaloid', 'genshin', 'raiden\\s*shogun', 'furina', 'nahida', 'zhongli', 'hu\\s*tao', 'arlecchino', 'honkai',
      'link', 'zelda', 'ganondorf', 'hyrule', 'mario', 'luigi', 'peach', 'bowser', 'yoshi', 'sonic', 'tails', 'knuckles', 'shadow\\s*the\\s*hedgehog',
      'cloud\\s*strife', 'tifa', 'sephiroth', 'aerith', 'final\\s*fantasy', '2b', 'nier\\s*automata', 'jinx', 'vi\\s*arcane', 'ekko', 'arcane',
      'zig\\s*et\\s*sharko', 'zig\\s*and\\s*sharko', 'zig', 'sharko', 'bernie', 'oggy', 'les\\s*dalton',
      'jibanyan', 'yo[- ]?kai\\s*watch', 'whisper\\s*yokai', 'komasan', 'mark\\s*evans', 'endou\\s*mamoru', 'axel\\s*blaze', 'gouenji', 'jude\\s*sharp', 'kidou', 'shawn\\s*froste', 'fubuki', 'inazuma\\s*eleven',
      'asterix', 'obelix', 'idefix', 'tintin', 'milou', 'lucky\\s*luke', 'marsupilami', 'gaston\\s*lagaffe', 'spirou', 'fantasio', 'schtroumpf', 'smurf', 'titeuf',
      'bob\\s*l[\' ]?eponge', 'spongebob', 'patrick\\s*star', 'squidward', 'carlo', 'mr\\s*krabs',
      'tom\\s*et\\s*jerry', 'tom\\s*and\\s*jerry', 'bugs\\s*bunny', 'daffy\\s*duck', 'scooby[- ]?doo', 'shaggy', 'sammy',
      'flintstones', 'pierrafeu', 'powerpuff', 'super\\s*nanas', 'dexter', 'samurai\\s*jack', 'ben\\s*10', 'adventure\\s*time', 'finn', 'jake', 'gumball', 'darwin',
      'rick\\s*et\\s*morty', 'rick\\s*and\\s*morty', 'rick\\s*sanchez', 'morty\\s*smith',
      'homer\\s*simpson', 'bart\\s*simpson', 'marge\\s*simpson', 'lisa\\s*simpson', 'simpsons?', 'futurama', 'bender', 'peter\\s*griffin', 'stewie', 'family\\s*guy', 'south\\s*park', 'cartman',
      'avatar\\s*aang', 'korra', 'mickey\\s*mouse', 'mickey', 'minnie', 'donald\\s*duck', 'dingo', 'goofy', 'pluto', 'stitch', 'lilo',
      'shrek', 'fiona', 'po\\s*kung\\s*fu', 'kung\\s*fu\\s*panda', 'krokmou', 'toothless', 'megamind', 'gru', 'minions?', 'minion',
      'buzz\\s*l[\' ]?eclair', 'buzz\\s*lightyear', 'woody', 'wall[- ]?e', 'baymax', 'ralph', 'elsa', 'anna', 'olaf', 'vaiana', 'moana', 'maui',
      'miraculous', 'ladybug', 'chat\\s*noir', 'totally\\s*spies', 'code\\s*lyoko', 'wakfu', 'dofus', 'yugo', 'nox', 'kirikou',
      'garfield', 'snoopy', 'peanuts', 'calvin', 'hobbes', 'popeye', 'pink\\s*panther', 'panthere\\s*rose', 'inspecteur\\s*gadget', 'inspector\\s*gadget',
      'tortues\\s*ninja', 'tmnt', 'sponge\\s*bob', 'pat\\s*patrouille', 'paw\\s*patrol', 'peppa\\s*pig', 'bluey',
      'steven\\s*universe', 'gravity\\s*falls', 'dipper', 'mabel', 'bill\\s*cipher', 'phineas', 'ferb', 'perry', 'kim\\s*possible', 'danny\\s*phantom',
      'bob\\s*razowski', 'mike\\s*wazowski', 'sulley', 'sulli', 'monstres\\s*et\\s*cie', 'indestructibles', 'incredibles', 'ratatouille', 'flash\\s*mcqueen', 'lightning\\s*mcqueen',
      'kirby', 'crash\\s*bandicoot', 'spyro', 'rayman', 'globox', 'lapins\\s*cretins', 'rabbids', 'pac[- ]?man', 'bomberman', 'megaman', 'cuphead', 'mugman', 'bendy', 'undertale', 'freddy\\s*fazbear', 'fnaf', 'huggy\\s*wuggy', 'jax', 'pomni', 'caine',
    ].join('|') +
    String.raw`)\b`,
  'i',
)

export const EXPLICIT_REAL_TEXTURES_OVERRIDE_RE = new RegExp(
  String.raw`\b(` +
    [
      'texture[s]?\\s+(?:de\\s+)?(?:personne|peau|humain[e]?|vrai[e]?)\\s+r[eé]el(?:le)?s?',
      'texture[s]?\\s+r[eé]aliste[s]?\\s+(?:de\\s+peau|humaine|personne)',
      'peau\\s+(?:humaine\\s+)?r[eé]elle',
      'vrai[e]?\\s+peau\\s+humaine',
      'en\\s+(?:vrai[e]?\\s+)?(?:personne|humain)\\s+r[eé]el(?:le)?',
      'version\\s+(?:personne\\s+)?r[eé]elle',
      'rendu\\s+personne\\s+r[eé]elle',
      'live[- ]?action',
      'cosplay\\s+r[eé]aliste',
      'photorealistic\\s+human\\s+skin',
      'real\\s+human\\s+(?:skin\\s+)?textures?',
      'realistic\\s+skin\\s+pores',
      'comme\\s+une?\\s+vrai[e]?\\s+(?:personne|humain)',
      'avec\\s+(?:des\\s+)?textures?\\s+(?:de\\s+personne\\s+)?r[eé]el(?:le)?s?',
    ].join('|') +
    String.raw`)\b`,
  'i',
)

export const EXPLICIT_STYLIZED_OVERRIDE_RE = new RegExp(
  String.raw`\b(` +
    [
      '(?:en|into|to|as\\s+a|comme\\s+un[e]?|fa[cç]on|type)\\s+(?:un[e]?\\s+)?(?:style\\s+|version\\s+|personnage\\s+)?(?:anime|anim[eé]|manga|cartoon|dessin\\s*anim[eé]|ghibli|pixar|disney|dreamworks|chibi|kawaii|pixel\\s*art|low[- ]?poly|voxel|bd|comics?|bande\\s*dessin[eé]e|figurine(?:\\s+cartoon)?|funko(?:\\s*pop)?|nendoroid|jouet|toy|peluche|plush(?:ie)?|p[aâ]te\\s+[aà]\\s+modeler|clay(?:mation)?|lego|playmobil|caricature|illustration|stylis[eé]e?)',
      'style\\s+(?:anime|anim[eé]|manga|cartoon|dessin\\s*anim[eé]|ghibli|pixar|disney|dreamworks|chibi|kawaii|pixel\\s*art|cel[- ]?shading|figurine|funko(?:\\s*pop)?|jouet|toy|peluche|p[aâ]te\\s+[aà]\\s+modeler|clay(?:mation)?|low[- ]?poly|voxel|bd|comics?|caricature|stylis[eé]e?)',
      '(?:transform(?:e|er)|chang(?:e|er)|converti(?:s|r)|adapt(?:e|er)| refais|rendre)\\s+(?:.+?\\s+)?(?:en|into|to)\\s+(?:un[e]?\\s+)?(?:style\\s+|version\\s+|personnage\\s+)?(?:anime|anim[eé]|manga|cartoon|dessin\\s*anim[eé]|ghibli|pixar|disney|chibi|figurine(?:\\s+cartoon)?|funko(?:\\s*pop)?|nendoroid|jouet|toy|peluche|plush|p[aâ]te\\s+[aà]\\s+modeler|clay(?:mation)?|low[- ]?poly|voxel|bd|comics?|caricature|stylis[eé]e?)',
      'version\\s+(?:anime|anim[eé]|manga|cartoon|dessin\\s*anim[eé]|figurine|funko(?:\\s*pop)?|chibi|pixar|disney|jouet|peluche|claymation|low[- ]?poly|voxel|stylis[eé]e?)',
      'cartoon\\s+figurine|figurine\\s+cartoon|personnage\\s+cartoon|style\\s+zig|style\\s+looney\\s*tunes|style\\s+tex\\s*avery|style\\s+simpson|style\\s+rick\\s*et\\s*morty|style\\s+south\\s*park|style\\s+asterix',
    ].join('|') +
    String.raw`)\b`,
  'i',
)

export function detectRequestedStylizedSubmode(rawText: string): StylizedSubmode {
  const norm = normalize(rawText)
  const hasFigurine = /\b(figurine|funko(?:\s*pop)?|nendoroid|statuette|action\s*figure|jouet|toy|vinyl\s*figure|collectible\s*figure|poup[eé]e|doll)\b/i.test(norm)
  const hasCartoon = /\b(cartoon|dessin\s*anime|toon|looney\s*tunes|tex\s*avery|hanna[- ]?barbera|xilam|zig|sharko|oggy|asterix|obelix|tintin|lucky\s*luke|marsupilami|gaston|spirou|schtroumpf|smurf|titeuf|spongebob|bob\s*l[' ]?eponge|patrick|bugs\s*bunny|daffy\s*duck|tom\s*(?:et|and)\s*jerry|simpson|homer|bart|rick|morty|scooby|flintstones|pierrafeu|powerpuff|dexter|ben\s*10|gumball|adventure\s*time|family\s*guy|south\s*park|mickey|minnie|donald|dingo|goofy|stitch|shrek|minion|gru|pixar|disney|dreamworks|illumination|garfield|snoopy|popeye|pink\s*panther|panthere\s*rose|caricature|bande\s*dessinee|\bbd\b|comics?|cuphead|rayman|crash\s*bandicoot|spyro)\b/i.test(norm)
  const hasClayOrPlush = /\b(pate\s+a\s+modeler|clay(?:mation)?|plasticine|aardman|stop[- ]?motion|peluche|plush(?:ie)?|laine|feutrine|felt|crochet|amigurumi)\b/i.test(norm)
  const hasLowpolyVoxel = /\b(low[- ]?poly|voxel|lego|playmobil|blocky|minecraft|roblox|polygon)\b/i.test(norm)
  if (hasFigurine && hasCartoon) return 'cartoon_figurine'
  if (hasFigurine) return 'figurine_toy'
  if (hasClayOrPlush) return 'clay_or_plush'
  if (hasLowpolyVoxel) return 'lowpoly_voxel'
  if (hasCartoon) return 'cartoon_3d'
  return 'anime_cel'
}

export const MODIFICATION_INTENT_RE = new RegExp(
  String.raw`(?:^|\b)(` +
    [
      'modifi(?:e|er|cation)', 'chang(?:e|er)', 'ajout(?:e|er)', 'rajout(?:e|er)',
      'enl[eè]v(?:e|er)', 'retir(?:e|er)', 'supprim(?:e|er)', 'remplac(?:e|er)',
      'met(?:s|tre)[- ]?(?:lui|le|la|les)?', 'transform(?:e|er)', 'corrige(?:r)?',
      'garde(?:r)?\\s+(?:le\\s+m[eê]me|la\\s+m[eê]me|exactement)',
      'sans\\s+changer', 'conserve(?:r)?', 'm[eê]me\\s+(?:personnage|sujet|objet|pose)',
      'make\\s+(?:him|her|it|the)', 'change\\s+the', 'add\\s+a', 'remove\\s+the', 'replace\\s+the', 'keep\\s+the\\s+same',
    ].join('|') +
    String.raw`)\b`,
  'i',
)

export const REPRODUCTION_INTENT_RE = new RegExp(
  String.raw`\b(` +
    [
      'reprodui(?:s|re)', 'fais[- ]?moi\\s+ce\\s+(?:personnage|sujet|mod[eè]le)',
      'identique\\s+[aà]', 'comme\\s+sur\\s+la\\s+photo', 'exactement\\s+ce\\s+perso',
      'replicate', 'exact\\s+copy\\s+of',
    ].join('|') +
    String.raw`)\b`,
  'i',
)

const CHARACTER_SUBJECT_RE =
  /\b(perso|personnage|character|hero[s]?|heroine|guerrier[e]?|warrior|mage|sorcier[e]?|chevalier|knight|ninja|samourai|samurai|pirate|assassin|paladin|archer|voleur|homme|femme|garcon|fille|enfant|vieillard|portrait|visage|humain[e]?|personne|man|woman|boy|girl|human|person|face|avatar|figurine|funko|statuette|jouet|peluche)\b/i

const MECHANICAL_CAD_RE =
  /\b(engrenage|gear|poulie|pulley|courroie|belt|verin|actuator|charniere|hinge|bielle|linkage|roulement|bearing|vis|ecrou|bride|flange|support\s+mecanique|boitier\s+pc|carte\s+mere|motherboard|strimer|cable|connecteur|gpu|rtx|ventirad|stl|cao|cad|imprimable|printable|piece\s+mecanique)\b/i

const GAME_ASSET_RE =
  /\b(pixel\s*art|sprite|spritesheet|tileset|isometrique|isometric|low[- ]?poly|icone\s+de\s+jeu|game\s+asset|game\s+prop|inventory\s+icon|pbr\s+texture|seamless\s+texture)\b/i

const GOKU_LORE =
  'Son Goku from Dragon Ball, muscular anime martial artist with iconic wild spiky jet-black hair, determined dark eyes, signature bright orange martial arts gi over a royal blue undershirt, blue wristbands, blue sash belt, and martial arts boots'
const GOHAN_LORE =
  'Son Gohan from Dragon Ball, muscular Saiyan martial artist with spiky black hair, sharp eyes, purple or orange martial arts gi, athletic fighting stance'
const ZORO_LORE =
  'Roronoa Zoro from One Piece, muscular anime swordsman with cropped green hair, three gold earrings on his left ear, scar over his left eye, dark green coat, crimson haramaki sash holding three katana swords at his waist'
const LEVI_LORE =
  'Levi Ackerman from Attack on Titan, sharp-featured anime captain with undercut black hair, steel-grey eyes, white cravat, Survey Corps jacket, green cloak, and dual ODM gear blades'
const KILLUA_LORE =
  'Killua Zoldyck from Hunter x Hunter, agile young anime assassin with spiky silver-white hair, sharp blue eyes, dark high-collared long-sleeve shirt under a white v-neck top, blue shorts, crackling electric aura'

const CANONICAL_CHARACTER_LORE: Record<string, string> = {
  natsu:
    'Natsu Dragneel from Fairy Tail, athletic young anime fire mage with spiky salmon-pink hair, sharp dark eyes, iconic white-and-black checkered scale scarf around his neck, open black sleeveless waistcoat with gold trim over bare muscular chest, white knee-length trousers, black open-toed sandals, red Fairy Tail guild mark on his right shoulder',
  lucy:
    'Lucy Heartfilia from Fairy Tail, expressive anime celestial spirit mage with golden blonde hair tied in side tails, warm brown eyes, iconic blue-and-white fitted sleeveless top, pleated skirt, leather belt with golden Celestial Spirit keys',
  goku: GOKU_LORE,
  sangoku: GOKU_LORE,
  'san goku': GOKU_LORE,
  'son goku': GOKU_LORE,
  kakarot: GOKU_LORE,
  gohan: GOHAN_LORE,
  sangohan: GOHAN_LORE,
  'san gohan': GOHAN_LORE,
  vegeta:
    'Vegeta from Dragon Ball, proud Saiyan prince with tall flame-shaped spiky black hair, sharp widow peak, royal blue bodysuit under white-and-gold Saiyan battle armor with shoulder pauldrons, white gloves and boots',
  luffy:
    'Monkey D. Luffy from One Piece, energetic anime pirate captain wearing his signature woven straw hat with a red ribbon, tousled black hair, small scar under his left eye, open red vest, blue denim shorts, yellow sash, and sandals',
  zoro: ZORO_LORE,
  zorro: ZORO_LORE,
  sanji:
    'Vinsmoke Sanji from One Piece, suave anime martial arts chef with blonde hair covering one eye, curled eyebrow, tailored black double-breasted suit, yellow dress shirt, black tie',
  shanks:
    'Red-Haired Shanks from One Piece, charismatic anime pirate emperor with crimson red hair, triple scar across his left eye, flowing black captain cloak, white open shirt, Gryphon saber at waist',
  ace:
    'Portgas D. Ace from One Piece, muscular anime fire pirate with wavy black hair, orange cowboy hat with smiley badges, bare chest with red bead necklace, black shorts, flame powers',
  naruto:
    'Naruto Uzumaki from Naruto, spirited anime ninja with spiky bright yellow-blond hair, cobalt blue eyes, three whisker marks on each cheek, Konoha metal headband, orange-and-black zip-up ninja jumpsuit, and ninja sandals',
  sasuke:
    'Sasuke Uchiha from Naruto, composed anime ninja with spiky black hair framing his face, dark Sharingan eyes, high-collared Uchiha outfit with rope belt and Kusanagi sword',
  kakashi:
    'Kakashi Hatake from Naruto, elite copy ninja with gravity-defying silver-grey hair, slanted Konoha headband, dark face mask covering lower face, green jonin flak vest over dark blue uniform',
  itachi:
    'Itachi Uchiha from Naruto, stoic Uchiha prodigy with black hair framed by long bangs, glowing red Sharingan eyes, black Akatsuki cloak with red clouds and high collar',
  madara:
    'Madara Uchiha from Naruto, legendary ninja warlord with long spiky black hair, crimson layered samurai battle armor over dark blue tunic',
  gojo:
    'Satoru Gojo from Jujutsu Kaisen, tall slender anime sorcerer with snow-white spiky hair, luminous sky-blue Six Eyes, dark high-necked Jujutsu High uniform jacket',
  sukuna:
    'Ryomen Sukuna from Jujutsu Kaisen, menacing King of Curses with spiked pinkish-salmon hair, black tribal curse tattoos across face and muscular body, second pair of eyes under main eyes',
  tanjiro:
    'Tanjiro Kamado from Demon Slayer, kind-hearted anime swordsman with burgundy-tipped ruffled black hair, dark red eyes, flame-like scar on his forehead, hanafuda earrings, green-and-black checkered haori coat over a dark Demon Slayer corps uniform, carrying a black Nichirin katana',
  nezuko:
    'Nezuko Kamado from Demon Slayer, anime girl with long black hair fading to flame-orange at the tips, soft pink eyes, bamboo muzzle tied with a red ribbon, pink geometric-patterned kimono with red-and-white checkered obi',
  ichigo:
    'Ichigo Kurosaki from Bleach, tall anime Soul Reaper with spiky bright orange hair, brown eyes, black shihakusho kimono robe with white sash and oversized Zangetsu cleaver sword',
  saitama:
    'Saitama from One Punch Man, anime hero with a smooth bald head, calm deadpan expression, bright yellow one-piece superhero jumpsuit with a white zipper, flowing white cape, red gloves and red boots',
  eren:
    'Eren Yeager from Attack on Titan, intense anime soldier with dark brown hair, striking green eyes, Survey Corps cropped brown leather jacket with Wings of Freedom emblem, white trousers, vertical maneuvering harness and dual blades',
  levi: LEVI_LORE,
  livai: LEVI_LORE,
  mikasa:
    'Mikasa Ackerman from Attack on Titan, agile anime soldier with chin-length black hair, dark eyes, iconic crimson red scarf, Survey Corps leather jacket and ODM gear',
  killua: KILLUA_LORE,
  kirua: KILLUA_LORE,
  deku:
    'Izuku Midoriya (Deku) from My Hero Academia, determined young hero with curly dark-green hair, freckled cheeks, dark green hero suit with red utility belt, white gloves and red armored boots',
  midoriya:
    'Izuku Midoriya (Deku) from My Hero Academia, determined young hero with curly dark-green hair, freckled cheeks, dark green hero suit with red utility belt, white gloves and red armored boots',
  asta:
    'Asta from Black Clover, muscular compact anime magic knight with spiky ash-blond hair, black headband with red Black Bull insignia, tattered black cloak, wielding a massive dark anti-magic greatsword',
  denji:
    'Denji from Chainsaw Man, wild anime devil hunter with messy blond hair, sharp teeth, white dress shirt with black tie or Chainsaw Man devil form with roaring chainsaw head and arm blades',
  guts:
    'Guts the Black Swordsman from Berserk, towering muscular dark-fantasy warrior with cropped black hair and white streak, scarred nose, black plate armor, flowing dark cape, prosthetic left iron arm, wielding the colossal Dragon Slayer slab greatsword',
  baki:
    'Baki Hanma from Baki the Grappler, hyper-muscular young underground martial artist with wavy reddish-brown hair, battle scars across his sculpted torso, white martial arts trunks',
  goldorak:
    'Goldorak (UFO Robot Grendizer), iconic giant super-robot anime mecha with horned red-and-gold head crest, silver face plate, blue-and-black armored chest with yellow crescent emblem, red-and-white spiked shoulder blades',
  grendizer:
    'Goldorak (UFO Robot Grendizer), iconic giant super-robot anime mecha with horned red-and-gold head crest, silver face plate, blue-and-black armored chest with yellow crescent emblem, red-and-white spiked shoulder blades',
  frieren:
    'Frieren, slender elven anime mage with long silver-white twin-tails, green eyes, pointed elf ears, white-and-gold striped capelet over a white tunic dress, carrying her red-gemmed golden mage staff',
  pikachu:
    'Pikachu from Pokemon, vibrant yellow electric mouse creature with long black-tipped ears, red cheek pouches, brown back stripes, and a lightning-bolt-shaped tail',
  dracaufeu:
    'Charizard (Dracaufeu) from Pokemon, powerful orange bipedal dragon creature with cream-colored underside, large leathery wings with blue-green inner membranes, and a blazing flame burning at the tip of its long tail',
  charizard:
    'Charizard (Dracaufeu) from Pokemon, powerful orange bipedal dragon creature with cream-colored underside, large leathery wings with blue-green inner membranes, and a blazing flame burning at the tip of its long tail',
  mewtwo:
    'Mewtwo from Pokemon, sleek humanoid psychic feline creature with pale lavender-grey body, twin blunt head horns, secondary neck tube, purple tail and three-fingered psychic hands',
  lucario:
    'Lucario from Pokemon, bipedal blue-and-black jackal martial arts creature with four dark aura appendages behind its head, cream chest fur, and metallic spikes on its paws and chest',
  link:
    'Link from The Legend of Zelda, agile Hylian hero with pointed ears, blonde hair, Champion tunic with leather cross-straps, Hylian shield and Master Sword',
  sonic:
    'Sonic the Hedgehog, sleek cobalt-blue anthropomorphic hedgehog with supersonic quills, emerald-green eyes, white gloves, and iconic red running shoes with white straps',
  shadow:
    'Shadow the Hedgehog, jet-black anthropomorphic hedgehog with crimson-striped quills, white chest fur, golden inhibitor rings on wrists and ankles, air shoes',
  '2b':
    'YoRHa No.2 Type B (2B) from NieR Automata, graceful android swordswoman with short silver-white bob hair, black tactical combat visor blindfold, black gothic high-slit combat dress with feather trim, wielding Virtuous Contract white katana',
  jinx:
    'Jinx from Arcane / League of Legends, lithe rebellious stateswoman with two floor-length electric-blue braids, pale skin, blue cloud tattoos on right arm and torso, cropped halter top, striped trousers',
  zig:
    'Zig the brown cartoon hyena from Zig & Sharko (Xilam 2D animated series), slender bipedal anthropomorphic cartoon hyena with warm brown fur, light tan belly and muzzle, dark brown back stripes, two tall upright pointed ears, elongated cartoon snout with round black nose tip, closed smiling toothy grin, and two oval eyes with yellow-white sclera completely enclosed by thick continuous black ink outlines, standing full-body facing forward on his feet without any pedestal',
  sharko:
    'Sharko the muscular cartoon great white shark from Zig & Sharko (Xilam 2D animated series), tall broad-shouldered bipedal anthropomorphic cartoon shark with slate blue-grey skin, bright white chest and belly, dorsal fin on his back, small oval cartoon eyes enclosed by black ink outlines, wide closed smiling white toothy shark grin facing forward (no dark gaping mouth cavity), wearing bright yellow swim trunks with red vertical stripes, standing full-body on his feet without any pedestal',
  jibanyan:
    'Jibanyan from Yo-kai Watch (Level-5 anime), cute bipedal red-orange nekomata cat yo-kai with large round head, cream-white face mask and chest, big round yellow eyes with black pupils, triangular pink ears with a notch in the left ear, yellow collar with turquoise bell, pale cream-yellow belly warmer haramaki, and two twin red tails tipped with pale blue-white flames, standing full-body with arms and twin tails clearly separated on a pure white studio background without any pedestal',
  'mark evans':
    'Mark Evans (Mamoru Endou) from Inazuma Eleven (Level-5 anime), energetic young anime soccer goalkeeper captain with spiky brown hair and two prominent side spikes, wide bright orange forehead headband, big cheerful brown eyes, smooth unified anime skin tone without harsh cheek shadow blotches, wearing the yellow-and-green Raimon goalkeeper jersey, white shorts, green-and-yellow goalkeeper gloves, holding a clean white-and-black soccer ball, standing full-body on a pure white studio background without any pedestal',
  'endou mamoru':
    'Mark Evans (Mamoru Endou) from Inazuma Eleven (Level-5 anime), energetic young anime soccer goalkeeper captain with spiky brown hair, bright orange forehead headband, Raimon goalkeeper uniform and gloves, holding a clean white-and-black soccer ball, standing full-body without any pedestal',
  'bernie zig':
    'Bernie the tiny red cartoon hermit crab from Zig & Sharko, clever small red crustacean with big glasses/eyes and conical shell',
  oggy:
    'Oggy from Oggy and the Cockroaches (Xilam cartoon), chubby light-blue bipedal cartoon cat with a big removable red ping-pong-ball nose, grey tummy patch, wide yellow eyes, black pointed ears, and expressive slapstick cartoon proportions',
  asterix:
    'Asterix the Gaul (Franco-Belgian comic/cartoon hero), short energetic cartoon Gaulish warrior with a big drooping yellow blonde mustache, winged silver helmet, black sleeveless vest, red trousers, green belt with yellow sheath and short Roman sword, and small gourde of magic potion',
  obelix:
    'Obelix the Gaul (Franco-Belgian comic/cartoon hero), tall rotund cartoon strongman with braided red hair and red mustache, bare muscular chest, iconic blue-and-white vertical striped trousers held by a green-and-gold belt, small winged helmet, carrying a sculpted stone menhir',
  tintin:
    'Tintin (Herge Franco-Belgian comic hero), young reporter with iconic upturned ginger-blonde quiff hair, round expressive face, blue sweater over white collared shirt, brown plus-fours knickerbocker trousers, white socks, accompanied by his white fox terrier Snowy (Milou)',
  'lucky luke':
    'Lucky Luke (Franco-Belgian cartoon cowboy), tall lanky cartoon cowboy with black hair forelock, white cowboy hat, red neckerchief, black sleeveless vest over yellow shirt, blue jeans and boots',
  'bob l eponge':
    'SpongeBob SquarePants, cheerful rectangular yellow sea sponge cartoon character with porous holes, huge blue eyes with three eyelashes, buck teeth, white shirt, red tie, and brown square pants with black belt and shoes',
  spongebob:
    'SpongeBob SquarePants, cheerful rectangular yellow sea sponge cartoon character with porous holes, huge blue eyes with three eyelashes, buck teeth, white shirt, red tie, and brown square pants with black belt and shoes',
  patrick:
    'Patrick Star from SpongeBob SquarePants, chubby pink cartoon starfish with thick black eyebrows and green-and-purple floral swim trunks',
  'bugs bunny':
    'Bugs Bunny from Looney Tunes, tall slender grey-and-white anthropomorphic cartoon rabbit with long upright ears, white gloves, carrot in hand, and sly toothy grin',
  'daffy duck':
    'Daffy Duck from Looney Tunes, sleek black anthropomorphic cartoon duck with bright orange bill and webbed feet and white neck ring',
  'tom et jerry':
    'Tom the grey-and-white cartoon cat and Jerry the small brown cartoon mouse from Tom and Jerry in classic slapstick cartoon style',
  homer:
    'Homer Simpson from The Simpsons, yellow-skinned cartoon father with round belly, bald head with two hair strands, white polo shirt, and blue trousers',
  bart:
    'Bart Simpson from The Simpsons, yellow-skinned cartoon boy with spiky flattop hair, red t-shirt, blue shorts, and skateboard',
  rick:
    'Rick Sanchez from Rick and Morty, lanky cartoon mad scientist with spiky pale-blue hair, unibrow, white lab coat over teal shirt, and portal gun',
  morty:
    'Morty Smith from Rick and Morty, nervous young cartoon boy with round head, brown hair, yellow t-shirt, and blue jeans',
  shrek:
    'Shrek from DreamWorks, large green cartoon ogre with trumpet-shaped ears, white tunic under brown laced vest, plaid trousers, and leather boots',
  stitch:
    'Stitch (Experiment 626) from Disney Lilo & Stitch, compact blue cartoon alien koala-like creature with large bat-like ears, dark blue eyes, wide mouth, and light blue chest patch',
  mickey:
    'Mickey Mouse from Disney, iconic anthropomorphic cartoon mouse with round black ears, red shorts with two white buttons, large yellow shoes, and white four-fingered gloves',
  donald:
    'Donald Duck from Disney, white anthropomorphic cartoon duck wearing a blue sailor shirt and cap with red bow tie and bright orange bill and webbed feet',
  dingo:
    'Goofy (Dingo) from Disney, tall lanky anthropomorphic cartoon dog with black ears, green hat, orange turtleneck, black vest, blue trousers, and big brown shoes',
  goofy:
    'Goofy from Disney, tall lanky anthropomorphic cartoon dog with black ears, green hat, orange turtleneck, black vest, blue trousers, and big brown shoes',
  minion:
    'Minion from Illumination Despicable Me, yellow cylindrical capsule-shaped cartoon creature wearing silver goggles and blue denim overalls with black gloves and boots',
  minions:
    'Minions from Illumination Despicable Me, yellow cylindrical capsule-shaped cartoon creatures wearing silver goggles and blue denim overalls',
  scooby:
    'Scooby-Doo, large brown Great Dane cartoon dog with black spots and a blue collar with an SD diamond tag',
  rayman:
    'Rayman, stylized cartoon video game hero with floating hands, white gloves, yellow-and-white sneakers, red hoodie with white ring symbol, and blonde hair',
  'crash bandicoot':
    'Crash Bandicoot, energetic orange anthropomorphic cartoon bandicoot with wide grin, Mohawk hair, blue shorts, and red-and-white sneakers',
}

const CANONICAL_TRANSFORMATION_LORE: Array<[RegExp, string]> = [
  [/\b(?:super\s*saiyan\s*blue|ssgss|ssj\s*blue|ssb)\b/i, 'transformed in Super Saiyan Blue (SSGSS) with glowing cyan-blue spiky hair, cyan eyebrows, and radiant divine blue ki aura'],
  [/\b(?:ultra\s*instinct|migatte)\b/i, 'in Mastered Ultra Instinct form with shimmering silver-white hair, piercing silver eyes, and crystalline cosmic heat aura'],
  [/\b(?:super\s*saiyan\s*rose|ssj\s*rose)\b/i, 'transformed in Super Saiyan Rose with glowing rose-pink spiky hair and dark crimson-violet aura'],
  [/\b(?:super\s*saiyan\s*4|ssj\s*4)\b/i, 'in Super Saiyan 4 form with wild shoulder-length black hair, crimson-red furred upper torso and tail, golden eyes with red eyeliner'],
  [/\b(?:super\s*saiyan\s*3|ssj\s*3)\b/i, 'in Super Saiyan 3 form with massive waist-length golden-blond spiky hair, prominent brow ridge with no eyebrows, and crackling electric golden aura'],
  [/\b(?:super\s*saiyan|ssj(?:1|2)?)\b/i, 'transformed in Super Saiyan with upright glowing golden-blond spiky hair, emerald-teal eyes, and blazing golden aura'],
  [/\b(?:gear\s*5|gear\s*fifth|nika)\b/i, 'awakened in Gear 5 Sun God Nika form with glowing pure-white cloud-like hair, floating white steam ribbon around shoulders, white outfit, and joyful expression'],
  [/\b(?:mode\s*ermite|sage\s*mode|mode\s*sennin)\b/i, 'in Sage Mode with golden-amber toad eyes and red-orange pigmentation around the eyes'],
  [/\b(?:mode\s*baryon|baryon\s*mode)\b/i, 'in Baryon Mode with blazing nine-tailed crimson energy cloak and fox-ear chakra silhouette'],
  [/\b(?:bankai)\b/i, 'in unleashed Bankai state with compressed black-and-crimson spiritual pressure and evolved zanpakuto blade'],
]

function adaptCanonicalLoreForContext(baseDesc: string, normText: string): string {
  let desc = baseDesc
  if (/\b(super\s*saiyan\s*blue|ssgss|ssj\s*blue|ssb)\b/i.test(normText)) {
    desc = desc.replace(/jet-black hair|black hair/gi, 'glowing cyan-blue Super Saiyan Blue spiky hair')
  } else if (/\b(ultra\s*instinct|migatte)\b/i.test(normText)) {
    desc = desc.replace(/jet-black hair|black hair/gi, 'shimmering silver-white Ultra Instinct hair and silver eyes')
  } else if (/\b(super\s*saiyan|ssj)\b/i.test(normText)) {
    desc = desc.replace(/jet-black hair|black hair/gi, 'glowing golden-blond Super Saiyan spiky hair and teal eyes')
  } else if (/\b(gear\s*5|gear\s*fifth|nika)\b/i.test(normText)) {
    desc = desc.replace(/tousled black hair/gi, 'glowing pure-white awakened Nika hair')
  }

  if (/\b(torse\s*nu|sans\s+haut|sans\s+t[- ]?shirt|sans\s+kimono|sans\s+veste|shirtless|bare\s*chest)\b/i.test(normText)) {
    desc = desc
      .replace(/signature bright orange martial arts gi over a royal blue undershirt/gi, 'bare muscular upper torso with battle-worn orange martial arts trousers')
      .replace(/open red vest/gi, 'bare upper torso')
  }
  if (/\b(sans\s+chapeau|without\s+(?:a\s+)?hat|no\s+hat)\b/i.test(normText)) {
    desc = desc.replace(/wearing his signature woven straw hat with a red ribbon,\s*/gi, 'bareheaded without any hat, ')
  }
  return desc
}

const NEGATIVE_CLAUSE_RULES: Array<[RegExp, string[], string]> = [
  [/\b(?:sans|pas\s+de|aucun[e]?|ni|without(?:\s+any)?|no)\s+(?:chapeau|casquette|couvre[- ]?chef|bonnet|hat|cap|headgear)\b/gi, ['hat', 'cap', 'headgear', 'straw hat'], 'bareheaded with full hair and head clearly visible'],
  [/\b(?:sans|pas\s+de|aucun[e]?|ni|without(?:\s+any)?|no)\s+(?:casque|heaume|helmet|head\s*armor)\b/gi, ['helmet', 'full-face visor', 'head armor'], 'unhelmeted bare head with face and hair clearly visible'],
  [/\b(?:sans|pas\s+de|aucun[e]?|ni|without(?:\s+any)?|no)\s+(?:lunettes?|glasses|eyewear|sunglasses)\b/gi, ['glasses', 'eyeglasses', 'sunglasses', 'spectacles'], 'unobstructed eyes with no eyewear'],
  [/\b(?:sans|pas\s+de|aucun[e]?|ni|without(?:\s+any)?|no)\s+(?:masque|bandeau|cache[- ]?oeil|mask|blindfold)\b/gi, ['mask', 'face mask', 'blindfold'], 'uncovered face and unobstructed eyes'],
  [/\b(?:sans|pas\s+de|aucun[e]?|ni|without(?:\s+any)?|no)\s+(?:barbe|moustache|poils?\s+au\s+visage|beard|mustache|facial\s*hair)\b/gi, ['beard', 'mustache', 'stubble', 'facial hair'], 'clean-shaven smooth jawline'],
  [/\b(?:sans|pas\s+de|aucun[e]?|ni|without(?:\s+any)?|no)\s+(?:cape|manteau|cloak|capelet)\b/gi, ['cape', 'cloak', 'flowing mantle'], 'clean back silhouette with no cape or cloak'],
  [/\b(?:sans|pas\s+de|aucun[e]?|ni|without(?:\s+any)?|no)\s+(?:bouclier|shield)\b/gi, ['shield', 'buckler'], 'free off-hand with no shield'],
  [/\b(?:sans|pas\s+de|aucun[e]?|ni|without(?:\s+any)?|no)\s+(?:arme[s]?|epee|sabre|katana|fusil|pistolet|weapon[s]?|sword|gun|blade)\b/gi, ['weapon', 'sword', 'blade', 'gun', 'rifle'], 'unarmed with empty hands'],
  [/\b(?:sans|pas\s+de|aucun[e]?|ni|without(?:\s+any)?|no)\s+(?:ailes?|wings?)\b/gi, ['wings', 'feathered wings', 'dragon wings'], 'wingless back anatomy'],
  [/\b(?:sans\s+haut|sans\s+t[- ]?shirt|sans\s+chemise|sans\s+veste|torse\s+nu|shirtless|bare[- ]?chested)\b/gi, ['shirt', 'jacket', 'upper tunic', 'top garment'], 'bare-chested with defined upper torso anatomy'],
]

export function extractStrictPromptConstraints(rawText: string): StrictPromptConstraints {
  const cleaned = (rawText || '').trim()
  if (!cleaned) {
    return {
      positiveTextClean: '',
      excludedItemsEn: [],
      affirmativeReplacementsEn: [],
      mandatoryAttributesEn: [],
    }
  }
  let working = stripAccents(cleaned)
  const excludedItemsEn: string[] = []
  const affirmativeReplacementsEn: string[] = []
  const mandatoryAttributesEn: string[] = []

  for (const [pattern, negTokens, affirmativeEn] of NEGATIVE_CLAUSE_RULES) {
    if (pattern.test(working)) {
      for (const tok of negTokens) {
        if (!excludedItemsEn.includes(tok)) excludedItemsEn.push(tok)
      }
      if (affirmativeEn && !affirmativeReplacementsEn.includes(affirmativeEn)) {
        affirmativeReplacementsEn.push(affirmativeEn)
      }
      working = working.replace(pattern, `, ${affirmativeEn}, `)
    }
  }

  const genericNegRe =
    /\b(?:sans|pas\s+de|aucun[e]?|without(?:\s+any)?)\s+([a-zA-Z0-9_-]+(?:\s+[a-zA-Z0-9_-]+){0,2}?)(?=\s*(?:,|;|\.|et\b|mais\b|avec\b|dans\b|sur\b|en\b|qui\b|$))/gi
  let match: RegExpExecArray | null
  while ((match = genericNegRe.exec(working)) !== null) {
    const phrase = match[1].trim().toLowerCase()
    if (/^(changer|modifier|toucher|alterer|fond\s+blanc|fond\s+noir)/.test(phrase)) continue
    if (!excludedItemsEn.includes(phrase)) excludedItemsEn.push(phrase)
  }
  working = working.replace(genericNegRe, (full, p1) =>
    /^(changer|modifier|toucher|alterer)/i.test(p1.trim()) ? full : ' ',
  )

  const norm = normalize(cleaned)
  if (/\b(?:main\s+droite|right\s+hand)\b/i.test(norm)) mandatoryAttributesEn.push('specifically in the right hand')
  if (/\b(?:main\s+gauche|left\s+hand)\b/i.test(norm)) mandatoryAttributesEn.push('specifically in the left hand')
  if (/\b(?:les\s+deux\s+mains|both\s+hands|two[- ]handed)\b/i.test(norm)) mandatoryAttributesEn.push('held with both hands')
  if (/\b(?:cicatrice\s+sur\s+l[' ]?oeil\s+gauche|scar\s+on\s+left\s+eye)\b/i.test(norm)) mandatoryAttributesEn.push('scar specifically over the left eye')
  if (/\b(?:cicatrice\s+sur\s+l[' ]?oeil\s+droit|scar\s+on\s+right\s+eye)\b/i.test(norm)) mandatoryAttributesEn.push('scar specifically over the right eye')

  for (const [transRe, transDesc] of CANONICAL_TRANSFORMATION_LORE) {
    if (transRe.test(norm) && !mandatoryAttributesEn.includes(transDesc)) {
      mandatoryAttributesEn.push(transDesc)
    }
  }

  const positiveTextClean = working
    .replace(/\s*,\s*,+/g, ', ')
    .replace(/\s{2,}/g, ' ')
    .replace(/^[\s,.;:-]+|[\s,.;:-]+$/g, '')
    .trim()

  return {
    positiveTextClean: positiveTextClean || cleaned,
    excludedItemsEn,
    affirmativeReplacementsEn,
    mandatoryAttributesEn,
  }
}

const FR_TO_EN_PHRASES: Array<[RegExp, string]> = [
  [/\b(?:fais[- ]?moi|fait[- ]?moi|cree[- ]?moi|creer|genere[- ]?moi|generer|dessine[- ]?moi|je\s+veux|je\s+voudrais|peux[- ]?tu\s+faire)\b/gi, ''],
  [/\bavec\s+des\s+textures?\s+de\s+personne\s+reelle\b/gi, 'with photorealistic real human skin textures and natural pores'],
  [/\btextures?\s+de\s+personne\s+reelle\b/gi, 'photorealistic real human skin textures and natural pores'],
  [/\btextures?\s+reelles?\b/gi, 'authentic physical real-world textures'],
  [/\bpersonne\s+reelle\b/gi, 'real living human person'],
  [/\bpersonnage\s+reel\b/gi, 'real-life human character'],
  [/\bun\s+perso\s+d[' ]?anime\b/gi, 'an authentic anime character'],
  [/\bun\s+personnage\s+d[' ]?anime\b/gi, 'an authentic anime character'],
  [/\bun\s+perso\s+anime\b/gi, 'an authentic anime character'],
  [/\bun\s+personnage\s+anime\b/gi, 'an authentic anime character'],
  [/\bun\s+perso\s+cartoon\b/gi, 'an expressive 3D cartoon character'],
  [/\bun\s+personnage\s+cartoon\b/gi, 'an expressive 3D cartoon character'],
  [/\ben\s+figurine\s+cartoon\b/gi, 'transformed into a stylized 3D cartoon collectible figurine'],
  [/\ben\s+cartoon\s+figurine\b/gi, 'transformed into a stylized 3D cartoon collectible figurine'],
  [/\bfigurine\s+cartoon\b/gi, 'stylized 3D cartoon collectible figurine'],
  [/\bcartoon\s+figurine\b/gi, 'stylized 3D cartoon collectible figurine'],
  [/\ben\s+figurine\b/gi, 'as a sculpted 3D collectible figurine'],
  [/\ben\s+funko\s*pop\b/gi, 'as a stylized Funko Pop vinyl collectible figurine with oversized head and glossy black button eyes'],
  [/\ben\s+cartoon\b/gi, 'in expressive 3D cartoon animation style'],
  [/\ben\s+dessin\s+anime\b/gi, 'in vibrant cartoon animation style'],
  [/\ben\s+style\s+cartoon\b/gi, 'in expressive 3D cartoon animation style'],
  [/\ben\s+style\s+pixar\b/gi, 'in Pixar/Disney 3D feature animation style'],
  [/\ben\s+pixar\b/gi, 'in Pixar/Disney 3D feature animation style'],
  [/\ben\s+chibi\b/gi, 'in cute super-deformed chibi figure style'],
  [/\ben\s+peluche\b/gi, 'as a soft stitched plush toy'],
  [/\ben\s+jouet\b/gi, 'as a molded plastic articulated toy figure'],
  [/\ben\s+pate\s+a\s+modeler\b/gi, 'in handcrafted stop-motion claymation plasticine style'],
  [/\ben\s+lego\b/gi, 'as an articulated LEGO minifigure'],
  [/\ben\s+low[- ]?poly\b/gi, 'in crisp faceted low-poly 3D game art style'],
  [/\ben\s+voxel\b/gi, 'in cubic 3D voxel art style'],
  [/\ben\s+bd\b/gi, 'in Franco-Belgian comic book illustration style'],
  [/\ben\s+caricature\b/gi, 'as an expressive stylized 3D caricature'],
  [/\btransforme\s+en\b/gi, 'transformed into'],
  [/\btransformer\s+en\b/gi, 'transformed into'],
  [/\bchanger\s+en\b/gi, 'transformed into'],
  [/\bchange\s+en\b/gi, 'transformed into'],
  [/\ben\s+anime\b/gi, 'in authentic anime style'],
  [/\ben\s+manga\b/gi, 'in authentic manga style'],
  [/\bun\s+perso\b/gi, 'a character'],
  [/\bun\s+personnage\b/gi, 'a character'],
  [/\bune\s+personne\b/gi, 'a real person'],
  [/\bqui\s+marche\b/gi, 'walking in a natural balanced stride'],
  [/\bqui\s+court\b/gi, 'running dynamically with athletic momentum'],
  [/\bqui\s+danse\b/gi, 'performing an expressive dance pose'],
  [/\bqui\s+saute\b/gi, 'leaping mid-air in a dynamic jump'],
  [/\bqui\s+vole\b/gi, 'floating and flying gracefully mid-air'],
  [/\bqui\s+se\s+bat\b/gi, 'in a dynamic martial combat stance'],
  [/\bqui\s+lance\s+du\s+feu\b/gi, 'casting swirling incandescent flames from their hands'],
  [/\ben\s+feu\b/gi, 'wreathed in dynamic glowing flames'],
  [/\bde\s+feu\b/gi, 'of fire'],
  [/\bde\s+glace\b/gi, 'of frost and crystalline ice'],
  [/\bde\s+foudre\b/gi, 'of crackling lightning'],
  [/\bd[' ]?ombre\b/gi, 'of shadow'],
  [/\bchevalier\s+noir\b/gi, 'dark armored knight'],
  [/\bchevalier\b/gi, 'armored knight'],
  [/\bguerrier\b/gi, 'warrior'],
  [/\bguerriere\b/gi, 'female warrior'],
  [/\bmage\b/gi, 'arcane mage'],
  [/\bsorcier\b/gi, 'sorcerer'],
  [/\bsorciere\b/gi, 'sorceress'],
  [/\bsamourai\b/gi, 'samurai'],
  [/\bchapeau\s+de\s+paille\b/gi, 'iconic straw hat'],
  [/\bcheveux\s+roses?\b/gi, 'spiky salmon-pink hair'],
  [/\bcheveux\s+blonds?\b/gi, 'golden blonde hair'],
  [/\bcheveux\s+noirs?\b/gi, 'jet-black hair'],
  [/\bcheveux\s+blancs?\b/gi, 'silver-white hair'],
  [/\bcheveux\s+rouges?\b/gi, 'crimson red hair'],
  [/\bcheveux\s+bleus?\b/gi, 'cobalt blue hair'],
  [/\byeux\s+bleus?\b/gi, 'vivid blue eyes'],
  [/\byeux\s+verts?\b/gi, 'emerald green eyes'],
  [/\byeux\s+rouges?\b/gi, 'glowing crimson eyes'],
  [/\bveste\s+noire?\b/gi, 'tailored black jacket'],
  [/\bveste\s+rouge\b/gi, 'crimson jacket'],
  [/\bmanteau\s+long\b/gi, 'long flowing coat'],
  [/\barmure\s+complete\b/gi, 'full articulated plate armor'],
  [/\barmure\b/gi, 'ornate armor'],
  [/\bepee\b/gi, 'sword'],
  [/\bkatana\b/gi, 'forged katana blade'],
  [/\bbaton\s+magique\b/gi, 'arcane staff'],
  [/\bdans\s+une\s+foret\b/gi, 'in an atmospheric ancient forest'],
  [/\bsur\s+une\s+falaise\b/gi, 'standing on a dramatic rocky cliffside'],
  [/\bdans\s+une\s+ville\b/gi, 'in a detailed urban street environment'],
  [/\bde\s+nuit\b/gi, 'at night under dramatic moonlight'],
  [/\bau\s+coucher\s+du\s+soleil\b/gi, 'at golden hour sunset'],
  [/\bportrait\s+d[' ]?un[e]?\b/gi, 'portrait of a'],
  [/\bdans\s+son\s+atelier\b/gi, 'in his traditional workshop'],
  [/\bsans\s+changer\s+le\s+reste\b/gi, 'without altering any other aspect of the subject or scene'],
  [/\bmodifie\s+la\s+couleur\b/gi, 'modify the color'],
  [/\bchange\s+la\s+couleur\b/gi, 'change the color'],
  [/\bbleu\s+nuit\b/gi, 'midnight blue'],
  [/\bvieil(?:le)?\b|\bvieux\b/gi, 'elderly'],
  [/\bhorloger\b/gi, 'master watchmaker'],
  [/\bsuisse\b/gi, 'Swiss'],
  [/\batelier\b/gi, 'artisan workshop'],
  [/\bchange\s+sa\b/gi, 'change their'],
  [/\bchange\s+son\b/gi, 'change their'],
  [/\bajoute\s+un[e]?\b/gi, 'add a'],
  [/\benleve\s+le\b/gi, 'remove the'],
  [/\benleve\s+la\b/gi, 'remove the'],
  [/\bgarde\s+le\s+meme\b/gi, 'preserve the exact same'],
]

const FR_STOPWORD_CLEANUP: Array<[RegExp, string]> = [
  [/\bde\s+sa\b|\bde\s+son\b/gi, 'of their'],
  [/\bsa\b|\bson\b/gi, 'their'],
  [/\bd[' ]?un[e]?\b/gi, 'of a'],
  [/\bavec\b/gi, 'with'],
  [/\bsans\b/gi, 'without'],
  [/\bdans\b/gi, 'in'],
  [/\bsur\b/gi, 'on'],
  [/\bsous\b/gi, 'under'],
  [/\bdevant\b/gi, 'in front of'],
  [/\bderriere\b/gi, 'behind'],
  [/\bentre\b/gi, 'between'],
  [/\bpour\b/gi, 'for'],
  [/\bmais\b/gi, 'but'],
  [/\bet\b/gi, 'and'],
  [/\bou\b/gi, 'or'],
  [/\ben\b/gi, 'into'],
  [/\btres\b/gi, 'very'],
  [/\bplus\b/gi, 'more'],
  [/\bmoins\b/gi, 'less'],
  [/\bgrand[e]?\b/gi, 'tall'],
  [/\bpetit[e]?\b/gi, 'small'],
  [/\bbeau\b|\bbelle\b/gi, 'striking'],
  [/\bsombre\b/gi, 'dark'],
  [/\blumineux\b|\blumineuse\b/gi, 'luminous'],
  [/\brealiste\b/gi, 'photorealistic'],
  [/\brouge[s]?\b/gi, 'crimson red'],
  [/\bbleu[e]?s?\b/gi, 'deep blue'],
  [/\bvert[e]?s?\b/gi, 'emerald green'],
  [/\bnoir[e]?s?\b/gi, 'obsidian black'],
  [/\bblanc(?:he)?s?\b/gi, 'pure white'],
  [/\bdore[e]?s?\b/gi, 'burnished gold'],
  [/\bargente[e]?s?\b/gi, 'polished silver'],
  [/\bviolet(?:te)?s?\b/gi, 'royal violet'],
  [/\bhomme\b/gi, 'man'],
  [/\bfemme\b/gi, 'woman'],
  [/\bgarcon\b/gi, 'young man'],
  [/\bfille\b/gi, 'young woman'],
  [/\bvisage\b/gi, 'face'],
  [/\bregard\b/gi, 'gaze'],
  [/\bsourire\b/gi, 'confident smile'],
  [/\bmain[s]?\b/gi, 'hands'],
  [/\bbras\b/gi, 'arms'],
  [/\bjambes?\b/gi, 'legs'],
  [/\bcheveux\b/gi, 'hair'],
  [/\byeux\b/gi, 'eyes'],
  [/\bpeau\b/gi, 'skin'],
  [/\btenue\b|\bvetements?\b|\bhabits?\b/gi, 'outfit'],
  [/\bveste\b/gi, 'jacket'],
  [/\bmanteau\b/gi, 'coat'],
  [/\bpantalon\b/gi, 'trousers'],
  [/\bchaussures?\b/gi, 'footwear'],
  [/\bchapeau\b/gi, 'hat'],
  [/\blunettes?\b/gi, 'glasses'],
  [/\bmontre\b/gi, 'mechanical watch'],
  [/\bvoiture\b/gi, 'car'],
  [/\bmoto\b/gi, 'motorcycle'],
  [/\bvelo\b/gi, 'bicycle'],
  [/\bmaison\b/gi, 'house'],
  [/\bchateau\b/gi, 'castle'],
  [/\bpaysage\b/gi, 'landscape'],
  [/\bmontagne[s]?\b/gi, 'mountains'],
  [/\bmer\b|\bocean\b/gi, 'ocean'],
  [/\bplage\b/gi, 'coastal beach'],
  [/\bforet\b/gi, 'forest'],
  [/\bchat\b/gi, 'cat'],
  [/\bchien\b/gi, 'dog'],
  [/\bloup\b/gi, 'wolf'],
  [/\bdragon\b/gi, 'dragon'],
  [/\boiseau\b/gi, 'bird'],
]

export function translateFrenchSubjectToEnglish(rawText: string): string {
  const trimmed = (rawText || '').trim()
  if (!trimmed) return ''
  const norm = normalize(trimmed)
  const constraints = extractStrictPromptConstraints(trimmed)

  const canonicalMatches: string[] = []
  for (const [key, desc] of Object.entries(CANONICAL_CHARACTER_LORE)) {
    const re = new RegExp(`\\b${key}\\b`, 'i')
    if (re.test(norm)) {
      const adapted = adaptCanonicalLoreForContext(desc, norm)
      if (!canonicalMatches.includes(adapted)) {
        canonicalMatches.push(adapted)
      }
    }
  }

  let working = stripAccents(constraints.positiveTextClean || trimmed)
  for (const [pattern, repl] of FR_TO_EN_PHRASES) {
    working = working.replace(pattern, repl)
  }
  for (const [pattern, repl] of FR_STOPWORD_CLEANUP) {
    working = working.replace(pattern, repl)
  }

  working = working
    .replace(/\b(un|une)\b/gi, 'a')
    .replace(/\b(le|la|les)\b/gi, 'the')
    .replace(/\b(du|des|de la|de l')\b/gi, 'of the')
    .replace(/\s+([,.;!?])/g, '$1')
    .replace(/\s{2,}/g, ' ')
    .replace(/^[\s,.;:-]+|[\s,.;:-]+$/g, '')
    .trim()

  const extraLocks: string[] = []
  for (const attr of constraints.mandatoryAttributesEn) {
    if (!working.toLowerCase().includes(attr.toLowerCase())) {
      extraLocks.push(attr)
    }
  }
  const extraStr = extraLocks.length > 0 ? ` (${extraLocks.join(', ')})` : ''

  if (canonicalMatches.length > 0) {
    const canonStr = canonicalMatches.join('; ')
    if (working.split(/\s+/).filter(Boolean).length <= 4) {
      return `${canonStr}${extraStr}`
    }
    return `${canonStr} — ${working}${extraStr}`
  }

  return `${working || trimmed}${extraStr}`
}

export type UniversalStyleClause = {
  hasStyleClause: boolean
  isTransformationVerb: boolean
  isRealOverride: boolean
  stylePhraseRaw: string | null
  coreSubjectClean: string
}

const RECOGNIZED_VISUAL_STYLE_CLAUSE_RE =
  /\b(anime|anim[eé]|manga|manhwa|webtoon|shonen|shojo|seinen|chibi|kawaii|cel[- ]?shad(?:ed|ing)|ghibli|pixar|disney|dreamworks|illumination|cartoon|dessin\s*anim[eé]|toon|looney\s*tunes|tex\s*avery|hanna[- ]?barbera|xilam|bande\s*dessin[eé]e|\bbd\b|comics?|franco[- ]?belge|figurine|funko(?:\s*pop)?|nendoroid|statuette|action\s*figure|jouet|toy|peluche|plush(?:ie)?|p[aâ]te\s+[aà]\s+modeler|clay(?:mation)?|plasticine|aardman|stop[- ]?motion|low[- ]?poly|voxel|lego|playmobil|minecraft|roblox|pixel\s*art|caricature|aquarelle|watercolor|peinture|oil\s*painting|croquis|sketch|cyberpunk|steampunk|personne\s+r[eé]elle|vrai\s+humain|vraie\s+personne|real\s+person|real\s+human|r[eé]aliste|photor[eé]aliste|photorealistic|live[- ]?action|peau\s+r[eé]elle)\b/i

const MATERIAL_COLOR_OR_SHAPE_ONLY_RE =
  /^(?:(?:du|de\s+la|des|un|une|le|la|les)\s+)?(?:verre|cristal|crystal|porcelaine|c[eé]ramique|terre\s+cuite|argile|bois|ch[eê]ne|noyer|acajou|bambou|m[eé]tal|acier|inox|fer|aluminium|cuivre|laiton|bronze|or|argent|platine|titane|plastique|pla|petg|abs|r[eé]sine|epoxy|silicone|caoutchouc|cuir|tissu|velours|soie|laine|marbre|pierre|granit|b[eé]ton| pl[aâ]tre|cire|glace|diamant|rubis|[eé]meraude|saphir|quartz|am[eé]thyste|jade|obsidienne|nacre|blanc(?:he)?s?|noir[e]?s?|rose[s]?|rouge[s]?|bleu[e]?s?|vert[e]?s?|jaune[s]?|orange[s]?|violet(?:te)?s?|mauve[s]?|gris[e]?s?|dor[eé][e]?s?|argent[eé][e]?s?|transparent[e]?s?|translucide[s]?|opaque[s]?|mat[e]?s?|brillant[e]?s?|satin[eé][e]?s?|c[oœ]ur|coeur|anatomique|emoji|[eé]moji|[eé]toile|spirale)(?:\s+(?:blanc(?:he)?s?|noir[e]?s?|rose[s]?|rouge[s]?|bleu[e]?s?|vert[e]?s?|jaune[s]?|dor[eé][e]?s?|argent[eé][e]?s?|transparent[e]?s?|translucide[s]?|mat[e]?s?|brillant[e]?s?|poli[e]?s?|bross[eé][e]?s?|grav[eé][e]?s?|anatomique|emoji|[eé]moji|cristal|verre))*$/i

export function extractUniversalStyleClause(rawText: string): UniversalStyleClause {
  const text = (rawText || '').trim()
  const result: UniversalStyleClause = {
    hasStyleClause: false,
    isTransformationVerb: false,
    isRealOverride: false,
    stylePhraseRaw: null,
    coreSubjectClean: text,
  }
  if (!text) return result

  const isGenuineVisualStyle = (candidate: string): boolean => {
    const cleanCand = normalize(candidate)
    if (!cleanCand) return false
    if (MATERIAL_COLOR_OR_SHAPE_ONLY_RE.test(cleanCand)) return false
    return RECOGNIZED_VISUAL_STYLE_CLAUSE_RE.test(cleanCand)
  }

  const mTrans = text.match(
    /\b(?:transform(?:e|er|ee?|es)?|chang(?:e|er|ee?|es)?|converti(?:s|r|e|es)?|adapt(?:e|er|ee?|es)?|met(?:s|tre)|pass(?:e|er)|rend(?:s|re))\s+((?:[\wÀ-ÿ'’_-]+\s+){0,6}?)en\s+([^,.;!?]+?)(?=\s+(?:qui\s+|avec\s+|sans\s+|dans\s+un|sur\s+fond)|[,.;!?]|$)/i,
  )
  if (mTrans && mTrans.index !== undefined) {
    const midSubj = (mTrans[1] || '').trim()
    const styleRaw = (mTrans[2] || '').trim()
    if (isGenuineVisualStyle(styleRaw)) {
      const prefix = text.slice(0, mTrans.index).trim()
      const suffix = text.slice(mTrans.index + mTrans[0].length).trim()
      const coreClean = [prefix, midSubj, suffix].filter(Boolean).join(' ').trim() || midSubj || text
      const isReal = /\b(personne\s+reelle|vrai\s+humain|vraie\s+personne|real\s+person|real\s+human|realiste|photorealiste|live[- ]?action|peau\s+reelle)\b/i.test(
        normalize(styleRaw),
      )
      return {
        hasStyleClause: true,
        isTransformationVerb: true,
        isRealOverride: isReal,
        stylePhraseRaw: styleRaw,
        coreSubjectClean: coreClean,
      }
    }
  }

  const mStyle = text.match(
    /\b(?:dans\s+le\s+style(?:\s+de|\s+d['’])?|en\s+style|style|fa[cç]on|[aà]\s+la\s+mani[eè]re\s+de|comme\s+dans|version|esth[eé]tique|rendu)\s+([^,.;!?]+?)(?=\s+(?:qui\s+|avec\s+|sans\s+|dans\s+un|sur\s+fond)|[,.;!?]|$)/i,
  )
  if (mStyle && mStyle.index !== undefined) {
    const styleRaw = (mStyle[1] || '').trim()
    if (isGenuineVisualStyle(styleRaw)) {
      const coreClean = `${text.slice(0, mStyle.index).trim()} ${text.slice(mStyle.index + mStyle[0].length).trim()}`.trim()
      const isReal = /\b(personne\s+reelle|vrai\s+humain|vraie\s+personne|real\s+person|real\s+human|realiste|photorealiste|live[- ]?action|peau\s+reelle)\b/i.test(
        normalize(styleRaw),
      )
      return {
        hasStyleClause: true,
        isTransformationVerb: true,
        isRealOverride: isReal,
        stylePhraseRaw: styleRaw,
        coreSubjectClean: coreClean || text,
      }
    }
  }

  const mEn = text.match(
    /(?<=\S)\s+\ben\s+(?!forme\b|formes\b|taille\b|coupe\b|biseau\b|relief\b|gravure\b|train\b|feu\b|flammes?\b|col[eè]re\b|pleurs?\b|larmes?\b|souriant\b|criant\b|courant\b|marchant\b|volant\b|sautant\b|dormant\b|dansant\b|nageant\b|tirant\b|frappant\b|mouvement\b|action\b|marche\b|course\b|vol\b|combat\b|bataille\b|guerre\b|garde\b|posture\b|pose\b|[eé]quilibre\b|l[eé]vitation\b|chute\b|vie\b|paix\b|danger\b|urgence\b|3d\b|2d\b|4k\b|8k\b|16k\b|hd\b|uhd\b|pbr\b|pied\b|entier\b|buste\b|gros\s+plan\b|plan\s+large\b|contre[- ]?plong[eé]e\b|plong[eé]e\b|profil\b|face\b|dos\b|couleurs?\b|noir\s+et\s+blanc\b|ligne\b|direct\b|jeu\b|vrai\b|armure\b|costume\b|veste\b|robe\b|short\b|pantalon\b|jean\b|t[- ]?shirt\b|chemise\b|pull\b|manteau\b|uniforme\b|maillot\b|kimono\b|smoking\b|pyjama\b|surv[eê]tement\b|sweat\b|bikini\b|tenue\b|bottes?\b|baskets?\b|chaussures?\b|cape\b|blouse\b|tablier\b|casque\b|plein(?:e)?\b|haut\b|bas\b|avant\b|arri[eè]re\b|milieu\b|centre\b|diagonale\b|cercle\b|studio\b|int[eé]rieur\b|ext[eé]rieur\b|ville\b|for[eê]t\b|mer\b|oc[eé]an\b|montagne\b|plage\b|d[eé]sert\b|espace\b|orbite\b|france\b|espagne\b|italie\b|allemagne\b|angleterre\b|japon\b|chine\b|cor[eé]e\b|am[eé]rique\b|europe\b|asie\b|afrique\b|[eé]t[eé]\b|hiver\b|automne\b|printemps\b|nuit\b|jour\b|soir[eé]e\b|matin[eé]e\b|[0-9]{3,4}\b|anglais\b|fran[cç]ais\b|japonais\b|un\b|une\b|le\b|la\b|les\b|des\b|du\b|de\b|ce\b|cet\b|cette\b|ces\b|son\b|sa\b|ses\b|mon\b|ma\b|mes\b|ton\b|ta\b|tes\b|leur\b|leurs\b|soi\b|lui\b|elle\b|eux\b|elles\b|qui\b|que\b|quoi\b|dont\b|o[uù]\b|plus\b|moins\b|tant\b|outre\b|effet\b|fait\b|cas\b)([a-zA-ZÀ-ÿ0-9'’\-]+(?:\s+[a-zA-ZÀ-ÿ0-9'’\-]+){0,5}?)(?=\s+(?:qui\s+|avec\s+|sans\s+|dans\s+un|sur\s+fond)|[,.;!?]|$)/i,
  )
  if (mEn && mEn.index !== undefined) {
    const styleRaw = (mEn[1] || '').trim()
    if (isGenuineVisualStyle(styleRaw)) {
      const coreClean = `${text.slice(0, mEn.index).trim()} ${text.slice(mEn.index + mEn[0].length).trim()}`.trim()
      const isReal = /\b(personne\s+reelle|vrai\s+humain|vraie\s+personne|real\s+person|real\s+human|realiste|photorealiste|live[- ]?action|peau\s+reelle)\b/i.test(
        normalize(styleRaw),
      )
      return {
        hasStyleClause: true,
        isTransformationVerb: true,
        isRealOverride: isReal,
        stylePhraseRaw: styleRaw,
        coreSubjectClean: coreClean || text,
      }
    }
  }

  return result
}

export function analyzePromptOntologySync(
  rawPrompt: string,
  options: {
    targetModule?: 'image' | '3d' | 'video' | 'drawing'
    modeHint?: 'create' | 'edit' | 'replicate' | 'style_transfer' | 'modification' | 'reproduction' | 'creation'
    requestedStyle?: string
    hasReference?: boolean
    conversationContext?: string
  } = {},
): CognitivePromptDecision {
  const cleanRaw = (rawPrompt || '').trim()
  const targetModule = options.targetModule ?? 'image'
  const norm = normalize(cleanRaw)
  const ctxNorm = normalize(options.conversationContext || '')
  const reqStyleNorm = normalize(options.requestedStyle || '')
  const strictConstraints = extractStrictPromptConstraints(cleanRaw)
  const syntacticStyle = extractUniversalStyleClause(cleanRaw)

  const explicitRealTexturesOverride =
    EXPLICIT_REAL_TEXTURES_OVERRIDE_RE.test(norm) || syntacticStyle.isRealOverride
  const hasAnimeStyleSelected = /(anime|manga|ghibli|cel|cartoon|figurine|funko|chibi|pixar|disney|clay|peluche|low-poly|low_poly|voxel)/.test(reqStyleNorm)
  const explicitStylizedOverride =
    EXPLICIT_STYLIZED_OVERRIDE_RE.test(norm) ||
    hasAnimeStyleSelected ||
    (syntacticStyle.hasStyleClause && !explicitRealTexturesOverride)
  const rawStylizedSubmode = detectRequestedStylizedSubmode(cleanRaw)

  const isStandaloneStyleCreation =
    !options.hasReference &&
    !ctxNorm &&
    options.modeHint !== 'edit' &&
    options.modeHint !== 'modification' &&
    (explicitStylizedOverride || syntacticStyle.isTransformationVerb) &&
    /\b(?:transform(?:e|er)|chang(?:e|er)|converti(?:s|r)|adapt(?:e|er))\b/i.test(norm) &&
    !/\b(?:garde|conserve|sans\s+changer|meme\s+(?:personnage|sujet|objet|pose)|couleur|cheveux|yeux|veste)\b/i.test(norm)

  const isReproduction =
    options.modeHint === 'replicate' ||
    options.modeHint === 'reproduction' ||
    REPRODUCTION_INTENT_RE.test(norm)
  const isModification =
    !isReproduction &&
    !isStandaloneStyleCreation &&
    (options.modeHint === 'edit' ||
      options.modeHint === 'modification' ||
      options.modeHint === 'style_transfer' ||
      MODIFICATION_INTENT_RE.test(norm))

  const operationMode: PromptOperationMode = isReproduction
    ? 'reproduction'
    : isModification
      ? 'modification'
      : 'creation'

  let canonicalSubjectName: string | null = null
  for (const key of Object.keys(CANONICAL_CHARACTER_LORE)) {
    const re = new RegExp(`\\b${key}\\b`, 'i')
    if (re.test(norm) || (isModification && re.test(ctxNorm))) {
      canonicalSubjectName = key
      break
    }
  }

  const coreSubjectNorm = normalize(syntacticStyle.coreSubjectClean || cleanRaw)
  const promptWithoutStyleOverride = coreSubjectNorm
    .replace(new RegExp(EXPLICIT_STYLIZED_OVERRIDE_RE.source, 'gi'), ' ')
    .replace(new RegExp(EXPLICIT_REAL_TEXTURES_OVERRIDE_RE.source, 'gi'), ' ')
  const hasStyleTransformationClause =
    syntacticStyle.hasStyleClause ||
    /\b(?:en\s+(?:style\s+|version\s+|mode\s+)?(?:anime|anim[eé]|manga|cartoon|dessin\s+anim[eé]|toon|ghibli|pixar|disney|dreamworks|chibi|kawaii|pixel\s*art|low[- ]?poly|voxel|bd|bande\s+dessin[eé]e|comics?|figurine(?:\s+cartoon)?|funko(?:\s*pop)?|pop\s*vinyl|nendoroid|jouet|toy|action\s+figure|peluche|plush(?:ie)?|p[aâ]te\s+[aà]\s+modeler|clay(?:mation)?|stop[- ]?motion|lego|playmobil|caricature|statue(?:tte)?)|(?:transform(?:e|er|ee?)|chang(?:e|er|ee?)|converti(?:s|r)?|adapt(?:e|er|ee?)|met(?:s|tre)|pass(?:e|er))\s+(?:[\w'’_-]+\s+){0,6}en\s+)\b/i.test(
      norm,
    )
  const hasExplicitRealSubjectPhrase =
    /\b(personnage\s+reel|personne\s+reelle|humain\s+reel|vrai[e]?\s+(?:personne|humain|homme|femme|acteur|actrice|chanteur|joueur|president|celebrit[eé])|real\s+(?:person|human|character|actor|celebrity)|homme|femme|pompier|policier|medecin|boulanger|soldat|footballeur|mbappe|zidane|ronaldo|messi|macron)\b/i.test(
      promptWithoutStyleOverride,
    )
  const hasIntrinsicAnimeEntity = ANIME_ONTOLOGY_RE.test(promptWithoutStyleOverride) && !hasExplicitRealSubjectPhrase
  const hasAnimeSignalInPrompt =
    hasIntrinsicAnimeEntity ||
    (ANIME_ONTOLOGY_RE.test(norm) && !hasExplicitRealSubjectPhrase && !hasStyleTransformationClause)
  const hasAnimeSignalInCtx = isModification && ANIME_ONTOLOGY_RE.test(ctxNorm)

  const isGameAsset =
    (GAME_ASSET_RE.test(norm) || /(pixel|isometric|low-poly|low_poly)/.test(reqStyleNorm)) &&
    !hasExplicitRealSubjectPhrase &&
    !hasStyleTransformationClause
  const isMechanicalCad = MECHANICAL_CAD_RE.test(norm)
  const isInanimateVesselOrObject =
    /\b(vase|vases|flacon|carafe|coupe|calice|bol|pot|urne|bocal|tasse|bouteille|verre\s+en\s+forme|coeur\s+en\s+(?:verre|cristal)|bijou|bague|pendentif|collier|medaillon|trophee|coffret|bougie|chandelier|lampe|miroir|sablier|sculpture\s+d[' ]objet|objet\s+decoratif)\b/i.test(
      norm,
    ) && !/\b(personnage|personne|humain|homme|femme|garcon|fille|guerrier|mage)\b/i.test(norm)
  const isCharacter =
    !isInanimateVesselOrObject &&
    (CHARACTER_SUBJECT_RE.test(norm) || hasAnimeSignalInPrompt || hasAnimeSignalInCtx)

  let subjectOntology: SubjectOntology
  let nativeOntology: 'anime_stylized' | 'real_photorealistic' | 'game_stylized' | 'engineering_cad'
  if (isMechanicalCad) {
    subjectOntology = 'mechanical_cad_engineering'
    nativeOntology = 'engineering_cad'
  } else if (isInanimateVesselOrObject) {
    subjectOntology = 'real_world_object_or_scene'
    nativeOntology = 'real_photorealistic'
  } else if ((hasExplicitRealSubjectPhrase || (hasStyleTransformationClause && !hasIntrinsicAnimeEntity && isCharacter)) && explicitStylizedOverride) {
    subjectOntology = 'real_human_subject'
    nativeOntology = 'real_photorealistic'
  } else if (isGameAsset) {
    subjectOntology = 'game_character_or_asset'
    nativeOntology = 'game_stylized'
  } else if (hasAnimeSignalInPrompt || hasAnimeSignalInCtx) {
    subjectOntology = 'anime_manga_character'
    nativeOntology = 'anime_stylized'
  } else if (isCharacter) {
    subjectOntology = 'real_human_subject'
    nativeOntology = 'real_photorealistic'
  } else {
    subjectOntology = 'real_world_object_or_scene'
    nativeOntology = 'real_photorealistic'
  }

  let effectiveRenderMode: EffectiveRenderMode
  let badgeLabelFr: string
  let styleDirectiveEn: string
  if (subjectOntology === 'anime_manga_character') {
    if (explicitRealTexturesOverride) {
      effectiveRenderMode = 'hybrid_anime_with_real_textures'
      badgeLabelFr = 'Animé / Cartoon + Textures Réelles (Override)'
      styleDirectiveEn =
        'HYBRID ANIME/CARTOON + REAL HUMAN TEXTURES: preserve the iconic character silhouette, hairstyle, and canonical costume, while applying photorealistic real human skin pores, subsurface scattering, and physical fabric weaves.'
    } else if (explicitStylizedOverride && ['cartoon_figurine', 'figurine_toy', 'clay_or_plush', 'lowpoly_voxel'].includes(rawStylizedSubmode)) {
      effectiveRenderMode = 'native_anime_stylized'
      badgeLabelFr = `Personnage Animé/Cartoon -> ${rawStylizedSubmode}`
      styleDirectiveEn =
        `STYLIZED CHARACTER ADAPTATION (${rawStylizedSubmode.toUpperCase()}): preserve the character's iconic identity, colors, and silhouette while rendering in authentic ${rawStylizedSubmode} 3D materials and proportions (DO NOT force realistic human skin pores).`
    } else if (rawStylizedSubmode === 'cartoon_3d') {
      effectiveRenderMode = 'native_anime_stylized'
      badgeLabelFr = 'Style Cartoon / Dessin Animé Natif Fidèle'
      styleDirectiveEn =
        'NATIVE CARTOON / ANIMATED STYLIZED FIDELITY: render directly in authentic 3D cartoon aesthetics with expressive cartoon proportions, iconic silhouette, vibrant cartoon colors, and smooth stylized cartoon surfaces (DO NOT force realistic human skin pores or live-action proportions).'
    } else {
      effectiveRenderMode = 'native_anime_stylized'
      badgeLabelFr = 'Style Animé / Manga Natif Fidèle'
      styleDirectiveEn =
        'NATIVE ANIME / MANGA STYLIZED FIDELITY: render directly in authentic anime/cel-shaded aesthetics with anime facial proportions, sculpted anime hair locks, vivid official colors, and smooth stylized anime skin (DO NOT force realistic human skin pores).'
    }
  } else if (subjectOntology === 'game_character_or_asset') {
    if (explicitRealTexturesOverride) {
      effectiveRenderMode = 'hybrid_anime_with_real_textures'
      badgeLabelFr = 'Personnage Jeu -> Textures Réelles (Override)'
      styleDirectiveEn = 'HYBRID GAME CHARACTER + REAL TEXTURES: preserve iconic game character silhouette with photorealistic surface micro-textures.'
    } else {
      effectiveRenderMode = 'native_game_stylized'
      badgeLabelFr = 'Asset / Personnage Jeu Vidéo Stylisé'
      styleDirectiveEn = 'NATIVE GAME ASSET STYLIZED: crisp silhouette, expressive stylized game proportions, readable game-ready materials.'
    }
  } else if (subjectOntology === 'mechanical_cad_engineering') {
    effectiveRenderMode = 'native_engineering_pbr'
    badgeLabelFr = 'Ingénierie CAO & PBR'
    styleDirectiveEn = 'PRECISION CAD & PBR ENGINEERING: crisp hard-surface geometry, clean bevels, distinct metallic/polymer PBR zones.'
  } else {
    if (explicitStylizedOverride && !explicitRealTexturesOverride) {
      effectiveRenderMode = 'hybrid_real_to_stylized'
      badgeLabelFr = `Sujet Réel -> Stylisation (${rawStylizedSubmode})`
      styleDirectiveEn =
        `STYLIZED ADAPTATION (${rawStylizedSubmode.toUpperCase()}): transform the real subject into an authentic ${rawStylizedSubmode} design (cartoon, figurine, Funko Pop, Pixar 3D, chibi, claymation, low-poly, or anime as requested), preserving recognizable identity cues while replacing photorealistic human skin pores and real proportions with the requested stylized aesthetic.`
    } else {
      effectiveRenderMode = 'native_photorealistic'
      badgeLabelFr = 'Photoréalisme Physique Natif'
      styleDirectiveEn =
        'NATIVE PHYSICAL PHOTOREALISM: render directly with authentic real-world optical lighting, genuine human skin micro-texture and natural pores (if human), and physically accurate surface materials.'
    }
  }

  const stylizedSubmode: StylizedSubmode | null =
    effectiveRenderMode === 'native_anime_stylized' ||
    effectiveRenderMode === 'hybrid_real_to_stylized' ||
    effectiveRenderMode === 'native_game_stylized'
      ? rawStylizedSubmode
      : null

  if (operationMode === 'modification') {
    badgeLabelFr = `Modification Conservatrice · ${badgeLabelFr}`
  }

  const englishSubject = translateFrenchSubjectToEnglish(cleanRaw)

  let englishExpandedPrompt = ''
  let negativePrompt = ''
  let reasoningFr = ''

  if (operationMode === 'modification') {
    if (effectiveRenderMode === 'native_anime_stylized' || effectiveRenderMode === 'hybrid_real_to_stylized') {
      englishExpandedPrompt =
        `CONSERVATIVE MODIFICATION — Targeted modification request: ${englishSubject}. ` +
        `STRICT MODIFICATION LOCK (STYLIZED / CARTOON / ANIME ONTOLOGY): Preserve 100% of the existing character's identity, ` +
        `proportions, stylized shading, pose, framing, and unmentioned costume colors. ` +
        `Do NOT convert the character into a photorealistic human or add real skin pores.`
      negativePrompt =
        'photorealistic human skin pores, live-action photo, uncanny valley, identity drift, altered pose, extra limbs, blurry linework, deformed hands, watermark'
    } else if (effectiveRenderMode === 'hybrid_anime_with_real_textures') {
      englishExpandedPrompt =
        `CONSERVATIVE MODIFICATION — Targeted modification request: ${englishSubject}. ` +
        `TARGETED TEXTURE MODIFICATION (ANIME/CARTOON TO REAL HUMAN SKIN): Preserve the exact iconic character silhouette, ` +
        `hairstyle geometry, pose, and costume design, while upgrading the surfaces to photorealistic real human skin ` +
        `micro-texture, natural pores, subsurface scattering, and physical fabric weaves.`
      negativePrompt =
        'flat 2d cel shading, cartoon outlines, plastic doll skin, lost character identity, wrong hairstyle, deformed anatomy, blurry, watermark'
    } else {
      englishExpandedPrompt =
        `CONSERVATIVE MODIFICATION — Targeted modification request: ${englishSubject}. ` +
        `STRICT MODIFICATION LOCK (PHOTOREALISTIC ONTOLOGY): Preserve 100% of the original subject's identity, ` +
        `facial structure, natural body proportions, lighting, and background. Apply ONLY the requested change ` +
        `seamlessly with physically accurate materials and shadows.`
      negativePrompt =
        'anime, cartoon, cel shading, plastic airbrushed skin, identity change, warped proportions, sticker look, ghost artifacts, extra fingers, watermark'
    }
    reasoningFr = `Modification détectée (${badgeLabelFr}) : verrouillage strict du sujet existant et application chirurgicale du delta en anglais.`
  } else if (targetModule === '3d') {
    if (effectiveRenderMode === 'native_anime_stylized' || effectiveRenderMode === 'hybrid_real_to_stylized' || effectiveRenderMode === 'native_game_stylized') {
      if (stylizedSubmode === 'cartoon_figurine' || stylizedSubmode === 'figurine_toy') {
        englishExpandedPrompt =
          `Full-body 3D collectible figurine reference of ${englishSubject}, sculpted as a high-end stylized 3D cartoon figurine / vinyl designer toy. ` +
          `Expressive stylized cartoon proportions, crisp sculpted facial features and hair/head silhouette, smooth matte vinyl and painted resin ` +
          `collectible surfaces, vibrant color separation, clean articulated limbs and hands clearly separated from the body for 3D reconstruction ` +
          `and rigging, centered full-body three-quarter studio view on a clean neutral background, zero realistic human skin pores.`
        negativePrompt =
          'photorealistic human skin pores, real live-action photograph, wrinkles, blurry geometry, fused limbs, cropped feet, cluttered background, text, watermark'
        reasoningFr =
          `Style Figurine / Cartoon 3D détecté (${stylizedSubmode}) : génération 3D en vraie figurine stylisée / cartoon (sans forcer le photoréalisme humain).`
      } else if (stylizedSubmode === 'clay_or_plush') {
        englishExpandedPrompt =
          `Full-body 3D stylized reference of ${englishSubject}, rendered in authentic tactile 3D claymation / plush toy aesthetic. ` +
          `Charming handcrafted volumetric proportions, clean expressive eyes and silhouette, tactile clay or stitched plush material shading, ` +
          `clear limb separation from head to feet on a clean studio background, zero photorealistic human skin pores.`
        negativePrompt =
          'photorealistic human skin, live-action photo, uncanny valley, flat 2d sketch, cropped body, fused limbs, watermark'
        reasoningFr =
          'Style Pâte à modeler / Peluche 3D détecté : génération 3D volumétrique fidèle au matériau demandé.'
      } else if (stylizedSubmode === 'lowpoly_voxel') {
        englishExpandedPrompt =
          `Full-body 3D stylized reference of ${englishSubject}, rendered in crisp geometric low-poly / voxel / blocky 3D aesthetic. ` +
          `Clean faceted polygon planes or voxel blocks, sharp readable silhouette, vibrant color zones, separated limbs for rigging ` +
          `from head to feet on a clean studio background.`
        negativePrompt =
          'photorealistic human skin pores, live-action photo, blurry noisy surfaces, cropped feet, watermark'
        reasoningFr =
          'Style Low-Poly / Voxel / Blocky 3D détecté : génération 3D géométrique stylisée.'
      } else if (stylizedSubmode === 'cartoon_3d' || effectiveRenderMode === 'native_game_stylized') {
        englishExpandedPrompt =
          `Full-body 3D cartoon character reference of ${englishSubject}, rendered in authentic vibrant 3D cartoon animation aesthetic ` +
          `(faithful to the character's iconic cartoon design and proportions). Expressive cartoon eyes, snout/mouth, and silhouette, ` +
          `bold saturated cartoon color zones, smooth stylized 3D cartoon shading with clean volumetric depth, clear separation between arms, ` +
          `hands/paws, and legs from head to feet for 3D skeletal rigging, centered on a clean studio background, zero photorealistic human skin pores.`
        negativePrompt =
          'photorealistic human skin pores, live-action cosplay photo, uncanny valley human face, realistic animal taxidermy, cropped legs, fused limbs, cluttered background, text, watermark'
        reasoningFr =
          'Personnage / style Cartoon 3D détecté : génération 3D directe dans son vrai style cartoon / dessin animé (proportions et couleurs fidèles, sans réalisme forcé).'
      } else {
        englishExpandedPrompt =
          `Full-body 3D character reference of ${englishSubject}, rendered in authentic native anime/stylized 3D aesthetic. ` +
          `Faithful anime facial proportions with crisp expressive eyes, clean defined nose and jawline, sculpted stylized ` +
          `hair locks with sharp silhouette separation, and iconic costume geometry with vibrant cel-shaded PBR material zones. ` +
          `Centered full-body three-quarter view on a solid black studio background, clear separation between arms, fingers, ` +
          `and legs for skeletal rigging, zero photorealistic skin pores or uncanny live-action textures.`
        negativePrompt =
          'photorealistic skin pores, old wrinkles, live-action cosplay photo, uncanny valley human face, melted blob, chibi marshmallow, cropped legs, fused fingers, cluttered background, text, watermark'
        reasoningFr =
          'Personnage/sujet animé détecté : génération 3D directe dans son vrai style animé/stylisé natif (sans textures de peau humaine réelle non demandées).'
      }
    } else if (effectiveRenderMode === 'hybrid_anime_with_real_textures') {
      englishExpandedPrompt =
        `Full-body 3D character reference of ${englishSubject}, combining the character's exact iconic anime/cartoon silhouette, ` +
        `signature hairstyle, and official costume design with explicit photorealistic real human skin textures, fine ` +
        `epidermal pores, natural subsurface scattering, and physically based fabric, leather, and metal micro-textures. ` +
        `Centered full-body three-quarter angle on a solid black studio background, anatomically articulated hands and ` +
        `separated limbs ready for 3D reconstruction and rigging.`
      negativePrompt =
        'flat 2d cartoon cel-shading, plastic toy skin, generic face losing character identity, melted geometry, fused limbs, cropped feet, watermark'
      reasoningFr =
        'Personnage animé avec demande explicite de textures de personne réelle : préservation du design animé avec vraies textures cutanées et matériaux PBR réalistes.'
    } else if (effectiveRenderMode === 'native_engineering_pbr') {
      englishExpandedPrompt =
        `Precision 3D engineering and product reference of ${englishSubject}. Crisp hard-surface CAD geometry, clean bevels, ` +
        `mechanically accurate part separation, distinct metallic and polymer PBR material zones, three-quarter ` +
        `orthographic-friendly studio angle on a solid black background revealing front, side, and top volume.`
      negativePrompt =
        'melted organic surfaces, asymmetric distortion, blurry edges, cartoon style, cluttered scene, text, watermark'
      reasoningFr = 'Pièce mécanique / produit technique détecté : expansion 3D CAO hard-surface et PBR.'
    } else {
      if (isCharacter) {
        englishExpandedPrompt =
          `Full-body photorealistic 3D reference of ${englishSubject}. True-to-life physical proportions (1:7.5 adult humanoid ` +
          `ratio if human), authentic natural skin micro-texture with fine pores, realistic hair strands, and physically ` +
          `accurate fabric and surface materials with strong albedo contrast. Centered three-quarter volumetric studio view ` +
          `on a solid black background with crisp edge separation and directional key and rim lighting.`
        negativePrompt =
          'anime, cartoon, cel-shaded, chibi, plastic doll skin, airbrushed wax face, melted blob, fused fingers, cropped body, watermark'
        reasoningFr = 'Personnage réel détecté : génération 3D photoréaliste physique directe avec proportions et textures réelles.'
      } else {
        englishExpandedPrompt =
          `Single isolated physical 3D object reference of ${englishSubject}. Complete standalone 3D volumetric form with crisp ` +
          `architectural/sculptural silhouette, authentic physical material optics (high-refraction optical crystal/glass transmission, ` +
          `caustics, and sharp engraved bas-relief calligraphy if glass/crystal or engraved), centered three-quarter studio view on a ` +
          `clean neutral studio background. Strictly isolated object ONLY: no person, no human, no man, no woman, no hands, no body.`
        negativePrompt =
          'person, human, man, woman, boy, girl, hands holding object, body, face, legs, feet, opaque plastic balloon, secondary object at feet, cluttered background, watermark'
        reasoningFr = 'Objet physique isolé détecté : génération 3D volumétrique pure de l\'objet seul (zéro personne hallucinée) avec physique optique des matériaux.'
      }
    }
  } else {
    if (effectiveRenderMode === 'native_anime_stylized') {
      if (stylizedSubmode === 'cartoon_figurine' || stylizedSubmode === 'figurine_toy') {
        englishExpandedPrompt =
          `Masterpiece high-end 3D collectible vinyl figurine of ${englishSubject}. Authentic stylized cartoon character ` +
          `proportions, smooth satin PVC and painted resin material finish, crisp sculpted facial features and closed eye contours, ` +
          `full body standing directly on flat ground on its feet without any base, pedestal, or stand, on a pure solid white studio background.`
        negativePrompt =
          'circular pedestal, black base, display stand, plinth, photorealistic human skin pores, live-action photography, uncanny valley, off-model face, deformed hands, extra fingers, watermark'
        reasoningFr =
          'Sujet Figurine Cartoon détecté : développement en vraie figurine 3D vinyle/résine sans socle parasite pour une parité 2D/3D parfaite.'
      } else if (stylizedSubmode === 'lowpoly_voxel') {
        englishExpandedPrompt =
          `Masterpiece 3D cubic voxel block character render of ${englishSubject}. Crisp 90-degree orthogonal voxel cube geometry, ` +
          `clean pixel-art block textures without organic rounding, full body standing directly on its feet without any pedestal or stand, ` +
          `on a pure solid white studio background.`
        negativePrompt =
          'smooth organic curves, spherical head, circular pedestal, display stand, photorealistic human skin pores, blurry textures, watermark'
        reasoningFr =
          'Style Cubique / Voxel détecté : géométrie orthogonale en cubes nets sans socle.'
      } else if (stylizedSubmode === 'cartoon_3d') {
        englishExpandedPrompt =
          `Masterpiece official 2D cartoon character model sheet illustration of ${englishSubject}. Authentic Franco-Belgian / Xilam / classic ` +
          `2D animation style with thick continuous closed black ink outlines completely enclosing the eyes and sclera, cheerful closed or toothy ` +
          `smiling mouth without any giant dark chest cavity, vibrant flat cel colors, full body standing upright facing forward directly on its ` +
          `feet without any pedestal or stand, on a pure solid white studio background.`
        negativePrompt =
          'open unclosed eye rims, white sclera bleeding into background, giant black gaping mouth cavity, 3d pedestal, display stand, photorealistic human skin pores, live-action photography, off-model face, deformed hands, watermark'
        reasoningFr =
          'Sujet Cartoon 2D détecté : modèle officiel 2D à contours d\'encre noire fermés autour des yeux, sans cavité noire ni socle.'
      } else {
        englishExpandedPrompt =
          `Masterpiece official-grade anime key visual of ${englishSubject}. Authentic native anime character design with ` +
          `crisp closed black ink linework around eyes and face, vibrant cel-shaded color separation, smooth unified anime skin tone ` +
          `without harsh dark cheek shadow blotches, luminous expressive anime eyes, dynamic sculpted hair silhouette, and faithful ` +
          `costume details, full body standing upright without any pedestal, pure 2D/cel-shaded anime fidelity, no realistic human skin pores.`
        negativePrompt =
          'photorealistic human skin pores, harsh brown facial shadow scar, live-action photography, 3d CGI doll, circular pedestal, display stand, uncanny valley, muddy shading, off-model face, deformed hands, extra fingers, watermark'
        reasoningFr =
          'Sujet animé détecté : développement artistique en anglais dans son style animé/cel-shadé authentique (aucune texture de peau humaine réelle forcée).'
      }
    } else if (effectiveRenderMode === 'hybrid_anime_with_real_textures') {
      englishExpandedPrompt =
        `High-end live-action cinematic portrait and full-scene realization of ${englishSubject}, faithfully preserving ` +
        `the character's iconic anime hairstyle silhouette, costume colors, and signature identity while rendering with ` +
        `explicit photorealistic real human skin texture, fine natural pores, lifelike eyes with corneal reflections, ` +
        `and tactile real-world fabric, leather, and metal weave. Framed in a richly detailed, physically lit environment ` +
        `with natural optical depth of field.`
      negativePrompt =
        'flat 2d cel-shading, cartoon lineart, plastic airbrushed skin, generic cosplay losing character traits, deformed anatomy, extra fingers, watermark'
      reasoningFr =
        'Sujet animé + override explicite « textures de personne réelle » : fusion de l\'identité canonique du personnage avec une vraie texture de peau humaine photoréaliste.'
    } else if (effectiveRenderMode === 'hybrid_real_to_stylized') {
      englishExpandedPrompt =
        `Expressive stylized adaptation of ${englishSubject} (${stylizedSubmode}), preserving the recognizable identity, ` +
        `posture, and key traits of the subject while translating the rendering into authentic ${stylizedSubmode} aesthetics ` +
        `(cartoon, figurine, Funko Pop, Pixar 3D, chibi, claymation, or anime as requested) with vibrant colors and zero raw photorealistic skin pores.`
      negativePrompt =
        'raw unstylized photograph, uncanny realistic skin pores, muddy colors, deformed hands, watermark'
      reasoningFr = `Sujet réel avec demande explicite de stylisation (${stylizedSubmode}) : adaptation fidèle dans le style demandé.`
    } else if (effectiveRenderMode === 'native_game_stylized') {
      englishExpandedPrompt =
        `Production-ready video game art of ${englishSubject}. Crisp readable silhouette, deliberate stylized materials ` +
        `and clean lighting, tailored for immediate game engine integration.`
      negativePrompt = 'blurry edges, noisy artifacts, cropped silhouette, watermark'
      reasoningFr = 'Asset de jeu vidéo détecté : développement en anglais optimisé pour la lisibilité en jeu.'
    } else {
      if (isCharacter) {
        englishExpandedPrompt =
          `Authentic editorial documentary photograph of ${englishSubject}. Natural directional illumination casting soft ` +
          `physical shadows that reveal genuine human skin micro-texture, fine natural pores, subtle organic imperfections, ` +
          `and expressive eyes with crisp catchlights. Set in a fully realized, atmospheric real-world environment with ` +
          `foreground-to-background depth, captured on an 85mm prime lens with true-to-life color science and zero ` +
          `artificial plastic smoothing.`
      } else {
        englishExpandedPrompt =
          `High-precision documentary-grade photograph of ${englishSubject}. Physically accurate lighting with natural ` +
          `specular highlights, tactile real-world surface micro-textures, grounded contact shadows, and rich environmental ` +
          `depth from foreground to horizon, captured with sharp optical clarity and organic tonal balance.`
      }
      negativePrompt =
        'anime, cartoon, cel-shading, 3d render, CGI doll, plastic airbrushed skin, wax face, oversaturated HDR, deformed anatomy, extra fingers, blurry, watermark'
      reasoningFr =
        'Sujet réel détecté : développement en anglais en photoréalisme physique natif (vraie texture de peau et lumière optique).'
    }
  }

  if (strictConstraints.mandatoryAttributesEn.length > 0) {
    englishExpandedPrompt += ` Mandatory user constraints: ${strictConstraints.mandatoryAttributesEn.join(', ')}.`
  }
  if (strictConstraints.excludedItemsEn.length > 0) {
    const excludedStr = strictConstraints.excludedItemsEn.join(', ')
    englishExpandedPrompt += ` Strictly exclude: ${excludedStr}.`
    negativePrompt = `${excludedStr}, ${negativePrompt}`
  }

  return {
    rawPrompt: cleanRaw,
    targetModule,
    operationMode,
    subjectOntology,
    nativeOntology,
    canonicalSubjectName,
    effectiveRenderMode,
    stylizedSubmode,
    explicitRealTexturesOverride,
    explicitStylizedOverride,
    preserveNativeAnimeStyle: effectiveRenderMode === 'native_anime_stylized',
    preserveNativeRealStyle: effectiveRenderMode === 'native_photorealistic',
    lockUnmentionedAttributes: operationMode === 'modification' || operationMode === 'reproduction',
    englishSubject,
    englishExpandedPrompt,
    styleDirectiveEn,
    negativePrompt,
    negativeDirectivesEn: negativePrompt.split(',').map((s) => s.trim()).filter(Boolean),
    strictConstraints,
    modificationDeltaEn: operationMode === 'modification' ? englishSubject : null,
    reasoningFr,
    explanationFr: reasoningFr,
    badgeLabelFr,
    wasLlmRefined: false,
  }
}

const OPEN_WORLD_ENTITY_CACHE = new Map<
  string,
  {
    entityTitle: string
    summaryExtract: string
    inferredOntology: SubjectOntology | null
    inferredSubmode: StylizedSubmode | null
  } | null
>()

export async function resolveOpenWorldEntityFrontend(
  rawPrompt: string,
  timeoutMs = 1450,
): Promise<{
  entityTitle: string
  summaryExtract: string
  inferredOntology: SubjectOntology | null
  inferredSubmode: StylizedSubmode | null
} | null> {
  const styleClause = extractUniversalStyleClause(rawPrompt || '')
  const normRawCheck = normalize(rawPrompt || '')
  if (
    /\b(vase|vases|flacon|carafe|coupe|calice|bol|pot|urne|bocal|tasse|bouteille|bijou|bague|pendentif|collier|medaillon|trophee|coffret|bougie|chandelier|lampe|miroir|sablier)\b/i.test(
      normRawCheck,
    ) &&
    !/\b(de\s+[A-Z]|du\s+jeu|dans\s+le\s+jeu|personnage)\b/.test(rawPrompt || '')
  ) {
    return null
  }
  let preCleaned = (styleClause.coreSubjectClean || rawPrompt || '')
    .replace(
      /\b(?:avec\s+)?(?:grav(?:er|é|ee|es|ure)|inscri(?:re|t|ption)|marqu(?:er|é)|[eé]crit)\s+(?:le\s+|la\s+|un\s+|une\s+)?(?:pr[eé]nom\s+|nom\s+|mot\s+|texte\s+)?[A-ZÀ-ÖØ-Þa-zà-öø-ÿ0-9'’-]+/gi,
      ' ',
    )
    .replace(
      /\b(?:pr[eé]nom|nom)\s+[A-ZÀ-ÖØ-Þa-zà-öø-ÿ0-9'’-]+/gi,
      ' ',
    )
    .replace(
      /^(?:fais[- ]?moi|fait[- ]?moi|cree[- ]?moi|creer|genere[- ]?moi|generer|dessine[- ]?moi|modifie|change|transforme|reproduis|je\s+veux)\s+/i,
      '',
    )
    .replace(
      /^(?:une?\s+(?:image|illustration|photo|portrait|modele\s+3d|rendu\s+3d|personnage|perso|figurine)\s+(?:de|d[' ])\s*)/i,
      '',
    )
    .split(/\b(?:avec|sans|pas\s+de|tenant|portant|qui\s+|en\s+train\s+de|dans\s+un|sur\s+fond|with\s+|without\s+|en\s+style|en\s+3d)\b|[,;.]/i)[0]
    .trim()

  if (/^(?:un|une|des|a|an)\s+[a-zà-öø-ÿ]/.test(preCleaned)) {
    const mOf = preCleaned.match(/(?:\b(?:de|du|des|de\s+la|de\s+l['’]|dans|from|of|in|comme|like)\s+|\bd['’])\s*([\wÀ-ÿ'’\s-]{2,40})$/i)
    if (mOf) {
      preCleaned = mOf[1].replace(/^(?:jeu(?:\s+vid[eé]o)?|video\s+game)\s+/i, '').trim()
    } else {
      const afterIndef = preCleaned.replace(/^(?:un|une|des|a|an)\s+[a-zà-öø-ÿ_-]+\s*/, '')
      if (afterIndef && /\b[A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ]{2,}/.test(afterIndef)) {
        preCleaned = afterIndef.trim()
      } else {
        return null
      }
    }
  }

  const cleaned = preCleaned.replace(/^(?:un|une|du|de\s+la|d[' ]|a|an)\s+/i, '').trim()

  const normKey = normalize(cleaned)
  if (!normKey || normKey.split(/\s+/).length > 6) return null
  if (OPEN_WORLD_ENTITY_CACHE.has(normKey)) {
    return OPEN_WORLD_ENTITY_CACHE.get(normKey) ?? null
  }

  const deStripped = cleaned.replace(/\b(?:d['’]|de\s+la\s+|de\s+l['’]|du\s+|des\s+|de\s+)/gi, ' ').replace(/\s+/g, ' ').trim()
  const phonetic = (deStripped || cleaned)
    .replace(/([aou])y\b/gi, '$1i')
    .replace(/([aou])y(?=[a-z])/gi, '$1i')
    .replace(/ou/gi, 'u')
  const searchVariants = Array.from(new Set([cleaned, deStripped, phonetic].filter(Boolean)))

  for (const variant of searchVariants) {
    for (const lang of ['fr', 'en'] as const) {
      const controller = new AbortController()
      const timer = setTimeout(() => controller.abort(), timeoutMs)
      try {
        const url =
          `https://${lang}.wikipedia.org/w/api.php?origin=*` +
          `&action=query&generator=search&gsrsearch=${encodeURIComponent(variant)}&gsrlimit=2` +
          `&prop=extracts|description&exintro=1&explaintext=1&exchars=850&format=json`
        const resp = await fetch(url, { signal: controller.signal })
        if (!resp.ok) continue
        const data = await resp.json()
        const pages = data?.query?.pages
        if (!pages) continue
        const top = Object.values(pages as Record<string, any>).sort((a, b) => (a.index ?? 99) - (b.index ?? 99))[0]
        const extract = String(top?.extract || '').trim()
        if (extract.length < 30) continue
        const title = String(top?.title || cleaned).trim()
        const desc = String(top?.description || '').trim()
        const summaryExtract = (desc ? `${title} (${desc}): ${extract}` : `${title}: ${extract}`).replace(/\s+/g, ' ').slice(0, 700)
        const normExt = normalize(summaryExtract)
        const firstSentence = normExt.slice(0, 260)

        let inferredOntology: SubjectOntology | null = null
        let inferredSubmode: StylizedSubmode | null = null

        const isRealPerson =
          /\b(ne\s+le|nee\s+le|born\s+on|born\s+\d|est\s+un\s+(?:footballeur|joueur|acteur|chanteur|rappeur|homme\s+politique|sportif)|est\s+une\s+(?:actrice|chanteuse|joueuse|femme\s+politique)|is\s+a(?:n)?\s+(?:french|american|british|spanish)?\s*(?:footballer|actor|actress|singer|politician|athlete))\b/.test(
            firstSentence,
          ) &&
          !/\b(personnage\s+de\s+fiction|fictional\s+character|serie\s+d\s+animation|animated\s+series|manga|bande\s+dessinee|jeu\s+video|video\s+game)\b/.test(
            firstSentence,
          )

        if (isRealPerson) {
          inferredOntology = 'real_human_subject'
          inferredSubmode = null
        } else {
          const isJapaneseAnime =
            /\b(manga|manhwa|webtoon|light\s+novel|shonen|seinen|shojo|isekai|animation\s+japonaise|japanese\s+anime|japanese\s+manga|anime\s+series)\b/.test(
              normExt,
            )
          const isStopMotion =
            /\b(animation\s+en\s+volume|stop[- ]?motion|pate\s+a\s+modeler|clay\s+animation|claymation|marionnette)\b/.test(
              normExt,
            )
          const isCartoonOrBd =
            /\b(serie\s+d\s+animation|serie\s+televisee\s+d\s+animation|bande\s+dessinee|franco[- ]?belge|cartoon|animated\s+series|animated\s+television|film\s+d\s+animation|animated\s+film|comics?|dessin\s+anime)\b/.test(
              normExt,
            )
          const isGame =
            /\b(jeu\s+video|jeux\s+video|video\s+game|personnage\s+de\s+jeu|action[- ]?adventure|role[- ]?playing\s+game|jeu\s+de\s+role|jeu\s+d\s+action|jeu\s+de\s+plateforme|platform\s+game|platformer|first[- ]?person\s+shooter|jeu\s+de\s+tir|battle\s+royale|sandbox\s+game|bac\s+a\s+sable|hack\s+and\s+slash|visual\s+novel|fighting\s+game|jeu\s+de\s+combat)\b/.test(
              normExt,
            )

          if (isStopMotion) {
            inferredOntology = 'anime_manga_character'
            inferredSubmode = 'clay_or_plush'
          } else if (isGame) {
            inferredOntology = 'game_character_or_asset'
            if (/\b(voxel|bloc[s]?\s+cubique|blocky|cubic\s+world)\b/.test(normExt)) {
              inferredSubmode = 'lowpoly_voxel'
            } else if (isJapaneseAnime || /\b(cel[- ]?shad|anime|manga|japonais|japanese\s+role[- ]?playing)\b/.test(normExt)) {
              inferredSubmode = 'anime_cel'
            } else if (isCartoonOrBd || /\b(cartoon|jeu\s+de\s+plateforme|platform\s+game|platformer)\b/.test(normExt)) {
              inferredSubmode = 'cartoon_3d'
            } else {
              inferredSubmode = null
            }
          } else if (isCartoonOrBd && !isJapaneseAnime) {
            inferredOntology = 'anime_manga_character'
            inferredSubmode = 'cartoon_3d'
          } else if (isJapaneseAnime) {
            inferredOntology = 'anime_manga_character'
            inferredSubmode = 'anime_cel'
          }
        }

        const res = { entityTitle: title, summaryExtract, inferredOntology, inferredSubmode }
        OPEN_WORLD_ENTITY_CACHE.set(normKey, res)
        return res
      } catch {
        // ignore timeout or offline
      } finally {
        clearTimeout(timer)
      }
    }
  }
  OPEN_WORLD_ENTITY_CACHE.set(normKey, null)
  return null
}

export async function analyzePromptOntologyOpenWorld(
  rawPrompt: string,
  options: Parameters<typeof analyzePromptOntologySync>[1] = {},
): Promise<CognitivePromptDecision> {
  const syncDecision = analyzePromptOntologySync(rawPrompt, options)
  const openWorld = await resolveOpenWorldEntityFrontend(rawPrompt)
  if (!openWorld) return syncDecision

  const enrichedContext = `${options?.conversationContext || ''} ${openWorld.summaryExtract}`.trim()
  const updated = analyzePromptOntologySync(rawPrompt, {
    ...options,
    conversationContext: enrichedContext,
    requestedStyle:
      openWorld.inferredOntology === 'anime_manga_character' && !syncDecision.explicitRealTexturesOverride
        ? openWorld.inferredSubmode === 'cartoon_3d'
          ? 'cartoon'
          : 'anime'
        : options?.requestedStyle,
  })
  const hasUserStyleClause = extractUniversalStyleClause(rawPrompt).hasStyleClause
  if (openWorld.inferredOntology === 'game_character_or_asset' && !hasUserStyleClause && !syncDecision.explicitRealTexturesOverride) {
    updated.subjectOntology = 'game_character_or_asset'
    updated.nativeOntology = 'game_stylized'
    updated.effectiveRenderMode = 'native_game_stylized'
    updated.stylizedSubmode = openWorld.inferredSubmode
  } else if (openWorld.inferredSubmode && !hasUserStyleClause && !syncDecision.explicitRealTexturesOverride) {
    updated.stylizedSubmode = openWorld.inferredSubmode
  }
  updated.canonicalSubjectName = openWorld.entityTitle
  updated.openWorldEntity = {
    title: openWorld.entityTitle,
    description: openWorld.summaryExtract,
    source: 'MediaWiki',
  }
  if (!updated.englishSubject.toLowerCase().includes(openWorld.entityTitle.toLowerCase())) {
    updated.englishSubject = `${updated.englishSubject} (${openWorld.summaryExtract.slice(0, 220)})`
  }
  updated.englishExpandedPrompt = `${updated.englishExpandedPrompt} Open-world entity identity: ${openWorld.summaryExtract.slice(0, 260)}.`
  updated.wasLlmRefined = true
  return updated
}

