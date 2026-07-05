/**
 * v77zy — quadruped + vehicle anatomy directives (pure, dep-free).
 *
 * Parallels humanoidAnatomy.ts (v77zl): injects Meshy-grade proportion
 * priors into the FLUX reference prompt for non-humanoid subjects so the
 * Hunyuan3D shape pipeline downstream cannot recover from a blob/chibi
 * silhouette. Two builders:
 *
 *   - buildQuadrupedAnatomyBlock(intent, prompt): fires when subject is
 *     creature AND the prompt has 4-leg cues (chien/chat/cheval/quadruped/
 *     wolf/lion/horse/cow/etc.). Pushes body-length-to-shoulder-height
 *     ratio, 4-leg layout, tail proportions, head-as-fraction-of-body.
 *
 *   - buildVehicleAnatomyBlock(intent, prompt): fires when subject is
 *     vehicle. Pushes wheelbase / overall length, track / wheelbase,
 *     wheel diameter / vehicle height, no fish-eye distortion.
 *
 * Both blocks return '' for off-target subjects so they're safe to chain
 * unconditionally in buildFluxVisualDescription.
 *
 * Pure: no Tauri / React / fs deps. Tested via node --experimental-strip-types.
 */

export type SubjectAnatomyIntent = {
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
}

// ---------------------------------------------------------------------------
//  QUADRUPED
// ---------------------------------------------------------------------------

const QUADRUPED_HINT_RX = /\b(chien|dog|chat|cat|cheval|horse|vache|cow|bull|lion|tigre|tiger|loup|wolf|ours|bear|leopard|leopard|panthere|panther|zebre|zebra|girafe|giraffe|cerf|deer|elan|moose|antelope|gazelle|elephant|elephant|rhinoceros|rhino|hippopotame|hippo|kangourou|kangaroo|chevreuil|sanglier|boar|brebis|sheep|chevre|goat|porc|pig|bouc|ane|donkey|mule|lama|alpaca|chameau|camel|panda|gorille|gorilla|bovin|bovine|equin|equine|canide|canid|felide|felid|quadrupede|quadruped|four legged|four-legged|on all fours|a quatre pattes)\b/i

// v77zae: species-specific proportion ratios. Detection by keyword maps a
// quadruped prompt to its taxonomic profile so the FLUX directive lists
// the EXACT body / tail / head / snout ratios for that species, not the
// generic 1.3-1.7 range. Order matters — most specific first (tigre
// before generic feline).
type QuadrupedSpecies = {
  name: string
  rx: RegExp
  bodyToShoulder: [number, number]   // [min, target]
  tailToBody: [number, number]
  headToBody: [number, number]
  snoutLength: 'short' | 'medium' | 'long'
  earShape: string
  defaultPose: string
}

const SPECIES_PROFILES: QuadrupedSpecies[] = [
  {
    name: 'cat',
    rx: /\b(chat|cat|kitten|chaton|feline|felin|matou|chartreux|persian|siamese|tabby)\b/i,
    bodyToShoulder: [1.25, 1.35],
    tailToBody: [0.6, 0.75],
    headToBody: [0.16, 0.20],
    snoutLength: 'short',
    earShape: 'pointed triangular ears positioned on top of the head',
    defaultPose: 'crouched-ready stance with low center of gravity',
  },
  {
    name: 'dog',
    rx: /\b(chien|dog|puppy|chiot|labrador|husky|berger|shepherd|bulldog|beagle|golden|retriever|caniche|poodle|pitbull|rottweiler|boxer|terrier|spaniel|chihuahua)\b/i,
    bodyToShoulder: [1.40, 1.55],
    tailToBody: [0.20, 0.50],
    headToBody: [0.18, 0.22],
    snoutLength: 'medium',
    earShape: 'breed-specific ears (pricked or floppy) positioned on top of the head',
    defaultPose: 'standing alert with weight balanced on all four paws',
  },
  {
    name: 'horse',
    rx: /\b(cheval|horse|stallion|mare|jument|etalon|[eé]talon|cob|pony|poney|pur sang|thoroughbred|arabian|arabe|frison|friesian|percheron)\b/i,
    bodyToShoulder: [1.55, 1.70],
    tailToBody: [0.30, 0.45],
    headToBody: [0.16, 0.20],
    snoutLength: 'long',
    earShape: 'tall pointed ears that swivel — positioned high on the head',
    defaultPose: 'standing on all four hooves, head lifted forward',
  },
  {
    name: 'wolf',
    rx: /\b(loup|wolf|wolves|lupine|loup garou|werewolf)\b/i,
    bodyToShoulder: [1.40, 1.50],
    tailToBody: [0.40, 0.55],
    headToBody: [0.18, 0.22],
    snoutLength: 'long',
    earShape: 'pointed erect ears, alert and forward-facing',
    defaultPose: 'low predator stance with shoulders slightly higher than hips',
  },
  {
    name: 'lion',
    rx: /\b(lion|lionne|lioness|lions|king of beasts|fauve|big cat male)\b/i,
    bodyToShoulder: [1.35, 1.50],
    tailToBody: [0.55, 0.70],
    headToBody: [0.20, 0.25],
    snoutLength: 'short',
    earShape: 'small rounded ears partially hidden in mane (males) or visible (females)',
    defaultPose: 'powerful standing or sitting stance, head held proudly',
  },
  {
    name: 'tiger',
    rx: /\b(tigre|tigress|tiger|tigers|big cat|fauve raye|fauve ray[eé])\b/i,
    bodyToShoulder: [1.40, 1.55],
    tailToBody: [0.55, 0.70],
    headToBody: [0.18, 0.22],
    snoutLength: 'short',
    earShape: 'small rounded ears with white spot pattern on the back',
    defaultPose: 'low prowling stance, shoulders rolling with each step',
  },
  {
    name: 'bear',
    rx: /\b(ours|bear|grizzly|polar bear|brown bear|black bear|kodiak|panda)\b/i,
    bodyToShoulder: [1.20, 1.35],
    tailToBody: [0.05, 0.15],
    headToBody: [0.18, 0.22],
    snoutLength: 'medium',
    earShape: 'small rounded ears positioned on top of the broad head',
    defaultPose: 'four-legged broad stance with massive shoulders, may rear up',
  },
  {
    name: 'cow',
    rx: /\b(vache|cow|bull|taureau|cattle|bovin|bovine|veau|calf)\b/i,
    bodyToShoulder: [1.35, 1.50],
    tailToBody: [0.45, 0.60],
    headToBody: [0.18, 0.22],
    snoutLength: 'long',
    earShape: 'large floppy ears on the sides of the head',
    defaultPose: 'four-legged grazing stance, head naturally lowered',
  },
  {
    name: 'elephant',
    rx: /\b(elephant|[eé]l[eé]phant|elephants|pachyderm|mammoth|mammouth)\b/i,
    bodyToShoulder: [1.20, 1.40],
    tailToBody: [0.30, 0.40],
    headToBody: [0.25, 0.35],
    snoutLength: 'long',
    earShape: 'massive flapping ears (Asian smaller, African huge)',
    defaultPose: 'four-legged columnar stance, trunk relaxed forward or curled',
  },
]

function detectSpecies(prompt: string): QuadrupedSpecies | null {
  for (const sp of SPECIES_PROFILES) {
    if (sp.rx.test(prompt)) return sp
  }
  return null
}

export type QuadrupedProportionMetrics = {
  /** body_length / shoulder_height. Cat ~1.3, dog ~1.5, horse ~1.6, lion ~1.4. */
  bodyToShoulderRatio?: number | null
  /** tail_length / body_length. Cats ~0.7, dogs varies, horses ~0.4, no-tail ~0. */
  tailToBodyRatio?: number | null
  /** head_length / body_length. Adult predator ~0.20, prey grazer ~0.18. */
  headToBodyRatio?: number | null
  /** distinct legs visible: 4 expected; <4 means hidden/cropped. */
  legCountVisible?: number | null
}

export function buildQuadrupedAnatomyBlock(
  intent: SubjectAnatomyIntent,
  prompt: string,
  previousMetrics?: QuadrupedProportionMetrics | null,
): string {
  if (intent.subjectKind !== 'creature') return ''
  if (!QUADRUPED_HINT_RX.test(prompt)) return ''

  const realistic = /\b(realiste|realistic|photorealist)\b/i.test(prompt)
  const stylized = /\b(chibi|cartoon|cute|stylis[eé])\b/i.test(prompt)

  // v77zae: tighten ratios to species when one was detected.
  const species = detectSpecies(prompt)

  const baseLines: string[] = [
    'QUADRUPED ANATOMY DIRECTIVES (Meshy-grade requirement):',
    '- Full-body lateral framing: all 4 legs visible, head at one end, tail at the other, body horizontal — NO close-up of head/face only',
    species
      ? `- Species detected: ${species.name}. Body length / shoulder height ratio between ${species.bodyToShoulder[0]} and ${species.bodyToShoulder[1]}.`
      : '- Body length to shoulder height ratio between 1.3 (compact cat) and 1.7 (long horse): the subject is LONGER than tall',
    '- Four distinct legs in clear separation: 2 visible front legs (under the chest) AND 2 visible hind legs (under the hips), each with its own knee/hock',
    '- Bilateral symmetry: matched left/right pair on each leg, ears match, eyes match',
    species
      ? `- Head: ${species.earShape}. ${species.snoutLength === 'short' ? 'Short flat snout' : species.snoutLength === 'long' ? 'Long pronounced snout/muzzle' : 'Medium-length defined snout'}. Head occupies ${(species.headToBody[0] * 100).toFixed(0)}-${(species.headToBody[1] * 100).toFixed(0)}% of body length.`
      : '- Head proportions: snout/muzzle clearly defined, ears positioned on top of head, eyes facing forward (predator) or sides (prey) per species',
    species
      ? `- Tail: ${(species.tailToBody[0] * 100).toFixed(0)}-${(species.tailToBody[1] * 100).toFixed(0)}% of body length${species.name === 'bear' ? ' (very short)' : species.name === 'cat' ? ' (long expressive)' : ''}.`
      : '- Tail proportions: present unless species is tailless (Manx cat, bobtail dog) — typical tail is 30%-80% of body length depending on species',
    species
      ? `- Default pose: ${species.defaultPose} (unless an explicit motion verb appears).`
      : '- Stable standing pose by default (4 legs grounded) unless an explicit motion verb (galope/trotte/saute/rampe) appears in the user prompt',
  ]

  if (realistic && !stylized) {
    baseLines.push(
      '- Realistic mode: photorealistic fur texture, individual hairs visible at silhouette edge, anatomically correct musculature, paw pads / hooves visible per species, breed-accurate proportions',
      '- NO marshmallow body, NO oversized head — push toward real adult animal anatomy',
    )
  } else if (stylized) {
    baseLines.push(
      '- Stylised mode acknowledged: chibi/anime quadruped allowed but still respect bilateral symmetry, 4-leg visibility, full-body framing',
    )
  }

  if (previousMetrics) {
    const corrections: string[] = []
    const ratio = previousMetrics.bodyToShoulderRatio ?? null
    const tail = previousMetrics.tailToBodyRatio ?? null
    const head = previousMetrics.headToBodyRatio ?? null
    const legs = previousMetrics.legCountVisible ?? null
    if (ratio !== null && ratio < 1.0) {
      corrections.push(`PREVIOUS ATTEMPT FAILED: body was taller than long (ratio ${ratio.toFixed(2)}). This time the body MUST be horizontal — length>height, ratio≥1.3.`)
    }
    if (ratio !== null && ratio > 2.5) {
      corrections.push(`PREVIOUS ATTEMPT FAILED: body was unrealistically elongated (ratio ${ratio.toFixed(2)}). This time keep ratio ≤ 1.7 for natural quadruped proportions.`)
    }
    if (head !== null && head > 0.35) {
      corrections.push(`PREVIOUS ATTEMPT FAILED: head was oversized (${(head * 100).toFixed(0)}% of body). This time head must be ≤ 25% of body length.`)
    }
    if (tail !== null && tail > 1.0) {
      corrections.push(`PREVIOUS ATTEMPT FAILED: tail longer than body (${(tail * 100).toFixed(0)}%). Cap tail at ≤ 80% of body length.`)
    }
    if (legs !== null && legs < 4) {
      corrections.push(`PREVIOUS ATTEMPT FAILED: only ${legs} leg(s) visible. ALL 4 LEGS must be visible in the reference image.`)
    }
    if (corrections.length > 0) baseLines.push('', ...corrections)
  }

  return baseLines.join('\n')
}

// ---------------------------------------------------------------------------
//  VEHICLE
// ---------------------------------------------------------------------------

export type VehicleProportionMetrics = {
  /** wheelbase / overall_length. Typical car ~0.6, sports car ~0.55, truck ~0.4. */
  wheelbaseToLengthRatio?: number | null
  /** track / wheelbase. Typical car ~0.55. */
  trackToWheelbaseRatio?: number | null
  /** wheel_diameter / vehicle_height. Typical car ~0.35, off-road ~0.45. */
  wheelToHeightRatio?: number | null
  /** distinct wheels visible: 4 for car, 2 for bike, 6+ for truck. */
  wheelCountVisible?: number | null
}

// v77zae: vehicle class profiles with class-specific wheelbase / clearance / height ratios.
type VehicleClass = {
  name: string
  rx: RegExp
  expectedWheels: number
  wheelbaseToLength: [number, number]
  trackToWheelbase: [number, number]
  heightToLength: [number, number]
  groundClearance: 'very low' | 'low' | 'medium' | 'high' | 'very high'
}

const VEHICLE_CLASSES: VehicleClass[] = [
  {
    name: 'sports_car',
    rx: /\b(sports? car|supercar|hypercar|sportive|gt|racing car|formula|f1|formula 1|race car|ferrari|lamborghini|porsche|mclaren)\b/i,
    expectedWheels: 4,
    wheelbaseToLength: [0.55, 0.62],
    trackToWheelbase: [0.55, 0.65],
    heightToLength: [0.27, 0.32],
    groundClearance: 'very low',
  },
  {
    name: 'sedan',
    rx: /\b(sedan|berline|family car|saloon|four door|4-door)\b/i,
    expectedWheels: 4,
    wheelbaseToLength: [0.58, 0.65],
    trackToWheelbase: [0.55, 0.62],
    heightToLength: [0.30, 0.36],
    groundClearance: 'medium',
  },
  {
    name: 'suv',
    rx: /\b(suv|4x4|crossover|off road|off-road|jeep|land rover|range rover|tahoe)\b/i,
    expectedWheels: 4,
    wheelbaseToLength: [0.55, 0.62],
    trackToWheelbase: [0.58, 0.66],
    heightToLength: [0.42, 0.50],
    groundClearance: 'high',
  },
  {
    name: 'truck',
    rx: /\b(camion|truck|semi|tracteur|tractor|lorry|18-wheeler|cargo truck)\b/i,
    expectedWheels: 6,
    wheelbaseToLength: [0.40, 0.55],
    trackToWheelbase: [0.55, 0.62],
    heightToLength: [0.55, 0.70],
    groundClearance: 'very high',
  },
  {
    name: 'bus',
    rx: /\b(bus|coach|autobus|autocar|minibus)\b/i,
    expectedWheels: 6,
    wheelbaseToLength: [0.55, 0.65],
    trackToWheelbase: [0.50, 0.58],
    heightToLength: [0.50, 0.62],
    groundClearance: 'high',
  },
  {
    name: 'motorcycle',
    rx: /\b(moto|motorcycle|motorbike|sportbike|cruiser|chopper|harley|ducati|kawasaki|yamaha)\b/i,
    expectedWheels: 2,
    wheelbaseToLength: [0.62, 0.72],
    trackToWheelbase: [0.0, 0.0],
    heightToLength: [0.55, 0.75],
    groundClearance: 'medium',
  },
  {
    name: 'bicycle',
    rx: /\b(velo|bicycle|bike|cycle|mountain bike|road bike|vtt|bmx)\b/i,
    expectedWheels: 2,
    wheelbaseToLength: [0.62, 0.72],
    trackToWheelbase: [0.0, 0.0],
    heightToLength: [0.55, 0.70],
    groundClearance: 'low',
  },
  {
    name: 'scooter',
    rx: /\b(scooter|trottinette)\b/i,
    expectedWheels: 2,
    wheelbaseToLength: [0.55, 0.65],
    trackToWheelbase: [0.0, 0.0],
    heightToLength: [0.55, 0.75],
    groundClearance: 'medium',
  },
]

function detectVehicleClass(prompt: string): VehicleClass | null {
  for (const cls of VEHICLE_CLASSES) {
    if (cls.rx.test(prompt)) return cls
  }
  return null
}

export function buildVehicleAnatomyBlock(
  intent: SubjectAnatomyIntent,
  prompt: string,
  previousMetrics?: VehicleProportionMetrics | null,
): string {
  if (intent.subjectKind !== 'vehicle') return ''

  // v77zae: prefer class-specific profile, fall back to legacy isBike/isTruck classification.
  const cls = detectVehicleClass(prompt)
  const isBike = cls?.expectedWheels === 2
  const isTruck = cls?.name === 'truck' || /\b(camion|truck|semi|tracteur|tractor|bus|lorry|18-wheeler)\b/i.test(prompt)
  const expectedWheels = cls ? cls.expectedWheels : (isBike ? 2 : isTruck ? 6 : 4)

  const baseLines: string[] = [
    'VEHICLE ANATOMY DIRECTIVES (Meshy-grade requirement):',
    '- Full-body 3/4 view: front + side + top visible in same image so 3D reconstruction has depth cues, NOT a flat side profile or flat front',
    `- Exactly ${expectedWheels} wheel(s) visible in the reference image, each with hub+rim+tire clearly readable`,
    cls
      ? `- Class detected: ${cls.name}. Wheelbase ${cls.wheelbaseToLength[0]}-${cls.wheelbaseToLength[1]} of length, height ${cls.heightToLength[0]}-${cls.heightToLength[1]} of length, ${cls.groundClearance} ground clearance.`
      : '- Wheelbase (front axle to rear axle distance) between 0.55 and 0.65 of the overall vehicle length — wheels at the corners, not centered',
    cls && cls.expectedWheels >= 4
      ? `- Track (left wheel to right wheel) ${cls.trackToWheelbase[0]}-${cls.trackToWheelbase[1]} of wheelbase`
      : '- Track (left wheel to right wheel) approximately 0.55 of wheelbase — wheels NOT inboard, NOT exterior to body',
    '- Wheel diameter approximately 0.35 of vehicle height (0.45 for off-road / monster trucks)',
    '- Bilateral symmetry: left = right (mirror identical), front-end matches across the vertical centerline',
    '- Body proportions stable: roof line clearly distinct from belt line, wheel arches not deformed, hood/bonnet flat or gently curved (no fish-eye distortion)',
    '- Ground contact obvious: all wheels on the same flat surface, no floating wheel, no crooked stance',
  ]

  if (isBike) {
    baseLines.push(
      '- Two-wheeled mode: 1 front wheel + 1 rear wheel aligned on the same longitudinal axis, frame visible between them, handlebar clearly above front wheel',
    )
  }
  if (isTruck) {
    baseLines.push(
      '- Truck mode: distinct cab + cargo body, 6+ wheels (2 front + 4 rear typical), tall ride height, exhaust stack if heavy duty',
    )
  }

  if (previousMetrics) {
    const corrections: string[] = []
    const wb = previousMetrics.wheelbaseToLengthRatio ?? null
    const track = previousMetrics.trackToWheelbaseRatio ?? null
    const wheelH = previousMetrics.wheelToHeightRatio ?? null
    const wheels = previousMetrics.wheelCountVisible ?? null
    if (wb !== null && wb < 0.45) {
      corrections.push(`PREVIOUS ATTEMPT FAILED: wheels were too centered (wheelbase ${(wb * 100).toFixed(0)}% of length). This time push wheels to the corners — wheelbase ≥ 55%.`)
    }
    if (wb !== null && wb > 0.75) {
      corrections.push(`PREVIOUS ATTEMPT FAILED: wheels were too spread out (wheelbase ${(wb * 100).toFixed(0)}%). This time keep wheelbase ≤ 65% of length so the body has clear front and rear overhangs.`)
    }
    if (track !== null && track < 0.4) {
      corrections.push(`PREVIOUS ATTEMPT FAILED: wheels were too inboard (track ${(track * 100).toFixed(0)}% of wheelbase). This time match track ≈ 55% of wheelbase.`)
    }
    if (wheelH !== null && wheelH > 0.6) {
      corrections.push(`PREVIOUS ATTEMPT FAILED: wheels were oversized (${(wheelH * 100).toFixed(0)}% of vehicle height). Cap wheel diameter at ≤ 50% of height.`)
    }
    if (wheels !== null && wheels !== expectedWheels) {
      corrections.push(`PREVIOUS ATTEMPT FAILED: ${wheels} wheel(s) visible, expected ${expectedWheels}. ALL ${expectedWheels} wheels must be visible.`)
    }
    if (corrections.length > 0) baseLines.push('', ...corrections)
  }

  return baseLines.join('\n')
}
