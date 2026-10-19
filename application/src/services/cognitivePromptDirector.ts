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

export type CognitivePromptDecision = {
  rawPrompt: string
  targetModule: 'image' | '3d' | 'video' | 'drawing'
  operationMode: PromptOperationMode
  subjectOntology: SubjectOntology
  nativeOntology: 'anime_stylized' | 'real_photorealistic' | 'game_stylized' | 'engineering_cad'
  canonicalSubjectName: string | null
  effectiveRenderMode: EffectiveRenderMode
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
  modificationDeltaEn: string | null
  reasoningFr: string
  explanationFr: string
  badgeLabelFr: string
  wasLlmRefined: boolean
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
      'pixar', 'disney', 'cartoon', 'dessin\\s*anime',
      'natsu', 'lucy\\s*heartfilia', 'erza', 'gray\\s*fullbuster', 'happy\\s*exceed', 'wendy\\s*marvell', 'fairy\\s*tail',
      'goku', 'son\\s*goku', 'vegeta', 'gohan', 'trunks', 'piccolo', 'frieza', 'freezer', 'broly', 'bulma', 'saiyan', 'super\\s*saiyan', 'dragon\\s*ball',
      'luffy', 'monkey\\s*d', 'zoro', 'roronoa', 'sanji', 'nami', 'robin', 'chopper', 'usopp', 'brook', 'franky', 'jinbe', 'shanks', 'ace', 'gear\\s*5', 'one\\s*piece',
      'naruto', 'sasuke', 'sakura', 'kakashi', 'itachi', 'madara', 'obito', 'hinata', 'gaara', 'jiraiya', 'minato', 'pain', 'akatsuki', 'sharingan', 'konoha',
      'ichigo', 'rukia', 'aizen', 'byakuya', 'kenpachi', 'ulquiorra', 'bleach', 'bankai', 'shinigami',
      'tanjiro', 'nezuko', 'zenitsu', 'inosuke', 'rengoku', 'giyu', 'muzan', 'shinobu', 'mitsuri', 'tengen', 'hashira', 'demon\\s*slayer', 'kimetsu',
      'gojo', 'satoru\\s*gojo', 'sukuna', 'yuji\\s*itadori', 'megumi', 'nobara', 'toji', 'geto', 'yuta', 'maki', 'jujutsu\\s*kaisen',
      'eren', 'mikasa', 'levi', 'armin', 'reiner', 'attaque\\s*des\\s*titans', 'attack\\s*on\\s*titan', 'shingeki',
      'saitama', 'genos', 'tatsumaki', 'garou', 'one\\s*punch',
      'gon', 'killua', 'kirua', 'kurapika', 'hisoka', 'meruem', 'chrollo', 'hunter\\s*x\\s*hunter',
      'deku', 'midoriya', 'bakugo', 'todoroki', 'all\\s*might', 'shigaraki', 'my\\s*hero\\s*academia',
      'asta', 'yuno', 'yami', 'noelle', 'black\\s*clover',
      'denji', 'makima', 'power', 'aki', 'chainsaw\\s*man',
      'frieren', 'fern', 'stark', 'himmel',
      'anya', 'yor\\s*forger', 'loid\\s*forger', 'spy\\s*x\\s*family',
      'sung\\s*jin[- ]?woo', 'solo\\s*leveling', 'igris', 'beru',
      'edward\\s*elric', 'alphonse\\s*elric', 'roy\\s*mustang', 'fullmetal',
      'light\\s*yagami', 'ryuk', 'l\\s*lawliet', 'death\\s*note',
      'lelouch', 'code\\s*geass', 'rem', 'emilia', 'subaru', 're\\s*zero',
      'kirito', 'asuna', 'sword\\s*art\\s*online', 'rimuru', 'tensura', 'ainz', 'overlord',
      'jotaro', 'dio\\s*brando', 'giorno', 'josuke', 'jolyne', 'jojo',
      'pikachu', 'charizard', 'dracaufeu', 'mewtwo', 'lucario', 'eevee', 'gengar', 'pokemon',
      'hatsune\\s*miku', 'vocaloid', 'genshin', 'raiden\\s*shogun', 'furina', 'nahida', 'zhongli', 'hu\\s*tao', 'arlecchino', 'honkai',
      'link', 'zelda', 'ganondorf', 'hyrule', 'mario', 'luigi', 'peach', 'bowser', 'yoshi', 'sonic', 'tails', 'knuckles', 'shadow\\s*the\\s*hedgehog',
      'cloud\\s*strife', 'tifa', 'sephiroth', 'aerith', 'final\\s*fantasy', '2b', 'nier\\s*automata', 'jinx', 'vi\\s*arcane', 'ekko', 'arcane',
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
      'en\\s+(?:style\\s+|version\\s+)?(?:anime|manga|cartoon|dessin\\s+anime|ghibli|pixar|chibi|pixel\\s*art|low[- ]?poly|bd|comics?)',
      'style\\s+(?:anime|manga|cartoon|ghibli|pixar|chibi|pixel\\s*art|cel[- ]?shading)',
      'transforme\\s+en\\s+(?:anime|manga|cartoon|dessin)',
      'version\\s+(?:anime|manga|cartoon|stylis[eé]e?)',
    ].join('|') +
    String.raw`)\b`,
  'i',
)

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
  /\b(perso|personnage|character|hero[s]?|heroine|guerrier[e]?|warrior|mage|sorcier[e]?|chevalier|knight|ninja|samourai|samurai|pirate|assassin|paladin|archer|voleur|homme|femme|garcon|fille|enfant|vieillard|portrait|visage|humain[e]?|personne|man|woman|boy|girl|human|person|face|avatar|figurine)\b/i

const MECHANICAL_CAD_RE =
  /\b(engrenage|gear|poulie|pulley|courroie|belt|verin|actuator|charniere|hinge|bielle|linkage|roulement|bearing|vis|ecrou|bride|flange|support\s+mecanique|boitier\s+pc|carte\s+mere|motherboard|strimer|cable|connecteur|gpu|rtx|ventirad|stl|cao|cad|imprimable|printable|piece\s+mecanique)\b/i

const GAME_ASSET_RE =
  /\b(pixel\s*art|sprite|spritesheet|tileset|isometrique|isometric|low[- ]?poly|icone\s+de\s+jeu|game\s+asset|game\s+prop|inventory\s+icon|pbr\s+texture|seamless\s+texture)\b/i

const CANONICAL_CHARACTER_LORE: Record<string, string> = {
  natsu:
    'Natsu Dragneel from Fairy Tail, athletic young anime fire mage with spiky salmon-pink hair, sharp dark eyes, iconic white-and-black checkered scale scarf around his neck, open black sleeveless waistcoat with gold trim over bare muscular chest, white knee-length trousers, black open-toed sandals, red Fairy Tail guild mark on his right shoulder',
  lucy:
    'Lucy Heartfilia from Fairy Tail, expressive anime celestial spirit mage with golden blonde hair tied in side tails, warm brown eyes, iconic blue-and-white fitted sleeveless top, pleated skirt, leather belt with golden Celestial Spirit keys',
  goku:
    'Son Goku from Dragon Ball, muscular anime martial artist with iconic wild spiky jet-black hair, determined dark eyes, signature bright orange martial arts gi over a royal blue undershirt, blue wristbands, blue sash belt, and martial arts boots',
  vegeta:
    'Vegeta from Dragon Ball, proud Saiyan prince with tall flame-shaped spiky black hair, sharp widow peak, royal blue bodysuit under white-and-gold Saiyan battle armor with shoulder pauldrons, white gloves and boots',
  luffy:
    'Monkey D. Luffy from One Piece, energetic anime pirate captain wearing his signature woven straw hat with a red ribbon, tousled black hair, small scar under his left eye, open red vest, blue denim shorts, yellow sash, and sandals',
  zoro:
    'Roronoa Zoro from One Piece, muscular anime swordsman with cropped green hair, three gold earrings on his left ear, scar over his left eye, dark green coat, crimson haramaki sash holding three katana swords at his waist',
  naruto:
    'Naruto Uzumaki from Naruto, spirited anime ninja with spiky bright yellow-blond hair, cobalt blue eyes, three whisker marks on each cheek, Konoha metal headband, orange-and-black zip-up ninja jumpsuit, and ninja sandals',
  sasuke:
    'Sasuke Uchiha from Naruto, composed anime ninja with spiky black hair framing his face, dark Sharingan eyes, high-collared Uchiha outfit with rope belt and Kusanagi sword',
  gojo:
    'Satoru Gojo from Jujutsu Kaisen, tall slender anime sorcerer with snow-white spiky hair, luminous sky-blue Six Eyes, dark high-necked Jujutsu High uniform jacket',
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
  levi:
    'Levi Ackerman from Attack on Titan, sharp-featured anime captain with undercut black hair, steel-grey eyes, white cravat, Survey Corps jacket, green cloak, and dual ODM gear blades',
  mikasa:
    'Mikasa Ackerman from Attack on Titan, agile anime soldier with chin-length black hair, dark eyes, iconic crimson red scarf, Survey Corps leather jacket and ODM gear',
  frieren:
    'Frieren, slender elven anime mage with long silver-white twin-tails, green eyes, pointed elf ears, white-and-gold striped capelet over a white tunic dress, carrying her red-gemmed golden mage staff',
  pikachu:
    'Pikachu from Pokemon, vibrant yellow electric mouse creature with long black-tipped ears, red cheek pouches, brown back stripes, and a lightning-bolt-shaped tail',
  link:
    'Link from The Legend of Zelda, agile Hylian hero with pointed ears, blonde hair, Champion tunic with leather cross-straps, Hylian shield and Master Sword',
}

const FR_TO_EN_PHRASES: Array<[RegExp, string]> = [
  [/\b(?:fais[- ]?moi|fait[- ]?moi|cree[- ]?moi|creer|genere[- ]?moi|generer|dessine[- ]?moi|je\s+veux|je\s+voudrais|peux[- ]?tu\s+faire)\b/gi, ''],
  [/\bavec\s+des\s+textures?\s+de\s+personne\s+reelle\b/gi, 'with photorealistic real human skin textures and natural pores'],
  [/\btextures?\s+de\s+personne\s+reelle\b/gi, 'photorealistic real human skin textures and natural pores'],
  [/\btextures?\s+reelles?\b/gi, 'authentic physical real-world textures'],
  [/\bpersonne\s+reelle\b/gi, 'real living human person'],
  [/\bun\s+perso\s+d[' ]?anime\b/gi, 'an authentic anime character'],
  [/\bun\s+personnage\s+d[' ]?anime\b/gi, 'an authentic anime character'],
  [/\bun\s+perso\s+anime\b/gi, 'an authentic anime character'],
  [/\bun\s+personnage\s+anime\b/gi, 'an authentic anime character'],
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

  const canonicalMatches: string[] = []
  for (const [key, desc] of Object.entries(CANONICAL_CHARACTER_LORE)) {
    const re = new RegExp(`\\b${key}\\b`, 'i')
    if (re.test(norm)) {
      canonicalMatches.push(desc)
    }
  }

  let working = stripAccents(trimmed)
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

  if (canonicalMatches.length > 0) {
    const canonStr = canonicalMatches.join('; ')
    if (working.split(/\s+/).filter(Boolean).length <= 4) {
      return canonStr
    }
    return `${canonStr} — ${working}`
  }

  return working || trimmed
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

  const isReproduction =
    options.modeHint === 'replicate' ||
    options.modeHint === 'reproduction' ||
    REPRODUCTION_INTENT_RE.test(norm)
  const isModification =
    !isReproduction &&
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

  const hasAnimeSignalInPrompt = ANIME_ONTOLOGY_RE.test(norm)
  const hasAnimeSignalInCtx = isModification && ANIME_ONTOLOGY_RE.test(ctxNorm)
  const hasAnimeStyleSelected = /(anime|manga|ghibli|cel)/.test(reqStyleNorm)

  const isGameAsset =
    GAME_ASSET_RE.test(norm) || /(pixel|isometric|low-poly|low_poly)/.test(reqStyleNorm)
  const isMechanicalCad = MECHANICAL_CAD_RE.test(norm)
  const isCharacter =
    CHARACTER_SUBJECT_RE.test(norm) || hasAnimeSignalInPrompt || hasAnimeSignalInCtx

  const explicitRealTexturesOverride = EXPLICIT_REAL_TEXTURES_OVERRIDE_RE.test(norm)
  const explicitStylizedOverride =
    EXPLICIT_STYLIZED_OVERRIDE_RE.test(norm) || hasAnimeStyleSelected

  let subjectOntology: SubjectOntology
  let nativeOntology: 'anime_stylized' | 'real_photorealistic' | 'game_stylized' | 'engineering_cad'
  if (isMechanicalCad) {
    subjectOntology = 'mechanical_cad_engineering'
    nativeOntology = 'engineering_cad'
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
      badgeLabelFr = 'Animé + Textures Humaines Réelles (Override)'
      styleDirectiveEn =
        'HYBRID ANIME + REAL HUMAN TEXTURES: preserve the iconic anime character silhouette, hairstyle, and canonical costume, while applying photorealistic real human skin pores, subsurface scattering, and physical fabric weaves.'
    } else {
      effectiveRenderMode = 'native_anime_stylized'
      badgeLabelFr = 'Style Animé / Manga Natif Fidèle'
      styleDirectiveEn =
        'NATIVE ANIME / MANGA STYLIZED FIDELITY: render directly in authentic anime/cel-shaded aesthetics with anime facial proportions, sculpted anime hair locks, vivid official colors, and smooth stylized anime skin (DO NOT force realistic human skin pores).'
    }
  } else if (subjectOntology === 'game_character_or_asset') {
    effectiveRenderMode = 'native_game_stylized'
    badgeLabelFr = 'Asset Jeu Vidéo Stylisé'
    styleDirectiveEn = 'NATIVE GAME ASSET STYLIZED: crisp silhouette, readable game-ready materials.'
  } else if (subjectOntology === 'mechanical_cad_engineering') {
    effectiveRenderMode = 'native_engineering_pbr'
    badgeLabelFr = 'Ingénierie CAO & PBR'
    styleDirectiveEn = 'PRECISION CAD & PBR ENGINEERING: crisp hard-surface geometry, clean bevels, distinct metallic/polymer PBR zones.'
  } else {
    if (explicitStylizedOverride && !explicitRealTexturesOverride) {
      effectiveRenderMode = 'hybrid_real_to_stylized'
      badgeLabelFr = 'Sujet Réel -> Stylisation Animée'
      styleDirectiveEn = 'STYLIZED ANIME ADAPTATION: adapt the real subject into expressive anime linework and cel-shaded colors.'
    } else {
      effectiveRenderMode = 'native_photorealistic'
      badgeLabelFr = 'Photoréalisme Physique Natif'
      styleDirectiveEn =
        'NATIVE PHYSICAL PHOTOREALISM: render directly with authentic real-world optical lighting, genuine human skin micro-texture and natural pores (if human), and physically accurate surface materials.'
    }
  }

  if (operationMode === 'modification') {
    badgeLabelFr = `Modification Conservatrice · ${badgeLabelFr}`
  }

  const englishSubject = translateFrenchSubjectToEnglish(cleanRaw)

  let englishExpandedPrompt = ''
  let negativePrompt = ''
  let reasoningFr = ''

  if (operationMode === 'modification') {
    if (effectiveRenderMode === 'native_anime_stylized') {
      englishExpandedPrompt =
        `CONSERVATIVE MODIFICATION — Targeted modification request: ${englishSubject}. ` +
        `STRICT MODIFICATION LOCK (ANIME ONTOLOGY): Preserve 100% of the existing anime character's identity, ` +
        `facial proportions, cel-shaded linework, pose, framing, and unmentioned costume colors. ` +
        `Do NOT convert the character into a photorealistic human or add real skin pores.`
      negativePrompt =
        'photorealistic human skin pores, live-action photo, 3d plastic doll, uncanny valley, identity drift, altered pose, extra limbs, blurry linework, deformed hands, watermark'
    } else if (effectiveRenderMode === 'hybrid_anime_with_real_textures') {
      englishExpandedPrompt =
        `CONSERVATIVE MODIFICATION — Targeted modification request: ${englishSubject}. ` +
        `TARGETED TEXTURE MODIFICATION (ANIME TO REAL HUMAN SKIN): Preserve the exact iconic anime character silhouette, ` +
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
    if (effectiveRenderMode === 'native_anime_stylized') {
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
    } else if (effectiveRenderMode === 'hybrid_anime_with_real_textures') {
      englishExpandedPrompt =
        `Full-body 3D character reference of ${englishSubject}, combining the character's exact iconic anime silhouette, ` +
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
      englishExpandedPrompt =
        `Full-body photorealistic 3D reference of ${englishSubject}. True-to-life physical proportions (1:7.5 adult humanoid ` +
        `ratio if human), authentic natural skin micro-texture with fine pores, realistic hair strands, and physically ` +
        `accurate fabric and surface materials with strong albedo contrast. Centered three-quarter volumetric studio view ` +
        `on a solid black background with crisp edge separation and directional key and rim lighting.`
      negativePrompt =
        'anime, cartoon, cel-shaded, chibi, plastic doll skin, airbrushed wax face, melted blob, fused fingers, cropped body, watermark'
      reasoningFr = 'Sujet réel détecté : génération 3D photoréaliste physique directe avec proportions et textures réelles.'
    }
  } else {
    if (effectiveRenderMode === 'native_anime_stylized') {
      englishExpandedPrompt =
        `Masterpiece official-grade anime key visual of ${englishSubject}. Authentic native anime character design with ` +
        `crisp expressive linework, vibrant cel-shaded color separation, luminous expressive anime eyes, dynamic sculpted ` +
        `hair silhouette, and faithful costume details. Set within a richly illustrated, cohesive anime environment with ` +
        `layered foreground-to-background atmospheric depth and dramatic cinematic anime lighting. Pure 2D/cel-shaded ` +
        `anime fidelity, no realistic human skin pores.`
      negativePrompt =
        'photorealistic human skin pores, live-action photography, 3d CGI doll, uncanny valley, muddy shading, off-model face, deformed hands, extra fingers, empty background, watermark'
      reasoningFr =
        'Sujet animé détecté : développement artistique en anglais dans son style animé/cel-shadé authentique (aucune texture de peau humaine réelle forcée).'
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
        `Expressive stylized anime/illustrated adaptation of ${englishSubject}, preserving the recognizable identity, ` +
        `posture, and key traits of the subject while translating the rendering into crisp anime linework, vibrant ` +
        `cel-shaded lighting, and a richly illustrated background environment.`
      negativePrompt =
        'raw unstylized photograph, uncanny realistic skin pores, muddy colors, deformed hands, watermark'
      reasoningFr = 'Sujet réel avec demande explicite de stylisation animée : adaptation fidèle en esthétique animée.'
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

  return {
    rawPrompt: cleanRaw,
    targetModule,
    operationMode,
    subjectOntology,
    nativeOntology,
    canonicalSubjectName,
    effectiveRenderMode,
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
    modificationDeltaEn: operationMode === 'modification' ? englishSubject : null,
    reasoningFr,
    explanationFr: reasoningFr,
    badgeLabelFr,
    wasLlmRefined: false,
  }
}
