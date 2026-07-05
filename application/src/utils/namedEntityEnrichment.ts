/**
 * namedEntityEnrichment — ancrage des éditions "ajoute le personnage X".
 *
 * Problème observé en live (module image) : demander à FLUX.1 Kontext
 * « ajoute le personnage Kora de Nebula » produit un résultat aléatoire si
 * édite très bien ce qu'il CONNAÎT (un chapeau, un fond, une couleur), mais il
 * n'a aucune représentation d'un personnage NOMMÉ récent/spécifique : on lui
 * donne la composition (« ami, main sur l'épaule ») mais zéro information
 * d'APPARENCE, donc il invente.
 *
 * Stratégie : quand une édition d'AJOUT cible une entité nommée explicitement
 * (« personnage X », « mascotte X », « character named X »), on demande au LLM
 * texte local une description visuelle concise. Deux issues :
 *   - le modèle décrit l'entité → on injecte la description dans l'instruction
 *     d'édition (Kontext a enfin des traits concrets à rendre) ;
 *   - le modèle ne connaît pas → on remonte un conseil clair à l'utilisateur
 *     (« joins une image de référence du personnage ») au lieu de livrer du
 *     bruit en silence.
 *
 * Générique : marche pour n'importe quelle entité nommée (personnage, mascotte,
 * marque, figure). Détection volontairement conservatrice (cue explicite) pour
 * NE PAS se déclencher sur un nom commun générique (« ajoute un chapeau »).
 */

export interface DescribeEntityOptions {
  generate?: (model: string, prompt: string) => Promise<{ response?: string } | null | undefined>
  model?: string
  signal?: AbortSignal
  /** Timeout de l'appel LLM (défaut 12s). */
  timeoutMs?: number
}

/**
 * Connecteurs d'intention/relation qui marquent la FIN du nom de l'entité.
 * On stoppe aussi sur un marqueur de FRANCHISE introduit par un article
 * ("de The Amazing Digital Circus", "of the ...") : "Jax de The Amazing
 * Digital Circus" -> "Jax". On ne stoppe PAS sur "de <Nom>" simple pour
 * préserver les vrais noms composés ("Kora de Nebula").
 */
const NAME_STOP = /\s+(?:de\s+the\b|du\s+the\b|of\s+the\b|from\s+the\b|de\s+fa[cç]on|de\s+mani[eè]re|d['’]une\s+mani[eè]re|afin\b|pour\b|qui\b|en\s+train|comme\b|avec\b|tenant\b|posant\b|montrant\b|faisant\b|assis\b|debout|allong[ée]|devant\b|face\s+a\b|face\s+au\b|à\s+c[oô]t[ée]|a\s+cot[ée]|sur\b|dans\b|near\b|next\b|in\s+front\b|holding\b|showing\b|with\b)/iu

/** Mots-clés qui annoncent explicitement une entité nommée à ajouter. */
const ENTITY_CUE = /\b(?:personnages?|perso|mascottes?|mascot|character|figure|h[ée]ros|h[ée]ro[ïi]ne|villain|m[ée]chant)\b/iu

/** Verbes d'ajout (FR + EN). */
const ADD_VERB = /\b(?:ajout|ajoute[rz]?|rajoute[rz]?|met[s]?|mettre|place[rz]?|pose[rz]?|incruste[rz]?|ins[eè]re[rz]?|integre[rz]?|int[èe]gre[rz]?|add|insert|put|place)\b/iu

const LEADING_ENTITY_DESCRIPTORS = /^(?:(?:un|une|le|la|les|des|du|de|d['’]|the|a|an)\s+|(?:petit|petite|grand|grande|jeune|adulte|nouveau|nouvelle|small|big|young|adult|new)\s+|(?:photo[-\s]?r[eé]aliste|photorealistic|realistic|r[eé]aliste|realiste|anime|manga|cartoon|cinematic|stylized|stylise|stylis[eé])\s+)+/iu
const LOWERCASE_GENERIC_START = /^(?:de\s+|d['’])?(?:jardinier|jardiniere|gardener|personne|person|homme|man|femme|woman|adulte|adult|enfant|child|chien|dog|chat|cat|animal|robot|ouvrier|worker|serveur|waiter|policier|police|pompier|firefighter|soldat|soldier|ami|friend)\b/iu

function clean(s: string): string {
  return s.replace(/\s+/g, ' ').trim()
}

function normalizeEntityName(s: string): string {
  return clean(s)
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
}

function stripLeadingEntityDescriptors(value: string): string {
  let out = clean(value)
  for (let i = 0; i < 4; i += 1) {
    const next = out.replace(LEADING_ENTITY_DESCRIPTORS, '').trim()
    if (next === out) break
    out = next
  }
  return out
}

function looksLikeExplicitNamedEntity(value: string): boolean {
  const trimmed = clean(value)
  if (!trimmed || LOWERCASE_GENERIC_START.test(trimmed)) return false
  return /^[A-ZÀ-Ÿ0-9]/u.test(trimmed) || /\b[A-Z0-9]{2,}\b/u.test(trimmed)
}

// Glossaire de DERNIER RECOURS (offline only). La voie normale est la recherche
// auto-informée (selfInformedReference) : vraie image + description vision. Ces
// entrées ne servent que si la recherche échoue hors-ligne ; elles doivent donc
// rester EXACTES (la description vague d'avant sortait un lapin violet générique).
const ENTITY_APPEARANCE_GLOSSARY: Array<{ aliases: string[]; description: string }> = []

export function lookupKnownEntityAppearance(entity: string): string {
  const normalized = normalizeEntityName(entity)
  if (!normalized) return ''
  for (const item of ENTITY_APPEARANCE_GLOSSARY) {
    if (item.aliases.some((alias) => normalized === alias || normalized.includes(alias))) {
      return item.description
    }
  }
  return ''
}

/**
 * Extrait le nom de l'entité ciblée par une édition d'ajout, ou null si la
 * demande ne nomme pas explicitement de personnage/entité (ex : nom commun).
 *
 * « ajoute le personnage Kora de Nebula de façon a montrer de l'amicalité »
 *   → "Kora de Nebula"
 * « ajoute un chapeau rouge » → null
 */
export function detectNamedAddTarget(prompt: string): string | null {
  const text = clean(prompt)
  if (!text) return null
  // Il faut au moins un verbe d'ajout pour parler d'enrichissement.
  if (!ADD_VERB.test(text)) return null

  // 1) Cue explicite « personnage/mascotte/character … <nom> ».
  const cue = text.match(
    /\b(?:personnages?|perso|mascottes?|mascot|character|figure|h[ée]ros|h[ée]ro[ïi]ne|villain|m[ée]chant)\s+(?:de\s+jeu\s+)?(?:nomm[ée]e?s?\s+|appel[ée]e?s?\s+|named\s+|called\s+|de\s+|du\s+)?(.+)$/iu,
  )
  if (cue) {
    let tail = stripLeadingEntityDescriptors(cue[1])
    const stop = tail.search(NAME_STOP)
    if (stop > 0) tail = tail.slice(0, stop)
    const name = clean(tail).split(/\s+/).slice(0, 4).join(' ').replace(/[,.;:!?]+$/u, '').trim()
    if (!looksLikeExplicitNamedEntity(name)) return null
    if (name && name.length >= 2) return name
  }

  return null
}

/** Vrai s'il reste du français de contenu (description non aboutie / repli). */
function looksFrench(text: string): boolean {
  return /[àâäçèéêëîïôöùûœ]|\b(?:un|une|le|la|les|avec|sans|cheveux|visage|corps|tête|porte)\b/i.test(text)
}

function withTimeout<T>(p: Promise<T>, ms: number): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const t = setTimeout(() => reject(new Error('describe timeout')), ms)
    p.then((v) => { clearTimeout(t); resolve(v) }, (e) => { clearTimeout(t); reject(e) })
  })
}

const DESCRIBE_PROMPT = (entity: string, fullRequest: string) => `/no_think
You help an instruction-based image editor add a specific named character or entity into a user's photo.

Task: describe the VISUAL APPEARANCE of "${entity}" so the editor can draw it.
Rules:
- Output ONE concise English line, max 30 words: species/body type, main colors, distinctive features, outfit/accessories.
- Describe appearance ONLY. No names of the franchise, no preamble, no quotes, no extra commentary.
- If you are NOT reasonably confident what "${entity}" looks like, output exactly: NONE

Context (user request): ${fullRequest}
Appearance:`

/**
 * Demande au LLM une description visuelle EN de l'entité nommée.
 * Retourne '' si le modèle ne connaît pas (NONE), si l'appel échoue, ou si le
 * texte rendu reste du français (description non aboutie). Ne lève jamais.
 */
export async function describeNamedEntity(
  entity: string,
  options: DescribeEntityOptions = {},
  fullRequest = '',
): Promise<string> {
  const target = clean(entity)
  if (!target) return ''
  const knownAppearance = lookupKnownEntityAppearance(target)
  if (knownAppearance) return knownAppearance
  if (!options.generate || !options.model) return ''
  if (options.signal?.aborted) return ''
  try {
    const res = await withTimeout(
      Promise.resolve(options.generate(options.model, DESCRIBE_PROMPT(target, clean(fullRequest) || target))),
      options.timeoutMs ?? 12_000,
    )
    const text = (res?.response || '')
      .replace(/<think>[\s\S]*?<\/think>/g, '')
      .replace(/<think>[\s\S]*$/g, '')
      .replace(/^["'`\s]+|["'`\s]+$/g, '')
      .trim()
    if (!text) return ''
    if (/^none\b/i.test(text) || text.length < 8) return ''
    if (looksFrench(text)) return ''
    // garde-fou longueur : on coupe à ~240 caractères (1 ligne).
    return text.length > 240 ? `${text.slice(0, 239)}…` : text
  } catch {
    return ''
  }
}

/**
 * Construit la clause d'apparence à injecter dans l'instruction d'édition.
 * Vide si pas de description.
 */
export function buildEntityAppearanceClause(entity: string, description: string): string {
  const desc = clean(description)
  if (!desc) return ''
  return `The added character (${clean(entity)}) must look exactly like this: ${desc}`
}

/** Conseil utilisateur quand l'apparence de l'entité est inconnue du modèle. */
export function entityReferenceAdvisory(entity: string): string {
  return `Aurora ne connaît pas l'apparence de « ${clean(entity)} ». Pour un ajout fidèle, joins une image de référence du personnage via 📎 Référence / Édition (le moteur d'édition ne peut pas inventer un personnage précis à partir de son seul nom).`
}

export const __test__ = { ENTITY_CUE, ADD_VERB, NAME_STOP }
