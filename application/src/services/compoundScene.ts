/**
 * Compound-scene fidelity contract — pure module (no Tauri / React deps) so
 * `node --test` can exercise it directly, mirroring the humanoidAnatomy /
 * pbrProfile pattern. Re-exported from threeDIntent.ts.
 *
 * A genuinely COMPOUND 3D request (named celebrity + decor + mechanical
 * apparatus + fluids + luminous effects + motion) must not be collapsed to its
 * dominant noun. We detect every requested facet and emit an explicit MUST-render
 * contract so the FLUX reference keeps all of them. Kept in lockstep with the
 * Python composer (faithful_scene_prompt.py) so the UI and CLI/tunnel paths stay
 * aligned.
 */

function uniqueLower(values: string[]): string[] {
  return Array.from(new Set(values.map((v) => v.trim().toLowerCase()).filter(Boolean)))
}

/**
 * Named real person / known character to preserve exactly (celebrity, historical
 * figure, named hero). Conservative: a two-token Proper Name (not a leading
 * stopword) OR an explicit fiction/celebrity context. Mirrors _detect_identity
 * in faithful_scene_prompt.py — it flags the requirement, never invents a look.
 */
const NAME_STOPWORDS = new Set([
  'le', 'la', 'les', 'un', 'une', 'des', 'the', 'a', 'an',
  'render', 'create', 'generate', 'make', 'fais', 'crée', 'cree', 'genere',
])
const PROPER_NAME_RX = /\b([A-ZÀ-Ý][\wÀ-ÿ'’._-]{2,})\s+([A-ZÀ-Ý][\wÀ-ÿ'’._-]{2,})\b/
const FICTION_CONTEXT_RX = /\b(comic|comics|bd|manga|anime|s[ée]rie|series|film|movie|game|jeu|franchise|marvel|dc|pokemon|zelda|final\s*fantasy|star\s*wars|acteur|actrice|actor|actress|c[ée]l[èe]bre|celebrity|chanteur|singer|rappeur|rapper|footballeur|joueur|player)\b/i

export function hasNamedIdentitySignal(prompt: string): boolean {
  const m = PROPER_NAME_RX.exec(prompt || '')
  if (m && !NAME_STOPWORDS.has(m[1].toLowerCase())) return true
  return FICTION_CONTEXT_RX.test(prompt || '')
}

export const COMPOUND_FACET_PATTERNS: Array<{ family: string; rx: RegExp; instruction: (snips: string) => string }> = [
  {
    family: 'decor',
    rx: /\b(decor|d[ée]cor|sc[èe]ne|scene|environnement|environment|background|arri[èe]re[\s-]?plan|paysage|landscape|cityscape|ruelle|all[ée]e|alley|rue|street|ville|city|cit[ée]|n[ée]o[\s-]?tokyo|rooftop|toit|for[êe]t|forest|d[ée]sert|desert|jungle|int[ée]rieur|interior|pi[èe]ce|room|chambre|atelier|workshop|temple|ru[ie]nes?|ruins?|grotte|cave|cavern|sous\s+la\s+pluie|in\s+the\s+rain|night\s+city|ville\s+nocturne)\b/i,
    instruction: (s) => `the surrounding decor/environment (${s}) must be present and readable around the subject, not replaced by a plain studio backdrop`,
  },
  {
    family: 'mechanical',
    rx: /\b(m[ée]canique|mechanical|m[ée]canisme|mechanism|machine|machinery|moteur|engine|turbine|h[ée]lice|propeller|r[ée]acteur|reactor|thruster|bras\s+m[ée]canique|bras\s+articul[ée]|mechanical\s+arm|robotic\s+arm|engrenage|gear|pignon|piston|v[ée]rin|actuator|hydraulic|hydraulique|pneumatic|pneumatique|rouage|cog|servo|exosquelette|exoskeleton|cybern[ée]tique|cybernetic|prosth[èe]se|prosthetic|rotor|crankshaft|vilebrequin|courroie|belt\s+drive)\b/i,
    instruction: (s) => `the mechanical apparatus (${s}) must be modeled as real functional hard-surface geometry with visible parts, not hinted or omitted`,
  },
  {
    family: 'fluids',
    rx: /\b(eau|water|liquide|liquid|fluide|fluid|pluie|rain|rainfall|averse|drizzle|vapeur|steam|fum[ée]e|smoke|brume|brouillard|fog|mist|haze|lave|lava|magma|flaques?|puddles?|ruissel|ruissell|drip|dripping|gouttes?|droplets?|[ée]claboussures?|splash|spray|cascades?|waterfalls?|vagues?|fontaines?|fountains?|sang|blood|huile|oil|[ée]coulement|flow)\b/i,
    instruction: (s) => `the fluid/atmospheric elements (${s}) must be visibly rendered as volumetric water/steam/smoke/spray, never dropped`,
  },
  {
    family: 'luminous',
    // Stem + bounded inflection so FR plurals/conjugations survive (néons,
    // étincelles, bioluminescents, éclairent, brillent). Kept in lockstep with
    // faithful_scene_prompt.py.
    rx: /\b(n[ée]ons?|neons?|lumineux|lumineuse[s]?|luminous|lumi[èe]res?|glow(?:s|ing|ed)?|lueurs?|halos?|bioluminescen[a-zà-ÿ]{0,4}|luminescen[a-zà-ÿ]{0,4}|fluorescent[a-zà-ÿ]{0,2}|phosphorescent[a-zà-ÿ]{0,2}|leds?|[ée]tincel[a-zà-ÿ]{0,5}|sparkl?[a-z]{0,4}|sparks?|[ée]clats?|[ée]clair[a-zà-ÿ]{0,5}|illumin[a-zà-ÿ]{0,6}|scintill[a-zà-ÿ]{0,5}|brill[a-zà-ÿ]{0,5}|flash(?:es|ing)?|lasers?|hologram(?:s|me|mes)?|holographi[a-zà-ÿ]{0,4}|[ée]missif[s]?|emissive|incandescen[a-zà-ÿ]{0,3}|braises?|embers?|refl[èe]t[a-zà-ÿ]{0,5}|enseignes?\s+lumineuses?|illuminated\s+sign|backlit)\b/i,
    instruction: (s) => `the luminous/emissive elements (${s}) must glow with strong saturated emissive color and cast visible light, not flat paint`,
  },
  {
    family: 'motion',
    // Stem + bounded inflection: "tournent", "oscille", "jaillissent" must not
    // be lost the way a literal list drops conjugations. Mirror of the Python
    // motion pattern.
    rx: /\b(tourn[a-zà-ÿ]{0,5}|spin(?:s|ning|ned)?|rotat(?:e|es|ed|ing|ion|ional)?|whirl(?:s|ing|ed)?|roul[a-zà-ÿ]{0,5}|roll(?:s|ing|ed)?|avanc[a-zà-ÿ]{0,5}|en\s+mouvement|in\s+motion|mov(?:e|es|ed|ing|ement)?|vol[ae][a-zà-ÿ]{0,4}|fly|flies|flying|hover(?:s|ing|ed)?|march[ae][a-zà-ÿ]{0,4}|walk(?:s|ing|ed)?|cour(?:s|t|ent|ir|ait|aient|u|ant)|run(?:s|ning)?|dans[ae][a-zà-ÿ]{0,3}|danc(?:e|es|ing|ed)?|saut[ae][a-zà-ÿ]{0,3}|jump(?:s|ing|ed)?|l[èe]v[a-zà-ÿ]{0,4}|rais(?:e|es|ing|ed)?|brandi[a-zà-ÿ]{0,5}|salu[a-zà-ÿ]{0,4}|wav(?:e|es|ing|ed)?|frapp[a-zà-ÿ]{0,4}|punch(?:es|ing|ed)?|kick(?:s|ing|ed)?|jaill[a-zà-ÿ]{0,6}|gush(?:es|ing|ed)?|erupt(?:s|ing|ed)?|spew(?:s|ing|ed)?|swing(?:s|ing)?|balanc[a-zà-ÿ]{0,5}|oscill[a-zà-ÿ]{0,5}|vibr[a-zà-ÿ]{0,5}|puls[a-zà-ÿ]{0,4}|battement[s]?|battant[s]?|mouvement[s]?|movement[s]?|articul[a-zà-ÿ]{0,5})\b/i,
    instruction: (s) => `the motion (${s}) must be expressed through pose and part orientation so the action reads clearly`,
  },
  {
    family: 'materials',
    rx: /\b(m[ée]tal|metal|chrome|acier|steel|cuivre|copper|or\b|gold|argent|silver|aluminium|aluminum|titane|titanium|cuir|leather|verre|glass|cristal|crystal|plastique|plastic|bois|wood|pierre|stone|marbre|marble|b[ée]ton|concrete|tissu|fabric|soie|silk|fourrure|fur|[ée]cailles?|scales?|caoutchouc|rubber|c[ée]ramique|ceramic|carbone|carbon)\b/i,
    instruction: (s) => `the named materials (${s}) must read as distinct PBR surfaces with correct metalness/roughness`,
  },
]

// ISOLATED-CHARACTER overrides (mirror of _FACET_INSTRUCTION_ISOLATED in
// faithful_scene_prompt.py). A riggable character is reconstructed from an
// isolated reference, so scene facets are reframed as atmosphere ON the subject
// rather than separate background geometry — the rig-vs-scene conflict only
// surfaces when you actually run the pipeline. Families absent here (motion,
// materials) use the default SCENE instruction unchanged.
const ISOLATED_INSTRUCTION: Record<string, (s: string) => string> = {
  decor: (s) => `the scene setting (${s}) must appear ONLY as coloured rim-light and atmospheric tint ON the subject against a PLAIN white studio background — NO street, buildings, walls or environment scenery behind the subject (a clean isolated subject is mandatory for 3D reconstruction)`,
  mechanical: (s) => `any mechanical apparatus (${s}) worn by, held by or attached to the subject must be real geometry; standalone machinery in the scene is conveyed only as reflection/lighting, not as separate parts`,
  fluids: (s) => `the fluid/atmospheric elements (${s}) must appear ON and AROUND the subject — rain-soaked surfaces, dripping water, steam haze hugging the figure — not as a separate volumetric background`,
  luminous: (s) => `the luminous/emissive elements (${s}) must LIGHT the subject — coloured rim-light and glowing reflections on the materials — emissive on the figure, not a detached neon sign`,
}

/**
 * Build a MULTI-ELEMENT FIDELITY CONTRACT for compound prompts. Returns '' for
 * simple/single-facet requests (no-op, identical policy to the Python composer).
 *
 * opts.isolated → ON-SUBJECT atmosphere phrasing for a riggable character
 * (scene facets become styling/lighting, not separate background geometry).
 */
export function buildCompoundSceneContract(prompt: string, motionText = '', opts: { isolated?: boolean } = {}): string {
  const text = `${prompt} ${motionText}`.trim()
  const isolated = Boolean(opts.isolated)
  const lines: string[] = []
  const families: string[] = []

  const hasIdentity = hasNamedIdentitySignal(prompt)
  for (const { family, rx, instruction } of COMPOUND_FACET_PATTERNS) {
    const hits = uniqueLower(text.match(new RegExp(rx, 'gi')) || [])
    if (hits.length > 0) {
      families.push(family)
      const render = (isolated && ISOLATED_INSTRUCTION[family]) || instruction
      lines.push(render(hits.slice(0, 4).join(', ')))
    }
  }

  const familyCount = families.length + (hasIdentity ? 1 : 0)
  if (familyCount < 2 || lines.length === 0) return ''

  const identityLine = hasIdentity
    ? 'the requested named identity must be preserved exactly — recognizable face and silhouette, no generic look-alike, no gender swap; '
    : ''
  // Isolated mode MUST force a plain background or neither the turnaround audit
  // (white = background) nor Hunyuan3D can segment the subject.
  const isolationLine = isolated
    ? 'ISOLATED FULL-BODY SUBJECT centered on a PLAIN WHITE studio background, the whole figure visible head to feet with clear white margin all around, no environment scenery behind the subject; '
    : ''
  const tradeoff = (isolated && families.some((f) => f === 'decor' || f === 'mechanical' || f === 'fluids'))
    ? '; single riggable subject: standalone scene props and separate machinery are conveyed as styling, lighting and reflection on the subject, not as separate animated geometry'
    : ''
  return (
    '\n\nMULTI-ELEMENT FIDELITY CONTRACT (render EVERY element described with precise '
    + 'detail; do NOT simplify the scene to a single subject, do NOT omit, merge or '
    + 'approximate any element listed): '
    + identityLine
    + isolationLine
    + lines.join('; ')
    + tradeoff
    + '.'
  )
}
