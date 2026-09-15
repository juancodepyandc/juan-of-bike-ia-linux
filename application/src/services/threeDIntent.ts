import { ollamaChat, ollamaGenerate } from '../hooks/useTauri.ts'
import { summarizePreparedContext, type PreparedContextFile } from '../utils/multimodalContext.ts'
import { detectThreeDClarification, type ThreeDClarification } from './threeDClarification.ts'
import { buildHumanoidAnatomyBlock, type HumanoidProportionMetrics } from './humanoidAnatomy.ts'
import { buildQuadrupedAnatomyBlock, buildVehicleAnatomyBlock } from './subjectAnatomy.ts'
import {
  buildKinematicsDirectiveBlock,
  parseCustomMotionPrompt,
  type KinematicSubjectKind,
  type KinematicSystemClass,
  type MotionDescriptor as KinematicMotionDescriptor,
} from './kinematicsLibrary.ts'

export type ThreeDPipeline =
  | 'ai_generation'       // TRELLIS.2 / DreamGaussian — creative or reference-based
  | 'photogrammetry'      // Meshroom/AliceVision — faithful reproduction from multi-view photos
  | 'procedural'          // Blender Python — mechanisms, cables, kinematics
  | 'hybrid'              // Combination: e.g. procedural skeleton + AI texture

export type ThreeDPipelineJustification = {
  point: string
  risk: 'low' | 'medium' | 'high'
  mitigation: string
}

export type ThreeDPipelineRouting = {
  pipeline: ThreeDPipeline
  justifications: ThreeDPipelineJustification[]
  fallbackPipeline: ThreeDPipeline | null
  blenderRequired: boolean
  meshoomRequired: boolean
  dreamgaussianPreferred: boolean
  proceduralTemplate: string | null
  validationChecks: string[]
  postProcessing: string[]
}

type ThreeDPurpose =
  | 'visual_preview'
  | 'printable_prototype'
  | 'mechanical_part'
  | 'character'
  | 'body_part'
  | 'product'
  | 'game_asset'

type ThreeDSubjectKind =
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

type MotionReadiness =
  | 'static_only'
  | 'poseable'
  | 'articulated'
  | 'rig_candidate'

type ThreeDSystemClass =
  | 'generic'
  | 'belt_drive'
  | 'gear_train'
  | 'cylinder_actuator'
  | 'hinge_joint'
  | 'linkage'
  | 'cable_routing'
  | 'pc_cabling'
  | 'electrical_harness'
  | 'led_strip'

type ThreeDRepresentationGoal =
  | 'static_shape'
  | 'kinematic_readability'
  | 'routing_readability'
  | 'rig_readability'

export type ThreeDReferenceFraming =
  | 'isolated_subject'
  | 'host_context'
  | 'scene_context'

export type ThreeDIntent = {
  purpose: ThreeDPurpose
  subjectKind: ThreeDSubjectKind
  systemClass: ThreeDSystemClass
  representationGoal: ThreeDRepresentationGoal
  referenceFraming: ThreeDReferenceFraming
  motionReadiness: MotionReadiness
  pipelineRouting: ThreeDPipelineRouting
  requiresDimensionalPrecision: boolean
  wantsNeutralPose: boolean
  wantsSymmetry: boolean
  needsResearch: boolean
  needsClarification: boolean
  clarificationQuestion: string | null
  // v77zg: targeted clarification metadata so the UI can render the options
  // as buttons instead of forcing the user to free-text the answer.
  clarificationCategory: ThreeDClarification['category'] | null
  clarificationOptions: string[]
  referencePromptAdditions: string[]
  meshConstraints: string[]
  motionGuidance: string[]
  motionRisks: string[]
  movingPartsFocus: string[]
  anchoredPartsFocus: string[]
  researchQueries: string[]
  motionPresets: ThreeDMotionPreset[]
  summary: string
}

export type ThreeDMotionPreset = {
  id: string
  label: string
  description: string
  promptDirective: string
  lockViewer: boolean
}

type HistoryTurn = {
  role: 'user' | 'assistant'
  content: string
}

function uniqueStrings(values: string[]) {
  return Array.from(new Set(values.map((value) => value.trim()).filter(Boolean)))
}

function parseIntentJson(text: string): Partial<ThreeDIntent> | null {
  const match = text.match(/\{[\s\S]*\}/)
  if (!match) return null

  try {
    return JSON.parse(match[0]) as Partial<ThreeDIntent>
  } catch {
    return null
  }
}

function hasDimensionalSignal(prompt: string) {
  return /\b\d+(?:[.,]\d+)?\s?(?:mm|millimetres?|millimeters?|cm|m|in|inch|inches|degres?|degrees?)\b/i.test(prompt)
}

function hasNegatedStylizedSignal(prompt: string) {
  return /\b(non[-\s]?anime|non[-\s]?manga|non[-\s]?cartoon|pas\s+(?:anime|manga|cartoon|stylis[eé])|not\s+(?:anime|manga|cartoon|stylized|stylised)|rendu\s+non[-\s]?anime)\b/i.test(prompt)
}

function hasPositiveStylizedSignal(prompt: string) {
  return /\b(anime|manga|stylise|stylis[eé]|cartoon|lowpoly|low poly|voxel|chibi)\b/i.test(prompt) && !hasNegatedStylizedSignal(prompt)
}

function hasPositiveAnimeSignal(prompt: string) {
  return /\b(anime|manga|shonen|fairy\s*tail|one\s*piece|naruto|dragon\s*ball|bleach|jujutsu|demon\s*slayer|kimetsu)\b/i.test(prompt) && !hasNegatedStylizedSignal(prompt)
}

function hasFlossSignal(prompt: string) {
  return /\bfloss(?:ing)?\b/i.test(prompt)
}

function hasDanceOrGestureSignal(prompt: string) {
  return /\b(macarena|danse|danser|dance|dancing|chor[eé]graph|choreograph|body\s+action|action\s+corporelle|gesture|gestuelle)\b/i.test(prompt) || hasFlossSignal(prompt)
}

function hasKnownCharacterSignal(prompt: string) {
  const normalized = prompt.toLowerCase()
  const fictionContext = (/\b(comic|comics|bd|serie|series|film|movie|game|jeu|franchise|marvel|dc|pokemon|zelda|final\s*fantasy)\b/i.test(normalized) || hasPositiveAnimeSignal(prompt))
  const properName = /\b[A-Z][a-zA-Z'_-]{2,}\s+[A-Z][a-zA-Z'_-]{2,}\b/.test(prompt)
  const humanoidActionOrCue = /\b(marche|marcher|walk|walking|court|courir|run|running|danse|danser|dance|dancing|macarena|pose|visage|face|cheveux|hair|costume|outfit|heros|hero|personnage|character)\b/i.test(normalized)
  return (fictionContext && (properName || humanoidActionOrCue || hasFlossSignal(prompt))) || (properName && (humanoidActionOrCue || hasFlossSignal(prompt)))
}

function isOriginalGenericCharacterPrompt(prompt: string) {
  const normalized = prompt.toLowerCase()
  const saysOriginalOrGeneric = /\b(original|generique|g[eé]n[eé]rique|generic|avatar|performer|danseur|dancer|personnage\s+(?:original|invent[eé]|cr[eé][eé]))\b/i.test(normalized)
  return saysOriginalOrGeneric && !hasKnownCharacterSignal(prompt)
}

function isExplicitProceduralHumanoidPrompt(prompt: string) {
  return /\b(procedural|prototype|mannequin|gabarit|test\s+rig|rig\s+test|placeholder|simple\s+rig|avatar\s+generique)\b/i.test(prompt)
}

function hasHandFidelitySignal(prompt: string) {
  return /\b(mains?|hands?|doigts?|fingers?|palms?|paumes?|poignets?|wrists?|retourner\s+ses\s+mains|open\s+palms?)\b/i.test(prompt)
}

function requiresHumanFidelityPrompt(prompt: string, purpose: ThreeDPurpose, subjectKind: ThreeDSubjectKind) {
  const characterRequest = purpose === 'character' || subjectKind === 'character'
  return characterRequest && !isExplicitProceduralHumanoidPrompt(prompt)
}

function buildCharacterIdentityPromptAdditions(prompt: string, purpose: ThreeDPurpose, subjectKind: ThreeDSubjectKind) {
  if (purpose !== 'character' && subjectKind !== 'character' && subjectKind !== 'creature' && !hasKnownCharacterSignal(prompt)) {
    return []
  }
  const normalized = prompt.toLowerCase()
  const additions = [
    'preserve the requested character identity exactly; do not invent a gender-swapped variant',
    'face must be sharp and readable with clear eyes, nose, jawline and expression, never blurry or melted',
    'hair shape, costume silhouette, colors and accessories must match the reference rather than becoming generic',
    'use distinct material/color zones for skin, hair, clothing and accessories so the viewer can inspect texture fidelity',
  ]
  if (requiresHumanFidelityPrompt(prompt, purpose, subjectKind)) {
    additions.push(
      'human fidelity is mandatory: reject mannequin, toy, chibi, marshmallow, blob or generic avatar substitutions',
      'skin, hair, eyes, clothing folds and accessories need texture-bearing detail, not flat single-color material zones',
    )
  }
  if (hasHandFidelitySignal(prompt) || hasDanceOrGestureSignal(prompt)) {
    additions.push(
      'hands are action-critical: both palms, wrists and separate fingers must be visible and anatomically readable',
      'do not hide hands in sleeves, pockets, blobs or mitten shapes; hand orientation must be inspectable',
    )
  }
  if (/\b(homme|masculin|male|man|boy|garcon|garçon|he\b|him\b)\b/i.test(normalized)) {
    additions.push('explicit male/masculine identity requested: do not feminize the body, face or costume')
  }
  if (/\b(femme|feminin|féminin|female|woman|girl|fille|she\b|her\b)\b/i.test(normalized)) {
    additions.push('explicit female/feminine identity requested: preserve that identity without masculinizing the design')
  }
  if (hasKnownCharacterSignal(prompt)) {
    if (hasPositiveAnimeSignal(prompt)) {
      additions.push('known anime/manga character: preserve anime identity cues, official costume colors, hairstyle silhouette and gender; reject generic lookalikes')
    } else {
      additions.push('named real/public person: preserve realistic adult proportions, face/costume cues and non-cartoon material treatment; reject generic avatar substitutions')
    }
  }
  return additions
}

// ── Compound-scene fidelity (UI path mirror of faithful_scene_prompt.py) ──
// A genuinely COMPOUND request (named celebrity + decor + mechanical apparatus +
// fluids + luminous effects + motion) must not be collapsed to its dominant
// noun. The detection + MUST-render contract live in the pure ./compoundScene
// module (no Tauri deps) so node --test can exercise it; re-exported here.
export { buildCompoundSceneContract, hasNamedIdentitySignal } from './compoundScene.ts'
import { buildCompoundSceneContract } from './compoundScene.ts'

function detectPurpose(prompt: string): ThreeDPurpose {
  const normalized = prompt.toLowerCase()

  if (/\b(imprim(?:e|er|able)|stl|3d print|printable|fabrication|usinage|tolerance|tolerance)\b/i.test(normalized)) {
    return 'printable_prototype'
  }
  if (/\b(piece|piece mecanique|mechanical|gear|engrenage|bearing|roulement|joint|assembly|assemblage|cad|technical|blueprint|chassis|frame|suspension|transmission|piston|moteur|engine|belt|courroie|pulley|poulie|gearbox|reducteur|reducer|verin|v[eé]rin|cylinder|hydraulic|hydraulique|pneumatic|pneumatique|hinge|charniere|charni[eè]re|linkage|bielle|cam|came|biellette|manivelle|tringlerie|pignon)\b/i.test(normalized)) {
    return 'mechanical_part'
  }
  if (/\b(personnage|character|hero|heroine|humanoid|avatar|figurine|statue|npc|villain|guerrier|warrior|mage|sorcier|chevalier|knight|ninja|samurai|pirate|assassin|paladin)\b/i.test(normalized)) {
    return 'character'
  }
  if (hasKnownCharacterSignal(prompt)) {
    return 'character'
  }
  if (/\b(anime|manga|waifu|shonen)\b/i.test(normalized) && /\b(personnage|character|fille|garcon|girl|boy|man|woman|homme|femme)\b/i.test(normalized)) {
    return 'character'
  }
  if (/\b(bras|jambe|main|pied|torse|tete|visage|skull|arm|leg|hand|foot|torso|anatomy|anatomie|membre|crane|organe)\b/i.test(normalized)) {
    return 'body_part'
  }
  if (/\b(game asset|jeu video|unity|unreal|low poly|game-ready|rig|animation)\b/i.test(normalized)) {
    return 'game_asset'
  }
  if (/\b(produit|product|packshot|consumer|objet design|device|accessoire|accessory|cable|wiring|wire harness|harness|faisceau|motherboard|carte mere|connector|connecteur|electrique|electrical|pcie|atx|sata|usb|strimer|argb|rgb|led|12vhpwr|24[\s-]?pin|8[\s-]?pin|extension cable|sleeved|cablemod|rallonge|alimentation|psu|gpu|carte graphique|graphics card|ram|memoire|ddr|ssd|nvme|ventilateur|ventirad|aio|watercool|refroidissement|noctua|corsair|lian li|nzxt|cooler master|be quiet|deepcool|phanteks|ekwb|arctic|boitier|bo[iî]tier|case|tower|tour|mid[\s-]?tower|full[\s-]?tower|mini[\s-]?tower|msi|mag forge|h510|4000d|o11)\b/i.test(normalized)) {
    return 'product'
  }

  return 'visual_preview'
}

function detectSubjectKind(prompt: string): ThreeDSubjectKind {
  const normalized = prompt.toLowerCase()

  if (/\b(assembly|assemblage|mechanical assembly|sous-ensemble|systeme mecanique|mechanical system)\b/i.test(normalized)) return 'assembly'
  if (/\b(cable|wiring|wire harness|harness|faisceau|routing|motherboard|carte mere|connector|connecteur|electrique|electrical|pcb|circuit|pcie|atx|sata|usb|ethernet|strimer|argb|12vhpwr|24[\s-]?pin|8[\s-]?pin|extension cable|sleeved|cablemod|rallonge|alimentation|psu)\b/i.test(normalized)) return 'electrical_system'
  if (/\b(rgb|led)\b/i.test(normalized) && /\b(cable|extension|strip|ruban)\b/i.test(normalized)) return 'electrical_system'
  if (/\b(mecanique|mechanical|gear|engrenage|bearing|roulement|joint|chassis|frame|suspension|transmission|piston|moteur|engine|belt|courroie|pulley|poulie|verin|v[eé]rin|cylinder|hinge|charniere|charni[eè]re|linkage|bielle|cam|came|biellette|manivelle|tringlerie|pignon)\b/i.test(normalized)) return 'mechanical_part'
  if (/\b(personnage|character|avatar|figurine|statue|humanoid|npc|hero|heroine|villain|guerrier|warrior|mage|sorcier|chevalier|knight|ninja|samurai|pirate|assassin|paladin)\b/i.test(normalized)) return 'character'
  if (hasKnownCharacterSignal(prompt)) return 'character'
  if (/\b(anime|manga|waifu|shonen)\b/i.test(normalized) && /\b(personnage|character|fille|garcon|girl|boy|man|woman|homme|femme)\b/i.test(normalized)) return 'character'
  if (/\b(creature|monster|monstre|animal|dragon|wolf|loup|chat|cat|chien|dog|oiseau|bird|serpent|snake|insecte|insect)\b/i.test(normalized)) return 'creature'
  if (/\b(bras|jambe|main|pied|torse|tete|skull|arm|leg|hand|foot|torso|anatomie|anatomy|membre|crane|organe)\b/i.test(normalized)) return 'body_part'
  if (/\b(velo|bike|car|voiture|vehicule|vehicle|drone|moto|motorcycle|camion|truck|avion|airplane|bateau|boat|ship|train|bus|scooter|skateboard|trottinette)\b/i.test(normalized)) return 'vehicle'
  if (/\b(produit|product|device|accessoire|accessory|objet design|packshot|consumer|gadget|lian li|noctua|corsair|nzxt|cooler master|be quiet|deepcool|phanteks|ekwb|arctic|aio|watercool|refroidissement|gpu|carte graphique|graphics card|rtx|gtx|radeon|ram|memoire|ddr|ssd|nvme|ventilateur|fan|ventirad)\b/i.test(normalized)) return 'product'
  if (/\b(building|batiment|b[aâ]timent|architecture|house|maison|room|piece|chambre|immeuble|tower|temple|castle|chateau|ch[aâ]teau|church|eglise|[eé]glise|pont|bridge|structure)\b/i.test(normalized)) return 'architecture'
  if (/\b(tool|outil|hammer|marteau|tournevis|screwdriver|wrench|cle|cl[eé]|pince|plier|scie|saw|perceuse|drill)\b/i.test(normalized)) return 'tool'

  return 'object'
}

function detectSystemClass(prompt: string): ThreeDSystemClass {
  const normalized = prompt.toLowerCase()

  if (/\b(courroie|belt|poulie|pulley|belt drive|transmission courroie)\b/i.test(normalized)) return 'belt_drive'
  if (/\b(engrenage|gear|gearbox|reducteur|reducer|pignon|pinion|gear train|train d[\s']?engrenage)\b/i.test(normalized)) return 'gear_train'
  if (/\b(verin|v[eé]rin|cylinder|hydraulic|hydraulique|pneumatic|pneumatique|actuator|piston)\b/i.test(normalized) && !/\b(engine|moteur)\b/i.test(normalized)) return 'cylinder_actuator'
  if (/\b(hinge|charniere|charni[eè]re|pivot|gond)\b/i.test(normalized)) return 'hinge_joint'
  if (/\b(linkage|bielle|cam|came|lever|levier|rocker|crank|slider|biellette|manivelle|tringlerie)\b/i.test(normalized)) return 'linkage'
  // LED strip: bandeau / ruban / strip RGB / chaser / chase / addressable / WS2812 etc.
  if (/\b(bandeau\s+led|ruban\s+led|led\s+strip|strip\s+led|ws2812|sk6812|addressable\s+led|neopixel|chaser|arc\s+en\s+ciel|rainbow\s+led|rgb\s+strip)\b/i.test(normalized)) return 'led_strip'
  if (/\bled\b/i.test(normalized) && /\b(bandeau|ruban|strip|bande|chaser|chenillard|pattern)\b/i.test(normalized)) return 'led_strip'
  // PC cabling — broad detection for any PC cable/component product
  if (/\b(strimer|lian li|cablemod|cable mod)\b/i.test(normalized)) return 'pc_cabling'
  if (/\b(motherboard|carte mere|psu|alimentation|pcie|atx|sata|gpu|carte graphique|case wiring|cable management|argb|12vhpwr|24[\s-]?pin|8[\s-]?pin|extension cable|sleeved cable|cable extension|rallonge)\b/i.test(normalized)) return 'pc_cabling'
  if (/\b(rgb|led)\b/i.test(normalized) && /\b(cable|extension|strip|ruban|bande)\b/i.test(normalized)) return 'pc_cabling'
  if (/\b(wire harness|harness|faisceau|electrique|electrical|connector|connecteur|loom|bornier|terminal block)\b/i.test(normalized)) return 'electrical_harness'
  if (/\b(cable|cables|wire|wiring|fil|fils|cordon)\b/i.test(normalized)) return 'cable_routing'

  return 'generic'
}

// v77ze: detect explicit motion verbs in the prompt — covers real-world
// objects where the user wants the result to actually MOVE, not just sit
// static on a turntable. "voiture qui roule", "ventilateur qui tourne",
// "drone qui vole", "balancier qui swing", "ascenseur qui monte"...
//
// Returns a hint about WHAT KIND of motion is requested so downstream code
// can pick the right Blender rig template (rotating mech, vehicle rolling,
// pendulum swing, hover bobbing) instead of a generic turntable.
export type ThreeDMotionVerbHint =
  | null
  | 'rotating'   // tourne, spin, rotate, ventilateur, helice, roue tournante
  | 'rolling'    // roule, drives, advance, voiture, moto
  | 'flying'     // vole, hover, drone, helicoptere, fusee
  | 'walking'    // marche, court, run, walk, jog
  | 'swinging'   // swing, pendule, balancier, hammock
  | 'oscillating'// vibre, oscille, pulse, breathe, bat
  | 'mechanism'  // generic articulated motion ("en mouvement", "moves")

export function detectMotionVerbHint(prompt: string): ThreeDMotionVerbHint {
  const normalized = prompt.toLowerCase()
  // Order matters: more specific patterns first.
  if (/\b(swing|swinging|swung|balanc(?:e|ier)|pendul(?:e|um)|hammock|hamac|chandelier|lustre|hanging|suspendu)\b/i.test(normalized)) return 'swinging'
  if (/\b(vibrat|oscillat|pulse|pulsing|battement|battant|breathing|respire|respira|bat|chuck)\b/i.test(normalized)) return 'oscillating'
  if (/\b(marche|marcher|court|courir|jogging|run|running|walk|walking|jog|sprint|sprinting|dance|danse|dancing)\b/i.test(normalized)) return 'walking'
  if (/\b(vole|voler|fly|flying|flies|hover|hovering|float|floating|drone|helicop|helicopter|fusee|rocket|levite|levitating)\b/i.test(normalized)) return 'flying'
  if (/\b(roule|rouler|rolling|rolls|drives|driving|advance|advancing|cruising|move forward|avance|mobile)\b/i.test(normalized)) return 'rolling'
  if (/\b(tourne|tourner|spin|spins|spinning|rotat|whirl|twirl|gire|girar|ventilateur|fan(?:s)? running|helice|propeller|whirling)\b/i.test(normalized)) return 'rotating'
  if (/\b(en mouvement|en marche|in motion|moving|motion study|kinematic|en action|fonctionne|fonctionnement|en service|in operation|active|active state)\b/i.test(normalized)) return 'mechanism'
  return null
}

// v77zf: Meshy-grade PBR material inference. The actual implementation lives
// in ./pbrProfile.ts (no Tauri / React deps) so node --test can exercise it
// without dragging the runtime bridge in. Re-exported here for callers that
// already import the rest of threeDIntent.
export { inferPbrProfile, type PbrProfile, type PbrProfileKind } from './pbrProfile.ts'

function detectMotionReadiness(
  prompt: string,
  purpose: ThreeDPurpose,
  subjectKind: ThreeDSubjectKind,
  systemClass: ThreeDSystemClass,
): MotionReadiness {
  const normalized = prompt.toLowerCase()
  const asksAnimation = /\b(animation|animate|animer|rig|rigging|pose|poser|mouvement|movement|joint|charniere|hinge|articulation)\b/i.test(normalized)
  // v77ze: motion-verb detection upgrades non-mechanical objects too.
  // A "drone qui vole" or "ventilateur qui tourne" is technically a static
  // mesh by default but the user obviously wants it animated, not turntable.
  const motionVerb = detectMotionVerbHint(prompt)

  if (systemClass === 'belt_drive' || systemClass === 'gear_train' || systemClass === 'cylinder_actuator' || systemClass === 'hinge_joint' || systemClass === 'linkage') {
    return 'articulated'
  }
  if (purpose === 'character' || subjectKind === 'character' || subjectKind === 'creature') {
    return asksAnimation || motionVerb === 'walking' ? 'rig_candidate' : 'poseable'
  }
  if (purpose === 'body_part' || subjectKind === 'body_part') {
    return asksAnimation ? 'poseable' : 'static_only'
  }
  if (purpose === 'mechanical_part' || purpose === 'printable_prototype' || subjectKind === 'assembly') {
    return asksAnimation || motionVerb ? 'articulated' : 'static_only'
  }
  // Real-world objects with explicit motion verbs (voiture qui roule, drone
  // qui vole, ventilateur qui tourne) get articulated motion instead of the
  // dull product turntable fallback.
  if (motionVerb) {
    return 'articulated'
  }
  return 'static_only'
}

function detectRepresentationGoal(systemClass: ThreeDSystemClass, motionReadiness: MotionReadiness): ThreeDRepresentationGoal {
  if (systemClass === 'cable_routing' || systemClass === 'pc_cabling' || systemClass === 'electrical_harness') {
    return 'routing_readability'
  }
  if (motionReadiness === 'rig_candidate') {
    return 'rig_readability'
  }
  if (motionReadiness === 'articulated') {
    return 'kinematic_readability'
  }

  return 'static_shape'
}

function promptExplicitlyRequestsHostContext(prompt: string) {
  const normalized = prompt.toLowerCase()
  return /\b(dans un boitier|inside a case|inside the case|installed in|installed on|carte mere|motherboard|gpu|psu|power supply|pc complet|full pc|whole computer|tour complete|chassis|cable management|routing through the chassis|in situ|monte sur|installed product|dans la machine|dans le pc)\b/i.test(normalized)
}

function promptExplicitlyRequestsSceneContext(prompt: string) {
  const normalized = prompt.toLowerCase()
  return /\b(scene|decor|d[ée]cor|environment|environnement|landscape|paysage|cityscape|room|piece complete|atelier|workshop|sur une table|mise en situation|dans une scene|dans un decor)\b/i.test(normalized)
}

function detectReferenceFraming(
  prompt: string,
  purpose: ThreeDPurpose,
  subjectKind: ThreeDSubjectKind,
  systemClass: ThreeDSystemClass,
): ThreeDReferenceFraming {
  if (promptExplicitlyRequestsSceneContext(prompt)) {
    return 'scene_context'
  }

  if (systemClass === 'pc_cabling' || systemClass === 'cable_routing' || systemClass === 'electrical_harness') {
    return promptExplicitlyRequestsHostContext(prompt) ? 'host_context' : 'isolated_subject'
  }

  if (purpose === 'character' || subjectKind === 'character' || subjectKind === 'creature' || purpose === 'body_part' || subjectKind === 'body_part') {
    return 'isolated_subject'
  }

  if (purpose === 'mechanical_part' || purpose === 'printable_prototype' || purpose === 'product' || subjectKind === 'product' || subjectKind === 'tool') {
    return 'isolated_subject'
  }

  return 'scene_context'
}

function buildPartFocus(
  systemClass: ThreeDSystemClass,
  subjectKind: ThreeDSubjectKind,
  motionReadiness: MotionReadiness,
  referenceFraming: ThreeDReferenceFraming,
) {
  switch (systemClass) {
    case 'belt_drive':
      return {
        movingPartsFocus: ['continuous belt loop', 'drive pulley', 'driven pulley', 'idler pulleys if present'],
        anchoredPartsFocus: ['motor housing', 'shaft supports', 'mounting frame'],
      }
    case 'gear_train':
      return {
        movingPartsFocus: ['meshing gears', 'shafts or axles'],
        anchoredPartsFocus: ['housing', 'bearing supports', 'mounting frame'],
      }
    case 'cylinder_actuator':
      return {
        movingPartsFocus: ['rod', 'clevis or end-effector', 'sliding carriage if present'],
        anchoredPartsFocus: ['cylinder body', 'base mount', 'support bracket'],
      }
    case 'hinge_joint':
      return {
        movingPartsFocus: ['moving leaf or arm', 'pivot pin'],
        anchoredPartsFocus: ['fixed leaf', 'frame or bracket'],
      }
    case 'linkage':
      return {
        movingPartsFocus: ['links and lever arms', 'pivot joints'],
        anchoredPartsFocus: ['fixed frame', 'ground link', 'support brackets'],
      }
    case 'cable_routing':
      return {
        movingPartsFocus: [],
        anchoredPartsFocus: referenceFraming === 'host_context'
          ? ['connector endpoints', 'routing anchors', 'bend zones', 'cable clamps']
          : ['connector ends', 'main cable body', 'strain-relief zones', 'cable clamps or separators'],
      }
    case 'pc_cabling':
      return {
        movingPartsFocus: [],
        anchoredPartsFocus: referenceFraming === 'host_context'
          ? ['motherboard connectors', 'GPU or PSU connectors', 'case routing points', 'bundle exits', 'cable combs or light guides']
          : ['connector housings', 'cable comb spacing', 'light-guide tubes or sleeves', 'bundle exits', 'connector orientation'],
      }
    case 'electrical_harness':
      return {
        movingPartsFocus: [],
        anchoredPartsFocus: referenceFraming === 'host_context'
          ? ['connectors', 'loom clips', 'bundle branches', 'termination points']
          : ['connectors', 'bundle branches', 'termination points', 'loom sleeve or protection'],
      }
    default:
      if (motionReadiness === 'rig_candidate') {
        return {
          movingPartsFocus: ['limbs', 'deformation zones around shoulders, elbows, hips and knees'],
          anchoredPartsFocus: ['torso or root body'],
        }
      }
      if (motionReadiness === 'articulated') {
        return {
          movingPartsFocus: ['moving subassemblies'],
          anchoredPartsFocus: ['fixed frame or housing'],
        }
      }
      if (subjectKind === 'electrical_system') {
        return {
          movingPartsFocus: [],
          anchoredPartsFocus: ['connectors', 'routing anchors', 'bundle exits'],
        }
      }
      return {
        movingPartsFocus: [],
        anchoredPartsFocus: [],
      }
  }
}

function buildReferencePromptAdditions(
  referenceFraming: ThreeDReferenceFraming,
  purpose: ThreeDPurpose,
  subjectKind: ThreeDSubjectKind,
  motionReadiness: MotionReadiness,
  systemClass: ThreeDSystemClass,
  representationGoal: ThreeDRepresentationGoal,
) {
  const shared = [
    'single isolated subject',
    'neutral studio background',
    'clear silhouette with no crop',
    'high edge separation',
    'real inspectable volume, never a cube placeholder or flat cardboard cutout',
    'visible material zones with surface texture cues, not single-color plastic',
    'no clutter, no extra objects, no text',
  ]

  const additions = [...shared]

  if (representationGoal === 'kinematic_readability') {
    additions.push(
      'all functional parts visible in one frame',
      'moving subassemblies and fixed supports clearly separated',
      'no exploded view unless explicitly requested',
    )
  }

  if (representationGoal === 'routing_readability') {
    additions.push(
      'routing path visible end to end',
      'connectors and endpoints clearly visible',
      'bundles and anchors readable at first glance',
    )
  }

  if (systemClass === 'belt_drive') {
    additions.push('continuous taut belt around aligned pulleys', 'frame and supports remain visible')
  }
  if (systemClass === 'gear_train') {
    additions.push('meshing gears visible together', 'axle alignment readable')
  }
  if (systemClass === 'cylinder_actuator') {
    additions.push('cylinder body and rod visible on one axis', 'mounts and stroke direction readable')
  }
  if (systemClass === 'hinge_joint' || systemClass === 'linkage') {
    additions.push('pivot order and link hierarchy readable', 'fixed bracket visible together with moving member')
  }
  if (systemClass === 'cable_routing' || systemClass === 'pc_cabling' || systemClass === 'electrical_harness') {
    additions.push(
      'connector interfaces readable',
      'plausible cable routing with realistic bend radius',
      referenceFraming === 'host_context'
        ? 'host device may appear only as the minimum structure needed to understand the routing'
        : 'only the requested cable or harness assembly unless a full host device is explicitly requested',
    )
  }

  if (systemClass === 'pc_cabling') {
    additions.push(
      referenceFraming === 'host_context'
        ? 'show only the relevant motherboard, GPU or PSU interfaces instead of a whole PC tower'
        : 'this is a standalone cable product or accessory, not a full PC tower',
      'keep light guides, comb spacing and connector orientation readable when RGB or LED cables are requested',
    )
  }

  if (referenceFraming === 'isolated_subject') {
    additions.push('subject isolated from any host environment')
  }
  if (referenceFraming === 'scene_context') {
    additions.push('scene context may appear, but the requested subject must stay dominant and fully readable')
  }

  if (purpose === 'mechanical_part' || purpose === 'printable_prototype') {
    additions.push(
      'orthographic-friendly product render',
      'hard-surface details',
      'clean part boundaries',
      'symmetry preserved when relevant',
      'industrial design readability',
    )
  }

  if (purpose === 'character') {
    additions.push(
      'full body visible',
      'neutral A-pose or relaxed turntable pose',
      'arms and legs clearly separated from the torso',
      'stable anatomy',
    )
    if (motionReadiness === 'rig_candidate') {
      additions.push('clear shoulder, elbow, hip and knee separation')
    }
  }

  if (purpose === 'body_part') {
    additions.push(
      'isolated anatomical subject',
      'medically coherent proportions',
      'clear front-facing readable pose',
    )
  }

  if (purpose === 'game_asset') {
    additions.push(
      'game-ready readable silhouette',
      'clean materials',
      'front three-quarter product render',
    )
  }

  if (subjectKind === 'vehicle' || subjectKind === 'product') {
    additions.push(
      'product render lighting',
      'front three-quarter angle',
      'high material readability',
    )
  }

  return uniqueStrings(additions)
}

function buildMeshConstraints(
  purpose: ThreeDPurpose,
  subjectKind: ThreeDSubjectKind,
  motionReadiness: MotionReadiness,
  systemClass: ThreeDSystemClass,
  representationGoal: ThreeDRepresentationGoal,
) {
  const constraints = [
    'closed readable silhouette',
    'no floating disconnected parts',
    'no cluttered background baked into the shape',
    'reject cube-like or primitive placeholder geometry unless the user explicitly asked for that primitive',
    'surface detail must be supported by real geometry or UV/PBR texture, not only a flat pasted image',
    'materials must remain separable: distinct albedo/roughness/metalness zones for metal, glass, fabric, plastic, wood, skin or emission when relevant',
  ]

  if (purpose === 'mechanical_part' || purpose === 'printable_prototype') {
    constraints.push(
      'preserve hard-surface edges and rigid alignments',
      'avoid melted surfaces and impossible joints',
      'prefer symmetry and assembly coherence',
    )
  }

  if (purpose === 'character' || subjectKind === 'body_part') {
    constraints.push(
      'keep believable anatomy and limb thickness',
      'avoid fused limbs and broken joints',
    )
  }

  if (representationGoal === 'kinematic_readability') {
    constraints.push('keep moving parts visually distinct from the fixed structure')
  }

  if (representationGoal === 'routing_readability') {
    constraints.push(
      'keep connectors, route anchors and cable bundles distinct',
      'avoid merged wires, impossible crossings and disconnected terminations',
    )
  }

  if (systemClass === 'pc_cabling') {
    constraints.push(
      'avoid turning the cable request into a full PC case scene',
      'keep LED diffusers, sleeves and comb spacing continuous and readable',
      'preserve connector count and orientation when visible',
    )
  }

  if (motionReadiness === 'articulated') {
    constraints.push(
      'keep hinge axes, pivots and part separations readable',
      'do not fake requested motion by rotating the whole mesh as one rigid block',
    )
  }

  if (motionReadiness === 'rig_candidate') {
    constraints.push(
      'keep deformation zones readable around shoulders, elbows, hips and knees',
      'limbs, head, hands and feet must be distinguishable enough for a real animation rig',
    )
  }

  if (systemClass === 'belt_drive') {
    constraints.push('belt must remain separate from pulleys and support frame', 'keep pulleys coplanar when relevant')
  }
  if (systemClass === 'gear_train') {
    constraints.push('gear teeth contact and axle spacing must stay readable')
  }
  if (systemClass === 'cylinder_actuator') {
    constraints.push('rod stays coaxial with cylinder body', 'mounting ends remain readable')
  }
  if (systemClass === 'hinge_joint' || systemClass === 'linkage') {
    constraints.push('pivot centers and link order remain readable')
  }

  if (purpose === 'game_asset') {
    constraints.push('prefer a stable hero silhouette for downstream retopo or baking')
  }

  return uniqueStrings(constraints)
}

function buildMotionGuidance(
  motionReadiness: MotionReadiness,
  purpose: ThreeDPurpose,
  subjectKind: ThreeDSubjectKind,
  systemClass: ThreeDSystemClass,
  referenceFraming: ThreeDReferenceFraming,
) {
  switch (systemClass) {
    case 'belt_drive':
      return [
        'show the full transmission chain, not just the belt',
        'keep pulleys aligned and visually tied together by one continuous belt loop',
        'frame and supports stay static while belt path and rotating members remain readable',
      ]
    case 'gear_train':
      return [
        'show the gear train as one coherent rotating system',
        'preserve rigid axle alignment and clear meshing order',
        'do not invent soft bending or drifting gear positions',
      ]
    case 'cylinder_actuator':
      return [
        'show the actuator body as fixed and the rod as the translating element',
        'keep the extension axis straight and readable',
        'mounts, clevises and end stops should stay visually coherent',
      ]
    case 'hinge_joint':
      return [
        'show the hinge axis clearly',
        'keep the fixed bracket distinct from the moving leaf or arm',
      ]
    case 'linkage':
      return [
        'show the order of links and pivots clearly',
        'separate moving links from the grounded frame',
      ]
    case 'cable_routing':
    case 'pc_cabling':
    case 'electrical_harness':
      return [
        'treat the system as static functional routing, not animated motion',
        'keep connector endpoints, anchors and bundle path readable',
        'respect plausible bend radius and route hierarchy',
        ...(systemClass === 'pc_cabling'
          ? [referenceFraming === 'host_context'
              ? 'show only the minimum host structure needed for routing comprehension'
              : 'avoid inventing a full chassis around the cable unless the prompt explicitly asks for it']
          : []),
      ]
    default:
      break
  }

  if (motionReadiness === 'rig_candidate') {
    return [
      'prefer neutral readable pose for future rigging',
      'keep limbs separated from torso when possible',
      'avoid merged fingers, elbows and knees',
    ]
  }

  if (motionReadiness === 'articulated') {
    return [
      'show functional pivots and articulations clearly',
      'separate moving parts from rigid frame',
      'do not fake soft organic bending on hard-surface parts',
    ]
  }

  if (motionReadiness === 'poseable') {
    return [
      'keep pose readable and balanced',
      'preserve stable anatomical proportions',
    ]
  }

  if (purpose === 'product' || subjectKind === 'product' || subjectKind === 'tool') {
    return ['treat the object as mostly static unless explicit articulation is requested']
  }

  return ['do not imply impossible articulation if the object is fundamentally static']
}

function buildMotionRisks(
  motionReadiness: MotionReadiness,
  purpose: ThreeDPurpose,
  subjectKind: ThreeDSubjectKind,
  systemClass: ThreeDSystemClass,
) {
  const risks: string[] = []

  if (systemClass === 'belt_drive') {
    risks.push('a still mesh can suggest belt motion but cannot prove real tension, slip or rotation direction')
  }
  if (systemClass === 'gear_train') {
    risks.push('gear ratios, backlash and true tooth geometry remain approximate without technical references')
  }
  if (systemClass === 'cylinder_actuator') {
    risks.push('stroke length, seals and real clearances remain approximate without dimensions')
  }
  if (systemClass === 'cable_routing' || systemClass === 'pc_cabling' || systemClass === 'electrical_harness') {
    risks.push('cable gauge, connector standard and exact bend radius remain approximate without real references')
  }

  if (motionReadiness === 'static_only') {
    risks.push('this type of object may not support meaningful motion representation without invented joints')
  }
  if (motionReadiness === 'articulated') {
    risks.push('generated mesh may suggest articulation but not provide CAD-accurate tolerances or real assemblies')
  }
  if (motionReadiness === 'rig_candidate') {
    risks.push('mesh may be visually riggable but not animation-ready topology by itself')
  }
  if (purpose === 'printable_prototype') {
    risks.push('printing accuracy cannot be guaranteed without exact dimensions and tolerances')
  }
  if (subjectKind === 'body_part') {
    risks.push('anatomical articulation may be approximate without explicit medical references')
  }

  return uniqueStrings(risks)
}

/**
 * Detect known product families and return an explicit visual description.
 * This is critical: FLUX does not know what "Strimer" or "12VHPWR extension" looks like.
 * Without this, it generates the manufacturer's main product (e.g. a PC case for Lian Li).
 */
function detectKnownProductDescription(prompt: string, systemClass: ThreeDSystemClass): string[] {
  const normalized = prompt.toLowerCase()
  const descriptions: string[] = []

  // ── PC CABLING / CABLE ROUTING / ELECTRICAL HARNESS ──

  if (systemClass === 'pc_cabling' || systemClass === 'cable_routing' || systemClass === 'electrical_harness') {
    // Lian Li Strimer family (24-pin, 8-pin, 12VHPWR, Plus v1/v2)
    if (/\bstrimer\b/i.test(normalized)) {
      descriptions.push(
        'THIS IS NOT A PC CASE. The Lian Li Strimer is an addressable RGB cable extension product.',
        'Visual description: a flat ribbon-like cable assembly with parallel transparent light-guide tubes held by stable clips, plus a lower row of sleeved power cables.',
        'One end has a standard power connector (24-pin ATX, 8-pin PCIe, or 12VHPWR depending on variant). The other end connects to a matching PSU cable.',
        'The tubes contain addressable LED strips that glow with vivid RGB colors, creating a rainbow or programmable lighting effect along the entire length.',
        'The product looks like a flat ribbon of glowing translucent tubes, NOT a box, NOT a tower, NOT a circuit board.',
        'Generate ONLY the illuminated cable extension product itself, isolated on a solid black background.',
        'DO NOT generate a PC tower, desktop case, motherboard, GPU, or any computer chassis or housing.',
      )
      if (/\b(plus|v2|plus\s?v2)\b/i.test(normalized)) {
        descriptions.push(
          'Strimer Plus V2 variant: 24-pin model uses 12 slim light guides, 120 LEDs, single-layer flat 18AWG cable row, black connector blocks, black stable clips, side light strip, translucent silicone/TPE diffuser and UV-resistant coating.',
        )
      }
      if (/\b24[\s-]?pin\b/i.test(normalized)) {
        descriptions.push('24-pin ATX variant: wider cable assembly (~50mm) with 24-pin motherboard power connector at one end.')
      }
      if (/\b(8[\s-]?pin|pcie)\b/i.test(normalized)) {
        descriptions.push('8-pin PCIe variant: narrower cable assembly (~25mm) for GPU power connection.')
      }
      if (/\b12vhpwr\b/i.test(normalized)) {
        descriptions.push('12VHPWR variant: 16-pin (12+4) connector for modern high-power GPUs.')
      }
    }

    // Generic RGB/ARGB extension cables
    if (!descriptions.length && /\b(rgb|argb|led)\b/i.test(normalized) && /\b(cable|extension|extension cable)\b/i.test(normalized)) {
      descriptions.push(
        'THIS IS NOT A PC CASE. This is an RGB/ARGB cable extension product.',
        'Visual description: parallel light-guide tubes or sleeved cables with embedded LED strips, held by cable combs in an organized row.',
        'Standard power connector at each end. The product is a flat ribbon-like cable assembly.',
        'DO NOT generate a PC tower, desktop case, or computer chassis.',
        'Generate ONLY the cable extension product itself in isolation on black background.',
      )
    }

    // Sleeved extension cables (CableMod, etc.)
    if (!descriptions.length && /\b(sleeved|cable\s?mod|cablement)\b/i.test(normalized) && /\b(cable|extension|psu|24[\s-]?pin|8[\s-]?pin|atx|pcie)\b/i.test(normalized)) {
      descriptions.push(
        'THIS IS NOT A PC CASE. This is a sleeved PSU extension cable.',
        'Visual description: individual sleeved wires (often braided mesh in solid colors) bundled together with cable combs every ~30mm.',
        'Standard power connector at each end (24-pin ATX, 8-pin PCIe, etc.). The product is a cable, not a box or device.',
        'DO NOT generate a PC tower, desktop case, motherboard, or computer.',
        'Generate ONLY the cable product itself in isolation.',
      )
    }

    // 12VHPWR / PCIe 5.0 cables
    if (!descriptions.length && /\b12vhpwr\b/i.test(normalized)) {
      descriptions.push(
        'THIS IS NOT A PC CASE. This is a 12VHPWR (12+4 pin) power cable or adapter.',
        'Visual description: a cable with a 16-pin 12VHPWR connector at one end and typically 2x 8-pin PCIe connectors at the other.',
        'DO NOT generate a PC tower or case. Generate ONLY the cable itself isolated on black background.',
      )
    }
  }

  // ── MECHANICAL SYSTEMS ──

  if (systemClass === 'belt_drive') {
    descriptions.push(
      'Visual description: a belt drive system consists of a toothed or V-belt wrapped around two or more pulleys (wheels with grooves).',
      'The belt is a continuous flexible loop. The pulleys are cylindrical wheels mounted on shafts.',
      'Generate the mechanical assembly showing the belt path, pulley diameters, and shaft positions clearly.',
    )
  }

  if (systemClass === 'gear_train') {
    descriptions.push(
      'Visual description: a gear train is a set of meshing toothed gears (spur, helical, or bevel) on parallel or intersecting shafts.',
      'Each gear has visible teeth around its circumference. Meshing gears have their teeth interlocked.',
      'Generate the gear assembly showing tooth profiles, mesh points, and shaft axes clearly.',
    )
  }

  if (systemClass === 'cylinder_actuator') {
    descriptions.push(
      'Visual description: a hydraulic or pneumatic cylinder with a cylindrical body (barrel), a piston rod extending from one end, and mounting points (clevis, trunnion, or flange) at each end.',
      'The barrel is a smooth cylinder, the rod is a polished shaft. Port fittings are visible on the barrel.',
      'Generate the actuator showing the full stroke range, mounting hardware, and port locations.',
    )
  }

  if (systemClass === 'hinge_joint') {
    descriptions.push(
      'Visual description: a mechanical hinge consisting of two plates or leaves connected by a pivot pin or knuckle.',
      'The pivot axis must be clearly visible. The two halves should be distinguishable.',
      'Generate the hinge showing both open and closed geometry potential, with clear pivot point.',
    )
  }

  if (systemClass === 'linkage') {
    descriptions.push(
      'Visual description: a mechanical linkage is a system of rigid bars (links) connected by pivot joints (pins).',
      'Each link is a rigid bar with holes at each end for the pivot pins. Joints allow rotation.',
      'Generate the linkage showing all links, pivot points, and the kinematic chain clearly.',
    )
  }

  // ── KNOWN PC COMPONENTS (when system class is generic but product is identifiable) ──

  if (!descriptions.length) {
    // AIO liquid coolers
    if (/\b(aio|liquid cool|watercool|refroidissement liquide)\b/i.test(normalized) && /\b(radiator|radiateur|240|280|360|420)\b/i.test(normalized)) {
      descriptions.push(
        'Visual description: an AIO (All-In-One) liquid cooler consists of a CPU water block (small square/circular pump unit), two flexible rubber tubes, and a flat rectangular radiator with fins.',
        'The radiator has fans mounted on one side. The tubes connect the pump block to the radiator.',
        'Generate the complete AIO assembly isolated, showing pump block, tubes, and radiator with fans.',
      )
    }

    // GPU (graphics card)
    if (/\b(gpu|carte graphique|graphics card|rtx|gtx|radeon|rx\s?\d{4})\b/i.test(normalized) && !/\b(cable|extension|strimer)\b/i.test(normalized)) {
      descriptions.push(
        'Visual description: a graphics card (GPU) is a large PCB with a prominent cooler shroud covering heat sink fins and fans.',
        'It has a PCIe gold-finger connector on the bottom edge, display output ports on the bracket end, and power connectors on the top or end.',
        'The cooler typically has 2-3 fans visible on one face. The card is roughly rectangular, 250-350mm long.',
      )
    }

    // Motherboard
    if (/\b(carte mere|motherboard|mobo)\b/i.test(normalized) && !/\b(cable|dans une|inside)\b/i.test(normalized)) {
      descriptions.push(
        'Visual description: a motherboard is a large flat PCB (circuit board) with a CPU socket, RAM slots, PCIe slots, VRM heatsinks, chipset heatsink, and I/O panel.',
        'Multiple connectors are visible: 24-pin ATX, 8-pin CPU, SATA, USB headers, fan headers.',
        'The board is rectangular, typically green/black/dark colored with various components soldered on.',
      )
    }

    // PSU (power supply unit)
    if (/\b(psu|alimentation|power supply|alim)\b/i.test(normalized) && !/\b(cable|extension|strimer)\b/i.test(normalized)) {
      descriptions.push(
        'Visual description: a PSU (Power Supply Unit) is a metal box with a large fan grille on one side and modular cable connectors on another.',
        'One end has the AC power inlet and on/off switch. The other end has DC output cables or modular sockets.',
        'The unit is roughly 150x86x140mm for ATX standard.',
      )
    }

    // RAM / memory
    if (/\b(ram|memoire vive|ddr4|ddr5|dimm)\b/i.test(normalized)) {
      descriptions.push(
        'Visual description: a RAM module (DIMM) is a thin rectangular PCB (~133mm long, ~31mm tall) with memory chips on both sides.',
        'Gold contact pins along the bottom edge. Many gaming RAM modules have a decorative heat spreader and sometimes RGB light bars on top.',
      )
    }

    // CPU cooler (air)
    if (/\b(ventirad|cpu cooler|air cooler|noctua|be quiet|hyper 212)\b/i.test(normalized) && !/\b(aio|liquid|watercool)\b/i.test(normalized)) {
      descriptions.push(
        'Visual description: a tower-style CPU air cooler has a copper/aluminum base plate, heat pipes rising vertically, aluminum fin stacks, and one or two fans.',
        'The heat pipes are U-shaped tubes visible at the sides. The fan clips onto the fin stack.',
      )
    }

    // SSD / NVMe
    if (/\b(ssd|nvme|m\.?2)\b/i.test(normalized)) {
      descriptions.push(
        'Visual description: an NVMe SSD is a small rectangular PCB (22x80mm for M.2 2280) with NAND flash chips and a controller chip.',
        'It has a gold M-key connector at one end. Some have a heatsink or heat spreader cover.',
      )
    }

    // Case fans
    if (/\b(ventilateur|case fan|fan rgb|ventilo)\b/i.test(normalized) && !/\b(cpu|ventirad|cooler)\b/i.test(normalized)) {
      descriptions.push(
        'Visual description: a PC case fan is a square frame (120mm or 140mm) with impeller blades in the center.',
        'The frame has mounting holes at four corners. RGB fans have a light ring or LED-lit blades.',
      )
    }

    // ── PC CASES / BOITIERS — with brand-specific detail requirements ──
    const isCasePrompt = /\b(boitier|bo[iî]tier|case|tower|tour|chassis|mid[\s-]?tower|full[\s-]?tower|mini[\s-]?tower|itx case|matx case|atx case)\b/i.test(normalized)
    if (isCasePrompt) {
      // MSI MAG FORGE series
      if (/\bmsi\b/i.test(normalized) && /\b(forge|mag)\b/i.test(normalized)) {
        const is100R = /\b100\s?r\b/i.test(normalized)
        descriptions.push(
          'Visual description: MSI MAG FORGE is a mid-tower ATX PC case with a flat tempered glass side panel and a mesh front panel for airflow.',
          is100R
            ? 'MAG FORGE 100R specifics: black steel body, full tempered glass left side panel (flat, not curved), mesh front panel with hexagonal pattern and subtle MSI dragon logo, two pre-installed 120mm ARGB fans (one front, one rear), PSU shroud at bottom covering cables and PSU, 7 PCIe expansion slots at rear, top I/O panel with USB 3.0, USB 2.0, audio jacks and power/reset buttons.'
            : 'MAG FORGE case: steel body, tempered glass left side, mesh front panel with MSI branding, top I/O panel, 7 PCIe expansion slots, PSU shroud.',
          'CRITICAL DETAILS TO RENDER: (1) the mesh front panel pattern must have visible perforations/hexagonal holes, (2) USB ports and audio jacks on top panel must be individually distinguishable, (3) fan mounting points must show screw holes, (4) PCIe slot covers at rear must be individually readable, (5) rubber feet/standoffs at bottom must be present, (6) power button on top must be a distinct circular element.',
          'The case interior is visible through the glass side panel: motherboard standoffs, cable routing holes with rubber grommets, drive bay brackets.',
          'Generate the case as a three-quarter front view showing both the glass panel side and the mesh front panel, on solid black studio background.',
        )
      }
      // NZXT cases
      else if (/\bnzxt\b/i.test(normalized)) {
        descriptions.push(
          'Visual description: NZXT PC case with minimalist design, clean lines, tempered glass side panel, steel/plastic body.',
          'NZXT cases have a distinctive clean aesthetic with cable management bar, minimal front I/O panel, and NZXT logo.',
          'CRITICAL DETAILS: USB-C port on top I/O, tempered glass with clean edges, smooth painted steel panels, visible interior through side window.',
        )
      }
      // Corsair cases
      else if (/\bcorsair\b/i.test(normalized)) {
        descriptions.push(
          'Visual description: Corsair PC case with tempered glass panel, typically iCUE RGB elements, steel construction.',
          'CRITICAL DETAILS: Corsair logo on front, tempered glass with mounting hardware visible, airflow-optimized mesh or glass front, USB ports and RGB button on top I/O.',
        )
      }
      // Lian Li cases (not Strimer cables)
      else if (/\blian li\b/i.test(normalized) && !/\bstrimer\b/i.test(normalized)) {
        descriptions.push(
          'Visual description: Lian Li PC case with premium aluminum or steel construction, tempered glass panels.',
          'Lian Li cases are known for clean aluminum finishes, tool-less side panels, and modular interiors.',
          'CRITICAL DETAILS: smooth aluminum panel surfaces, precision-cut ventilation slots, premium build quality visible in edges and joins.',
        )
      }
      // Generic PC case
      else {
        descriptions.push(
          'Visual description: a PC mid-tower case is a rectangular metal box (~450x210x430mm) with removable side panels.',
          'One side panel is typically tempered glass. The front panel may be mesh, glass, or solid with RGB elements.',
          'Top has an I/O panel (USB, audio, power/reset buttons). Rear has a PSU mount, exhaust fan, I/O cutout, and 7 PCIe slot covers.',
          'Bottom has rubber feet/standoffs and often a dust filter for the PSU intake.',
          'CRITICAL DETAILS TO RENDER: (1) front panel texture (mesh holes or glass reflections), (2) USB ports on top I/O must be separate elements, (3) power button distinct shape, (4) PCIe slots at rear individually readable, (5) fan grilles must show blade pattern or mesh, (6) screws and mounting hardware visible, (7) rubber grommets on cable routing holes visible through glass.',
        )
      }
    }
  }

  return descriptions
}

function buildResearchQueries(prompt: string, systemClass: ThreeDSystemClass, referenceFraming: ThreeDReferenceFraming) {
  const queries = [prompt]
  const normalized = prompt.toLowerCase()

  switch (systemClass) {
    case 'belt_drive':
      queries.push('systeme courroie poulie transmission mecanique')
      queries.push('belt drive pulley transmission')
      break
    case 'gear_train':
      queries.push('train d engrenages transmission mecanique')
      queries.push('gear train mechanical transmission')
      break
    case 'cylinder_actuator':
      queries.push('verin mecanique hydraulique pneumatique')
      queries.push('cylinder actuator assembly')
      break
    case 'hinge_joint':
      queries.push('charniere mecanique axe pivot')
      queries.push('mechanical hinge pivot joint')
      break
    case 'linkage':
      queries.push('bielle tringlerie mecanique')
      queries.push('mechanical linkage pivot system')
      break
    case 'cable_routing':
      queries.push('routage cable guide faisceau')
      queries.push('cable routing harness guide')
      break
    case 'pc_cabling':
      if (referenceFraming === 'host_context') {
        queries.push('pc cable management motherboard psu gpu connectors')
        queries.push('installed gpu psu cable routing reference')
      } else {
        queries.push('rgb led extension cable strimer pcie 24 pin product photo')
        queries.push('isolated strimer cable product reference')
        queries.push('standalone rgb extension cable connector close-up')
      }
      break
    case 'electrical_harness':
      queries.push('faisceau electrique connecteurs routage')
      queries.push('electrical harness routing connectors')
      break
    default:
      break
  }

  if (/\b(reference|exact|existing|modele|model|datasheet|product|produit|component|composant|piece|part)\b/i.test(normalized)) {
    queries.push(`${prompt} dimensions size measurements`)
    queries.push(`${prompt} reference photo`)
    queries.push(`${prompt} isolated product view`)
  }

  if (/\b(anime|manga|personnage|character|hero|waifu|villain)\b/i.test(normalized)) {
    queries.push(`${prompt} official character design`)
    queries.push(`${prompt} full body reference`)
    queries.push(`${prompt} isolated character render`)
  }

  return uniqueStrings(queries)
}

function buildMotionPresets(
  referenceFraming: ThreeDReferenceFraming,
  purpose: ThreeDPurpose,
  subjectKind: ThreeDSubjectKind,
  systemClass: ThreeDSystemClass,
  representationGoal: ThreeDRepresentationGoal,
  motionReadiness: MotionReadiness,
): ThreeDMotionPreset[] {
  switch (systemClass) {
    case 'belt_drive':
      return [
        {
          id: 'belt_motion_study',
          label: 'Courroie en charge',
          description: 'Montre la boucle complete avec courroie tendue, poulies alignees et bati fixe.',
          promptDirective: 'Show a coherent belt-drive motion study with a continuous taut belt loop, aligned pulleys, static frame and supports, and a clear side view of the full transmission path.',
          lockViewer: true,
        },
        {
          id: 'belt_contact_focus',
          label: 'Contact poulies',
          description: 'Insiste sur l enroulement de la courroie et les zones de contact utiles.',
          promptDirective: 'Emphasize belt wrap angle, contact zones on each pulley, and a fixed frame while keeping the entire belt path visible and under plausible tension.',
          lockViewer: true,
        },
        {
          id: 'belt_input_output',
          label: 'Entrée / sortie',
          description: 'Rend lisible la poulie motrice, la poulie menée et leurs supports.',
          promptDirective: 'Show the driving pulley, driven pulley, full belt loop and static supports together in one readable motion-study view.',
          lockViewer: true,
        },
      ]
    case 'gear_train':
      return [
        {
          id: 'gear_mesh_readable',
          label: 'Train d engrenages',
          description: 'Montre l engrenement complet avec axes et bati fixes.',
          promptDirective: 'Show a readable gear-train study with meshing gears, clear axle alignment, static housing, and no drifting or soft deformation.',
          lockViewer: true,
        },
        {
          id: 'gear_input_output',
          label: 'Entrée / sortie',
          description: 'Insiste sur l engrenage d entrée, la sortie et le chemin de transmission.',
          promptDirective: 'Emphasize input gear, output gear, and the full transmission order while keeping the housing and bearing supports fixed.',
          lockViewer: true,
        },
      ]
    case 'cylinder_actuator':
      return [
        {
          id: 'actuator_extend',
          label: 'Extension',
          description: 'Le corps du verin reste fixe, la tige est l element mobile principal.',
          promptDirective: 'Show an actuator extension study with a fixed cylinder body, clear rod travel along one axis, readable mounts, and no motion on the static frame.',
          lockViewer: true,
        },
        {
          id: 'actuator_retract',
          label: 'Retraction',
          description: 'Rend lisible la position rentrée et les points de fixation.',
          promptDirective: 'Show an actuator retraction study with the cylinder body anchored, the rod retracted on-axis, and all mounting points clearly visible.',
          lockViewer: true,
        },
        {
          id: 'actuator_midstroke',
          label: 'Course moyenne',
          description: 'Montre une position intermediaire qui aide a comprendre la course.',
          promptDirective: 'Show a mid-stroke actuator study with the body fixed, the rod at an intermediate extension, and the stroke direction immediately readable.',
          lockViewer: true,
        },
      ]
    case 'hinge_joint':
      return [
        {
          id: 'hinge_open',
          label: 'Ouverture',
          description: 'Met l accent sur l axe de charniere et la piece mobile.',
          promptDirective: 'Show an open hinge study with a clear hinge axis, fixed bracket, moving leaf, and a locked view that explains the opening motion.',
          lockViewer: true,
        },
        {
          id: 'hinge_half_open',
          label: 'Mi-ouverture',
          description: 'Position intermediaire pour bien lire l articulation.',
          promptDirective: 'Show a half-open hinge study with pivot center, fixed support, and moving member clearly separated in one stable view.',
          lockViewer: true,
        },
      ]
    case 'linkage':
      return [
        {
          id: 'linkage_extended',
          label: 'Configuration ouverte',
          description: 'Montre la chaine d articulation dans une position etendue.',
          promptDirective: 'Show an extended linkage study with all links, pivots, grounded frame and moving chain visible in one coherent locked view.',
          lockViewer: true,
        },
        {
          id: 'linkage_midcycle',
          label: 'Position intermediaire',
          description: 'Position utile pour comprendre les pivots et les courses.',
          promptDirective: 'Show a mid-cycle linkage study with pivot order, grounded frame and moving links clearly separated.',
          lockViewer: true,
        },
      ]
    case 'cable_routing':
      return [
        {
          id: 'cable_routing_clean',
          label: 'Routage propre',
          description: 'Montre le cheminement du cable, les points d ancrage et la courbure.',
          promptDirective: 'Show a cable-routing study with connector endpoints, anchors, service loops, realistic bend radius and a stable inspection view.',
          lockViewer: true,
        },
        {
          id: 'cable_connectors',
          label: 'Connecteurs visibles',
          description: 'Insiste sur les terminaisons et les interfaces de connexion.',
          promptDirective: 'Emphasize connector endpoints, cable terminations, routing anchors and branch points while keeping the route continuous and plausible.',
          lockViewer: true,
        },
      ]
    case 'pc_cabling':
      return referenceFraming === 'host_context'
        ? [
          {
            id: 'pc_routing',
            label: 'Cablage PC',
            description: 'Montre la carte mere, les connecteurs et le passage des faisceaux.',
            promptDirective: 'Show a PC cabling study with motherboard, GPU or PSU connectors, clear cable paths, service loops, and tidy routing through the chassis.',
            lockViewer: true,
          },
          {
            id: 'pc_connectors',
            label: 'Ports et prises',
            description: 'Insiste sur les connecteurs principaux et leur raccordement coherent.',
            promptDirective: 'Emphasize motherboard, PSU and GPU connector endpoints with coherent cable routing, plausible bend radius and visible anchor points.',
            lockViewer: true,
          },
        ]
        : [
          {
            id: 'pc_product_isolated',
            label: 'Produit isole',
            description: 'Montre uniquement le cable ou l extension, sans boitier complet autour.',
            promptDirective: 'Show the standalone cable product only, isolated on a clean studio background, with both connector ends, cable combs, sleeves or light guides clearly readable.',
            lockViewer: true,
          },
          {
            id: 'pc_led_guides',
            label: 'Guides LED',
            description: 'Insiste sur les light guides, la diffusion lumineuse et leur alignement.',
            promptDirective: 'Emphasize LED light guides, comb spacing, diffusion quality and connector orientation while keeping the cable product isolated and free of any PC case.',
            lockViewer: true,
          },
          {
            id: 'pc_connector_closeup',
            label: 'Connecteurs',
            description: 'Rend lisibles les prises et leur orientation exacte.',
            promptDirective: 'Emphasize connector housings, pin-side orientation, strain relief and cable exit direction while keeping the standalone cable accessory isolated.',
            lockViewer: true,
          },
        ]
    case 'electrical_harness':
      return [
        {
          id: 'harness_layout',
          label: 'Faisceau organise',
          description: 'Rend lisible le tronc principal, les branches et les clips.',
          promptDirective: 'Show an electrical harness study with main bundle, branches, connectors, clips and termination points clearly organized in one stable view.',
          lockViewer: true,
        },
        {
          id: 'harness_endpoints',
          label: 'Branches et terminaisons',
          description: 'Insiste sur les sorties et terminaisons du faisceau.',
          promptDirective: 'Emphasize harness branch points, connector endpoints, anchors and routing order while keeping the bundle structure coherent.',
          lockViewer: true,
        },
      ]
    default:
      break
  }

  if (purpose === 'character' || subjectKind === 'character' || subjectKind === 'creature') {
    return [
      {
        id: 'character_idle',
        label: 'Pose neutre',
        description: 'Pose propre pour inspecter le personnage sans rotation automatique.',
        promptDirective: 'Show the character in a neutral readable pose with stable anatomy, clear limb separation and a locked inspection view.',
        lockViewer: true,
      },
      {
        id: 'character_walk',
        label: 'Marcher',
        description: 'Cycle de marche realiste avec transfert de poids et opposition bras-jambes.',
        promptDirective: 'Show the character mid-stride in a believable walk cycle: heel strike forward foot, push-off rear foot, opposite arm swung forward, hips shifted toward the planted leg, head leveled, balanced weight transfer following human biomechanics.',
        lockViewer: true,
      },
      {
        id: 'character_run',
        label: 'Courir',
        description: 'Foulee dynamique avec phase de suspension et inclinaison du buste.',
        promptDirective: 'Show the character in a believable running pose: airborne suspension phase, knees high, arms bent at ~90 degrees driving forward and back, torso leaning ~10 degrees forward, opposite arm-leg synchronization respected.',
        lockViewer: true,
      },
      {
        id: 'character_applaud',
        label: 'Applaudir',
        description: 'Met l accent sur les bras, les mains et la lecture du geste.',
        promptDirective: 'Show the character in a clear applauding pose with readable hand contact, expressive upper-body posture, and stable anatomy.',
        lockViewer: true,
      },
      {
        id: 'character_wave',
        label: 'Saluer',
        description: 'Pose simple et claire pour les bras et les mains.',
        promptDirective: 'Show the character in a clear waving pose with one arm raised, readable hand silhouette and stable stance.',
        lockViewer: true,
      },
      {
        id: 'character_jump',
        label: 'Saut (lois physiques)',
        description: 'Saut respectant la trajectoire parabolique et la flexion preparatoire.',
        promptDirective: 'Show the character at the apex of a believable jump: arms reaching upward, knees tucked, torso slightly tilted, gravity-respecting parabolic trajectory implied — clearly mid-air with feet off the ground at the highest point.',
        lockViewer: true,
      },
      {
        id: 'character_fall',
        label: 'Chute libre',
        description: 'Chute libre realiste avec position naturelle de gravite.',
        promptDirective: 'Show the character mid-fall under gravity: limbs slightly trailing upward due to relative motion, torso forward-tilted, arms naturally splayed for balance, body oriented head-up, expression coherent with the fall.',
        lockViewer: true,
      },
      {
        id: 'character_pendulum',
        label: 'Balancement',
        description: 'Pendule corporel: rotation autour d un axe avec amplitude et bras tendus.',
        promptDirective: 'Show the character mid-swing on an implicit pendulum motion: body rotated ~30 degrees from vertical, arms or legs extended outward following angular momentum, hair and loose clothing trailing in the opposite direction of motion.',
        lockViewer: true,
      },
      {
        id: 'character_throw',
        label: 'Lancer parabolique',
        description: 'Lancer avec recul, propulsion et suivi balistique.',
        promptDirective: 'Show the character executing a throwing motion: rear leg planted, hips rotated, throwing arm extended forward at shoulder height, off-arm counter-balanced backward, follow-through visible, torso aligned with the parabolic launch direction.',
        lockViewer: true,
      },
      {
        id: 'character_landing',
        label: 'Atterrissage',
        description: 'Reception d un saut avec absorption d energie.',
        promptDirective: 'Show the character landing from a jump: knees deeply bent absorbing impact, torso forward-leaning, arms swung forward for balance, weight centered low, feet planted with shock-absorption stance.',
        lockViewer: true,
      },
    ]
  }

  if (representationGoal === 'kinematic_readability' || motionReadiness === 'articulated') {
    return [
      {
        id: 'mechanical_motion_readable',
        label: 'Etude mouvement',
        description: 'Force une vue stable pour lire les parties mobiles et fixes.',
        promptDirective: 'Show a motion-study view with moving subassemblies and fixed supports clearly separated, all functional relationships readable and the camera locked to the most informative angle.',
        lockViewer: true,
      },
      {
        id: 'mechanical_fixed_vs_moving',
        label: 'Fixe / mobile',
        description: 'Insiste sur ce qui reste fixe et ce qui se deplace.',
        promptDirective: 'Emphasize the distinction between static frame or housing and the moving chain, with no drift on anchored supports.',
        lockViewer: true,
      },
    ]
  }

  if (representationGoal === 'routing_readability') {
    return [
      {
        id: 'routing_inspection',
        label: 'Inspection routage',
        description: 'Vue verrouillee pour suivre le cheminement complet.',
        promptDirective: 'Show a locked routing-inspection view with endpoints, anchors, branches and the full route readable end to end.',
        lockViewer: true,
      },
    ]
  }

  return []
}

/**
 * Pipeline router: decides the best 3D pipeline based on intent, input count, and constraints.
 * Based on the multi-pipeline architecture from the deep research report:
 * - >= 30 multi-angle photos of a real object => photogrammetry
 * - 1-4 images and simple object => ai_generation or hybrid
 * - mechanism / pulley / belt / cable with kinematics => procedural
 * - character / creature / stylized => ai_generation (DreamGaussian preferred for EU compliance)
 */
function routePipeline(
  prompt: string,
  purpose: ThreeDPurpose,
  subjectKind: ThreeDSubjectKind,
  systemClass: ThreeDSystemClass,
  motionReadiness: MotionReadiness,
  representationGoal: ThreeDRepresentationGoal,
  files: PreparedContextFile[],
): ThreeDPipelineRouting {
  const imageCount = files.filter((f) => f.kind === 'image').length
  const normalized = prompt.toLowerCase()
  const justifications: ThreeDPipelineJustification[] = []
  const validationChecks: string[] = ['non_manifold_edges', 'degenerate_faces', 'open_boundaries']
  const postProcessing: string[] = []

  // ── PHOTOGRAMMETRY: many multi-angle photos of a real object ──
  const hasPhotogrammetrySignal = /\b(photogramm|scan|reconstru|multi[\s-]?vues? reelle|real[\s-]?photos?|photos? reelle|capture 3d)\b/i.test(normalized)
  if (imageCount >= 8 || (imageCount >= 4 && hasPhotogrammetrySignal)) {
    justifications.push(
      { point: `${imageCount} images de reference fournies`, risk: 'low', mitigation: 'Pipeline photogrammetrie active' },
      { point: 'Fidelite geometrique maximale via reconstruction MVS', risk: 'medium', mitigation: 'Meshroom + nettoyage Blender + CloudCompare si reference' },
    )
    validationChecks.push('geometric_fidelity', 'texture_coherence', 'scale_sanity')
    postProcessing.push('blender_retopo', 'uv_repack', 'texture_bake')
    return {
      pipeline: 'photogrammetry',
      justifications,
      fallbackPipeline: 'ai_generation',
      blenderRequired: true,
      meshoomRequired: true,
      dreamgaussianPreferred: false,
      proceduralTemplate: null,
      validationChecks,
      postProcessing,
    }
  }

  // ── PROCEDURAL: mechanisms, kinematics, cables with correct physics ──
  const isKinematic = systemClass === 'belt_drive' || systemClass === 'gear_train'
    || systemClass === 'cylinder_actuator' || systemClass === 'hinge_joint' || systemClass === 'linkage'
  const hasCinematicSignal = /\b(cinematique|kinematic|ratio|vitesse|rpm|couple|torque|course|stroke|driver|driven|transmission)\b/i.test(normalized)
  const wantsProceduralCable = (systemClass === 'pc_cabling' || systemClass === 'cable_routing' || systemClass === 'electrical_harness')
    && /\b(bundle|faisceau|routage exact|exact routing|strimer|cable management|geometry nodes)\b/i.test(normalized)
  const requiresHumanFidelity = requiresHumanFidelityPrompt(prompt, purpose, subjectKind)
  const requiresHandFidelity = (purpose === 'character' || subjectKind === 'character')
    && (hasHandFidelitySignal(prompt) || hasDanceOrGestureSignal(prompt))

  if (isKinematic && (hasCinematicSignal || motionReadiness === 'articulated')) {
    const template = systemClass === 'belt_drive' ? 'pulley_belt_system'
      : systemClass === 'gear_train' ? 'gear_train_system'
      : systemClass === 'cylinder_actuator' ? 'cylinder_actuator_system'
      : systemClass === 'hinge_joint' ? 'hinge_joint_system'
      : systemClass === 'linkage' ? 'linkage_system'
      : null

    justifications.push(
      { point: `Systeme mecanique ${systemClass} avec cinematique`, risk: 'low', mitigation: 'Modelisation procedurale Blender avec drivers et contraintes' },
      { point: 'Les ratios cinematiques sont mathematiquement exacts', risk: 'low', mitigation: 'Formules standards (n2 = d1*n1/d2 pour courroies)' },
    )
    validationChecks.push('kinematic_ratio', 'joint_continuity', 'assembly_coherence')
    postProcessing.push('blender_drivers', 'animation_keyframes', 'export_glb_animated')
    return {
      pipeline: 'procedural',
      justifications,
      fallbackPipeline: 'ai_generation',
      blenderRequired: true,
      meshoomRequired: false,
      dreamgaussianPreferred: false,
      proceduralTemplate: template,
      validationChecks,
      postProcessing,
    }
  }

  if (wantsProceduralCable) {
    const isStrimerPlusV2 = /\b(strimer(?:\s+plus)?(?:\s*v2)?|lian\s+li\s+strimer)\b/i.test(normalized)
    const cableTemplate = isStrimerPlusV2 ? 'strimer_plus_v2_cable' : 'cable_bundle_system'
    justifications.push(
      isStrimerPlusV2
        ? { point: 'Lian Li Strimer Plus V2 detecte', risk: 'low', mitigation: 'Template procedural dedie: 12 light guides, connecteurs noirs, clips, nappe plate et animation ARGB par canaux' }
        : { point: 'Cable/faisceau avec routage exact demande', risk: 'low', mitigation: 'Modelisation procedurale Blender avec curves et Geometry Nodes' },
    )
    validationChecks.push(
      ...(isStrimerPlusV2
        ? ['strimer_light_guides', 'strimer_connectors', 'strimer_clips', 'runtime_led_channels']
        : ['routing_continuity', 'connector_count', 'bend_radius']),
    )
    postProcessing.push(
      ...(isStrimerPlusV2
        ? ['blender_strimer_v2_reference', 'emissive_channel_materials', 'export_glb']
        : ['blender_geometry_nodes', 'emissive_materials', 'export_glb']),
    )
    return {
      pipeline: 'procedural',
      justifications,
      fallbackPipeline: 'ai_generation',
      blenderRequired: true,
      meshoomRequired: false,
      dreamgaussianPreferred: false,
      proceduralTemplate: cableTemplate,
      validationChecks,
      postProcessing,
    }
  }

  if (systemClass === 'led_strip') {
    justifications.push(
      { point: 'Bandeau LED RGB addressable', risk: 'low', mitigation: 'Modelisation procedurale: domes LED individuels + lumieres punctuelles + animation pulse/chase' },
      { point: 'Couleurs configurables par l utilisateur', risk: 'low', mitigation: 'Palette override propagee via parametres colors et env AURORA_COLORS' },
    )
    validationChecks.push('led_count', 'emission_range', 'light_count')
    postProcessing.push('blender_led_pattern', 'emissive_materials', 'export_glb_animated')
    return {
      pipeline: 'procedural',
      justifications,
      fallbackPipeline: 'ai_generation',
      blenderRequired: true,
      meshoomRequired: false,
      dreamgaussianPreferred: false,
      proceduralTemplate: 'led_strip_system',
      validationChecks,
      postProcessing,
    }
  }

  // iter25: motherboards / brand SKUs → procedural motherboard_layout.
  // Single-image AI reconstruction on motherboards consistently produces
  // "mixed up" meshes even with FLUX prompt enrichment, because the model
  // can't keep 100+ components in correct topology. Procedural template gives a clean
  // recognisable PCB + components layout (AM5 socket, DIMMs, M.2, OLED face,
  // ROG RGB) and crucially keeps the OLED screen as a SEPARATE face plane
  // with aurora.oled-atlas.v1 extras so it animates as a real screen at
  // draw-time, not a baked image of a screen.
  const wantsProceduralMobo =
    /\b(x870e|x670e|x670|b850|b650|z890|z790|z690|rog\s+strix|rog\s+crosshair|rog\s+maximus|rog\s+(?:c|h)ero|tuf\s+gaming|prime\s+(?:x|z|b)\d|msi\s+(?:meg|mpg|mag)|gigabyte\s+aorus|asrock\s+(?:taichi|phantom)|motherboard|carte\s+m[èe]re|mainboard|pcb\s+motherboard)\b/i
      .test(normalized)
  if (wantsProceduralMobo) {
    justifications.push(
      { point: 'Carte mère brandée (X870E/ROG/etc) — fidélité layout', risk: 'low', mitigation: 'Template procedural blender: PCB + AM5 + DIMMs + M.2 + OLED face séparée' },
      { point: 'OLED LiveDash anime au runtime (aurora.oled-atlas.v1)', risk: 'low', mitigation: 'Face plane distinct + extras schema + reader ModelView/aurora_3d_viewer' },
    )
    validationChecks.push('component_count', 'oled_face_present', 'pcb_white_color')
    postProcessing.push('blender_motherboard_layout', 'oled_atlas_overlay', 'export_glb_draco')
    return {
      pipeline: 'procedural',
      justifications,
      fallbackPipeline: 'ai_generation',
      blenderRequired: true,
      meshoomRequired: false,
      dreamgaussianPreferred: false,
      proceduralTemplate: 'motherboard_layout',
      validationChecks,
      postProcessing,
    }
  }

  // ── HYBRID: mechanism + AI texture, or procedural skeleton + AI detail ──
  const wantsHistoricalPublicFigure =
    (purpose === 'character' || subjectKind === 'character')
    && /\b(abraham\s+lincoln|lincoln)\b/i.test(prompt)
  if (wantsHistoricalPublicFigure) {
    justifications.push(
      { point: 'Personnage historique public-domain reconnu', risk: 'low', mitigation: 'Template procedural dedie avec visage long, barbe chin-curtain, costume et animation articulee' },
      { point: 'Evite le mode image->IA qui peut produire une plaque plate ou un crash GPU sur reference unique', risk: 'low', mitigation: 'Generation Blender locale legere + gate final texture/mouvement/fidelite humaine' },
    )
    validationChecks.push('historical_identity_cues', 'human_face_detail', 'separate_fingers', 'non_root_limb_animation')
    postProcessing.push('blender_historical_person_performer', 'export_glb_animated')
    return {
      pipeline: 'procedural',
      justifications,
      fallbackPipeline: 'ai_generation',
      blenderRequired: true,
      meshoomRequired: false,
      dreamgaussianPreferred: false,
      proceduralTemplate: 'historical_person_performer',
      validationChecks,
      postProcessing,
    }
  }

  const wantsProceduralHumanoidPerformer =
    imageCount === 0
    && (purpose === 'character' || subjectKind === 'character')
    && isOriginalGenericCharacterPrompt(prompt)
    && !requiresHumanFidelity
    && hasDanceOrGestureSignal(prompt)
  if (wantsProceduralHumanoidPerformer) {
    justifications.push(
      { point: 'Personnage avec mouvement corporel complexe sans reference fournie', risk: 'medium', mitigation: 'Fallback procedural humanoide colore avec membres separes, materiaux distincts et animation de danse multi-membres' },
      { point: 'Evite les sorties blanches/statiques quand le service IA local est indisponible', risk: 'low', mitigation: 'GLB Blender anime, testable par captures et gate mouvement' },
    )
    validationChecks.push('character_material_zones', 'limb_separation', 'non_root_limb_animation', 'texture_presence')
    postProcessing.push('blender_humanoid_performer', 'macarena_action_test', 'export_glb_animated')
    return {
      pipeline: 'procedural',
      justifications,
      fallbackPipeline: 'ai_generation',
      blenderRequired: true,
      meshoomRequired: false,
      dreamgaussianPreferred: false,
      proceduralTemplate: 'humanoid_performer',
      validationChecks,
      postProcessing,
    }
  }

  if (isKinematic && !hasCinematicSignal && purpose === 'visual_preview') {
    justifications.push(
      { point: 'Systeme mecanique en mode apercu visuel', risk: 'medium', mitigation: 'Squelette procedural + texture IA pour rendu final' },
    )
    validationChecks.push('assembly_coherence', 'texture_coherence')
    postProcessing.push('blender_procedural_base', 'ai_texture_pass')
    return {
      pipeline: 'hybrid',
      justifications,
      fallbackPipeline: 'ai_generation',
      blenderRequired: true,
      meshoomRequired: false,
      dreamgaussianPreferred: false,
      proceduralTemplate: systemClass === 'belt_drive' ? 'pulley_belt_system' : null,
      validationChecks,
      postProcessing,
    }
  }

  // ── AI GENERATION: default for characters, creatures, products, visual previews ──
  // TRELLIS.2 est toujours tente en premier (aurora_3d_pipeline). dreamgaussianPreferred
  // decide seulement si DreamGaussian (MIT, EU-safe) est tente en secours quand TRELLIS.2
  // echoue et que trellisOnly est desactive — sinon aucun second moteur n'est tente.
  const isStylized = hasPositiveStylizedSignal(prompt)
  // Stylized material descriptors (Cat 1 PC boitier "quartz fumé / lotus or rose / obsidienne / acajou nordique"
  // and similar luxury treatments) benefit from DreamGaussian's silhouette retention on
  // architectural / hard-edge surfaces with rich material storytelling.
  const hasLuxuryMaterials = /\b(quartz fum[eé]|fum[eé] translucide|obsidienne|obsidian|acajou nordique|mahogany|or rose|rose gold|nacre|mother of pearl|onyx|jade noir|marbre|marble|opalescent|dichro[iï]que|dichroic|liquid metal|chrome bross[eé]|brushed chrome)\b/i.test(normalized)
  const dreamgaussianPreferred = isStylized
    || hasLuxuryMaterials
    || requiresHumanFidelity
    || purpose === 'character' || subjectKind === 'character' || subjectKind === 'creature'
    || purpose === 'game_asset'

  justifications.push(
    { point: `Generation IA (TRELLIS.2${dreamgaussianPreferred ? ', secours DreamGaussian MIT si echec' : ''})`, risk: 'low', mitigation: 'Licence MIT compatible UE' },
  )

  if (purpose === 'character' || subjectKind === 'character' || subjectKind === 'creature') {
    validationChecks.push(
      'anatomy_coherence',
      'limb_separation',
      'face_readability',
      ...(requiresHumanFidelity ? ['human_identity_fidelity', 'pbr_skin_hair_clothing_textures'] : []),
      ...(requiresHandFidelity ? ['separate_fingers_or_palm_geometry', 'hand_motion_readability'] : []),
    )
    postProcessing.push(
      'blender_rigify_autorig',
      'weight_paint_check',
      'action_test',
      ...(requiresHumanFidelity ? ['multiview_human_reference_audit'] : []),
    )
  } else if (purpose === 'product' || subjectKind === 'product') {
    validationChecks.push('surface_quality', 'proportions', 'material_readability')
  } else if (purpose === 'printable_prototype') {
    validationChecks.push('watertight', 'wall_thickness', 'overhang_angle')
    postProcessing.push('blender_3d_print_check', 'manifold_repair')
  }

  postProcessing.push('clip_similarity_check')

  return {
    pipeline: 'ai_generation',
    justifications,
    fallbackPipeline: dreamgaussianPreferred ? 'ai_generation' : null,
    blenderRequired: purpose === 'character' || purpose === 'printable_prototype' || motionReadiness === 'rig_candidate',
    meshoomRequired: false,
    dreamgaussianPreferred,
    proceduralTemplate: null,
    validationChecks,
    postProcessing,
  }
}

function buildFallbackIntent(prompt: string, files: PreparedContextFile[]): ThreeDIntent {
  const purpose = detectPurpose(prompt)
  const subjectKind = detectSubjectKind(prompt)
  const systemClass = detectSystemClass(prompt)
  const motionReadiness = detectMotionReadiness(prompt, purpose, subjectKind, systemClass)
  const representationGoal = detectRepresentationGoal(systemClass, motionReadiness)
  const referenceFraming = detectReferenceFraming(prompt, purpose, subjectKind, systemClass)
  const partFocus = buildPartFocus(systemClass, subjectKind, motionReadiness, referenceFraming)
  const hasImageReference = files.some((file) => file.kind === 'image')
  const hasTechnicalContext = files.some((file) => file.kind !== 'image')
  const requiresDimensionalPrecision = purpose === 'printable_prototype' || purpose === 'mechanical_part'
  const wantsNeutralPose = purpose === 'character' || purpose === 'body_part' || purpose === 'printable_prototype' || motionReadiness === 'rig_candidate'
  // characters / creatures / body_parts also want bilateral symmetry by
  // default — single-image reconstruction drifts subtly off-axis otherwise.
  // Opt out via "asymmetric" / "asymetrique" / "lopsided" in the prompt.
  const explicitlyAsymmetric = /\b(asym[eé]trique|asymmetric|asymmetrical|lopsided|uneven|biased to one side)\b/i.test(prompt)
  const wantsSymmetry = !explicitlyAsymmetric && (
    /\b(symetrique|symmetry|symmetrical)\b/i.test(prompt)
    || purpose === 'mechanical_part'
    || purpose === 'printable_prototype'
    || purpose === 'character'
    || purpose === 'body_part'
    || subjectKind === 'character'
    || subjectKind === 'creature'
    || subjectKind === 'body_part'
  )
  const needsResearch = systemClass !== 'generic'
    || hasKnownCharacterSignal(prompt)
    || /\b(real|existing|reference|exact|inspire de|inspired by|marque|brand|engine|moteur|bearing|roulement|hinge|charniere|anatomy|anatomie|datasheet|connector|connecteur|motherboard|carte mere|anime|manga|personnage|character|product|produit|modele)\b/i.test(prompt)
  // v77zg: targeted clarification beats the legacy "missing dimension"
  // single-case prompt — we now ask the right question per ambiguity kind
  // (real-person reproduction, character anatomy, mechanism motion type,
  // vehicle wheels-vs-static, multi-material object, dimension precision).
  const motionVerbHint = detectMotionVerbHint(prompt)
  const targetedClarification = detectThreeDClarification({
    prompt,
    purpose,
    subjectKind,
    systemClass,
    motionReadiness,
    motionVerbHint,
    hasImageReference,
    hasDimensionalSignal: hasDimensionalSignal(prompt),
    hasMaterialHint: hasTechnicalContext,
  })
  const missingPrecisionContext = requiresDimensionalPrecision && !needsResearch && !hasDimensionalSignal(prompt) && !hasImageReference && !hasTechnicalContext
  let clarificationQuestion = targetedClarification?.question
    ?? (missingPrecisionContext
      ? 'Si tu vises une piece mecanique ou imprimable fidele, ajoute dimensions, vues orthographiques ou contraintes d assemblage. Sans reponse, je genererai un prototype visuel propre mais non dimensionnel.'
      : null)

  const productDescriptions = detectKnownProductDescription(prompt, systemClass)
  const pipelineRouting = routePipeline(prompt, purpose, subjectKind, systemClass, motionReadiness, representationGoal, files)

  return {
    purpose,
    subjectKind,
    systemClass,
    representationGoal,
    referenceFraming,
    motionReadiness,
    pipelineRouting,
    requiresDimensionalPrecision,
    wantsNeutralPose,
    wantsSymmetry,
    needsResearch,
    ...(hasImageReference && clarificationQuestion && /photo|image|r[ée]f[ée]rence|source/i.test(clarificationQuestion)
      ? (clarificationQuestion = null, {})
      : {}),
    needsClarification: Boolean(clarificationQuestion),
    clarificationQuestion,
    clarificationCategory: targetedClarification?.category ?? (missingPrecisionContext ? 'dimensional_precision' : null),
    clarificationOptions: targetedClarification?.options ?? [],
    referencePromptAdditions: uniqueStrings([
      ...buildReferencePromptAdditions(referenceFraming, purpose, subjectKind, motionReadiness, systemClass, representationGoal),
      ...buildCharacterIdentityPromptAdditions(prompt, purpose, subjectKind),
      ...productDescriptions,
    ]),
    meshConstraints: buildMeshConstraints(purpose, subjectKind, motionReadiness, systemClass, representationGoal),
    motionGuidance: buildMotionGuidance(motionReadiness, purpose, subjectKind, systemClass, referenceFraming),
    motionRisks: buildMotionRisks(motionReadiness, purpose, subjectKind, systemClass),
    movingPartsFocus: partFocus.movingPartsFocus,
    anchoredPartsFocus: partFocus.anchoredPartsFocus,
    researchQueries: buildResearchQueries(prompt, systemClass, referenceFraming),
    motionPresets: buildMotionPresets(referenceFraming, purpose, subjectKind, systemClass, representationGoal, motionReadiness),
    summary: `${purpose} / ${subjectKind} / ${systemClass} / ${representationGoal} / ${referenceFraming} / ${motionReadiness} / pipeline:${pipelineRouting.pipeline}`,
  }
}

export function previewThreeDIntent(prompt: string, files: PreparedContextFile[] = []) {
  return buildFallbackIntent(prompt, files)
}

/**
 * Build a FLUX-native visual description for the 3D subject.
 * This bypasses the generic distillation LLM and produces a prompt
 * specifically optimized for diffusion models: comma-separated visual tags,
 * concrete material/shape/color terms, and explicit negative guidance.
 *
 * This runs AFTER intent analysis and uses the intent + product knowledge
 * to produce a faithful visual description that FLUX can actually render.
 */
// v77zl: humanoid anatomy directive block lives in ./humanoidAnatomy.ts
// (no Tauri / React deps) so node --test can exercise it directly.
// Re-exported here for callers that already import from threeDIntent.
export { buildHumanoidAnatomyBlock }

// v77zm: re-export kinematics surface so callers can drive Blender-side
// animation baking without importing the library twice.
export {
  buildKinematicsDirectiveBlock,
  parseCustomMotionPrompt,
  selectKinematicPresets,
  listAllPresetIds as listAllKinematicPresetIds,
} from './kinematicsLibrary.ts'
export type { MotionDescriptor as KinematicMotionDescriptor } from './kinematicsLibrary.ts'

/**
 * v77zm: maps ThreeDIntent's wider subjectKind / systemClass enums onto the
 * narrower KinematicQuery types and emits the FLUX kinematic-contract block.
 *
 * Custom motion (parsed from the user prompt) wins over preset suggestions —
 * if the user types "fait une roue arriere puis salue", we emit the parsed
 * sequence directly so the reference image is shaped around it.
 */
function buildKinematicsBlockForIntent(intent: ThreeDIntent, prompt: string): string {
  const subjectMap: Partial<Record<ThreeDSubjectKind, KinematicSubjectKind>> = {
    character: 'character',
    creature: 'creature',
    body_part: 'body_part',
    vehicle: 'vehicle',
    mechanical_part: 'mechanism',
    assembly: 'assembly',
    object: 'object',
    // product / architecture / tool / electrical_system → no kinematics block
  }
  const systemMap: Record<ThreeDSystemClass, KinematicSystemClass> = {
    generic: 'generic',
    belt_drive: 'belt_drive',
    gear_train: 'gear_train',
    cylinder_actuator: 'cylinder_actuator',
    hinge_joint: 'hinge_joint',
    linkage: 'linkage',
    cable_routing: 'cable_routing',
    pc_cabling: 'pc_cabling',
    electrical_harness: 'electrical_harness',
    led_strip: 'led_strip',
  }
  const mappedSubject = subjectMap[intent.subjectKind]
  const mappedSystem = systemMap[intent.systemClass] ?? 'generic'
  if (!mappedSubject && mappedSystem === 'generic') return ''

  const customMotion = parseCustomMotionPrompt(prompt)
  return buildKinematicsDirectiveBlock(
    { subjectKind: mappedSubject ?? 'object', systemClass: mappedSystem },
    customMotion,
  )
}

export async function buildFluxVisualDescription({
  prompt,
  intent,
  model,
  motionPreset,
  researchContext = '',
  previousHumanoidMetrics = null,
}: {
  prompt: string
  intent: ThreeDIntent
  model: string
  motionPreset?: ThreeDMotionPreset | null
  researchContext?: string
  /**
   * v77zl: when buildFluxVisualDescription is called as part of an auto-
   * correction pass, the previous attempt's humanoid proportion metrics
   * are forwarded here so the next reference image is generated with
   * explicit corrections baked in (not just appended after the fact).
   */
  previousHumanoidMetrics?: HumanoidProportionMetrics | null
}): Promise<string> {
  // Gather all product/subject identity knowledge
  const identityLines = intent.referencePromptAdditions.filter((line) =>
    /^(THIS IS NOT|Visual description:|DO NOT generate|Generate ONLY|The .+ is a|.+ variant:)/i.test(line),
  )
  const visualDescriptionLines = intent.referencePromptAdditions.filter((line) =>
    /^Visual description:/i.test(line),
  )

  // If we have explicit visual descriptions from product knowledge, use them as the core
  const productKnowledge = identityLines.length > 0
    ? `\n\nKNOWN PRODUCT/SUBJECT IDENTITY (MUST BE THE BASIS OF YOUR DESCRIPTION):\n${identityLines.join('\n')}`
    : ''

  const motionDirective = motionPreset
    ? `\n\nMANDATORY POSE/MOTION STATE: ${motionPreset.promptDirective}`
    : ''

  const researchSnippet = researchContext
    ? `\n\nResearch context (use for visual accuracy):\n${researchContext.slice(0, 800)}`
    : ''

  const systemClassHints: Record<ThreeDSystemClass, string> = {
    generic: '',
    belt_drive: 'mechanical belt-drive system with pulleys, taut belt loop, shafts and mounting frame',
    gear_train: 'gear train with meshing toothed gears on shafts, visible tooth profiles and housing',
    cylinder_actuator: 'hydraulic/pneumatic cylinder actuator with barrel, piston rod, mounting points and port fittings',
    hinge_joint: 'mechanical hinge with pivot pin, two leaves/plates, visible rotation axis',
    linkage: 'mechanical linkage with rigid bars connected by pivot joints',
    cable_routing: 'cable assembly with connector endpoints, routing anchors, organized bundle',
    pc_cabling: 'PC cable/extension product, connector interfaces, cable organization',
    electrical_harness: 'electrical wire harness with branches, connectors, clips and termination points',
    led_strip: 'addressable LED strip with evenly-spaced emitters, diffuser housing and visible wiring',
  }

  const subjectKindHints: Record<ThreeDSubjectKind, string> = {
    object: 'standalone object',
    mechanical_part: 'mechanical part with precise hard surfaces',
    assembly: 'mechanical assembly with multiple connected components',
    character: 'full-body character with clear anatomy, costume and silhouette',
    creature: 'creature with distinct body form and features',
    body_part: 'anatomical body part with accurate proportions',
    product: 'consumer product with brand-accurate appearance',
    vehicle: 'vehicle with accurate proportions and details',
    architecture: 'architectural structure with accurate geometry',
    tool: 'tool with functional details and handle',
    electrical_system: 'electrical system with connectors, cables and routing',
  }

  const systemHint = systemClassHints[intent.systemClass] || ''
  const kindHint = subjectKindHints[intent.subjectKind] || ''

  const fluxPromptRequest = `/no_think
You are a FLUX diffusion model prompt engineer. Your job is to convert a user's 3D modeling request into a precise, FLUX-optimized visual description.

CRITICAL RULES:
- Output ONLY the visual description, nothing else, no explanations, no markdown
- English only, maximum 120 words
- Use comma-separated descriptive phrases (FLUX prompt style), NOT sentences or paragraphs
- Describe the EXACT PHYSICAL APPEARANCE of the subject: shape, materials, colors, textures, proportions, distinctive features
- If product identity knowledge is provided below, that is the ABSOLUTE TRUTH about what this product looks like — use it as your primary source
- NEVER substitute with a different product, component, or object. If the user asks for a cable, describe a CABLE, not a case
- NEVER describe a generic version — describe the SPECIFIC product/character/object named
- Include: solid black studio background, single isolated subject, THREE-QUARTER front view (not flat front-on), clean edge separation
- CRITICAL FOR 3D RECONSTRUCTION: the image MUST show DEPTH and VOLUME — show the object at a slight angle so 3 faces are visible (front + one side + top or bottom)
- NEVER generate a flat front-on view — TRELLIS.2 needs depth cues to reconstruct proper 3D geometry
- The object MUST look like a real physical 3D product photograph, not a flat icon or diagram
- Ensure strong lighting contrast to reveal surface depth, edges, bevels, recesses, and protruding features
- Do NOT use primitive block-in shapes, cubes, spheres, cylinders or toy placeholders unless the user explicitly asked for a primitive. The reference must contain the real silhouette and real part structure of the requested subject.
- Texture is part of fidelity: show material grain, fabric weave, brushed metal, glass transparency, skin pores, rubber, wood grain, emission or paint finish when relevant. Avoid flat single-color surfaces and avoid a 2D image pasted onto a simple block.
- For characters: describe PRECISE hairstyle shape, detailed costume geometry, EXACT body proportions (slim/muscular/etc), face features (eye shape, nose, jawline), accessories. Preserve the requested/official gender and body type; NEVER gender-swap a named character. Face, hair and costume details must be sharp, not blurry, blobby or single-color. Characters MUST look PHOTOREALISTIC unless anime is explicitly requested — sharp edges on clothing folds, visible fabric texture, realistic hair strands NOT blobby masses, correct finger separation, clear facial geometry. NEVER produce a blobby/cartoony/marshmallow character.
- For products: describe exact shape, connector types, materials, size proportions, surface finish, ALL fine details (USB ports, buttons, screws, ventilation holes, fan grilles, mesh patterns)
- For PC cases: MUST include tempered glass panel, mesh front pattern, USB/audio ports on top I/O panel, PCIe slots at rear, PSU shroud, rubber feet, power button, fan positions, cable routing holes
- For mechanical parts: describe geometry, moving vs fixed parts, materials, surface qualities
- For motion/pose requests: describe EXACTLY which body parts are mobilized and HOW — if "running" then one leg forward bent at knee, other leg back pushing off, arms in opposite swing, torso leaning forward. If "punching" then one fist extended, shoulder rotated, hips turned. Show ANATOMICALLY CORRECT joint articulation.
- COLOR & PBR (Meshy-grade output): use VIVID SATURATED PBR-ready base colors with strong albedo contrast — clean vibrant materials, deep blacks, bright highlights, NO washed-out greys, NO muddy mids. The downstream texture-paint pass needs maximum color information to bake rich PBR maps. Mention specific material qualities (matte plastic, polished metal, brushed aluminum, glossy paint, soft fabric) so the texture pipeline produces correct metalness/roughness. For mechanical parts: clean primary colors on housings, contrasting accent colors on moving parts so motion is readable. For real-world objects in motion: describe the moving subassemblies with distinctive colors that contrast with the static frame.
- CRITICAL: Generate a PHOTOREALISTIC product photograph style by default. Only use cartoon/stylized if the user EXPLICITLY requests anime, cartoon, or stylized. When the user says "realistic" or provides a real photo reference, the output MUST look like a real photograph, not AI-generated or illustrated.
${motionPreset ? `- The subject MUST be in this exact pose/state: ${motionPreset.promptDirective}` : ''}

Subject type: ${kindHint}
${systemHint ? `System class: ${systemHint}` : ''}
Purpose: ${intent.purpose}
Framing: ${intent.referenceFraming}
${productKnowledge}${motionDirective}${researchSnippet}${buildHumanoidAnatomyBlock(intent, prompt, previousHumanoidMetrics)}
${buildQuadrupedAnatomyBlock(intent, prompt)}
${buildVehicleAnatomyBlock(intent, prompt)}
${buildKinematicsBlockForIntent(intent, prompt)}
${buildCompoundSceneContract(prompt, motionPreset?.promptDirective ?? '', { isolated: intent.subjectKind === 'character' || intent.subjectKind === 'creature' })}

User request: ${prompt}

FLUX visual description:`

  // v77zaj: hard timeout on the FLUX prompt builder. Same rationale as
  // v77zai on analyzeThreeDIntent — Ollama can sit on a request for
  // minutes producing zero tokens. Without a timeout, this blocks the
  // shape stage from ever being reached.
  const FLUX_PROMPT_TIMEOUT_MS = 20_000
  const fluxAbort = new AbortController()
  const fluxTimeout = setTimeout(() => fluxAbort.abort(), FLUX_PROMPT_TIMEOUT_MS)

  try {
    const response = await ollamaGenerate(model, fluxPromptRequest, { signal: fluxAbort.signal, num_predict: 350, num_ctx: 4096 })
    clearTimeout(fluxTimeout)
    const text = (response?.response || '').trim()
    const cleaned = text.replace(/<think>[\s\S]*?<\/think>/g, '').replace(/<think>[\s\S]*$/g, '').trim()
    if (cleaned.length > 15) {
      // Ensure product identity is present even if LLM ignored it
      let result = cleaned
      if (visualDescriptionLines.length > 0 && !result.toLowerCase().includes('light-guide') && !result.toLowerCase().includes('light guide') && intent.systemClass === 'pc_cabling') {
        // LLM failed to include the visual description — prepend it
        const visualCore = visualDescriptionLines[0].replace(/^Visual description:\s*/i, '').trim()
        result = `${visualCore}, ${result}`
      }
      return result
    }
  } catch (err) {
    clearTimeout(fluxTimeout)
    if (err instanceof Error && (err.name === 'AbortError' || /aborted|timeout/i.test(err.message))) {
      console.warn('[buildFluxVisualDescription] Ollama timeout (>60s), using manual fallback')
    }
    // Fall through to manual construction
  }

  // Fallback: build the prompt manually from product knowledge + intent
  return buildManualFluxDescription(prompt, intent, motionPreset)
}

/**
 * Manual FLUX prompt construction when the LLM fails.
 * Uses product knowledge, intent, and structural terms to build a
 * comma-separated visual description directly.
 */
function buildManualFluxDescription(
  prompt: string,
  intent: ThreeDIntent,
  motionPreset?: ThreeDMotionPreset | null,
): string {
  const parts: string[] = []

  // Extract visual description from product knowledge
  const visualLines = intent.referencePromptAdditions
    .filter((line) => /^Visual description:/i.test(line))
    .map((line) => line.replace(/^Visual description:\s*/i, '').trim())

  if (visualLines.length > 0) {
    parts.push(...visualLines)
  } else {
    // Use the raw prompt as the core description
    parts.push(prompt.split('\n')[0].trim())
  }

  // Add intent-derived terms
  if (intent.subjectKind === 'character' || intent.subjectKind === 'creature') {
    parts.push('full body visible', 'clear silhouette', 'readable face and costume details')
  } else if (intent.systemClass === 'pc_cabling') {
    parts.push('isolated cable product', 'visible connectors', 'no PC case or tower')
  } else if (intent.subjectKind === 'mechanical_part' || intent.subjectKind === 'assembly') {
    parts.push('precise hard surfaces', 'readable part separation', 'mechanically plausible geometry')
  } else if (intent.subjectKind === 'product') {
    parts.push('product photography style', 'accurate proportions', 'clean surface finish')
  }

  // Motion preset
  if (motionPreset) {
    parts.push(motionPreset.promptDirective)
  }

  // Standard 3D reference framing — optimized for 3D reconstruction
  parts.push(
    'solid black studio background',
    'single isolated subject centered in frame',
    'three-quarter angle product photograph showing front side and top visible with depth',
    'strong directional studio lighting revealing edges bevels recesses and surface details',
    'clean edge separation',
    'high detail realistic proportions',
  )

  // Anti-confusion terms
  const forbiddenLines = intent.referencePromptAdditions
    .filter((line) => /^DO NOT generate/i.test(line))
    .map((line) => line.replace(/^DO NOT generate\s*/i, 'no ').trim())

  if (forbiddenLines.length > 0) {
    parts.push(...forbiddenLines.slice(0, 3))
  }

  // Compound-scene contract also applies to the manual fallback so a complex
  // request stays faithful even when the LLM prompt-builder is unavailable.
  const compoundContract = buildCompoundSceneContract(prompt, motionPreset?.promptDirective ?? '', {
    isolated: intent.subjectKind === 'character' || intent.subjectKind === 'creature',
  })
  return parts.join(', ') + compoundContract
}

export async function analyzeThreeDIntent({
  prompt,
  model,
  files,
  conversationHistory = [],
}: {
  prompt: string
  model: string
  files: PreparedContextFile[]
  conversationHistory?: HistoryTurn[]
}) {
  const fallback = buildFallbackIntent(prompt, files)
  const documentContext = summarizePreparedContext(files)
  const historyContext = conversationHistory
    .slice(-4)
    .map((turn) => `${turn.role.toUpperCase()}: ${turn.content}`)
    .join('\n')

  // v77zai: hard timeout on the intent classification call. Without it,
  // a hung Ollama (slow first-token, model swap, GPU contention) blocks
  // the whole generation forever — user sees the overlay's red "stuck"
  // warning but the bake never starts. Fallback heuristic is always
  // available so we lose nothing by abandoning the LLM call after 90s.
  const INTENT_TIMEOUT_MS = 20_000
  const abortController = new AbortController()
  const timeoutId = setTimeout(() => abortController.abort(), INTENT_TIMEOUT_MS)

  try {
    const response = await ollamaChat(model, [
      {
        role: 'system',
        content: [
          '/no_think',
          'You classify 3D generation requests for AuroraIA.',
          'Return only valid JSON with this exact shape:',
          '{"purpose":"visual_preview|printable_prototype|mechanical_part|character|body_part|product|game_asset","subjectKind":"object|mechanical_part|assembly|character|creature|body_part|product|vehicle|architecture|tool|electrical_system","systemClass":"generic|belt_drive|gear_train|cylinder_actuator|hinge_joint|linkage|cable_routing|pc_cabling|electrical_harness","representationGoal":"static_shape|kinematic_readability|routing_readability|rig_readability","referenceFraming":"isolated_subject|host_context|scene_context","motionReadiness":"static_only|poseable|articulated|rig_candidate","requiresDimensionalPrecision":false,"wantsNeutralPose":false,"wantsSymmetry":false,"needsResearch":false,"needsClarification":false,"clarificationQuestion":null,"referencePromptAdditions":["..."],"meshConstraints":["..."],"motionGuidance":["..."],"motionRisks":["..."],"movingPartsFocus":["..."],"anchoredPartsFocus":["..."],"researchQueries":["..."],"summary":"..."}',
          'Interpret the real production goal, not just style words.',
          'clarificationQuestion, when set, MUST be written in FRENCH (the user is French-speaking).',
          files.some((f) => f.kind === 'image')
            ? 'THE USER HAS ATTACHED A REFERENCE IMAGE. Never ask for a source image, a photo, or what the subject looks like — read it from the image. Set needsClarification=false unless something is truly absent from BOTH the prompt and the image.'
            : '',
          "If the prompt references a NAMED move/dance/trend (e.g. \"fait le X\"), do NOT ask what it means — the pipeline researches named moves itself; set needsClarification=false for that reason.",
          'Never ask about gender when the French article already gives it (\"un guerrier\" = masculine, \"une guerriere\" = feminine).',
          'If the user wants 3D print, mechanics, CAD-like part or assembly fidelity, requiresDimensionalPrecision=true.',
          'If the user wants a character or figurine, prefer neutral full-body readable pose.',
          'If the user wants a body part or anatomy, isolate the anatomical subject and preserve coherence.',
          'Recognize concrete system families when possible: belt or pulley systems, gear trains, cylinder actuators, hinges, linkages, cable routing, PC cabling, or electrical harnesses.',
          'If the request is a mechanism, movingPartsFocus must list the moving chain and anchoredPartsFocus must list the fixed supports or mounts.',
          'If the request is wiring or cable routing, treat it as routing_readability rather than fake motion, and highlight connectors, anchors and bend-radius-sensitive zones.',
          'Use referenceFraming=isolated_subject when the user wants a standalone product, cable, character or component. Use host_context only when the prompt explicitly asks for the object installed inside or attached to another device. Use scene_context only when the surrounding scene is intentionally part of the request.',
          'If the user wants rigging or animation, use motionReadiness=rig_candidate only for characters or creatures. For hard-surface mechanisms, use articulated. For ordinary products, use static_only unless explicit joints exist.',
          'If motion would be misleading or physically implausible, say so via motionRisks and keep motionReadiness conservative.',
          'If the request appears to target an existing object, product, known character or reference subject, prefer needsResearch=true so Aurora can search visual references and dimensions before building the 3D reference image.',
          'If dimensions, tolerances or orthographic views are likely needed and missing, set needsClarification=true with one precise question. The question must allow continuing with a visual prototype if unanswered.',
          'Do not invent impossible guarantees. If no dimensions are given, do not pretend the output is manufacturing-accurate.',
        ].join('\n'),
      },
      {
        role: 'user',
        content: [
          `Prompt:\n${prompt}`,
          historyContext ? `Conversation context:\n${historyContext}` : '',
          documentContext ? `Attached context:\n${documentContext}` : '',
        ].filter(Boolean).join('\n\n'),
      },
    ], 0.05, { signal: abortController.signal, num_predict: 512, num_ctx: 4096 })
    clearTimeout(timeoutId)

    const parsed = parseIntentJson(response?.message?.content || '')
    if (!parsed) {
      return fallback
    }

    const resolvedPurpose = parsed.purpose || fallback.purpose
    const resolvedSubjectKind = parsed.subjectKind || fallback.subjectKind
    const resolvedSystemClass = parsed.systemClass || fallback.systemClass
    const resolvedMotionReadiness = parsed.motionReadiness || fallback.motionReadiness
    const resolvedRepresentationGoal = parsed.representationGoal || fallback.representationGoal
    const resolvedPipelineRouting = routePipeline(prompt, resolvedPurpose, resolvedSubjectKind, resolvedSystemClass, resolvedMotionReadiness, resolvedRepresentationGoal, files)

    return {
      purpose: resolvedPurpose,
      subjectKind: resolvedSubjectKind,
      systemClass: resolvedSystemClass,
      representationGoal: resolvedRepresentationGoal,
      referenceFraming: parsed.referenceFraming || fallback.referenceFraming,
      motionReadiness: resolvedMotionReadiness,
      pipelineRouting: resolvedPipelineRouting,
      requiresDimensionalPrecision: parsed.requiresDimensionalPrecision ?? fallback.requiresDimensionalPrecision,
      wantsNeutralPose: parsed.wantsNeutralPose ?? fallback.wantsNeutralPose,
      wantsSymmetry: parsed.wantsSymmetry ?? fallback.wantsSymmetry,
      needsResearch: parsed.needsResearch ?? fallback.needsResearch,
      needsClarification: parsed.needsClarification ?? fallback.needsClarification,
      clarificationQuestion: (parsed.needsClarification ?? fallback.needsClarification)
        ? parsed.clarificationQuestion || fallback.clarificationQuestion
        : null,
      // v77zg: keep the targeted question metadata from the fallback so the
      // UI always has a categorised question + actionable button options,
      // even when the LLM only returned the free-text question.
      clarificationCategory: fallback.clarificationCategory,
      clarificationOptions: fallback.clarificationOptions,
      referencePromptAdditions: uniqueStrings([
        ...(parsed.referencePromptAdditions || []),
        ...fallback.referencePromptAdditions,
        ...buildCharacterIdentityPromptAdditions(prompt, resolvedPurpose, resolvedSubjectKind),
        ...detectKnownProductDescription(prompt, resolvedSystemClass),
      ]),
      meshConstraints: uniqueStrings([...(parsed.meshConstraints || []), ...fallback.meshConstraints]),
      motionGuidance: uniqueStrings([...(parsed.motionGuidance || []), ...fallback.motionGuidance]),
      motionRisks: uniqueStrings([...(parsed.motionRisks || []), ...fallback.motionRisks]),
      movingPartsFocus: uniqueStrings([...(parsed.movingPartsFocus || []), ...fallback.movingPartsFocus]),
      anchoredPartsFocus: uniqueStrings([...(parsed.anchoredPartsFocus || []), ...fallback.anchoredPartsFocus]),
      researchQueries: uniqueStrings([...(parsed.researchQueries || []), ...fallback.researchQueries]),
      motionPresets: buildMotionPresets(
        parsed.referenceFraming || fallback.referenceFraming,
        resolvedPurpose,
        resolvedSubjectKind,
        resolvedSystemClass,
        resolvedRepresentationGoal,
        resolvedMotionReadiness,
      ),
      summary: parsed.summary?.trim() || `${resolvedPurpose} / ${resolvedSubjectKind} / ${resolvedSystemClass} / ${resolvedRepresentationGoal} / ${parsed.referenceFraming || fallback.referenceFraming} / ${resolvedMotionReadiness} / pipeline:${resolvedPipelineRouting.pipeline}`,
    } satisfies ThreeDIntent
  } catch (err) {
    clearTimeout(timeoutId)
    // v77zai: timeout / network / Ollama crash → safe fallback heuristic.
    // The fallback never blocks the pipeline so the user gets a generation
    // even when the LLM is stuck. We tag the summary so it's visible the
    // intent came from the heuristic path, not the model.
    if (err instanceof Error && (err.name === 'AbortError' || /aborted|timeout/i.test(err.message))) {
      console.warn('[analyzeThreeDIntent] Ollama timeout (>90s), using fallback heuristic')
      return { ...fallback, summary: `[fallback heuristic, Ollama timeout] ${fallback.summary}` }
    }
    return fallback
  }
}

export type MeshFidelityVerification = {
  score: number
  passed: boolean
  missingDetails: string[]
  artifacts: string[]
  suggestions: string[]
  notes: string
  failureCategory: 'none' | 'wrong_subject' | 'missing_details' | 'geometry_artifacts' | 'proportion_error' | 'surface_quality'
}

export type MeshCorrectionStrategy = {
  shouldContinue: boolean
  shouldRetryReference: boolean
  shouldRetryMesh: boolean
  referenceCorrections: string[]
  meshCorrections: string[]
  corrections: string[]
  escalation: 'moderate' | 'strong' | 'maximum'
  attemptNumber: number
  previousScore: number
}

/**
 * Build a targeted correction strategy from mesh fidelity verification results.
 * This drives the auto-correction loop: each retry gets a progressively stronger prompt.
 */
/**
 * Humanoid proportion metrics (aspect ratio, head/body fractions) that let the
 * correction strategy issue targeted "make the body taller, the head smaller,
 * the hips wider" prompts instead of the generic "fix proportions" fallback.
 * Type lives in ./humanoidAnatomy.ts (pure module) so node --test can exercise
 * consumers. Currently unpopulated: no Python stage emits these fields since
 * the mesh-proportion validator was removed with hunyuan3d_run.py; the
 * correction strategy falls back to its generic path until a mesh-geometry
 * script (independent of which generator produced the GLB) computes them.
 */
export type { HumanoidProportionMetrics } from './humanoidAnatomy.ts'

export function buildMeshCorrectionStrategy({
  fidelity,
  intent,
  prompt,
  attemptNumber,
  meshQualityIssues,
  meshQualityWarnings,
  meshGeometryGrade,
  humanoidMetrics,
}: {
  fidelity: MeshFidelityVerification
  intent: ThreeDIntent
  prompt: string
  attemptNumber: number
  meshQualityIssues?: string[]
  /** v77zk: Python-emitted warnings (including humanoid proportion warnings). */
  meshQualityWarnings?: string[]
  meshGeometryGrade?: string
  /** v77zk: structured humanoid proportion metrics (character / body_part only). */
  humanoidMetrics?: HumanoidProportionMetrics | null
}): MeshCorrectionStrategy {
  const corrections: string[] = []
  let shouldRetryReference = false
  let shouldRetryMesh = false
  let referenceCorrections: string[] = []
  const meshCorrections: string[] = []

  // ── Analyze why the mesh is bad ──

  // Category 1: Wrong subject entirely
  const wrongSubject = fidelity.score < 30 || fidelity.notes.toLowerCase().includes('wrong')
  if (wrongSubject) {
    shouldRetryReference = true
    referenceCorrections = [
      `CRITICAL: The previous generation produced THE WRONG SUBJECT.`,
      `The user asked for: ${prompt.split('\n')[0]}`,
      `Regenerate EXACTLY the correct subject. Do not substitute with a similar product.`,
      ...intent.referencePromptAdditions
        .filter((l) => /^(THIS IS NOT|Visual description:|DO NOT generate)/i.test(l))
        .map((l) => `MANDATORY: ${l}`),
    ]
    corrections.push('wrong_subject_correction')
  }

  // Category 2: Missing fine details
  if (fidelity.missingDetails.length > 0) {
    const detailsList = fidelity.missingDetails.slice(0, 6)
    shouldRetryReference = shouldRetryReference || fidelity.missingDetails.length >= 3
    shouldRetryMesh = true
    referenceCorrections.push(
      `The reference image MUST prominently show these details: ${detailsList.join(', ')}`,
      `Increase lighting contrast to reveal fine surface features, holes, ports, and connectors`,
    )
    meshCorrections.push(
      `The 3D mesh is missing these details: ${detailsList.join(', ')}`,
      `Use higher octree resolution and more inference steps to capture fine geometry`,
    )
    corrections.push('missing_details_correction')
  }

  // Category 3: Geometry artifacts
  if (fidelity.artifacts.length > 0) {
    shouldRetryMesh = true
    for (const artifact of fidelity.artifacts.slice(0, 4)) {
      const lower = artifact.toLowerCase()
      if (lower.includes('melt') || lower.includes('blob')) {
        meshCorrections.push('Avoid melted/blobby surfaces: use cleaner reference with harder edges')
        shouldRetryReference = true
        referenceCorrections.push('Make edges SHARP and CRISP, avoid soft organic blending on hard surfaces')
      }
      if (lower.includes('merge') || lower.includes('fused')) {
        meshCorrections.push('Separate distinct components: connectors, panels, ports must be individually distinct')
        shouldRetryReference = true
        referenceCorrections.push('Each component must have clear SEPARATION and visible GAP between parts')
      }
      if (lower.includes('float') || lower.includes('disconnect')) {
        meshCorrections.push('Ensure all geometry is connected: no floating or disconnected fragments')
      }
      if (lower.includes('distort') || lower.includes('proportion')) {
        meshCorrections.push('Fix proportions: the dimensions must match the real product')
        shouldRetryReference = true
        referenceCorrections.push('Show ACCURATE proportions that match the real product dimensions')
      }
    }
    corrections.push('artifact_correction')
  }

  // Category 4: Python-level quality issues
  if (meshQualityIssues && meshQualityIssues.length > 0) {
    shouldRetryMesh = true
    for (const issue of meshQualityIssues) {
      if (issue.includes('plat') || issue.includes('flat')) {
        shouldRetryReference = true
        referenceCorrections.push(
          'The reference MUST show the subject at a STRONG THREE-QUARTER ANGLE with visible depth',
          'Include visible DEPTH CUES: shadows under overhangs, visible side surfaces, top surface',
        )
        meshCorrections.push('Previous mesh was flat (bas-relief). Use --dimensional-precision')
      }
      if (issue.includes('degenere') || issue.includes('degenerate')) {
        meshCorrections.push('Previous mesh had too few faces. Increase octree resolution')
      }
      if (issue.includes('NaN') || issue.includes('corrompue')) {
        meshCorrections.push('Previous mesh had corrupted geometry. Retry with stability_fallback strategy')
      }
    }
    corrections.push('geometry_quality_correction')
  }

  // v77zk Category 5: humanoid proportion failure (character / body_part).
  // The Python validator (v77zj) emits structured metrics + warnings; we use
  // them to push specific anatomical guidance into the next reference + mesh
  // generation instead of the generic "fix proportions" line that was
  // unactionable. Only applies when the subject is character/body_part —
  // products with low aspect ratio (e.g. a flat keyboard) shouldn't be
  // told to "stand taller".
  const isHumanoidSubject = (
    intent.purpose === 'character'
    || intent.purpose === 'body_part'
    || intent.subjectKind === 'character'
    || intent.subjectKind === 'creature'
    || intent.subjectKind === 'body_part'
  )
  if (isHumanoidSubject && humanoidMetrics) {
    const aspect = humanoidMetrics.aspectRatio ?? null
    const headFraction = humanoidMetrics.headVertexFraction ?? null
    const headWidth = humanoidMetrics.headBodyWidthRatio ?? null

    if (aspect !== null && aspect < 1.4) {
      shouldRetryReference = true
      shouldRetryMesh = true
      referenceCorrections.push(
        `CRITICAL HUMANOID PROPORTIONS: previous mesh height/width ratio was ${aspect.toFixed(2)} — too cubical/blobby for a standing human. Make the reference image show the subject FULL-BODY STANDING UPRIGHT, vertical framing, head at top, feet at bottom, ratio at least 3:1 vertical-to-horizontal.`,
      )
      meshCorrections.push(
        'Previous humanoid was too cubical (height:width < 1.4). Generate a tall standing silhouette next pass.',
      )
      corrections.push('humanoid_blob_correction')
    } else if (aspect !== null && aspect < 1.8) {
      referenceCorrections.push(
        `HUMANOID PROPORTIONS: previous mesh height/width ratio was ${aspect.toFixed(2)} — chibi/squat. If realistic adult was requested, make the reference taller (3:1 vertical) with longer legs.`,
      )
      meshCorrections.push('Previous humanoid was squat (height:width < 1.8). Push toward 3:1 adult proportions.')
      corrections.push('humanoid_squat_correction')
    }

    if (headFraction !== null && headFraction > 0.45) {
      shouldRetryReference = true
      referenceCorrections.push(
        `CRITICAL: previous mesh had ${(headFraction * 100).toFixed(0)}% of vertices in the head zone (top 1/8) — head dominated the silhouette. Reference image MUST show the head occupying ~12% of total vertical extent for a realistic adult. Show the entire body, not a head close-up.`,
      )
      meshCorrections.push('Previous head was dominant — regenerate with full-body framing, head ~1/8 of total height.')
      corrections.push('humanoid_head_dominant_correction')
    } else if (headFraction !== null && headFraction > 0.30 && /\b(realiste|realistic|adult|adulte)\b/i.test(prompt)) {
      referenceCorrections.push(
        `HUMANOID HEAD: previous mesh had ${(headFraction * 100).toFixed(0)}% in the head zone — chibi-style detected but the prompt asked for realistic. Push reference toward adult 1:7 head:body ratio.`,
      )
      corrections.push('humanoid_chibi_when_realistic_correction')
    }

    if (headWidth !== null && headWidth > 1.5) {
      shouldRetryReference = true
      shouldRetryMesh = true
      referenceCorrections.push(
        `CRITICAL: previous mesh had head ${headWidth.toFixed(2)}x wider than the legs/feet zone — proportions inverted. Make sure the reference shows hips/feet WIDER than the head, like a real human standing.`,
      )
      meshCorrections.push('Previous mesh had inverted head:body width. Hips/legs must be wider than the head next pass.')
      corrections.push('humanoid_inverted_correction')
    }
  }

  // v77zk: also surface non-humanoid Python warnings (the v77zj validator
  // emits them in the same warnings array).
  if (meshQualityWarnings && meshQualityWarnings.length > 0) {
    for (const warning of meshQualityWarnings) {
      const lower = warning.toLowerCase()
      if (lower.includes('blob') || lower.includes('trapue')) {
        shouldRetryReference = true
        referenceCorrections.push('Make the reference more vertically oriented — current output reads as a blob silhouette.')
      }
      if (lower.includes('chibi') && /\b(realiste|realistic|adult|adulte)\b/i.test(prompt)) {
        shouldRetryReference = true
        referenceCorrections.push('Prompt asked for realistic, but the mesh output was chibi — push reference toward adult proportions.')
      }
    }
  }

  // ── Strategy escalation based on attempt number ──
  const escalation = attemptNumber <= 1 ? 'moderate'
    : attemptNumber <= 3 ? 'strong'
    : 'maximum'

  if (escalation === 'strong') {
    referenceCorrections.push(
      'Use MAXIMUM detail in the reference: every port, every hole, every button must be individually visible',
      'Increase lighting from multiple angles to eliminate shadows that hide detail',
    )
    meshCorrections.push(
      'Use dimensional-precision mode with maximum octree resolution',
    )
  }

  if (escalation === 'maximum') {
    referenceCorrections.push(
      'Generate a HYPER-DETAILED technical illustration: every single surface feature must be rendered',
    )
    meshCorrections.push(
      'Use maximum_quality shape strategy with 70+ inference steps',
    )
  }

  // ── Decide continue vs stop ──
  // Target: 95% fidelity minimum. Only concede diminishing returns when the
  // geometry is genuinely excellent (grade A + score >= 90) so that a mesh
  // stuck at 75% never bails out just because the loop ran for a while.
  const shouldContinue = fidelity.score < 95 || !fidelity.passed
  const diminishingReturns = attemptNumber >= 5
    && meshGeometryGrade === 'A'
    && fidelity.score >= 90

  return {
    shouldContinue: shouldContinue && !diminishingReturns,
    shouldRetryReference,
    shouldRetryMesh: shouldRetryMesh || shouldRetryReference,
    referenceCorrections: uniqueStrings(referenceCorrections),
    meshCorrections: uniqueStrings(meshCorrections),
    corrections,
    escalation,
    attemptNumber,
    previousScore: fidelity.score,
  }
}

/**
 * Verify a generated 3D mesh screenshot against the original reference image.
 * Uses the vision model to compare the 3D output with the intent and detect:
 * - Missing fine details (USB ports, fans, mesh holes, screws, etc.)
 * - Geometry artifacts (melted surfaces, merged parts, floating geometry)
 * - Proportion mismatches
 * Returns a fidelity score and actionable correction suggestions.
 */
export async function verify3DMeshFidelity({
  meshScreenshotBase64,
  referenceImageBase64,
  prompt,
  intent,
  model,
}: {
  meshScreenshotBase64: string
  referenceImageBase64: string | null
  prompt: string
  intent: ThreeDIntent
  model: string
}): Promise<MeshFidelityVerification> {
  const productDetails = intent.referencePromptAdditions
    .filter((l) => /^(CRITICAL DETAILS|Visual description:|The .+ is a)/i.test(l))
    .slice(0, 4)
    .join('\n')

  const messages: Array<{ role: 'user' | 'system'; content: string; images?: string[] }> = [
    {
      role: 'system',
      content: `/no_think
You are a 3D mesh quality inspector for AuroraIA. You compare a generated 3D mesh (shown as a rendered screenshot) against the user's original request and optionally a reference image.

Return ONLY valid JSON with this exact shape:
{"score":0-100,"passed":true/false,"missingDetails":["..."],"artifacts":["..."],"suggestions":["..."],"notes":"one sentence summary","failureCategory":"none|wrong_subject|missing_details|geometry_artifacts|proportion_error|surface_quality"}

Scoring guidelines:
- 90-100: Excellent fidelity, all key details present, no artifacts
- 75-89: Good overall shape, minor details missing
- 60-74: Recognizable but significant details missing or artifacts present
- 40-59: Shape is roughly correct but many problems
- 0-39: Wrong object or completely broken

What to check:
- Overall shape matches the request (is it the right object?)
- Fine details: USB ports, fans, ventilation holes, screws, buttons, connectors, mesh patterns, panel textures, light guides, cable combs
- Proportions: correct relative sizes of components
- Artifacts: melted surfaces, merged parts, floating geometry, impossible topology
- Surface quality: clean edges vs. blobby/melted surfaces
- Structural coherence: parts that should be separate are separate, no merged geometry

failureCategory must be the PRIMARY reason for any score below 75:
- "wrong_subject": the mesh is a completely different object than requested
- "missing_details": the shape is correct but fine features are absent
- "geometry_artifacts": melted/merged/floating/distorted geometry
- "proportion_error": wrong relative sizes or aspect ratio
- "surface_quality": blobby or poorly defined surfaces
- "none": score >= 75 and no critical issues

passed=true if score >= 95 AND no critical missing features. The bar is VERY HIGH — only pass if the mesh is truly excellent.
Keep missingDetails to concrete physical features, not abstract concepts.
Keep artifacts to specific geometry problems observed.
Keep suggestions to actionable corrections for the NEXT regeneration attempt.`,
    },
    {
      role: 'user',
      content: [
        `Original request: ${prompt}`,
        `Subject type: ${intent.subjectKind}, purpose: ${intent.purpose}, system: ${intent.systemClass}`,
        productDetails ? `Expected details:\n${productDetails}` : '',
        referenceImageBase64 ? 'The first image is the reference (what it should look like). The second image is the generated 3D mesh.' : 'The image is the generated 3D mesh. Compare it against the description above.',
      ].filter(Boolean).join('\n'),
      images: referenceImageBase64
        ? [referenceImageBase64, meshScreenshotBase64]
        : [meshScreenshotBase64],
    },
  ]

  try {
    const response = await ollamaChat(model, messages)
    const text = (response?.message?.content || '').trim()
    const cleaned = text.replace(/<think>[\s\S]*?<\/think>/g, '').replace(/<think>[\s\S]*$/g, '').trim()
    const match = cleaned.match(/\{[\s\S]*\}/)
    if (match) {
      const parsed = JSON.parse(match[0]) as Partial<MeshFidelityVerification>
      return {
        score: parsed.score ?? 50,
        passed: parsed.passed ?? (parsed.score ?? 50) >= 95,
        missingDetails: parsed.missingDetails ?? [],
        artifacts: parsed.artifacts ?? [],
        suggestions: parsed.suggestions ?? [],
        notes: parsed.notes ?? '',
        failureCategory: parsed.failureCategory ?? 'none',
      }
    }
  } catch {
    // Verification non-critical — don't block the pipeline
  }

  return { score: 60, passed: false, missingDetails: [], artifacts: [], suggestions: ['Verification vision indisponible — re-essayer'], notes: 'Verification automatique indisponible.', failureCategory: 'none' }
}
