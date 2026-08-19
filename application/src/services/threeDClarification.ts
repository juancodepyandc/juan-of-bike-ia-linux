/**
 * v77zg — targeted 3D clarification questions (pure, no Tauri / React deps).
 *
 * The previous behaviour only surfaced a clarification when a mechanical /
 * printable part lacked dimensions. Everything else generated silently with
 * arbitrary defaults — which is exactly why a "personnage" prompt or a
 * "ventilateur" prompt would ship a flat static turntable instead of a
 * proper rigged Meshy-grade output.
 *
 * This module classifies the dominant ambiguity in the prompt and returns
 * one targeted question + the option list to surface in the UI:
 *
 *   - person_reproduction → views (face / multi-views), age band, tenue,
 *     expression — when the user wants to reproduce a real or specific
 *     person (portrait, ressemble à, lookalike).
 *   - character_anatomy   → gender, morphology, pose — for fictional
 *     characters with no explicit anatomical hint.
 *   - mechanism_motion    → kind of motion (rotating / rolling / pendulum /
 *     articulated linkage) when an articulated subject ships with no motion
 *     verb in the prompt.
 *   - vehicle_motion      → wheels-rolling vs static turntable when a
 *     vehicle prompt has no motion verb.
 *   - material_ambiguous  → ceramic vs glass vs metal vs wood when the
 *     subject (vase, lamp, mug, sword, bowl, stool, table…) is a known
 *     multi-material object and the prompt names no material.
 *   - dimensional_precision (handled by caller — kept as a category here
 *     so callers can suppress the generic prompt when one of the targeted
 *     ones is more useful).
 *
 * The ordering below picks the highest-stakes ambiguity first; the caller
 * only ever surfaces a single question per intent so the user never sees
 * a wall of follow-ups.
 */

export type ThreeDClarificationCategory =
  | 'person_reproduction'
  | 'character_anatomy'
  | 'mechanism_motion'
  | 'vehicle_motion'
  | 'motion_intensity'
  | 'material_ambiguous'
  | 'dimensional_precision'

export type ThreeDClarification = {
  category: ThreeDClarificationCategory
  question: string
  options: string[]
}

type ClarificationContext = {
  prompt: string
  purpose:
    | 'visual_preview'
    | 'printable_prototype'
    | 'mechanical_part'
    | 'character'
    | 'body_part'
    | 'product'
    | 'game_asset'
  subjectKind:
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
  systemClass: string
  motionReadiness:
    | 'static_only'
    | 'poseable'
    | 'articulated'
    | 'rig_candidate'
  motionVerbHint:
    | null
    | 'rotating' | 'rolling' | 'flying' | 'walking' | 'swinging' | 'oscillating' | 'mechanism'
  hasImageReference: boolean
  hasDimensionalSignal: boolean
  hasMaterialHint: boolean
}

const REAL_PERSON_PATTERNS = [
  /\b(portrait|ressemble\s+a|ressemble[er]?\s+a|lookalike|look\s?-?\s?alike|ressemblant|likeness|reconstitution|reconstit[uú]er|recreate[r]?|recreate\s+a\s+person|real person|vraie?\s+personne|personne reelle|moi en 3d|me in 3d|my face|mon visage|son visage|her face|his face|client|customer|reproduce[er]?\s+a?\s*person|deepfake|jumeau virtuel|virtual twin)\b/i,
  /\b(jean|john|maria|peter|alice|emma|alex|marc|julie|nicolas|pierre|paul|sarah|lisa|anna|sofia|david|michel|daniel|olivier|thomas|antoine|aurelie|claire|stephane|laure|antoine|leo|elise|cedric)\b.*\b(en 3d|3d model|model 3d|model of|in 3d)\b/i,
]

/**
 * v77zk: shared regex predicate so threeDViewPlanner can force multi-view
 * shape generation when the prompt asks for a real-person reproduction.
 * Mirrors the patterns used internally in detectThreeDClarification.
 */
export function isPersonReproductionPrompt(prompt: string): boolean {
  if (!prompt) return false
  return REAL_PERSON_PATTERNS.some((re) => re.test(prompt))
}

const FICTIONAL_CHARACTER_HINTS = /\b(personnage|character|hero|heroine|humanoid|avatar|figurine|villain|guerrier|warrior|mage|sorcier|chevalier|knight|ninja|samurai|pirate|assassin|paladin|adventurer|aventurier|explorer|explorateur|magicien|sorcerer|witch|sorciere|wizard|jedi|sith|elf|elfe|orc|orque|dwarf|nain|fairy|fee|angel|ange|demon|robot character|cyborg)\b/i

const ANATOMY_HINTS = /\b(homme|femme|man|woman|fille|garcon|girl|boy|male|female|masculin|feminin|androgyne|androgynous|enfant|child|child[\s-]?like|teen|adolescent|jeune|young|old|age[ée]?|mature|elder|aine|elderly|musculeux|muscular|athletic|sportif|sportive|svelte|slim|elance|stocky|trapus|trapue|costaud|petite|grand|grande|tall|short|petit)\b/i

const POSE_HINTS = /\b(pose|posing|debout|standing|assis|sitting|seated|kneeling|agenouille|allonge|lying|couche|t-?pose|a-?pose|combat|fight|fighting|action pose|hero pose|relax|casual|dramatic|defi|defying|defiant|dancing|danse|running|courant|jumping|sautant|crouched|accroupi)\b/i

const MOTION_VERBS_OR_NOUNS = /\b(roule|rolling|rolls|drives|driving|advance|tourne|spin|spinning|rotat|whirl|swing|pendul|hover|fly|flying|drone|walk|walking|march|run|running|cours|move|moves|moving|in motion|en mouvement|fonctionn|en marche|en service|active|articulated|articule|kinematic)\b/i

// v77zz: motion-action verbs on characters/creatures whose intensity/speed
// strongly affects the bake. "saute" / "danse" / "court" without a modifier
// produces a default-tempo cycle that may not match the user's mental
// picture — surface a clarification BEFORE the bake fires.
const CHARACTER_MOTION_ACTIONS_RX = /\b(saute|sauter|jump|jumping|danse|danser|dance|dancing|court|courir|run|runs|running|sprint|sprinting|kick|coup de pied|punch|coup de poing|nage|nager|swim|swimming|cartwheel|roue|throw|lance|lancer|wave|salue|salut|applaud|applaudis|trotte|gallop|galope|fait coucou|coucou|wagging|remue queue)\b/i

// v77zv modifier vocabulary — if any of these tokens is present we don't
// need to ask, the parser already absorbed the intensity signal.
const MOTION_MODIFIER_PRESENT_RX = /\b(rapidement|vite|fast|quickly|swiftly|frenetiquement|fr[eé]n[eé]tiquement|frantically|lentement|doucement|slowly|leisurely|tranquillement|au ralenti|fort(?:ement)?|intensement|intens[eé]ment|powerfully|vigoureusement|brutalement|violemment|legerement|l[eé]g[eè]rement|gently|softly|delicatement|joyeusement|happily|cheerfully|tristement|sadly|en colere|angrily|furieusement|fatigue|fatigu[eé]|tired|exhausted|epuise|[eé]puis[eé]|haut|high|loin|far|tres|tr[eè]s|very|extremement|extr[eê]mement)\b/i

const VEHICLE_MOVEMENT_HINTS = /\b(stationary|static|parked|gare|stationne|displayed|montrer|exposition|showroom|showcase|vitrine|musee|museum|standing|stopped|arrete)\b/i

const MULTI_MATERIAL_OBJECTS = /\b(vase|lamp|lampe|mug|tasse|bol|bowl|sword|epee|cup|chalice|coupe|stool|tabouret|table|chaise|chair|jar|jarre|amphore|amphora|pichet|pitcher|bouteille|bottle|carafe|figurine|statue|sculpture|colonne|column|pillar|knife|couteau|axe|hache|shield|bouclier|helm|casque|helmet|crown|couronne|ring|bague|necklace|collier|bracelet|brooch|broche|pendentif|pendant|trophy|trophee|cup\s+award|award)\b/i

const MATERIAL_HINTS = /\b(chrome|brushed|brossee?|verre|glass|cristal|crystal|transparent|diamant|diamond|gem|jewel|ceramique|ceramic|porcelaine|porcelain|pierre|stone|granite|marbre|marble|cuir|leather|tissu|fabric|cloth|coton|wool|silk|soie|bois|wood|wooden|chene|oak|noyer|walnut|caoutchouc|rubber|silicone|electronique|electronics|plastique|plastic|abs|metal peint|painted|acier|steel|iron|titanium|aluminium|aluminum|laiton|brass|bronze|cuivre|copper|gold|silver|peau|skin|chair|flesh)\b/i

const DIMENSIONAL_SIGNAL = /\b\d+(?:[.,]\d+)?\s?(?:mm|millim[eè]tres?|millimeters?|cm|centim[eè]tres?|centimeters?|m\b|metres?|meters?|in|inch|inches|degre[ée]?s?|degrees?)\b/i

export function detectThreeDClarification(ctx: ClarificationContext): ThreeDClarification | null {
  const { prompt } = ctx
  if (!prompt || prompt.trim().length < 3) return null

  // UNE IMAGE REPOND DEJA (30/07). Quand l'utilisateur joint une photo, la
  // morphologie, la pose, le genre, la tenue et le style SONT DANS L'IMAGE:
  // les lui redemander, c'est lui faire decrire ce que le systeme peut voir.
  // L'analyse vision du pipeline s'en charge. On ne questionne plus rien de
  // ce que l'image montre.
  if (ctx.hasImageReference) return null

  // 1. Real-person reproduction — highest stakes (likeness). Do not auto-fill.
  if (
    (ctx.purpose === 'character' || ctx.subjectKind === 'character')
    && REAL_PERSON_PATTERNS.some((re) => re.test(prompt))
  ) {
    return {
      category: 'person_reproduction',
      question: 'Reproduction d\'une personne reelle: precise les vues souhaitees (face seule ou multi-vues face/profil/dos), la tranche d age, la tenue, l expression et le style (realiste / stylise).',
      options: [
        'Vue de face seule (portrait) — multi-vues a generer par diffusion',
        'Multi-vues face + profil + dos (recommande pour rigging)',
        'Style realiste, neutre (T-pose, expression detendue)',
        'Style stylise (cartoon / anime) au lieu du realisme photographique',
      ],
    }
  }

  // 2. Fictional character with no anatomy / pose hint.
  if (
    (ctx.purpose === 'character' || ctx.subjectKind === 'character' || ctx.subjectKind === 'creature')
    && !ANATOMY_HINTS.test(prompt)
    && !POSE_HINTS.test(prompt)
    && FICTIONAL_CHARACTER_HINTS.test(prompt)
  ) {
    // GRAMMAIRE: l'article francais donne deja le genre ("UN guerrier" =
    // masculin, "UNE guerriere" = feminin). Redemander le genre alors que
    // l'utilisateur l'a ecrit est incoherent — on ne questionne que ce qui
    // manque vraiment (morphologie / pose).
    // NE PAS CONFONDRE GENRE GRAMMATICAL ET SEXE DU SUJET (30/07): « le
    // personnage », « un personnage » sont masculins EN GRAMMAIRE et ne
    // disent rien du sujet — annoncer « Personnage masculin deduit de votre
    // formulation » etait faux et deroutant. On n'infere le sexe que si un
    // mot le PORTE reellement (guerriere, femme, homme, roi, sorciere...).
    const MOTS_MASC = /\b(homme|garcon|gar\u00e7on|monsieur|roi|prince|guerrier|chevalier|soldat|heros|h\u00e9ros|mage|sorcier|moine|pere|p\u00e8re|fils|barbu)\b/iu
    const MOTS_FEM = /\b(femme|fille|dame|reine|princesse|guerriere|guerri\u00e8re|chevaliere|heroine|h\u00e9ro\u00efne|magicienne|sorciere|sorci\u00e8re|nonne|mere|m\u00e8re|soeur|s\u0153ur)\b/iu
    const masculin = MOTS_MASC.test(prompt) && !MOTS_FEM.test(prompt)
    const feminin = MOTS_FEM.test(prompt) && !MOTS_MASC.test(prompt)
    if (masculin || feminin) {
      return {
        category: 'character_anatomy',
        question: `Personnage ${masculin ? 'masculin' : 'feminin'} (vous l'avez ecrit): quelle morphologie et quelle pose ?`,
        options: masculin
          ? ['Athletique, T-pose neutre', 'Trapu/massif, T-pose', 'Mince, A-pose', 'Pose dynamique (action/combat) — sera plus dur a riger']
          : ['Svelte, A-pose neutre', 'Athletique, T-pose', 'Ronde, T-pose', 'Pose dynamique (action/combat) — sera plus dur a riger'],
      }
    }
    return {
      category: 'character_anatomy',
      question: 'Personnage fictif: precise le genre, la morphologie et la pose. Sans reponse je genererai une T-pose neutre androgyne.',
      options: [
        'Masculin athletique, T-pose neutre',
        'Feminin svelte, A-pose neutre',
        'Androgyne taille moyenne, T-pose',
        'Pose dynamique (action/combat) — sera plus dur a riger',
      ],
    }
  }

  // 3. Articulated mechanism without explicit motion verb — the rig branch
  //    will default to a turntable, which is rarely what the user wants.
  if (
    (ctx.motionReadiness === 'articulated' || ctx.motionReadiness === 'rig_candidate')
    && ctx.subjectKind !== 'character'
    && ctx.subjectKind !== 'creature'
    && !ctx.motionVerbHint
    && !MOTION_VERBS_OR_NOUNS.test(prompt)
  ) {
    return {
      category: 'mechanism_motion',
      question: 'Sujet articule sans verbe de mouvement explicite: quel mouvement representer?',
      options: [
        'Rotation continue (ventilateur, roue, helice)',
        'Mecanisme articule (engrenage, biellette, verin) avec cycle complet',
        'Pendule / oscillation (chandelier, balancier)',
        'Aucun mouvement (pose statique sur turntable)',
      ],
    }
  }

  // 4. Vehicle without motion verb — explicit choice avoids the default
  //    static product turntable for a car/bike that the user expects to roll.
  if (
    ctx.subjectKind === 'vehicle'
    && !ctx.motionVerbHint
    && !MOTION_VERBS_OR_NOUNS.test(prompt)
    && !VEHICLE_MOVEMENT_HINTS.test(prompt)
  ) {
    return {
      category: 'vehicle_motion',
      question: 'Vehicule sans indication de mouvement: roues qui tournent ou maquette statique?',
      options: [
        'Roues qui tournent + suspension (vehicle rolling rig)',
        'Maquette statique sur turntable (showroom)',
        'Rotation des helices/turbines uniquement (vehicule aerien stationnaire)',
      ],
    }
  }

  // 5. Motion-action without intensity modifier — for characters / creatures
  //    that have a motion verb but no speed/intensity adjective, ask the
  //    user how energetic the action should be so the bake doesn't lock
  //    into a default tempo that mismatches the mental picture.
  if (
    (ctx.subjectKind === 'character' || ctx.subjectKind === 'creature')
    && CHARACTER_MOTION_ACTIONS_RX.test(prompt)
    && !MOTION_MODIFIER_PRESENT_RX.test(prompt)
  ) {
    return {
      category: 'motion_intensity',
      question: 'Verbe d action sans modificateur d intensite: comment doit-il etre execute?',
      options: [
        'Lentement / doucement (au ralenti, posement)',
        'Rythme normal (par defaut, pas de modificateur)',
        'Rapidement / fortement (intense, energique)',
        'Burst extreme (frenetiquement / violemment)',
      ],
    }
  }

  // 6. Multi-material objects without a stated material — different output
  //    every time depending on Hunyuan paint guesses.
  if (
    !ctx.hasMaterialHint
    && !MATERIAL_HINTS.test(prompt)
    && MULTI_MATERIAL_OBJECTS.test(prompt)
  ) {
    return {
      category: 'material_ambiguous',
      question: 'Objet multi-materiau sans indication: precise le materiau dominant pour un rendu Meshy-grade fidele.',
      options: [
        'Ceramique (vase, mug, bol — emaillee, mate ou satinee)',
        'Verre / cristal (transparent, refractif)',
        'Metal poli (chrome, laiton, acier brillant)',
        'Bois sculpte (chene, noyer, teck — verni ou brut)',
        'Pierre (marbre, granite, calcaire)',
      ],
    }
  }

  // 6. Dimensional precision — kept as last because it is the original
  //    fallback and least specific.
  if (
    (ctx.purpose === 'printable_prototype' || ctx.purpose === 'mechanical_part')
    && !ctx.hasDimensionalSignal
    && !DIMENSIONAL_SIGNAL.test(prompt)
    && !ctx.hasImageReference
  ) {
    return {
      category: 'dimensional_precision',
      question: 'Piece mecanique ou imprimable sans dimensions. Donne taille (cm/mm), tolerances ou vues orthographiques pour un prototype fidele.',
      options: [
        'Petite piece de precision (< 5cm, tolerances strictes)',
        'Piece moyenne (5-30cm, tolerance industrielle)',
        'Grande piece (> 30cm, prototype visuel suffit)',
        'Continuer en mode visuel sans dimensions',
      ],
    }
  }

  return null
}
