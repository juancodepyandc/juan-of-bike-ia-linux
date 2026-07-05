/**
 * v77zf — Meshy-grade PBR material inference (pure, dependency-free).
 *
 * Hunyuan3D-Paint exports a single baseColor texture, so the resulting GLB
 * materials default to roughness=1.0 / metalness=0.0 — visually flat matte
 * plastic regardless of the actual subject. Meshy on the other hand returns
 * proper metalness / roughness / clearcoat / sheen / iridescence per material
 * zone, which is why a Meshy chrome looks like real chrome and a Meshy
 * character looks like real skin instead of beige plastic.
 *
 * To close that gap without retraining the texture network, we parse the
 * user prompt + the detected subject kind and infer a sensible PBR profile.
 * The viewer then applies it to any material that still has the
 * post-paint flat default.
 *
 * Kept in its own file (no Tauri / React imports) so node --test can exercise
 * the inference without dragging in the runtime bridge.
 */

export type PbrSubjectKind =
  | 'object'
  | 'mechanical_part'
  | 'assembly'
  | 'character'
  | 'creature'
  | 'body_part'
  | 'product'
  | 'vehicle'
  | 'architecture'
  | 'tool'
  | 'electrical_system'

export type PbrProfileKind =
  | 'chrome'
  | 'brushed_metal'
  | 'painted_metal'
  | 'glass'
  | 'plastic_glossy'
  | 'plastic_matte'
  | 'rubber'
  | 'tire'           // v77zac: vehicle tire (rubber + asymmetric tread, high envMap absorption)
  | 'wood'
  | 'fabric'
  | 'leather'
  | 'skin'
  | 'fur'            // v77zac: animal fur / pelage (sheen + high roughness)
  | 'feathers'       // v77zac: bird plumage (sheen + iridescence on accents)
  | 'scales'         // v77zac: reptile / fish scales (semi-metallic + iridescence)
  | 'ceramic'
  | 'stone'
  | 'gem'
  | 'electronics'
  | 'character_default'
  | 'creature_default' // v77zac: distinct from character — fur-leaning baseline
  | 'product_default'
  | 'vehicle_default'
  | 'mechanism_default'
  | 'neutral'

export type PbrProfile = {
  kind: PbrProfileKind
  metalness: number
  roughness: number
  clearcoat?: number
  clearcoatRoughness?: number
  sheen?: number
  iridescence?: number
  transmission?: number
  ior?: number
  envMapIntensity: number
  emissiveBoost?: number
}

const PBR_PROFILES: Record<PbrProfileKind, PbrProfile> = {
  chrome:           { kind: 'chrome',           metalness: 0.95, roughness: 0.12, envMapIntensity: 1.55 },
  brushed_metal:    { kind: 'brushed_metal',    metalness: 0.90, roughness: 0.42, envMapIntensity: 1.40 },
  painted_metal:    { kind: 'painted_metal',    metalness: 0.55, roughness: 0.32, clearcoat: 0.55, clearcoatRoughness: 0.18, envMapIntensity: 1.45 },
  glass:            { kind: 'glass',            metalness: 0.00, roughness: 0.05, transmission: 0.92, ior: 1.52, clearcoat: 1.0, clearcoatRoughness: 0.05, envMapIntensity: 1.50 },
  plastic_glossy:   { kind: 'plastic_glossy',   metalness: 0.04, roughness: 0.28, clearcoat: 0.65, clearcoatRoughness: 0.12, envMapIntensity: 1.30 },
  plastic_matte:    { kind: 'plastic_matte',    metalness: 0.02, roughness: 0.62, envMapIntensity: 1.10 },
  rubber:           { kind: 'rubber',           metalness: 0.00, roughness: 0.85, envMapIntensity: 0.85 },
  tire:             { kind: 'tire',             metalness: 0.00, roughness: 0.92, envMapIntensity: 0.55 },
  wood:             { kind: 'wood',             metalness: 0.00, roughness: 0.78, clearcoat: 0.20, clearcoatRoughness: 0.55, envMapIntensity: 1.00 },
  fabric:           { kind: 'fabric',           metalness: 0.00, roughness: 0.92, sheen: 0.65, envMapIntensity: 0.90 },
  leather:          { kind: 'leather',          metalness: 0.02, roughness: 0.68, sheen: 0.30, envMapIntensity: 1.05 },
  skin:             { kind: 'skin',             metalness: 0.00, roughness: 0.55, sheen: 0.25, clearcoat: 0.10, clearcoatRoughness: 0.45, envMapIntensity: 1.10 },
  fur:              { kind: 'fur',              metalness: 0.00, roughness: 0.95, sheen: 0.55, envMapIntensity: 0.95 },
  feathers:         { kind: 'feathers',         metalness: 0.00, roughness: 0.78, sheen: 0.45, iridescence: 0.20, envMapIntensity: 1.05 },
  scales:           { kind: 'scales',           metalness: 0.20, roughness: 0.45, sheen: 0.30, iridescence: 0.35, clearcoat: 0.40, clearcoatRoughness: 0.20, envMapIntensity: 1.30 },
  ceramic:          { kind: 'ceramic',          metalness: 0.05, roughness: 0.22, clearcoat: 0.85, clearcoatRoughness: 0.10, envMapIntensity: 1.40 },
  stone:            { kind: 'stone',            metalness: 0.04, roughness: 0.88, envMapIntensity: 0.95 },
  gem:              { kind: 'gem',              metalness: 0.00, roughness: 0.04, transmission: 0.88, ior: 1.78, iridescence: 0.45, clearcoat: 1.0, clearcoatRoughness: 0.04, envMapIntensity: 1.60 },
  electronics:      { kind: 'electronics',      metalness: 0.18, roughness: 0.40, clearcoat: 0.45, clearcoatRoughness: 0.20, envMapIntensity: 1.30, emissiveBoost: 0.18 },
  character_default:{ kind: 'character_default',metalness: 0.05, roughness: 0.55, sheen: 0.12, envMapIntensity: 1.20 },
  creature_default: { kind: 'creature_default', metalness: 0.00, roughness: 0.78, sheen: 0.30, envMapIntensity: 1.05 },
  product_default:  { kind: 'product_default',  metalness: 0.10, roughness: 0.45, clearcoat: 0.30, clearcoatRoughness: 0.20, envMapIntensity: 1.30 },
  vehicle_default:  { kind: 'vehicle_default',  metalness: 0.45, roughness: 0.38, clearcoat: 0.55, clearcoatRoughness: 0.18, envMapIntensity: 1.40 },
  mechanism_default:{ kind: 'mechanism_default',metalness: 0.65, roughness: 0.35, envMapIntensity: 1.40 },
  neutral:          { kind: 'neutral',          metalness: 0.10, roughness: 0.55, envMapIntensity: 1.25 },
}

export function detectPbrProfileKindFromPrompt(prompt: string): PbrProfileKind | null {
  const n = prompt.toLowerCase()
  // Order matters: more specific signals first.
  if (/\b(chrome|chromee?|chromed|miroir poli|mirror polished|polished steel|highly polished|aluminum polished|aluminium poli)\b/i.test(n)) return 'chrome'
  if (/\b(brossee?|brushed|satin\s?finish|fini satin|brossage|aluminium brosse|stainless brushed)\b/i.test(n)) return 'brushed_metal'
  if (/\b(verre|glass|cristal|crystal|transparent|verriere|verriere?|glasswork|see-through|translucide)\b/i.test(n)) return 'glass'
  if (/\b(diamant|diamond|ruby|rubis|emerald|emeraude|sapphire|saphir|gemme?|gem|jewel|bijou)\b/i.test(n)) return 'gem'
  if (/\b(ceramique|ceramic|porcelaine|porcelain|earthenware|gres|gr[eè]s|faience|fa[iï]ence)\b/i.test(n)) return 'ceramic'
  if (/\b(pierre|stone|granite|marbre|marble|rocher|rock\s?formation|brick|brique|beton|b[eé]ton|concrete)\b/i.test(n)) return 'stone'
  if (/\b(cuir|leather|cuirassee?|saddle leather)\b/i.test(n)) return 'leather'
  if (/\b(tissu|fabric|cloth|linen|lin|coton|cotton|wool|laine|silk|soie|velour|velvet|denim|jean|robe|dress|shirt|chemise)\b/i.test(n)) return 'fabric'
  if (/\b(bois|wood|wooden|chene|ch[eê]ne|oak|noyer|walnut|teck|teak|bamboo|bambou|plywood|contreplaque|contreplaqu[ée])\b/i.test(n)) return 'wood'
  if (/\b(caoutchouc|rubber|silicone|latex|hard rubber)\b/i.test(n)) return 'rubber'
  if (/\b(electronique|electronics|circuit|pcb|carte mere|motherboard|gpu|cpu|connector|connecteur|led|argb|rgb|cable management)\b/i.test(n)) return 'electronics'
  if (/\b(plastique brillant|glossy plastic|abs poli|plastic glossy|verni|varnished|laque|lacquered|peinture brillante|gloss paint)\b/i.test(n)) return 'plastic_glossy'
  if (/\b(plastique mat|matte plastic|abs mat|plastic matte|peinture mate|matte paint|mat finish)\b/i.test(n)) return 'plastic_matte'
  if (/\b(plastique|plastic|abs|polypropylene|polycarbonate)\b/i.test(n)) return 'plastic_matte'
  if (/\b(metal peint|painted metal|painted steel|enamelled metal|tole peinte|carrosserie peinte|peinture carrosserie)\b/i.test(n)) return 'painted_metal'
  if (/\b(acier|steel|iron|fer|fonte|cast iron|titanium|titane|aluminium|aluminum|alu|laiton|brass|bronze|cuivre|copper|gold|or massif|silver|argent massif)\b/i.test(n)) return 'brushed_metal'
  if (/\b(peau|skin|chair|flesh|epiderme|epidermis|visage|face|teint|skin tone|complexion)\b/i.test(n)) return 'skin'
  // v77zac: fur / feathers / scales — for creature subjects with hair/plumage/scaly skin
  if (/\b(fourrure|fur|poil|pelage|coat of fur|furry|hairy creature|fluffy|chevelu|hirsute|moelleux|peluche|plush)\b/i.test(n)) return 'fur'
  if (/\b(plumes|feathers|plumage|plumee?|plumed|feathery|down|duvet)\b/i.test(n)) return 'feathers'
  if (/\b(ecailles|[eé]cailles|scales|scaly|scaled|scale skin|peau ecailleuse|peau [eé]cailleuse|reptilien|reptilian)\b/i.test(n)) return 'scales'
  // v77zac: tires / wheels — distinct from generic rubber
  if (/\b(pneu|pneus|tire|tires|tyre|tyres|tread|gomme de pneu|wheel rubber)\b/i.test(n)) return 'tire'
  return null
}

export function inferPbrProfile(prompt: string, subjectKind: PbrSubjectKind): PbrProfile {
  const explicit = detectPbrProfileKindFromPrompt(prompt)
  if (explicit) return PBR_PROFILES[explicit]
  switch (subjectKind) {
    case 'character':
    case 'body_part':
      return PBR_PROFILES.character_default
    case 'creature':
      // v77zac: creature default leans toward fur/animal hide rather than skin —
      // a non-explicit "a wolf" prompt should NOT inherit human skin defaults.
      return PBR_PROFILES.creature_default
    case 'vehicle':
      return PBR_PROFILES.vehicle_default
    case 'mechanical_part':
    case 'assembly':
    case 'tool':
      return PBR_PROFILES.mechanism_default
    case 'electrical_system':
      return PBR_PROFILES.electronics
    case 'product':
      return PBR_PROFILES.product_default
    case 'architecture':
      return PBR_PROFILES.stone
    default:
      return PBR_PROFILES.neutral
  }
}
