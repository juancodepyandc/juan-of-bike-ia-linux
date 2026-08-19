export type ImageEditMode =
  | 'create'
  | 'replicate'
  | 'preserve_refine'
  | 'add_element'
  | 'remove_element'
  | 'replace_element'
  | 'restyle'
  | 'background_change'
  | 'color_lighting'
  | 'repair_cleanup'
  | 'upscale_detail'
  | 'composition_pose'
  | 'scene_transform'
  | 'text_edit'

export interface ImageReplacement {
  from: string
  to: string
}

export interface ImageEditContract {
  mode: ImageEditMode
  label: string
  denoise: number | null
  stepsBoost: number
  promptLines: string[]
  negativeLines: string[]
  requestedTargets: string[]
  preserveLines: string[]
}

export interface ParsedImageIntent {
  cleanedPrompt: string
  removals: string[]
  additions: string[]
  replacements: ImageReplacement[]
  isEditIntent: boolean
  editMode: ImageEditMode
  editContract: ImageEditContract
}

export interface ParseImageIntentOptions {
  hasReference?: boolean
}

const REMOVAL_PATTERNS: Array<{ re: RegExp; label: string }> = [
  { re: /\b(?:suppression|retrait|effacement|removal|deletion)\s+(?:compl[e\u00e8]te?|complete|totale?|total|enti[e\u00e8]re?|entire|full)?\s*(?:(?:de la|des|les|une|du|le|la|un|de|d'|d\u2019|l'|l\u2019|the|a|an|any)\s*)?([^,.;!?\n]+?)(?=\s+(?:puis|ensuite|then|et\s+(?:donc\s+)?(?:l['\u2019]?\s*)?(?:ajout|insertion|integration|int[e\u00e9]gration|ajoute|rajoute|mets|met|mettre|place|insert|add|put|with|avec))\b|[,.;!?\n]|$)/giu, label: 'suppression' },
  { re: /\b(?:mais\s+)?sans\s+(?!changer\b|modifier\b|toucher\b|alt[e\u00e9]rer\b|d[e\u00e9]former\b|ab[i\u00ee]mer\b|perdre\b|effacer\b)(?:(?:de la|des|les|une|du|le|la|un|de|d'|l')\s+)?([^,.;!?\n]+?)(?=\s+(?:puis|ensuite|then)\b|[,.;!?\n]|$)/giu, label: 'sans' },
  { re: /\b(?:il\s+faut\s+)?(?:(?:enl(?:e|\u00e8)v)(?:er|es|ez|\u00e9|\u00e9s|\u00e9e|\u00e9es|ait|aient|e)|retir(?:er|es|ez|\u00e9|\u00e9s|\u00e9e|\u00e9es|ait|aient|e)|supprim(?:er|es|ez|\u00e9|\u00e9s|\u00e9e|\u00e9es|ait|aient|e)|effac(?:er|es|ez|\u00e9|\u00e9s|\u00e9e|\u00e9es|ait|aient|e)|vir(?:er|es|ez|\u00e9|\u00e9s|\u00e9e|\u00e9es|e))\s+(?:(?:de la|des|les|une|du|le|la|un|de|d'|l')\s+)?([^,.;!?\n]+?)(?=\s+(?:puis|ensuite|then|et\s+(?:remplace|change|ajoute)|and\s+(?:replace|change|add))\b|[,.;!?\n]|$)/giu, label: 'retirer' },
  { re: /\bpas\s+(?:de|d')\s*([^,.;!?\n]+?)(?=[,.;!?\n]|$)/giu, label: 'pas de' },
  { re: /,\s*ni\s+(?:(?:de la|des|les|une|du|le|la|un|de|d'|l')\s+)?([^,.;!?\n]+?)(?=[,.;!?\n]|$)/giu, label: 'ni' },
  { re: /,\s*nor\s+(?:(?:any|the|a|an)\s+)?([^,.;!?\n]+?)(?=[,.;!?\n]|$)/gi, label: 'nor' },
  { re: /\bne\s+(?:doit|peut|veut|veux)\s+pas\s+(?:y\s+)?(?:avoir|\u00eatre|figurer)\s+(?:(?:de la|des|les|du|le|la|de|d')\s+)?([^,.;!?\n]+?)(?=[,.;!?\n]|$)/giu, label: 'absence' },
  { re: /\bwithout\s+(?:(?:any|the|a|an)\s+)?([^,.;!?\n]+?)(?=[,.;!?\n]|$)/gi, label: 'without' },
  { re: /\b(?:remove|delete|erase|drop|get\s+rid\s+of)\s+(?:(?:any|the|a|an)\s+)?([^,.;!?\n]+?)(?=[,.;!?\n]|$)/gi, label: 'remove' },
  { re: /\bno\s+(?!one|body|where|matter)([^,.;!?\n]+?)(?=[,.;!?\n]|$)/gi, label: 'no' },
]

const ADDITION_PATTERNS: RegExp[] = [
  /\b(?:ajout|insertion|integration|int[e\u00e9]gration|addition)\s+(?:(?:de la|des|les|une|du|le|la|un|de|d'|d\u2019|l'|l\u2019|the|a|an|any)\s*)?([^,.;!?\n]+?)(?=\s+sans\s+(?:changer|modifier|toucher|alt[e\u00e9]rer|d[e\u00e9]former|ab[i\u00ee]mer|perdre|effacer)\b|[,.;!?\n]|$)/giu,
  /\b(?:ajoute|ajouter|rajoute|rajouter|mets|met|mettre|place|placer)\s+(?:(?:de la|des|les|une|du|le|la|un|de|d'|l')\s+)?([^,.;!?\n]+?)(?=\s+sans\s+(?:changer|modifier|toucher|alt[e\u00e9]rer|d[e\u00e9]former|ab[i\u00ee]mer|perdre|effacer)\b|[,.;!?\n]|$)/giu,
  /\b(?:add|insert|place|put)\s+(?:(?:any|the|a|an)\s+)?([^,.;!?\n]+?)(?=\s+without\s+(?:changing|modifying|touching|altering|deforming|damaging|losing|erasing)\b|[,.;!?\n]|$)/gi,
  /(?<!continue\s)(?<!continu\s)(?<!coherent\s)(?<!coherente\s)(?<!coh[e\u00e9]rent\s)(?<!coh[e\u00e9]rente\s)\bavec\s+(?:(?:de la|des|les|une|du|le|la|un|de|d'|l')\s+)?([^,.;!?\n]+?)(?=\s+sans\s+(?:changer|modifier|toucher|alt[e\u00e9]rer|d[e\u00e9]former|ab[i\u00ee]mer|perdre|effacer)\b|[,.;!?\n]|$)/giu,
  /\bwith\s+(?:(?:any|the|a|an)\s+)?([^,.;!?\n]+?)(?=\s+without\s+(?:changing|modifying|touching|altering|deforming|damaging|losing|erasing)\b|[,.;!?\n]|$)/gi,
]

const REPLACEMENT_PATTERNS: RegExp[] = [
  /\b(?:remplace|remplacer|replace)\s+(.+?)\s+(?:par|avec|by|with)\s+(.+?)(?=\s+(?:puis|ensuite|then)\b|[,.;!?\n]|$)/giu,
  /\b(?:change|changer)\s+(.+?)\s+(?:en|into|to)\s+(.+?)(?=\s+(?:puis|ensuite|then)\b|[,.;!?\n]|$)/giu,
]

const PRESERVATION_PATTERNS: RegExp[] = [
  /\b(?:m\u00eame|meme)\s+(?:image|photo|illustration|dessin|rendu)\b/iu,
  /\b(?:garde|keep|preserve|conserve)\s+(?:la|the|l')?\s*(?:image|photo|illustration|dessin|composition|reste|tout)\b/iu,
  /\b(?:modifie|change|edit)\s+(?:juste|seulement|only|just)\b/iu,
  /\b(?:exactement\s+(?:la|le|l')?\s*(?:m\u00eame|meme)|exactly\s+(?:the\s+)?same|same\s+(?:image|photo|composition|framing|camera))\b/iu,
  /\b(?:reprends?|reuse|r\u00e9utilise|reutilise)\s+(?:la|the|l')?\s*(?:image|photo)\b/iu,
  /\b(?:r[eé]pliqu|replicate|reprodui|reproduce|recr[eé]|recreate|dupliqu|copi|imit|fais\s+pareil|identique)\b/iu,
  /\bsans\s+(?:changer|modifier|toucher|alt[e\u00e9]rer|d[e\u00e9]former|ab[i\u00ee]mer|perdre|effacer)\b/iu,
  /\bwithout\s+(?:changing|modifying|touching|altering|deforming|damaging|losing|erasing)\b/iu,
]

const REPLICATION_PATTERN = /\b(r[eé]pliqu(?:er|ez|e|ent|ait|ant|es|\u00e9|\u00e9e|\u00e9s|\u00e9es)|r[eé]plication|replicate|replicating|reproduction|reprodui(?:re|s|t|sez|sent|sant)|recr[eé](?:er|ez|e|ent|ait|ant|es|\u00e9|\u00e9e|\u00e9s|\u00e9es)|recreate|recreating|dupliqu(?:er|ez|e|ent|ait|ant|es|\u00e9|\u00e9e|\u00e9s|\u00e9es)|duplication|duplicate|duplicating|copi(?:er|ez|e|ent|ait|ant|es|\u00e9|\u00e9e|\u00e9s|\u00e9es)|copy|copying|imit(?:er|ez|e|ent|ait|ant|es|\u00e9|\u00e9e|\u00e9s|\u00e9es)|imitation|mimic|mimicking|fais\s+pareil|clone|cloner|clonage|remix)\b/i

const CONNECTOR_SPLIT = /\s+(?:et|and|ou|or|ni|nor)\s+/iu
const LEADING_REMOVAL_VERB = /^(?:sans|without|no|pas\s+de)\s+(?:(?:de la|des|les|une|du|le|la|un|de|d'|l'|the|a|an|any)\s+)?/iu
const LEADING_ARTICLE_ONLY = /^(?:de la|des|les|une|du|le|la|l|un|de|d'|d\u2019|l'|l\u2019|the|a|an|any)\s+/iu
const LEADING_ATTACHED_ARTICLE = /^(?:d|l)['\u2019]/iu
const LEADING_INTENSITY_MODIFIER = /^(?:compl[e\u00e8]tement|completement|compl[e\u00e8]te?|complete|totalement|totale?|enti[e\u00e8]rement|entierement|enti[e\u00e8]re?|fully|completely|entirely|totally)\s+(?:de\s+|of\s+)?/iu

const TEXT_EDIT_PATTERN = /\b(pancarte|panneau|affiche|inscription|slogan|logo texte|texte|ecrire|ecris|ecrit|mot|phrase|message|label|etiquette|sign|billboard|write|text saying|message saying)\b/i
const NEGATED_TEXT_PATTERN = /\b(?:sans|aucun|aucune|pas\s+de|no|without)\s+(?:texte|inscription|slogan|message|label|etiquette|sign|text|logo)\b/i
const EXPLICIT_TEXT_COMMAND_PATTERN = /\b(?:ecrire|ecris|ecrit|write|text saying|message saying)\b/i
const BACKGROUND_PATTERN = /\b(fond|arri[e\u00e8]re.?plan|background|decor|d[e\u00e9]cor|environnement|nuit\s+[eé]toil[eé]e|ciel\s+[eé]toil[eé]|ciel\s+de\s+nuit|en\s+pleine\s+nuit|coucher\s+de\s+soleil|soleil\s+couchant|soleil\s+levant|lever\s+de\s+soleil|aurore\s+bor[eé]ale|clair\s+de\s+lune|pleine\s+lune|sous\s+la\s+pluie|sous\s+la\s+neige|starry\s+night|night\s+sky|starry\s+sky|sunset|sunrise|moonlight|twilight)\b/i
const BACKGROUND_PRESERVE_PATTERN = /\b(?:garde|garder|keep|preserve|conserve|conserver)\b.{0,140}\b(?:fond|arriere.?plan|background|decor|environnement)\b/i
const SCENE_PATTERN = /\b(nouvelle scene|new scene|autre endroit|another place|transporte|teleporte|t[e\u00e9]l[e\u00e9]porte|change le decor|change de decor|nouvel endroit|nouveau lieu|change pose|change clothes|change outfit|autre action)\b/i
const RESTYLE_PATTERN = /\b(pixel art|pixel-art|sprite|anime|manga|aquarelle|watercolor|peinture a l'huile|oil painting|comic|bd|low poly|isometrique|isometric|flat illustration|concept art|croquis|sketch|style)\b/i
const COLOR_LIGHT_PATTERN = /\b(couleur|color|colorise|coloriser|colorer|palette|lumiere|lumi\u00e8re|eclairage|eclairage|lighting|eclaire|assombris|contraste|exposition|teinte|hue|saturation)\b/i
const REPAIR_PATTERN = /\b(corrige|corriger|nettoie|nettoyer|r[e\u00e9]pare|r[e\u00e9]parer|retouche|retoucher|clean up|cleanup|fix|repair|artefact|artifact|defaut|d[e\u00e9]faut|bruit|noise)\b/i
const UPSCALE_PATTERN = /\b(upscale|haute resolution|haute definition|high resolution|hi.?res|4k|8k|plus net|plus detaille|plus pr[e\u00e9]cis|sharp|sharpen)\b/i
const MOVE_PATTERN = /\b(d[e\u00e9]place|d[e\u00e9]placer|repositionne|repositionner|d[e\u00e9]cale|d[e\u00e9]caler|move|reposition|shift)\b/i
const POSE_PATTERN = /\b(pose|sourire|smile|expression|regard|yeux|main|bras|jambe|tourne|rotation|recadre|crop|zoom|cadre|composition)\b/i
const GENERIC_EDIT_PATTERN = /\b(modifie|modifier|change|changer|edite|edit|retouche|retoucher|transforme|transformer|transform|fais|faire|rends|rendre|ameliore|ameliorer|enhance|improve|d[e\u00e9]place|d[e\u00e9]placer|repositionne|repositionner|d[e\u00e9]cale|d[e\u00e9]caler|move|reposition|shift|r[eé]plique|r[eé]pliquer|replicate|reproduis|reproduire|reproduce|recr[eé]e|recr[eé]er|recreate|duplique|dupliquer|duplicate|copie|copier|copy|imite|imiter|imitate|clone|cloner)\b/i
const ADD_COMMAND_PATTERN = /\b(ajoute|ajouter|rajoute|rajouter|mets|met|mettre|place|placer|add|insert|put)\b/i
const HUMAN_REMOVAL_TARGET_RE = /\b(?:personne|personnage|humain|humaine|homme|femme|garcon|fille|gars|mec|meuf|individu|sujet|ami|amie|copain|copine|person|character|human|man|woman|boy|girl|guy|dude|male|female|subject|friend)\b/i
const CLOTHING_OR_ACCESSORY_TARGET_RE = /^(?:uniquement|seulement|only|just)?\s*(?:(?:le|la|les|un|une|des|du|de|d'|l'|the|a|an)\s+)?(?:t\s?-?\s?shirt|tee\s?shirt|chemise|shirt|pull|sweat|hoodie|veste|jacket|manteau|coat|cape|cloak|pantalon|pants|short|shorts|robe|dress|jupe|skirt|tenue|outfit|vetement|vetements|clothing|chaussure|chaussures|shoe|shoes|botte|bottes|boots|chapeau|hat|casquette|cap|lunettes|glasses|accessoire|accessory)\b/i
const NON_ACTIONABLE_REMOVAL_TARGET_RE = /^(?:nudite|nudity|contenu explicite|explicit content|explicite|explicit|nsfw|sexe|sexual|sexuel|sexuelle|obscene|obscene content|doublon|doublons|duplicate|duplicates|monde|foule|gens|personne|personnes|passant|passants|personnages?|bystanders?|crowd|extra\s+people|random\s+people|ajouter\s+de\s+monde|ajouter\s+de\s+la\s+foule|ajouter\s+du\s+monde|ajouter\s+des\s+personnages?|mettre\s+du\s+monde)$/i
const META_REFERENCE_TARGET_RE = /^(?:(?:plusieurs|quelques|mes|les|la|le|cette|ces|deux|2|3|mon|ma)\s+)?(?:r[eé]f[eé]rences?|references?|images?|photos?|illustrations?|visuels?|fichiers?|rendus?|source|sources?|modele|mod[eè]les?|prompt|prompts?)(?:\s+(?:fournies?|transmises?|jointes?|disponibles?|existantes?|actuelles?|ci-dessus|ci-dessous|humain|soign[eé]))?$/i

function stripAccents(text: string): string {
  return text.normalize('NFD').replace(/[\u0300-\u036f]/g, '')
}

function normalizeForIntent(text: string): string {
  return stripAccents(text).replace(/\s+/g, ' ').trim().toLowerCase()
}

export function isHumanRemovalTarget(target: string): boolean {
  const normalized = normalizeForIntent(target)
  if (CLOTHING_OR_ACCESSORY_TARGET_RE.test(normalized)) return false
  return HUMAN_REMOVAL_TARGET_RE.test(normalized)
}

export function hasHumanRemovalTarget(targets: string[]): boolean {
  return targets.some(isHumanRemovalTarget)
}

function cleanTarget(value: string): string {
  return value
    .replace(/\s+sans\s+(?:changer|modifier|toucher|alt[e\u00e9]rer|d[e\u00e9]former|ab[i\u00ee]mer|perdre|effacer|ajouter|mettre)\b.*$/iu, '')
    .replace(/\s+without\s+(?:changing|modifying|touching|altering|deforming|damaging|losing|erasing|adding)\b.*$/iu, '')
    .replace(LEADING_REMOVAL_VERB, '')
    .replace(LEADING_INTENSITY_MODIFIER, '')
    .replace(LEADING_ARTICLE_ONLY, '')
    .replace(LEADING_ATTACHED_ARTICLE, '')
    .replace(/\b(?:from the frame|de l'image|de la photo|du cadre|sur l'image|dans l'image)\b/giu, '')
    .replace(/\s+/g, ' ')
    .trim()
}

function splitConnectors(value: string): string[] {
  if (!CONNECTOR_SPLIT.test(value)) return [value]
  return value.split(CONNECTOR_SPLIT).map(cleanTarget).filter(Boolean)
}

function dedupeAndClean(values: string[]): string[] {
  const seen = new Set<string>()
  const out: string[] = []
  for (const raw of values) {
    for (const item of splitConnectors(raw)) {
      const value = cleanTarget(item)
      if (!value || value.length < 2) continue
      const key = normalizeForIntent(value)
      if (NON_ACTIONABLE_REMOVAL_TARGET_RE.test(key)) continue
      if (META_REFERENCE_TARGET_RE.test(key)) continue
      if (seen.has(key)) continue
      seen.add(key)
      out.push(value)
    }
  }
  return out
}

function collectMatches(prompt: string, patterns: RegExp[]): string[] {
  const values: string[] = []
  for (const pattern of patterns) {
    const clone = new RegExp(pattern.source, pattern.flags)
    for (const match of prompt.matchAll(clone)) {
      const value = match[1]?.trim()
      if (value) values.push(value)
    }
  }
  return dedupeAndClean(values)
}

function collectReplacements(prompt: string): ImageReplacement[] {
  const values: ImageReplacement[] = []
  const seen = new Set<string>()

  for (const pattern of REPLACEMENT_PATTERNS) {
    const clone = new RegExp(pattern.source, pattern.flags)
    for (const match of prompt.matchAll(clone)) {
      const from = cleanTarget(match[1] || '')
      const to = cleanTarget(match[2] || '')
      if (!from || !to) continue
      const key = `${normalizeForIntent(from)}=>${normalizeForIntent(to)}`
      if (seen.has(key)) continue
      seen.add(key)
      values.push({ from, to })
    }
  }

  return values
}

const STYLE_PRESERVE_PATTERN = /\b(?:garde|garder|gardant|preserve|conserve|conserver|sans\s+changer|sans\s+modifier|m[eê]me)\b.{0,40}\bstyle\b/iu
const EXPLICIT_RESTYLE_GENRE = /\b(pixel art|pixel-art|sprite|anime|manga|aquarelle|watercolor|peinture a l'huile|oil painting|comic|bd|low poly|isometrique|isometric|flat illustration|concept art|croquis|sketch)\b/i
const EXPLICIT_REMOVE_COMMAND_PATTERN = /\b(?:enl[eè]ve|enl[eè]ver|retire|retirer|supprime|supprimer|efface|effacer|virer|vire|remove|delete|erase|drop)\b/i

function detectMode(prompt: string, removals: string[], additions: string[], replacements: ImageReplacement[], options: ParseImageIntentOptions): ImageEditMode {
  const normalized = normalizeForIntent(prompt)
  const isBackgroundEdit = (BACKGROUND_PATTERN.test(normalized) && (GENERIC_EDIT_PATTERN.test(normalized) || options.hasReference || /\b(en|vers|dans|au|sous|ciel|nuit|fond)\b/i.test(normalized))) && !BACKGROUND_PRESERVE_PATTERN.test(normalized)
  const isRestyleEdit = (EXPLICIT_RESTYLE_GENRE.test(normalized) || (/\bstyle\b/i.test(normalized) && /\b(?:change|changer|nouveau|autre|en\s+style|passe\s+en|transforme\s+en)\b/i.test(normalized))) && !STYLE_PRESERVE_PATTERN.test(normalized)
  const hasPreservationCue = PRESERVATION_PATTERNS.some((pattern) => pattern.test(prompt))
  const hasReplicationCue = REPLICATION_PATTERN.test(normalized)
  const hasAddCommand = ADD_COMMAND_PATTERN.test(normalized)

  if (removals.length > 0) return 'remove_element'
  if (isBackgroundEdit && (options.hasReference || GENERIC_EDIT_PATTERN.test(normalized))) return 'background_change'
  if (replacements.length > 0) return 'replace_element'
  if (TEXT_EDIT_PATTERN.test(normalized) && !NEGATED_TEXT_PATTERN.test(normalized) && (options.hasReference || GENERIC_EDIT_PATTERN.test(normalized) || hasAddCommand || EXPLICIT_TEXT_COMMAND_PATTERN.test(normalized))) return 'text_edit'
  if (SCENE_PATTERN.test(normalized)) return 'scene_transform'
  if (hasReplicationCue && (options.hasReference || removals.length === 0)) {
    if (isRestyleEdit && EXPLICIT_RESTYLE_GENRE.test(normalized) && (options.hasReference || GENERIC_EDIT_PATTERN.test(normalized))) return 'restyle'
    if (COLOR_LIGHT_PATTERN.test(normalized) && GENERIC_EDIT_PATTERN.test(normalized)) return 'color_lighting'
    return 'replicate'
  }
  if (additions.length > 0 && (hasAddCommand || options.hasReference)) return 'add_element'
  if (isRestyleEdit && (options.hasReference || GENERIC_EDIT_PATTERN.test(normalized))) return 'restyle'
  if (COLOR_LIGHT_PATTERN.test(normalized) && GENERIC_EDIT_PATTERN.test(normalized)) return 'color_lighting'
  if (REPAIR_PATTERN.test(normalized)) return 'repair_cleanup'
  if (UPSCALE_PATTERN.test(normalized)) return 'upscale_detail'
  if (MOVE_PATTERN.test(normalized)) return 'composition_pose'
  if (POSE_PATTERN.test(normalized) && GENERIC_EDIT_PATTERN.test(normalized)) return 'composition_pose'
  if (hasPreservationCue) return 'preserve_refine'
  if (GENERIC_EDIT_PATTERN.test(normalized)) return 'preserve_refine'

  return 'create'
}

function buildEditContract(mode: ImageEditMode, removals: string[], additions: string[], replacements: ImageReplacement[]): ImageEditContract {
  const replacementTargets = replacements.flatMap((item) => [item.from, item.to]).filter(Boolean)
  const requestedTargets = mode === 'remove_element'
    ? removals
    : mode === 'add_element'
      ? additions
      : mode === 'replace_element'
      ? replacementTargets
      : []
  const removesHumanTarget = hasHumanRemovalTarget(removals)

  const commonPreserve = [
    'preserver l identite du sujet principal',
    'preserver le cadrage, les proportions et la perspective sauf demande explicite',
    'ne modifier que les zones concernees par la demande',
  ]

  const table: Record<ImageEditMode, Omit<ImageEditContract, 'mode' | 'requestedTargets'>> = {
    create: {
      label: 'creation libre',
      denoise: null,
      stepsBoost: 0,
      promptLines: [],
      negativeLines: [],
      preserveLines: [],
    },
    replicate: {
      label: 'replication fidele',
      denoise: 0.28,
      stepsBoost: 8,
      promptLines: [
        'reproduire fidelement le sujet, l identite, les traits et la composition de la reference',
        'conserver l allure generale, la perspective et les proportions sans deformation',
      ],
      negativeLines: [
        'identite perdue',
        'morphologie deformee',
        'composition alteree',
        'nouveau sujet invente',
        'traits incoherents',
      ],
      preserveLines: commonPreserve,
    },
    preserve_refine: {
      label: 'amelioration douce',
      denoise: 0.18,
      stepsBoost: 6,
      promptLines: ['ameliorer la nettete, la lumiere et les textures sans changer le contenu'],
      negativeLines: ['identite modifiee', 'nouveau sujet', 'composition changee'],
      preserveLines: commonPreserve,
    },
    add_element: {
      label: 'ajout cible',
      denoise: 0.48,
      stepsBoost: 10,
      promptLines: [
        `integrer naturellement les nouveaux elements demandes${additions.length ? `: ${additions.join(', ')}` : ''}`,
        'si l ajout concerne une cape, un vetement ou un accessoire, le porter par-dessus sans recolorer ni modifier la tenue existante',
        'preserver scrupuleusement le visage, la tete, la coiffure, la couleur de cheveux et l identite du personnage',
        'ajouter des ombres de contact, reflets et perspective coherents',
      ],
      negativeLines: [
        'vetement existant recolore',
        'tenue modifiee',
        'visage altere',
        'coiffure modifiee',
        'identite perdue',
        'objet flottant',
        'collage visible',
        'ombres incoherentes',
        'doublons inutiles',
      ],
      preserveLines: commonPreserve,
    },
    remove_element: {
      label: 'suppression et reconstruction',
      denoise: 0.50,
      stepsBoost: 12,
      promptLines: [
        'reconstruire naturellement la zone liberee',
        'resultat final propre, sans trace ni silhouette fantome de l element retire',
        ...(removesHumanTarget
          ? [
              'si la cible retiree est une personne ou un personnage, retirer toute sa silhouette visible: visage, cheveux, corps, vetements, chemise, bretelles, accessoires, ombres et points de contact',
              'reconstruire derriere elle le fond et les parties visibles des sujets restants sans garder de textile appartenant a la personne retiree',
              'ne jamais combler la zone supprimee en agrandissant l epaule, le torse, la poitrine, le cou ou la morphologie d une personne restante; utiliser le fond ou la scene quand le corps n etait pas visible dans la reference',
            ]
          : []),
      ],
      negativeLines: [
        ...removals,
        ...(removesHumanTarget
          ? ['vetements de la personne retiree', 'chemise residuelle', 'bretelles residuelles', 'corps residuel', 'accessoire residuel', 'epaule de la personne retiree', 'epaule surdimensionnee', 'torse invente', 'poitrine agrandie', 'morphologie deformee']
          : []),
        'trace fantome',
        'ombre residuelle',
        'bord de collage',
        'zone floue',
      ],
      preserveLines: commonPreserve,
    },
    replace_element: {
      label: 'remplacement cible',
      denoise: 0.54,
      stepsBoost: 12,
      promptLines: [`remplacer par le nouvel element demande${replacements.length ? `: ${replacements.map((item) => item.to).join(', ')}` : ''}`, 'fusionner le remplacement avec la lumiere, l echelle et les contacts au sol'],
      negativeLines: [...replacements.map((item) => item.from), 'ancien element restant', 'double version', 'collage visible'],
      preserveLines: commonPreserve,
    },
    restyle: {
      label: 'changement de style',
      denoise: 0.62,
      stepsBoost: 10,
      promptLines: ['transformer le style visuel tout en gardant la meme scene et les memes formes principales'],
      negativeLines: ['identite perdue', 'composition inventee', 'elements non demandes'],
      preserveLines: commonPreserve,
    },
    background_change: {
      label: 'changement de fond',
      denoise: 0.52,
      stepsBoost: 10,
      promptLines: [
        'changer uniquement le fond, le ciel ou l ambiance du decor demande',
        'garder le sujet principal 100% identique: preserver exactement le visage, les traits, la coiffure, la couleur de cheveux, les yeux, la morphologie et les vetements d origine',
        'aucun personnage secondaire ajoute, aucune foule en arriere-plan, aucun passant non demande',
      ],
      negativeLines: [
        'sujet modifie',
        'visage altere',
        'coiffure modifiee',
        'couleur de cheveux changee',
        'personnages secondaires inventes',
        'foule aleatoire',
        'passants non demandes',
        'mauvais detourage',
        'ombres incoherentes',
        'fond collage',
      ],
      preserveLines: commonPreserve,
    },
    color_lighting: {
      label: 'couleur et lumiere',
      denoise: 0.34,
      stepsBoost: 8,
      promptLines: ['modifier uniquement la couleur, la lumiere, le contraste ou l ambiance demandes'],
      negativeLines: ['forme changee', 'nouvel objet', 'composition modifiee'],
      preserveLines: commonPreserve,
    },
    repair_cleanup: {
      label: 'correction propre',
      denoise: 0.24,
      stepsBoost: 8,
      promptLines: ['corriger les defauts visibles, nettoyer les artefacts et garder le contenu intact'],
      negativeLines: ['sur-lissage', 'texture plastique', 'details effaces', 'contenu invente'],
      preserveLines: commonPreserve,
    },
    upscale_detail: {
      label: 'detail et resolution',
      denoise: 0.16,
      stepsBoost: 6,
      promptLines: ['augmenter les details lisibles sans changer les formes ni la composition'],
      negativeLines: ['suraccentuation', 'texture inventee', 'visage modifie', 'artefacts de nettete'],
      preserveLines: commonPreserve,
    },
    composition_pose: {
      label: 'pose ou composition',
      denoise: 0.46,
      stepsBoost: 10,
      promptLines: ['appliquer la pose, l expression, le cadrage ou la composition demandes avec anatomie coherente'],
      negativeLines: ['membres deformes', 'mains cassees', 'visage instable', 'composition chaotique'],
      preserveLines: commonPreserve,
    },
    scene_transform: {
      label: 'transformation de scene',
      denoise: 0.65,
      stepsBoost: 12,
      promptLines: [
        'transformer la scene selon la demande tout en conservant l identite, le visage, la coiffure et les vetements principaux du sujet',
        'perspective spatiale lineaire et echelle coherente, aucun personnage geant au loin, aucun passant difforme',
      ],
      negativeLines: [
        'identite perdue',
        'visage altere',
        'coiffure modifiee',
        'personnages geants au loin',
        'foule difforme',
        'perspective impossible',
        'sujet duplique',
        'collage incoherent',
      ],
      preserveLines: commonPreserve,
    },
    text_edit: {
      label: 'texte ou logo',
      denoise: 0.66,
      stepsBoost: 12,
      promptLines: ['reecrire ou ajouter le texte demande avec lettres nettes et placement coherent'],
      negativeLines: ['lettres aleatoires', 'texte illisible', 'mots deformes', 'double inscription'],
      preserveLines: commonPreserve,
    },
  }

  return {
    mode,
    requestedTargets,
    ...table[mode],
  }
}

export function parseImageIntent(rawPrompt: string, options: ParseImageIntentOptions = {}): ParsedImageIntent {
  const original = rawPrompt
  const removals: string[] = []
  let positive = original

  for (const { re } of REMOVAL_PATTERNS) {
    const cloneA = new RegExp(re.source, re.flags)
    for (const match of positive.matchAll(cloneA)) {
      const captured = match[1]?.trim()
      if (captured) removals.push(captured)
    }
    const cloneB = new RegExp(re.source, re.flags)
    positive = positive.replace(cloneB, ' ')
  }

  positive = positive
    .replace(/\s+([,.;!?])/g, '$1')
    .replace(/([,.;!?])\1+/g, '$1')
    .replace(/\s{2,}/g, ' ')
    .replace(/^\s*(?:puis|ensuite|then|and|et)\s+/iu, '')
    .replace(/^[\s,;.]+|[\s,;]+$/g, '')
    .trim()

  const cleanRemovals = dedupeAndClean(removals)
  const additions = collectMatches(original, ADDITION_PATTERNS)
  const replacements = collectReplacements(original)
  const editMode = detectMode(original, cleanRemovals, additions, replacements, options)
  const editContract = buildEditContract(editMode, cleanRemovals, additions, replacements)

  return {
    cleanedPrompt: positive || original.trim(),
    removals: cleanRemovals,
    additions,
    replacements,
    isEditIntent: editMode !== 'create',
    editMode,
    editContract,
  }
}

export function buildNegativePrompt(
  userNegative: string,
  parsedRemovals: string[],
): string {
  const userBits = userNegative.split(/[,;\n]+/).map((item) => item.trim()).filter(Boolean)
  const merged = dedupeAndClean([...userBits, ...parsedRemovals])
  return merged.join(', ')
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}

export function resolveReferenceDenoise(intent: ParsedImageIntent, userDenoise: number, style?: string): number {
  const target = intent.editContract.denoise
  if (target === null) return userDenoise

  const pixelRestyle = style === 'pixel_art' && intent.editMode !== 'preserve_refine' && intent.editMode !== 'upscale_detail'
  const desired = pixelRestyle ? Math.max(target, 0.68) : target

  if (intent.editMode === 'replicate') {
    return clamp(Math.min(userDenoise, desired), 0.12, 0.40)
  }

  if (intent.editMode === 'preserve_refine' || intent.editMode === 'repair_cleanup' || intent.editMode === 'upscale_detail') {
    return clamp(Math.min(userDenoise, desired), 0.08, 0.35)
  }

  if (intent.editMode === 'color_lighting') {
    return clamp(Math.max(Math.min(userDenoise, 0.55), desired), 0.18, 0.62)
  }

  return clamp(Math.max(userDenoise, desired), desired, 0.86)
}
