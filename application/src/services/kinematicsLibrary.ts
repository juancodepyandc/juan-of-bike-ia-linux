/**
 * v77zm — kinematics library + custom motion parser (pure, dep-free).
 *
 * The 3D pipeline already detects subject (character/creature/mechanism/vehicle),
 * system class (gear_train/belt_drive/cylinder_actuator/hinge_joint/linkage),
 * and a top-level motion verb hint. What was missing — and what Meshy delivers
 * out-of-the-box — is a structured catalog of bakeable kinematic descriptors:
 *
 *   - characters: walk, run, idle, dance, wave, jump, sit, kneel, salute,
 *     attack, kick, punch, climb, swim, crawl, dodge, bow, cartwheel, throw,
 *     landing, fall, pendulum, applaud, breathe, talk
 *   - creatures: prowl, leap, fly_flap, swim, slither, perch, growl
 *   - vehicles: roll_forward, hover, fly_pattern, brake, turn
 *   - mechanisms: gear_mesh_rotate, belt_loop, piston_stroke, hinge_swing,
 *     linkage_cycle, actuator_extend
 *
 * Each descriptor carries:
 *   - a structured primitive sequence (rotate / translate / oscillate / gait /
 *     custom_pose) so the rigify_autorig pipeline can bake it as a real NLA
 *     action, not just a static FLUX pose
 *   - a promptDirective string for the FLUX reference image
 *   - duration + loop flag so the GLB exporter knows what to keyframe
 *
 * On top of the catalog, parseCustomMotionPrompt() turns free-text French /
 * English motion descriptions ("le perso fait une roue arriere puis salue")
 * into the same MotionDescriptor structure — sequencing primitives by
 * conjunctions (puis / then / et ensuite / and then / before / after / while).
 *
 * Pure: no Tauri / React deps so node --test can exercise it directly.
 */

export type KinematicSubjectKind =
  | 'character'
  | 'creature'
  | 'body_part'
  | 'vehicle'
  | 'mechanism'
  | 'assembly'
  | 'object'

export type KinematicSystemClass =
  | 'belt_drive'
  | 'gear_train'
  | 'cylinder_actuator'
  | 'hinge_joint'
  | 'linkage'
  | 'cable_routing'
  | 'pc_cabling'
  | 'electrical_harness'
  | 'led_strip'
  | 'electrical_system'
  | 'generic'

export type KinematicPrimitiveKind =
  | 'gait'           // bipedal walk/run cycle (heel-strike, swing, push-off)
  | 'rotate'         // continuous rotation around an axis
  | 'translate'      // linear translation along an axis
  | 'oscillate'      // back-and-forth around a center
  | 'swing'          // pendulum-like rotation around a pivot
  | 'extend'         // actuator-style on-axis extension
  | 'loop_path'      // closed-loop path (belt around pulleys)
  | 'gesture'        // upper-body gesture (wave, salute, applaud)
  | 'jump'           // ballistic parabolic motion
  | 'crouch'         // squat / kneel / sit
  | 'lunge'          // forward thrust (kick, punch, attack)
  | 'flap'           // wing flap / fin oscillation
  | 'breathe'        // subtle chest expansion / idle micro-motion
  | 'custom_pose'    // free-text fallback for unrecognized verbs

export type KinematicAxis = 'x' | 'y' | 'z' | 'auto'

export type KinematicPrimitive = {
  kind: KinematicPrimitiveKind
  // Optional fields — only the ones meaningful to the kind are populated:
  axis?: KinematicAxis
  amplitude?: number          // degrees for rotate/swing, meters for translate/extend
  frequency_hz?: number       // for oscillate / breathe / flap / gait
  duration_seconds?: number   // primitive-local duration override
  target?: string             // body region or part name ("right_arm", "drive_pulley")
  description?: string        // human-readable rationale (FR/EN)
}

export type MotionDescriptor = {
  id: string                       // stable identifier — "character.walk_cycle"
  label: string                    // FR label for UI
  description: string              // FR description
  appliesTo: {
    subjectKind?: KinematicSubjectKind[]
    systemClass?: KinematicSystemClass[]
  }
  primitives: KinematicPrimitive[]
  promptDirective: string          // injected into FLUX prompt
  duration_seconds: number         // total length of one cycle
  loop: boolean                    // true = NLA loop, false = play once
  source: 'preset' | 'custom'      // preset library vs parsed from user prompt
}

// ---------------------------------------------------------------------------
//  CHARACTER PRESETS (humanoid subjects: character / creature with humanoid
//  limbs / body_part). Each one is a real cinematic cycle, not just a pose.
// ---------------------------------------------------------------------------

const CHARACTER_PRESETS: MotionDescriptor[] = [
  {
    id: 'character.idle',
    label: 'Idle (respiration)',
    description: 'Pose neutre vivante avec respiration et micro-balancements.',
    appliesTo: { subjectKind: ['character', 'creature'] },
    primitives: [
      { kind: 'breathe', frequency_hz: 0.25, amplitude: 0.02, target: 'chest' },
      { kind: 'oscillate', axis: 'x', amplitude: 1.5, frequency_hz: 0.15, target: 'hips', description: 'micro hip sway' },
    ],
    promptDirective: 'Show the character in a relaxed standing idle: weight slightly on one leg, subtle chest breathing motion implied, arms hanging naturally with micro counter-sway, eyes forward, balanced grounded stance.',
    duration_seconds: 4.0,
    loop: true,
    source: 'preset',
  },
  {
    id: 'character.walk_cycle',
    label: 'Marcher (cycle complet)',
    description: 'Cycle de marche bipede: heel-strike, swing, push-off, opposition bras-jambes.',
    appliesTo: { subjectKind: ['character', 'creature'] },
    primitives: [
      { kind: 'gait', frequency_hz: 1.0, amplitude: 30, target: 'legs', description: 'heel-strike → swing → push-off' },
      { kind: 'gait', frequency_hz: 1.0, amplitude: 25, target: 'arms', description: 'opposite arm swing' },
      { kind: 'oscillate', axis: 'y', amplitude: 0.04, frequency_hz: 2.0, target: 'pelvis', description: 'vertical bounce' },
    ],
    promptDirective: 'Show the character mid-stride in a believable walk cycle: heel strike forward foot, push-off rear foot, opposite arm swung forward, hips shifted toward the planted leg, head leveled, balanced biomechanical weight transfer.',
    duration_seconds: 1.0,
    loop: true,
    source: 'preset',
  },
  {
    id: 'character.run_cycle',
    label: 'Courir',
    description: 'Foulee dynamique avec phase de suspension et inclinaison du buste.',
    appliesTo: { subjectKind: ['character', 'creature'] },
    primitives: [
      { kind: 'gait', frequency_hz: 2.5, amplitude: 60, target: 'legs', description: 'high-knee airborne suspension' },
      { kind: 'gait', frequency_hz: 2.5, amplitude: 50, target: 'arms', description: 'arms bent ~90 degrees' },
      { kind: 'oscillate', axis: 'y', amplitude: 0.12, frequency_hz: 5.0, target: 'pelvis' },
    ],
    promptDirective: 'Show the character in a believable running pose: airborne suspension phase, knees high, arms bent at ~90 degrees driving forward and back, torso leaning ~10 degrees forward, opposite arm-leg synchronization respected.',
    duration_seconds: 0.8,
    loop: true,
    source: 'preset',
  },
  {
    id: 'character.dance_default',
    label: 'Danser',
    description: 'Balancement rythmique avec rebond genoux et rotation hanches.',
    appliesTo: { subjectKind: ['character', 'creature'] },
    primitives: [
      { kind: 'oscillate', axis: 'x', amplitude: 12, frequency_hz: 1.5, target: 'hips' },
      { kind: 'oscillate', axis: 'y', amplitude: 0.08, frequency_hz: 1.5, target: 'pelvis', description: 'knee bounce' },
      { kind: 'gesture', amplitude: 30, frequency_hz: 0.75, target: 'arms', description: 'rythmic arm sway' },
    ],
    promptDirective: 'Show the character mid-dance: rhythmic hip rotation, knee bounce, arms loose and swaying with the beat, head following the body rhythm, expressive grounded stance with weight shifting between legs.',
    duration_seconds: 2.0,
    loop: true,
    source: 'preset',
  },
  {
    id: 'character.wave',
    label: 'Saluer (wave)',
    description: 'Salut amical d une main avec amplitude lisible.',
    appliesTo: { subjectKind: ['character', 'creature'] },
    primitives: [
      { kind: 'oscillate', axis: 'z', amplitude: 30, frequency_hz: 1.5, target: 'right_arm_raised' },
    ],
    promptDirective: 'Show the character waving: one arm raised to head height, forearm rocking side-to-side around the elbow, hand open with readable silhouette, relaxed body stance, friendly facing.',
    duration_seconds: 1.5,
    loop: true,
    source: 'preset',
  },
  {
    id: 'character.applaud',
    label: 'Applaudir',
    description: 'Applaudissements rythmiques mains en contact.',
    appliesTo: { subjectKind: ['character', 'creature'] },
    primitives: [
      { kind: 'oscillate', axis: 'x', amplitude: 0.18, frequency_hz: 2.5, target: 'hands', description: 'palm-to-palm rebound' },
    ],
    promptDirective: 'Show the character in a clear applauding pose with readable hand contact, expressive upper-body posture, and stable anatomy.',
    duration_seconds: 1.2,
    loop: true,
    source: 'preset',
  },
  {
    id: 'character.salute',
    label: 'Salut militaire',
    description: 'Salut formel avec coude releve et main pres du front.',
    appliesTo: { subjectKind: ['character', 'creature'] },
    primitives: [
      { kind: 'gesture', amplitude: 90, target: 'right_arm', description: 'arm to forehead, hand flat' },
    ],
    promptDirective: 'Show the character in a formal salute: right arm raised with elbow at shoulder height, hand flat against the brow, body upright, feet together, gaze forward, military posture.',
    duration_seconds: 1.0,
    loop: false,
    source: 'preset',
  },
  {
    id: 'character.bow',
    label: 'S incliner',
    description: 'Salut respectueux avec inclinaison du buste.',
    appliesTo: { subjectKind: ['character', 'creature'] },
    primitives: [
      { kind: 'crouch', amplitude: 30, target: 'torso', description: 'torso forward bend' },
    ],
    promptDirective: 'Show the character bowing: torso bent forward ~30 degrees from the hips, arms relaxed at sides or one over the chest, head following the bow direction, feet planted respectfully.',
    duration_seconds: 1.5,
    loop: false,
    source: 'preset',
  },
  {
    id: 'character.jump',
    label: 'Saut (apex)',
    description: 'Saut respectant la trajectoire parabolique et la flexion preparatoire.',
    appliesTo: { subjectKind: ['character', 'creature'] },
    primitives: [
      { kind: 'crouch', amplitude: 40, target: 'legs', description: 'pre-jump squat' },
      { kind: 'jump', amplitude: 1.2, axis: 'y', description: 'parabolic trajectory' },
      { kind: 'crouch', amplitude: 50, target: 'legs', description: 'landing absorption' },
    ],
    promptDirective: 'Show the character at the apex of a believable jump: arms reaching upward, knees tucked, torso slightly tilted, gravity-respecting parabolic trajectory implied — clearly mid-air with feet off the ground at the highest point.',
    duration_seconds: 1.4,
    loop: false,
    source: 'preset',
  },
  {
    id: 'character.kick',
    label: 'Coup de pied',
    description: 'Coup de pied frontal avec armement et retour.',
    appliesTo: { subjectKind: ['character', 'creature'] },
    primitives: [
      { kind: 'lunge', amplitude: 90, target: 'right_leg', description: 'knee chamber + extension' },
    ],
    promptDirective: 'Show the character mid-kick: support leg planted, kicking leg extended forward at hip height, hips rotated into the strike, arms counter-balanced, torso leaning slightly back for balance.',
    duration_seconds: 0.8,
    loop: false,
    source: 'preset',
  },
  {
    id: 'character.punch',
    label: 'Coup de poing',
    description: 'Direct du droit avec rotation des hanches.',
    appliesTo: { subjectKind: ['character', 'creature'] },
    primitives: [
      { kind: 'lunge', amplitude: 0.5, target: 'right_arm', description: 'cross with hip drive' },
    ],
    promptDirective: 'Show the character throwing a punch: rear hip rotated forward, lead arm extended at shoulder height with closed fist, off-arm guarding the face, weight transferred to the front foot.',
    duration_seconds: 0.5,
    loop: false,
    source: 'preset',
  },
  {
    id: 'character.sit',
    label: 'Assis',
    description: 'Posture assise stable, dos droit.',
    appliesTo: { subjectKind: ['character', 'creature'] },
    primitives: [
      { kind: 'crouch', amplitude: 90, target: 'hips_knees', description: 'seated 90deg flexion' },
    ],
    promptDirective: 'Show the character seated: hips and knees bent at ~90 degrees, back straight, hands resting on knees or thighs, feet flat on the floor, balanced upright sitting posture.',
    duration_seconds: 0.0,
    loop: false,
    source: 'preset',
  },
  {
    id: 'character.kneel',
    label: 'Agenouille',
    description: 'Genou au sol, posture stable.',
    appliesTo: { subjectKind: ['character', 'creature'] },
    primitives: [
      { kind: 'crouch', amplitude: 90, target: 'right_knee', description: 'one knee down' },
    ],
    promptDirective: 'Show the character kneeling: one knee on the ground, the other leg bent at ~90 degrees in front, torso upright, hands resting on the raised knee or at the sides, balanced respectful posture.',
    duration_seconds: 0.0,
    loop: false,
    source: 'preset',
  },
  {
    id: 'character.crawl',
    label: 'Ramper',
    description: 'Cycle de reptation sur quatre appuis.',
    appliesTo: { subjectKind: ['character', 'creature'] },
    primitives: [
      { kind: 'gait', frequency_hz: 0.8, amplitude: 20, target: 'arms_legs', description: 'diagonal four-point gait' },
    ],
    promptDirective: 'Show the character crawling on hands and knees: diagonal opposite limb advancing, hips and shoulders aligned with the floor, head looking forward, controlled four-point gait.',
    duration_seconds: 1.2,
    loop: true,
    source: 'preset',
  },
  {
    id: 'character.swim',
    label: 'Nager',
    description: 'Crawl: bras alternes, battement de jambes.',
    appliesTo: { subjectKind: ['character', 'creature'] },
    primitives: [
      { kind: 'gait', frequency_hz: 1.2, amplitude: 180, target: 'arms', description: 'crawl arm rotation' },
      { kind: 'oscillate', axis: 'y', amplitude: 15, frequency_hz: 4.0, target: 'legs', description: 'flutter kick' },
    ],
    promptDirective: 'Show the character swimming front crawl: alternating arms in full rotation overhead, flutter kick from the hips, body horizontal, face turned to the side for breathing.',
    duration_seconds: 2.0,
    loop: true,
    source: 'preset',
  },
  {
    id: 'character.cartwheel',
    label: 'Roue (cartwheel)',
    description: 'Rotation laterale sur les mains.',
    appliesTo: { subjectKind: ['character', 'creature'] },
    primitives: [
      { kind: 'rotate', axis: 'z', amplitude: 360, target: 'body', description: 'lateral handspring rotation' },
    ],
    promptDirective: 'Show the character executing a cartwheel: body rotating laterally through a handstand position, legs extended apart in the air, arms straight to the floor, momentum carrying the body sideways.',
    duration_seconds: 1.2,
    loop: false,
    source: 'preset',
  },
  {
    id: 'character.fall',
    label: 'Chute libre',
    description: 'Chute libre realiste avec position naturelle de gravite.',
    appliesTo: { subjectKind: ['character', 'creature'] },
    primitives: [
      { kind: 'jump', amplitude: -2.0, axis: 'y', description: 'gravity descent' },
    ],
    promptDirective: 'Show the character mid-fall under gravity: limbs slightly trailing upward due to relative motion, torso forward-tilted, arms naturally splayed for balance, body oriented head-up, expression coherent with the fall.',
    duration_seconds: 1.0,
    loop: false,
    source: 'preset',
  },
  {
    id: 'character.throw',
    label: 'Lancer',
    description: 'Lancer parabolique avec armement, propulsion, suivi.',
    appliesTo: { subjectKind: ['character', 'creature'] },
    primitives: [
      { kind: 'lunge', amplitude: 1.0, target: 'right_arm', description: 'wind-up + release + follow-through' },
    ],
    promptDirective: 'Show the character executing a throwing motion: rear leg planted, hips rotated, throwing arm extended forward at shoulder height, off-arm counter-balanced backward, follow-through visible, torso aligned with the parabolic launch direction.',
    duration_seconds: 1.0,
    loop: false,
    source: 'preset',
  },
  // v77zad: combat presets
  {
    id: 'character.block',
    label: 'Parer (block)',
    description: 'Garde defensive avec bras leves devant le visage.',
    appliesTo: { subjectKind: ['character', 'creature'] },
    primitives: [
      { kind: 'gesture', amplitude: 60, target: 'arms', description: 'arms raised crossed in front' },
      { kind: 'crouch', amplitude: 15, target: 'legs', description: 'slight defensive crouch' },
    ],
    promptDirective: 'Show the character in a defensive guard: forearms raised and crossed in front of the face/chest, elbows tight, weight slightly back on the rear foot, hips squared, eyes locked on the threat.',
    duration_seconds: 0.8,
    loop: false,
    source: 'preset',
  },
  {
    id: 'character.parry',
    label: 'Parade (parry)',
    description: 'Deviation laterale d une attaque entrante.',
    appliesTo: { subjectKind: ['character', 'creature'] },
    primitives: [
      { kind: 'lunge', amplitude: 90, target: 'right_arm', description: 'sweeping arc to deflect' },
    ],
    promptDirective: 'Show the character mid-parry: lead arm sweeping in a quick arc across the body to deflect an incoming strike, off-arm braced, body turned slightly to absorb the redirected force, weight transferring to the rear foot.',
    duration_seconds: 0.6,
    loop: false,
    source: 'preset',
  },
  {
    id: 'character.dodge',
    label: 'Esquiver (dodge)',
    description: 'Esquive laterale rapide hors de la trajectoire.',
    appliesTo: { subjectKind: ['character', 'creature'] },
    primitives: [
      { kind: 'translate', axis: 'x', amplitude: 1.2, target: 'body', description: 'lateral side-step' },
      { kind: 'crouch', amplitude: 25, target: 'legs', description: 'low evasion' },
    ],
    promptDirective: 'Show the character mid-dodge: body torqued sharply to one side, knees bent low for explosive lateral push, head tucked, arms swept to balance, feet at angle to push off the ground.',
    duration_seconds: 0.5,
    loop: false,
    source: 'preset',
  },
  {
    id: 'character.combat_roll',
    label: 'Roulade (combat roll)',
    description: 'Roulade avant pour absorber une chute ou esquiver.',
    appliesTo: { subjectKind: ['character', 'creature'] },
    primitives: [
      { kind: 'rotate', axis: 'x', amplitude: 360, target: 'body', description: 'forward shoulder roll' },
      { kind: 'translate', axis: 'z', amplitude: 1.5, target: 'body', description: 'forward momentum' },
    ],
    promptDirective: 'Show the character mid-combat-roll: body curled forward over one shoulder, knees tucked, head protected, momentum carrying them forward and through to the standing position, arms ready to push back up.',
    duration_seconds: 0.9,
    loop: false,
    source: 'preset',
  },
  // v77zad: interaction presets
  {
    id: 'character.push',
    label: 'Pousser',
    description: 'Pousse un objet vers l avant avec les deux bras.',
    appliesTo: { subjectKind: ['character', 'creature'] },
    primitives: [
      { kind: 'lunge', amplitude: 0.4, target: 'arms', description: 'extend forward against resistance' },
      { kind: 'crouch', amplitude: 20, target: 'legs', description: 'push from the legs' },
    ],
    promptDirective: 'Show the character pushing: torso leaned forward against an unseen resistance, both arms extended at chest height pushing away, hips squared, feet planted with one slightly behind for leverage, knees bent to drive force.',
    duration_seconds: 1.5,
    loop: true,
    source: 'preset',
  },
  {
    id: 'character.pull',
    label: 'Tirer',
    description: 'Tire un objet vers soi avec les deux bras flechis.',
    appliesTo: { subjectKind: ['character', 'creature'] },
    primitives: [
      { kind: 'lunge', amplitude: 0.4, target: 'arms', description: 'pull toward chest' },
      { kind: 'crouch', amplitude: 20, target: 'legs', description: 'lean back for leverage' },
    ],
    promptDirective: 'Show the character pulling: arms flexed bringing weight toward the chest, torso leaned slightly backward to use body weight, hips tucked, knees bent, one foot anchored behind for stability.',
    duration_seconds: 1.5,
    loop: true,
    source: 'preset',
  },
  {
    id: 'character.grab',
    label: 'Saisir',
    description: 'Saisit un objet avec une main.',
    appliesTo: { subjectKind: ['character', 'creature'] },
    primitives: [
      { kind: 'gesture', amplitude: 45, target: 'right_arm', description: 'reach + grasp' },
    ],
    promptDirective: 'Show the character grabbing: dominant arm extended forward, hand opening then closing around an object at chest or eye level, body weight shifted to the lead foot, off-arm relaxed.',
    duration_seconds: 0.7,
    loop: false,
    source: 'preset',
  },
  {
    id: 'character.lift',
    label: 'Soulever',
    description: 'Souleve un objet du sol vers le torse.',
    appliesTo: { subjectKind: ['character', 'creature'] },
    primitives: [
      { kind: 'crouch', amplitude: 70, target: 'legs', description: 'squat to grip' },
      { kind: 'gesture', amplitude: 0.5, target: 'arms', description: 'lift to torso' },
      { kind: 'crouch', amplitude: 0, target: 'legs', description: 'stand back up' },
    ],
    promptDirective: 'Show the character lifting from the floor: deep squat with back straight, arms extended downward gripping the object, body straightening upward in one continuous motion, torso vertical, knees driving the upward force.',
    duration_seconds: 1.8,
    loop: false,
    source: 'preset',
  },
  // v80v: 2 new character presets (climb, spin/pirouette)
  {
    id: 'character.climb',
    label: 'Grimper / escalader',
    description: 'Cycle de grimpe verticale: reach alterné main, push genou, transfert poids.',
    appliesTo: { subjectKind: ['character', 'creature'] },
    primitives: [
      { kind: 'gait', frequency_hz: 0.6, amplitude: 60, target: 'arms', description: 'alternating reach + grip overhead' },
      { kind: 'gait', frequency_hz: 0.6, amplitude: 50, target: 'legs', description: 'opposite knee drive into wall' },
      { kind: 'translate', axis: 'y', amplitude: 0.4, frequency_hz: 0.6, target: 'body', description: 'vertical ascent step per cycle' },
    ],
    promptDirective: 'Show the character mid-climb on a vertical surface: one hand reaching overhead for the next hold, opposite knee driving up against the wall, body weight shifted onto the planted foot, free hand gripping a hold at chest height, torso angled into the wall, eyes scanning upward.',
    duration_seconds: 1.7,
    loop: true,
    source: 'preset',
  },
  {
    id: 'character.spin',
    label: 'Tourner sur soi (pirouette)',
    description: 'Rotation 360 axiale du corps en place avec bras déployés.',
    appliesTo: { subjectKind: ['character', 'creature'] },
    primitives: [
      { kind: 'rotate', axis: 'y', amplitude: 360, frequency_hz: 1.0, target: 'body', description: 'continuous body spin around vertical axis' },
      { kind: 'oscillate', axis: 'x', amplitude: 25, frequency_hz: 1.0, target: 'arms', description: 'arms extended for momentum' },
    ],
    promptDirective: 'Show the character spinning on the spot: full body rotation around the vertical axis, arms extended outward for balance and momentum, head leading the rotation slightly, weight centered on the supporting foot, fluid pirouette motion.',
    duration_seconds: 1.0,
    loop: true,
    source: 'preset',
  },
]

// ---------------------------------------------------------------------------
//  CREATURE-SPECIFIC PRESETS (non-humanoid: birds, reptiles, fish, quadrupeds)
// ---------------------------------------------------------------------------

const CREATURE_PRESETS: MotionDescriptor[] = [
  {
    id: 'creature.flap_fly',
    label: 'Voler (battement)',
    description: 'Vol bat avec battement d ailes synchronise.',
    appliesTo: { subjectKind: ['creature'] },
    primitives: [
      { kind: 'flap', frequency_hz: 3.0, amplitude: 60, target: 'wings' },
      { kind: 'oscillate', axis: 'y', amplitude: 0.05, frequency_hz: 3.0, target: 'body', description: 'lift bob' },
    ],
    promptDirective: 'Show the creature in active flight: wings mid-downstroke at maximum spread, body lifted by the wing power, tail extended for stability, head forward following the flight direction.',
    duration_seconds: 0.33,
    loop: true,
    source: 'preset',
  },
  {
    id: 'creature.slither',
    label: 'Ramper (serpent)',
    description: 'Ondulation laterale serpentine.',
    appliesTo: { subjectKind: ['creature'] },
    primitives: [
      { kind: 'oscillate', axis: 'x', amplitude: 30, frequency_hz: 1.0, target: 'body', description: 'sinusoidal lateral wave' },
    ],
    promptDirective: 'Show the creature slithering: body forming a sinusoidal lateral wave from head to tail, ground contact along multiple curves, head leading, smooth continuous undulation.',
    duration_seconds: 1.0,
    loop: true,
    source: 'preset',
  },
  {
    id: 'creature.prowl',
    label: 'Rodeur (felidae)',
    description: 'Marche feline lente, dos abaisse, predateur.',
    appliesTo: { subjectKind: ['creature'] },
    primitives: [
      { kind: 'gait', frequency_hz: 0.6, amplitude: 15, target: 'all_four_legs', description: 'low predator quadruped gait' },
      { kind: 'oscillate', axis: 'x', amplitude: 5, frequency_hz: 0.6, target: 'tail', description: 'tail counter-balance' },
    ],
    promptDirective: 'Show the creature prowling: back lowered, head forward and slightly down, paws placed deliberately one in front of the other, predator stalking gait, eyes locked forward.',
    duration_seconds: 1.6,
    loop: true,
    source: 'preset',
  },
  // v77zt: full quadruped preset set — proper 4-leg gaits with tail.
  {
    id: 'creature.quadruped_walk',
    label: 'Marche (quadrupede)',
    description: 'Marche a 4 pattes avec coordination diagonale (dog/horse trot).',
    appliesTo: { subjectKind: ['creature'] },
    primitives: [
      { kind: 'gait', frequency_hz: 1.2, amplitude: 25, target: 'all_four_legs', description: 'diagonal trot — front_L+hind_R sync' },
      { kind: 'oscillate', axis: 'x', amplitude: 10, frequency_hz: 1.2, target: 'tail', description: 'tail follows gait' },
      { kind: 'oscillate', axis: 'y', amplitude: 0.03, frequency_hz: 2.4, target: 'pelvis', description: 'subtle vertical bounce' },
    ],
    promptDirective: 'Show the quadruped mid-stride in a believable trotting walk: diagonal opposite limbs paired (front-left + hind-right advancing), tail relaxed counter-balancing the gait, head leveled, four-point ground contact alternating cleanly.',
    duration_seconds: 0.83,
    loop: true,
    source: 'preset',
  },
  {
    id: 'creature.quadruped_run',
    label: 'Galop (quadrupede)',
    description: 'Galop dynamique avec phase de suspension a 4 pattes.',
    appliesTo: { subjectKind: ['creature'] },
    primitives: [
      { kind: 'gait', frequency_hz: 2.5, amplitude: 50, target: 'all_four_legs', description: 'gallop — bound or rotary' },
      { kind: 'oscillate', axis: 'y', amplitude: 0.15, frequency_hz: 2.5, target: 'pelvis', description: 'powerful vertical impulse' },
      { kind: 'oscillate', axis: 'x', amplitude: 20, frequency_hz: 2.5, target: 'tail', description: 'tail extended for momentum' },
    ],
    promptDirective: 'Show the quadruped in a believable gallop: airborne suspension phase visible, front legs tucked or extended forward, hind legs powering off the ground, spine arched forward, tail extended horizontally for momentum, head lowered slightly.',
    duration_seconds: 0.4,
    loop: true,
    source: 'preset',
  },
  {
    id: 'creature.quadruped_idle',
    label: 'Idle (quadrupede)',
    description: 'Posture debout naturelle avec respiration et balayage de queue.',
    appliesTo: { subjectKind: ['creature'] },
    primitives: [
      { kind: 'breathe', frequency_hz: 0.3, amplitude: 0.025, target: 'chest' },
      { kind: 'oscillate', axis: 'x', amplitude: 8, frequency_hz: 0.4, target: 'tail', description: 'lazy tail wag' },
      { kind: 'oscillate', axis: 'z', amplitude: 3, frequency_hz: 0.2, target: 'head', description: 'micro head shift' },
    ],
    promptDirective: 'Show the quadruped standing relaxed on all four legs: weight balanced evenly, head at neutral height, ears alert, tail hanging naturally with slow gentle sway, chest visibly breathing.',
    duration_seconds: 4.0,
    loop: true,
    source: 'preset',
  },
  {
    id: 'creature.quadruped_jump',
    label: 'Saut (quadrupede)',
    description: 'Saut a 4 pattes avec coiled leap et reception.',
    appliesTo: { subjectKind: ['creature'] },
    primitives: [
      { kind: 'crouch', amplitude: 50, target: 'all_four_legs', description: 'pre-jump coil' },
      { kind: 'jump', amplitude: 1.5, axis: 'y', description: 'ballistic leap' },
      { kind: 'crouch', amplitude: 60, target: 'all_four_legs', description: 'landing absorption' },
    ],
    promptDirective: 'Show the quadruped at the apex of a leap: all four legs tucked under the body, spine arched, head forward and looking ahead, tail extended for balance, momentum carrying horizontally, gravity-respecting parabolic trajectory clear.',
    duration_seconds: 1.2,
    loop: false,
    source: 'preset',
  },
  {
    id: 'creature.tail_wag',
    label: 'Remue-queue',
    description: 'Battement rapide de queue (chien content).',
    appliesTo: { subjectKind: ['creature'] },
    primitives: [
      { kind: 'oscillate', axis: 'x', amplitude: 30, frequency_hz: 3.5, target: 'tail', description: 'enthusiastic tail wag' },
      { kind: 'oscillate', axis: 'y', amplitude: 0.02, frequency_hz: 1.5, target: 'pelvis', description: 'hip wiggle from wag' },
    ],
    promptDirective: 'Show the quadruped wagging its tail enthusiastically: tail swept side-to-side at high frequency, hips slightly wiggling along, body language alert and friendly, ears perked forward.',
    duration_seconds: 1.5,
    loop: true,
    source: 'preset',
  },
  // v80v: creature.roar — chest expansion + head raise + jaw drop
  {
    id: 'creature.roar',
    label: 'Rugir',
    description: 'Rugissement: expansion thorax, tête relevée, mâchoire ouverte.',
    appliesTo: { subjectKind: ['creature'] },
    primitives: [
      { kind: 'breathe', frequency_hz: 0.5, amplitude: 0.18, target: 'chest', description: 'deep chest expansion' },
      { kind: 'oscillate', axis: 'x', amplitude: 35, frequency_hz: 0.5, target: 'head', description: 'head tilt up + back' },
      { kind: 'oscillate', axis: 'x', amplitude: 40, frequency_hz: 0.5, target: 'jaw', description: 'jaw fully open' },
    ],
    promptDirective: 'Show the creature mid-roar: chest expanded fully forward, head thrown up and back, jaw open wide showing teeth, neck muscles taut, front limbs planted firmly, audible-implied loud bellow posture.',
    duration_seconds: 2.0,
    loop: true,
    source: 'preset',
  },
]

// ---------------------------------------------------------------------------
//  MECHANISM PRESETS — bakeable continuous animations for gear trains, belt
//  drives, actuators, hinges, linkages.
// ---------------------------------------------------------------------------

const MECHANISM_PRESETS: MotionDescriptor[] = [
  {
    id: 'mechanism.gear_mesh_rotate',
    label: 'Engrenage (mesh)',
    description: 'Rotation continue avec vitesses inversement proportionnelles aux dents.',
    appliesTo: { systemClass: ['gear_train'] },
    primitives: [
      { kind: 'rotate', axis: 'z', amplitude: 360, frequency_hz: 0.5, target: 'drive_gear', description: 'driver continuous rotation' },
      { kind: 'rotate', axis: 'z', amplitude: 360, frequency_hz: 0.5, target: 'driven_gear', description: 'follows ratio = teeth_drive / teeth_driven, opposite sign' },
    ],
    promptDirective: 'Show the gear train in active mesh rotation: drive gear turning continuously around its axle, driven gear synchronized in the opposite direction at the gear-ratio speed, axles fixed, housing static, teeth contact maintained.',
    duration_seconds: 2.0,
    loop: true,
    source: 'preset',
  },
  {
    id: 'mechanism.belt_loop',
    label: 'Courroie en boucle',
    description: 'Boucle continue de la courroie autour des poulies alignees.',
    appliesTo: { systemClass: ['belt_drive'] },
    primitives: [
      { kind: 'loop_path', frequency_hz: 0.5, target: 'belt', description: 'closed continuous loop' },
      { kind: 'rotate', axis: 'z', amplitude: 360, frequency_hz: 0.5, target: 'drive_pulley' },
      { kind: 'rotate', axis: 'z', amplitude: 360, frequency_hz: 0.5, target: 'driven_pulley', description: 'same direction as drive_pulley' },
    ],
    promptDirective: 'Show the belt drive in active operation: continuous taut belt loop translating around all pulleys, drive pulley rotating, driven pulley following at the diameter ratio in the same direction, frame and supports static, no belt slip or sag.',
    duration_seconds: 2.0,
    loop: true,
    source: 'preset',
  },
  {
    id: 'mechanism.piston_stroke',
    label: 'Verin (course)',
    description: 'Course aller-retour du verin sur son axe.',
    appliesTo: { systemClass: ['cylinder_actuator'] },
    primitives: [
      { kind: 'extend', axis: 'auto', amplitude: 0.3, frequency_hz: 0.5, target: 'rod', description: 'extend → retract cycle' },
    ],
    promptDirective: 'Show the actuator cycling: cylinder body anchored, rod extending fully along its axis then retracting, mounting points clearly fixed, stroke direction immediately readable.',
    duration_seconds: 2.0,
    loop: true,
    source: 'preset',
  },
  {
    id: 'mechanism.hinge_swing',
    label: 'Charniere (battement)',
    description: 'Ouverture-fermeture autour de l axe.',
    appliesTo: { systemClass: ['hinge_joint'] },
    primitives: [
      { kind: 'swing', axis: 'auto', amplitude: 90, frequency_hz: 0.4, target: 'leaf', description: '0deg → 90deg → 0deg' },
    ],
    promptDirective: 'Show the hinge cycling open and closed: hinge axis fixed, the leaf swinging from 0 to 90 degrees and back, bracket stationary, axis center clearly visible.',
    duration_seconds: 2.5,
    loop: true,
    source: 'preset',
  },
  {
    id: 'mechanism.linkage_cycle',
    label: 'Tringlerie (cycle)',
    description: 'Cycle complet de l articulation a quatre barres.',
    appliesTo: { systemClass: ['linkage'] },
    primitives: [
      { kind: 'rotate', axis: 'z', amplitude: 360, frequency_hz: 0.5, target: 'crank', description: 'crank rotation drives the cycle' },
      { kind: 'oscillate', axis: 'auto', amplitude: 1.0, frequency_hz: 0.5, target: 'rocker', description: 'rocker follows the four-bar coupling' },
    ],
    promptDirective: 'Show the four-bar linkage cycling: crank rotating continuously, rocker oscillating in response, coupler tracing its characteristic path, ground link fixed, all pivots clearly visible.',
    duration_seconds: 2.0,
    loop: true,
    source: 'preset',
  },
  // v80v: mechanism.vibrate — high-freq low-amp buzz (electronics, machinery)
  {
    id: 'mechanism.vibrate',
    label: 'Vibrer',
    description: 'Vibration haute fréquence faible amplitude (machinery buzz, motor hum).',
    appliesTo: { systemClass: ['gear_train', 'cylinder_actuator'] },
    primitives: [
      { kind: 'oscillate', axis: 'x', amplitude: 0.005, frequency_hz: 30.0, target: 'body', description: 'high-frequency lateral buzz' },
      { kind: 'oscillate', axis: 'y', amplitude: 0.003, frequency_hz: 28.0, target: 'body', description: 'slightly off-phase vertical' },
    ],
    promptDirective: 'Show the device vibrating in place: housing buzzing with high-frequency low-amplitude micro-motion, no net translation, motion-blur cue on edges if visible, surface contact clearly maintained.',
    duration_seconds: 1.5,
    loop: true,
    source: 'preset',
  },
]

// ---------------------------------------------------------------------------
//  VEHICLE PRESETS
// ---------------------------------------------------------------------------

const VEHICLE_PRESETS: MotionDescriptor[] = [
  {
    id: 'vehicle.roll_forward',
    label: 'Rouler',
    description: 'Avance avec roues en rotation et corps stable.',
    appliesTo: { subjectKind: ['vehicle'] },
    primitives: [
      { kind: 'translate', axis: 'z', amplitude: 5.0, frequency_hz: 0.5, target: 'body', description: 'forward travel' },
      { kind: 'rotate', axis: 'x', amplitude: 360, frequency_hz: 4.0, target: 'wheels' },
    ],
    promptDirective: 'Show the vehicle rolling forward: wheels rotating in sync with the ground travel, body level and stable, suspension barely loaded, motion-blur cue if relevant.',
    duration_seconds: 2.0,
    loop: true,
    source: 'preset',
  },
  {
    id: 'vehicle.hover',
    label: 'Vol stationnaire',
    description: 'Hover avec micro-corrections verticales.',
    appliesTo: { subjectKind: ['vehicle'] },
    primitives: [
      { kind: 'oscillate', axis: 'y', amplitude: 0.05, frequency_hz: 1.0, target: 'body', description: 'hover bob' },
      { kind: 'rotate', axis: 'y', amplitude: 360, frequency_hz: 30.0, target: 'rotors' },
    ],
    promptDirective: 'Show the vehicle hovering in place: rotors spinning fast with motion-blur, body kept level with small vertical correction motion, no horizontal drift.',
    duration_seconds: 2.0,
    loop: true,
    source: 'preset',
  },
]

// ---------------------------------------------------------------------------
//  PUBLIC SELECTOR — given subject + system class, return relevant presets.
// ---------------------------------------------------------------------------

export type KinematicQuery = {
  subjectKind: KinematicSubjectKind
  systemClass: KinematicSystemClass
}

export function selectKinematicPresets(query: KinematicQuery): MotionDescriptor[] {
  const all = [...MECHANISM_PRESETS, ...VEHICLE_PRESETS, ...CREATURE_PRESETS, ...CHARACTER_PRESETS]
  const matches: MotionDescriptor[] = []

  for (const preset of all) {
    const subjectMatch = preset.appliesTo.subjectKind?.includes(query.subjectKind) ?? false
    const systemMatch = preset.appliesTo.systemClass?.includes(query.systemClass) ?? false
    if (subjectMatch || systemMatch) {
      matches.push(preset)
    }
  }
  return matches
}

export function listAllPresetIds(): string[] {
  return [
    ...CHARACTER_PRESETS.map((p) => p.id),
    ...CREATURE_PRESETS.map((p) => p.id),
    ...MECHANISM_PRESETS.map((p) => p.id),
    ...VEHICLE_PRESETS.map((p) => p.id),
  ]
}

// ---------------------------------------------------------------------------
//  CUSTOM MOTION PARSER — turns free-text into a MotionDescriptor.
//
//  Examples it handles:
//    "fait une roue arriere puis salue"  → cartwheel + wave
//    "marche puis saute"                  → walk + jump
//    "danse en applaudissant"             → dance + applaud (parallel)
//    "ouvre la charniere"                 → hinge_swing
//    "le perso s assoit puis se leve"     → sit + stand_up (custom_pose for stand_up)
// ---------------------------------------------------------------------------

const VERB_TO_PRESET: { rx: RegExp; presetId: string }[] = [
  // v80u — vocabulary expansion: each existing regex picks up 3-5 natural-
  // language synonyms (déambule, flâne, pirouette, se baisse, etc.). Plus
  // 2 newly-wired verbs for quadruped_idle and quadruped_jump (presets that
  // existed but had no surface form). Mirror in motion_parser.py + fixtures.
  { rx: /\b(roue|cartwheel|handspring|salto|backflip|frontflip|aerial)\b/i, presetId: 'character.cartwheel' },
  { rx: /\b(salue|salut\b|wave|waves|waving|saluer|fait coucou|coucou|signe de la main|hi-five|high five)\b/i, presetId: 'character.wave' },
  { rx: /\b(salut militaire|formal salute|garde a vous|garde-a-vous|attention salute)\b/i, presetId: 'character.salute' },
  { rx: /\b(applaudis(?:s|t)?|applaudit|applaud|clap|clapping|claps|claque des mains|tape des mains|ovation|cheer|cheers|cheering)\b/i, presetId: 'character.applaud' },
  { rx: /\b(s incline|s'incline|s incliner|bow|bows|bowing|reverence|r[eé]v[eé]rence|courber|courbure|incliner)\b/i, presetId: 'character.bow' },
  // v80u: quadruped_jump precedes character.jump to win on "four-legged jump" / "chien qui saute"
  { rx: /\b(quadruped(?:e)? saute|quadruped jump|four-legged leap|chien qui saute|cat jumping|saut quadrupede)\b/i, presetId: 'creature.quadruped_jump' },
  { rx: /\b(saute|sauter|jump|jumping|jumps|leap|leaps|leaping|bond|bondis|bondit|hop|hops|hopping|spring|springs|springing)\b/i, presetId: 'character.jump' },
  { rx: /\b(coup de pied|kick|kicks|kicking|donne un coup de pied|footstrike|round[\s-]?house)\b/i, presetId: 'character.kick' },
  { rx: /\b(coup de poing|punch|punches|punching|jab|cross|hook|uppercut|donne un coup de poing|frappe du poing)\b/i, presetId: 'character.punch' },
  { rx: /\b(s assoit|s'assoit|s asseoit|assis|assoit|sit|sits|sitting|seated|s installer|prend place|takes a seat)\b/i, presetId: 'character.sit' },
  { rx: /\b(s agenouille|s'agenouille|agenouille|kneel|kneeling|kneels|se baisse|s accroupit|accroupi|crouch|crouches|crouching|squat|squats|squatting)\b/i, presetId: 'character.kneel' },
  { rx: /\b(rampe|ramper|crawl|crawls|crawling|se tra[iî]ne|se traine|sur le ventre|prone crawl)\b/i, presetId: 'character.crawl' },
  { rx: /\b(nage|nager|swim|swims|swimming|crawl natation|brasse|breaststroke|freestyle swimming)\b/i, presetId: 'character.swim' },
  { rx: /\b(court|courir|run|runs|running|jog|jogs|jogging|sprint|sprints|sprinting|fonce|file|file en courant)\b/i, presetId: 'character.run_cycle' },
  { rx: /\b(marche|marcher|walk|walks|walking|d[eé]ambule|d[eé]ambuler|fl[âa]ne|fl[âa]ner|stroll|strolls|strolling|saunter|saunters|sauntering|amble|ambles|ambling|prom[eè]ne|promener|stride|strides|striding)\b/i, presetId: 'character.walk_cycle' },
  { rx: /\b(danse|danser|dance|dances|dancing|groove|grooves|grooving|boogie|boogies)\b/i, presetId: 'character.dance_default' },
  { rx: /\b(lance|lancer|throw|throws|throwing|pitch|pitches|pitching|hurl|hurls|hurling|toss|tosses|tossing)\b/i, presetId: 'character.throw' },
  { rx: /\b(tombe|tomber|fall|falls|falling|chute|s effondre|s'effondre|trip|trips|tripping|stumble|stumbles)\b/i, presetId: 'character.fall' },
  // v80u: quadruped_idle precedes character.idle to win on "four-legged idle"
  { rx: /\b(quadruped(?:e)? au repos|quadruped idle|four-legged idle|quadruped resting|chien assis tranquille|cat resting)\b/i, presetId: 'creature.quadruped_idle' },
  { rx: /\b(idle|repos|au repos|stand idle|inactif|au calme|sans bouger|stationary|breathe|breathes|breathing|respire|respirer|attente)\b/i, presetId: 'character.idle' },
  { rx: /\b(bloque|bloquer|block|blocking|blocks|garde|guard|guards|defend|defends|defending|protege|prot[eé]ger)\b/i, presetId: 'character.block' },
  { rx: /\b(pare|parer|parade|parry|parries|parrying|deflect|deflects|deflecting|deviation|d[eé]viation|repousse|repousser)\b/i, presetId: 'character.parry' },
  { rx: /\b(esquive|esquiver|dodge|dodges|dodging|sidestep|sidesteps|side-step|evade|evades|evading|fait un pas de cot[eé])\b/i, presetId: 'character.dodge' },
  { rx: /\b(roulade|combat roll|forward roll|tumble|tumbles|tumbling|fait une roulade|barrel roll)\b/i, presetId: 'character.combat_roll' },
  { rx: /\b(pousse|pousser|push|pushes|pushing|shoves?|shoving|repousse|repousser|bouscule)\b/i, presetId: 'character.push' },
  { rx: /\b(tire|tirer|pull|pulls|pulling|drag|drags|dragging|tracte|tracter|hauls?|hauling)\b/i, presetId: 'character.pull' },
  { rx: /\b(saisit|saisir|grab|grabs|grabbing|grasp|grasps|grasping|attrape|attraper|catches|catching|empoigne|empoigner|ramasse|ramasser|pick(?:s|ed)? up|picks up)\b/i, presetId: 'character.grab' },
  { rx: /\b(souleve|soulever|lift|lifts|lifting|hoist|hoists|hoisting|raises an object|porte|porter|carries an object)\b/i, presetId: 'character.lift' },
  // v80v: 2 new character presets
  { rx: /\b(grimpe|grimper|escalade|escalader|climb|climbs|climbing|scale|scaling|monter en escalade)\b/i, presetId: 'character.climb' },
  { rx: /\b(pirouette|pirouettes|tourne sur (?:lui|elle)[\s-]m[eê]me|spins?\s+on\s+the\s+spot|spin\s+in\s+place|tournoiement|whirls?|twirls?|twirling|tourbillonne)\b/i, presetId: 'character.spin' },

  { rx: /\b(vole|voler|volant|volante|volants|fly|flying|flies|battement[s]?\s+(?:d['’]|des?\s+|d\s+)?ailes?|flapping\s+wings?|wings?\s+flap(?:ping|s)?|plane|planes|planing|soar|soars|soaring|sustentation)\b/i, presetId: 'creature.flap_fly' },
  { rx: /\b(serpente|slither|slithers|slithering|onduler|ondule|ondulant|wriggle|wriggles|wriggling|squirm|squirms)\b/i, presetId: 'creature.slither' },
  { rx: /\b(rode|r[oô]der|rodeur|prowl|prowling|stalk|stalking|sneak|sneaks|sneaking|creep|creeps|creeping)\b/i, presetId: 'creature.prowl' },
  { rx: /\b(galop|galope|galoper|gallop|galloping|gallops|charge|charges|charging|fonce a quatre pattes)\b/i, presetId: 'creature.quadruped_run' },
  { rx: /\b(trotte|trotter|trot|trotting|trots|amble quadrupede|patte par patte)\b/i, presetId: 'creature.quadruped_walk' },
  { rx: /\b(remue queue|remuer la queue|wag tail|tail wag|wagging|tail wagging|frétille|fretille la queue)\b/i, presetId: 'creature.tail_wag' },
  // v80v: creature roar
  { rx: /\b(rugit|rugir|roar|roars|roaring|bellows?|bellowing|growl|growls|growling|grogne|gronde)\b/i, presetId: 'creature.roar' },
  { rx: /\b(quadrupede|quadruped|on all fours|a quatre pattes|four-legged|four legged)\b/i, presetId: 'creature.quadruped_walk' },
  // v80u: orphan-preset wirings — moved earlier in this list so they win
  // over the generic character.idle / character.jump regexes.

  { rx: /\b(engrenages? (?:qui )?tourne(?:nt)?|engrenage qui tourner|gear (?:mesh|rotation|rotates|rotating|spinning)|engrenage en rotation)\b/i, presetId: 'mechanism.gear_mesh_rotate' },
  { rx: /\b(courroie en (?:marche|fonctionnement|boucle)|belt running|belt loop)\b/i, presetId: 'mechanism.belt_loop' },
  { rx: /\b(verin|piston (?:en |)course|cylinder stroke|actuator stroke)\b/i, presetId: 'mechanism.piston_stroke' },
  { rx: /\b(charniere qui (?:s ouvre|s'ouvre|bat)|hinge swing|hinge swinging)\b/i, presetId: 'mechanism.hinge_swing' },
  { rx: /\b(tringlerie|four-bar|linkage cycle|articulation a quatre barres)\b/i, presetId: 'mechanism.linkage_cycle' },
  // v80v: machinery vibration
  { rx: /\b(vibre|vibrer|vibrates?|vibrating|buzz|buzzing|buzzes|hums?|humming|trepide|tr[eé]pide)\b/i, presetId: 'mechanism.vibrate' },
  // Generic rotation fallback — keeps TS in lock-step with motion_parser.py
  // (v79o). Catches "tourne lentement", "spinning slowly", "rotates", etc.
  { rx: /\b(tournoie|tournoient|spins?|spinning|spin (?:slowly|quickly|fast)|rotates?|rotating|gyrates?|gyrating|rotation continue|continuous rotation|tourne(?:nt)? (?:lentement|doucement|rapidement|sur (?:lui|elle|eux|elles)[\s-]m[eê]me|en place|sur place))\b/i, presetId: 'mechanism.gear_mesh_rotate' },

  { rx: /\b(roule|rouler|drive forward|rolling forward)\b/i, presetId: 'vehicle.roll_forward' },
  { rx: /\b(vol stationnaire|hover|hovering)\b/i, presetId: 'vehicle.hover' },
]

const ALL_PRESET_INDEX: Record<string, MotionDescriptor> = (() => {
  const out: Record<string, MotionDescriptor> = {}
  for (const p of [...CHARACTER_PRESETS, ...CREATURE_PRESETS, ...MECHANISM_PRESETS, ...VEHICLE_PRESETS]) {
    out[p.id] = p
  }
  return out
})()

const SEQUENCE_SEPARATOR_RX =
  /\s+(?:puis|then|et\s+ensuite|et\s+apres|et\s+apr[eè]s|after\s+that|next|ensuite|et\s+puis|and\s+then)\s+/i
const PARALLEL_SEPARATOR_RX =
  /\s+(?:en\s+m[eê]me\s+temps\s+que|while|tout\s+en|en\s+|whilst)\s+/i

// v77zv: motion modifiers. A segment like "marche rapidement" or "danse
// joyeusement et fortement" applies multipliers to the resolved preset's
// primitives — frequency_hz scales for speed, amplitude scales for
// intensity. Modifiers are detected after the verb match so they layer
// onto whichever preset the verb resolved.
type SpatialDirection = 'up' | 'down' | 'forward' | 'backward' | 'left' | 'right' | null

type SegmentModifiers = {
  speedMul: number       // multiplier on frequency_hz
  amplitudeMul: number   // multiplier on amplitude
  emotion: 'happy' | 'sad' | 'angry' | 'tired' | null
  // v77zaa: spatial modifiers — affect amplitude on a specific axis and
  // tag a direction so downstream renderer / baker can orient the motion.
  // 'haut'/'high' boosts vertical amplitude on jump/oscillate; 'loin'/'far'
  // boosts horizontal translation amplitude; direction tags target axis.
  heightMul: number      // multiplier on jump amplitude / vertical oscillate
  distanceMul: number    // multiplier on translate amplitude
  direction: SpatialDirection
  matched: string[]      // text tokens matched, for diagnostics
}

const MODIFIER_RULES: Array<{ rx: RegExp; effect: Partial<Omit<SegmentModifiers, 'matched'>> & { matched: string } }> = [
  // SPEED
  { rx: /\b(rapidement|vite|fast|quickly|speedily|swiftly|hate(?:ment)?|en vitesse|au galop|ultra rapide|tres vite)\b/i,
    effect: { speedMul: 1.6, matched: 'speed_fast' } },
  { rx: /\b(extremement vite|extr[eê]mement vite|tres rapidement|frenetiquement|fr[eé]n[eé]tiquement|frantically)\b/i,
    effect: { speedMul: 2.2, matched: 'speed_very_fast' } },
  { rx: /\b(lentement|doucement|slowly|leisurely|tranquillement|au ralenti|in slow motion|posement|pos[eé]ment)\b/i,
    effect: { speedMul: 0.6, matched: 'speed_slow' } },
  { rx: /\b(tres lentement|tr[eè]s lentement|extremely slowly|au ralenti extreme)\b/i,
    effect: { speedMul: 0.35, matched: 'speed_very_slow' } },

  // INTENSITY (amplitude)
  { rx: /\b(fort(?:ement)?|intensement|intens[eé]ment|intense|hard|powerfully|vigoureusement|vigoroso|brutalement|avec force)\b/i,
    effect: { amplitudeMul: 1.4, matched: 'intensity_high' } },
  { rx: /\b(violemment|tres fort|tr[eè]s fort|with full force|de toutes ses forces|enormous force)\b/i,
    effect: { amplitudeMul: 1.8, matched: 'intensity_very_high' } },
  { rx: /\b(legerement|l[eé]g[eè]rement|gently|softly|delicatement|d[eé]licatement|a peine|barely|subtilement|en finesse)\b/i,
    effect: { amplitudeMul: 0.65, matched: 'intensity_low' } },
  { rx: /\b(a peine perceptible|imperceptiblement|microscopiquement|microscopically)\b/i,
    effect: { amplitudeMul: 0.35, matched: 'intensity_very_low' } },

  // EMOTION (annotated; modifies amplitude/speed slightly + tags descriptor)
  { rx: /\b(joyeusement|happily|cheerfully|content(?:ement)?|gaiement|allegrement|all[eé]grement|enjoue|enjou[eé])\b/i,
    effect: { speedMul: 1.15, amplitudeMul: 1.15, emotion: 'happy', matched: 'emotion_happy' } },
  { rx: /\b(tristement|sadly|melancoliquement|m[eé]lancoliquement|abattu|d[eé]courag[eé]|d[eé]prim[eé])\b/i,
    effect: { speedMul: 0.7, amplitudeMul: 0.85, emotion: 'sad', matched: 'emotion_sad' } },
  { rx: /\b(en colere|angrily|fiercement|furieusement|aggressivement|agressivement|rageusement|hargneusement)\b/i,
    effect: { speedMul: 1.3, amplitudeMul: 1.5, emotion: 'angry', matched: 'emotion_angry' } },
  { rx: /\b(fatigue|fatigu[eé]|tired|exhausted|epuise|[eé]puis[eé]|las(?:sement)?|sans energie)\b/i,
    effect: { speedMul: 0.55, amplitudeMul: 0.7, emotion: 'tired', matched: 'emotion_tired' } },

  // v77zaa: SPATIAL — height (vertical), distance (horizontal), direction
  { rx: /\b(haut|high|vers le haut|upward|en hauteur|sky high|en l air|en l'air)\b/i,
    effect: { heightMul: 1.6, direction: 'up', matched: 'spatial_high' } },
  { rx: /\b(tres haut|tr[eè]s haut|very high|extremement haut|extr[eê]mement haut|sky high)\b/i,
    effect: { heightMul: 2.2, direction: 'up', matched: 'spatial_very_high' } },
  { rx: /\b(bas|low|au sol|ground level|ras du sol|vers le bas|downward|en plongee)\b/i,
    effect: { heightMul: 0.5, direction: 'down', matched: 'spatial_low' } },
  { rx: /\b(loin|far|au loin|distant|sur une longue distance|long range|tres loin|tr[eè]s loin|very far)\b/i,
    effect: { distanceMul: 1.7, direction: 'forward', matched: 'spatial_far' } },
  { rx: /\b(pres|close|just there|courte distance|short range|tout pres)\b/i,
    effect: { distanceMul: 0.55, matched: 'spatial_close' } },
  { rx: /\b(vers la gauche|to the left|gauche|leftward|on the left side)\b/i,
    effect: { direction: 'left', matched: 'spatial_left' } },
  { rx: /\b(vers la droite|to the right|droite|rightward|on the right side)\b/i,
    effect: { direction: 'right', matched: 'spatial_right' } },
  { rx: /\b(en arriere|en arri[eè]re|backward|behind|en recul|en reculant)\b/i,
    effect: { distanceMul: 0.8, direction: 'backward', matched: 'spatial_backward' } },
  { rx: /\b(en avant|forward|toward|vers l avant|en se rapprochant)\b/i,
    effect: { direction: 'forward', matched: 'spatial_forward' } },
]

function extractSegmentModifiers(segment: string): SegmentModifiers {
  const out: SegmentModifiers = {
    speedMul: 1.0,
    amplitudeMul: 1.0,
    emotion: null,
    heightMul: 1.0,
    distanceMul: 1.0,
    direction: null,
    matched: [],
  }
  for (const { rx, effect } of MODIFIER_RULES) {
    if (rx.test(segment)) {
      if (effect.speedMul !== undefined) out.speedMul *= effect.speedMul as number
      if (effect.amplitudeMul !== undefined) out.amplitudeMul *= effect.amplitudeMul as number
      if (effect.emotion !== undefined && effect.emotion !== null) out.emotion = effect.emotion
      if (effect.heightMul !== undefined) out.heightMul *= effect.heightMul as number
      if (effect.distanceMul !== undefined) out.distanceMul *= effect.distanceMul as number
      if (effect.direction !== undefined && effect.direction !== null) out.direction = effect.direction
      out.matched.push(effect.matched)
    }
  }
  return out
}

// v77zx: returns the per-rule raw effects matched in `text`, in declaration
// order. Used by parseCustomMotionPrompt to dedupe modifier tags between
// global-scope and segment-scope so "marche rapidement" applies "rapidement"
// once (1.6×) instead of twice (2.56×). Mirror of motion_parser.py
// _split_global_effects.
function splitGlobalEffects(text: string): Array<Partial<Omit<SegmentModifiers, 'matched'>> & { matched: string }> {
  const out: Array<Partial<Omit<SegmentModifiers, 'matched'>> & { matched: string }> = []
  for (const { rx, effect } of MODIFIER_RULES) {
    if (rx.test(text)) out.push(effect)
  }
  return out
}

function applyModifiersToPrimitive(p: KinematicPrimitive, mods: SegmentModifiers): KinematicPrimitive {
  const noChange = mods.speedMul === 1.0 && mods.amplitudeMul === 1.0 && mods.emotion === null
    && mods.heightMul === 1.0 && mods.distanceMul === 1.0 && mods.direction === null
  if (noChange) return p
  const out: KinematicPrimitive = { ...p }
  if (mods.speedMul !== 1.0 && typeof out.frequency_hz === 'number') {
    out.frequency_hz = +(out.frequency_hz * mods.speedMul).toFixed(4)
  }
  if (mods.amplitudeMul !== 1.0 && typeof out.amplitude === 'number') {
    out.amplitude = +(out.amplitude * mods.amplitudeMul).toFixed(4)
  }
  // v77zaa: spatial multipliers — height boosts jump amplitude (upward
  // ballistic) and vertical oscillate; distance boosts translate amplitude.
  if (mods.heightMul !== 1.0 && typeof out.amplitude === 'number'
      && (out.kind === 'jump' || (out.kind === 'oscillate' && out.axis === 'y'))) {
    out.amplitude = +(out.amplitude * mods.heightMul).toFixed(4)
  }
  if (mods.distanceMul !== 1.0 && typeof out.amplitude === 'number' && out.kind === 'translate') {
    out.amplitude = +(out.amplitude * mods.distanceMul).toFixed(4)
  }
  if (mods.emotion) {
    const emoTag = ` [emotion:${mods.emotion}]`
    out.description = (out.description || '') + emoTag
  }
  if (mods.direction) {
    const dirTag = ` [direction:${mods.direction}]`
    out.description = (out.description || '') + dirTag
  }
  return out
}

// ---------------------------------------------------------------------------
//  SUBJECT-CONSTRAINED PRESET RESOLUTION
// ---------------------------------------------------------------------------
// The verb table is subject-BLIND: "le loup marche" matched
// character.walk_cycle, a bipedal preset targeting `legs` (DEF-thigh/shin/foot)
// and `arms` (hand_ik.*). rigify_autorig.py builds a WOLF metarig for a
// quadruped/creature subject — no hand_ik, no upper_arm, front limbs named
// front_thigh_fk / front_shin_fk. The animal walked on its hind legs with its
// front legs frozen, silently.
//
// Invariant: THE PRESET FAMILY MUST MATCH THE METARIG FAMILY. The predicate
// below is the same one that drives metarig selection in aurora_3d_pipeline
// ("quadruped" | "creature" -> quadruped rig), so preset and skeleton cannot
// disagree. Only presets with a genuine four-legged counterpart are remapped;
// a gesture with no equivalent (punch, wave...) is left alone rather than
// invented. MIRROR of motion_parser.py QUADRUPED_PRESET_FOR.

export const QUADRUPED_PRESET_FOR: Record<string, string> = {
  'character.walk_cycle': 'creature.quadruped_walk',
  'character.run_cycle': 'creature.quadruped_run',
  'character.idle': 'creature.quadruped_idle',
  'character.jump': 'creature.quadruped_jump',
}

const QUADRUPED_KINDS = new Set(['quadruped', 'creature'])

/** True when this subject will be rigged on the quadruped (wolf) metarig. */
export function isQuadrupedSubject(subjectKind?: string | null): boolean {
  return QUADRUPED_KINDS.has(String(subjectKind ?? '').trim().toLowerCase())
}

/** Constrain a verb-matched preset by the subject's morphology. */
export function resolvePresetForSubject(
  presetId: string | null,
  subjectKind?: string | null,
): string | null {
  if (!presetId || !isQuadrupedSubject(subjectKind)) return presetId
  return QUADRUPED_PRESET_FOR[presetId] ?? presetId
}

export function parseCustomMotionPrompt(
  rawPrompt: string,
  subjectKind?: string | null,
): MotionDescriptor | null {
  if (!rawPrompt || typeof rawPrompt !== 'string') return null
  const cleaned = rawPrompt.trim().replace(/\s+/g, ' ')
  if (cleaned.length < 3) return null

  const sequentialSegments = cleaned.split(SEQUENCE_SEPARATOR_RX).map((s) => s.trim()).filter(Boolean)

  type ParsedSegment = { presetId: string | null; segment: string }
  const sequenced: ParsedSegment[] = []

  for (const segment of sequentialSegments) {
    let matchedPreset: string | null = null
    for (const { rx, presetId } of VERB_TO_PRESET) {
      if (rx.test(segment)) {
        matchedPreset = presetId
        break
      }
    }
    // the subject's morphology overrides the verb's default family
    matchedPreset = resolvePresetForSubject(matchedPreset, subjectKind)
    sequenced.push({ presetId: matchedPreset, segment })
  }

  // If the entire prompt yielded zero matches AND there is no sequence /
  // parallel separator, this isn't a motion description — let the caller fall
  // back to the static motion-verb hint detector.
  const hasAnyMatch = sequenced.some((s) => s.presetId !== null)
  const hasSeparator = sequentialSegments.length > 1 || PARALLEL_SEPARATOR_RX.test(cleaned)
  if (!hasAnyMatch && !hasSeparator) return null

  const primitives: KinematicPrimitive[] = []
  let totalDuration = 0
  const parts: string[] = []
  const directiveParts: string[] = []

  // v77zx: when there's a single segment (no "puis"/"then" separator), the
  // whole prompt IS the segment — extracting both global and segment mods
  // would double-apply every modifier. Treat single-segment prompts as
  // segment-only; multi-segment prompts use global as a baseline that
  // individual segments override (compounding only when the global tag is
  // NOT already in the segment's matched set).
  const globalMods = sequenced.length > 1 ? extractSegmentModifiers(cleaned) : null
  const globalEffects = sequenced.length > 1 ? splitGlobalEffects(cleaned) : []

  for (const seg of sequenced) {
    const segmentMods = extractSegmentModifiers(seg.segment)
    let effective: SegmentModifiers
    if (!globalMods) {
      effective = segmentMods
    } else {
      // Dedupe by tag: a global modifier tag already present in the segment
      // is skipped so it's not applied twice.
      const seenTags = new Set(segmentMods.matched)
      let speedMul = segmentMods.speedMul
      let amplitudeMul = segmentMods.amplitudeMul
      let heightMul = segmentMods.heightMul
      let distanceMul = segmentMods.distanceMul
      let emotion = segmentMods.emotion
      let direction = segmentMods.direction
      for (let i = 0; i < globalMods.matched.length; i++) {
        const tag = globalMods.matched[i]
        if (seenTags.has(tag)) continue
        const e = globalEffects[i]
        if (e.speedMul !== undefined) speedMul *= e.speedMul as number
        if (e.amplitudeMul !== undefined) amplitudeMul *= e.amplitudeMul as number
        if (e.heightMul !== undefined) heightMul *= e.heightMul as number
        if (e.distanceMul !== undefined) distanceMul *= e.distanceMul as number
        if (!emotion && e.emotion) emotion = e.emotion
        if (!direction && e.direction) direction = e.direction
      }
      effective = {
        speedMul,
        amplitudeMul,
        heightMul,
        distanceMul,
        emotion,
        direction,
        matched: [...segmentMods.matched, ...globalMods.matched.filter((t) => !seenTags.has(t))],
      }
    }
    if (seg.presetId && ALL_PRESET_INDEX[seg.presetId]) {
      const preset = ALL_PRESET_INDEX[seg.presetId]
      // Deep-copy primitives so applying modifiers doesn't mutate the
      // shared preset object.
      const adjustedPrimitives = preset.primitives.map((p) => applyModifiersToPrimitive(p, effective))
      primitives.push(...adjustedPrimitives)
      totalDuration += (preset.duration_seconds || 1.0) / Math.max(0.1, effective.speedMul)
      const tag = effective.matched.length > 0 ? ` (${effective.matched.join(',')})` : ''
      parts.push(preset.label + tag)
      directiveParts.push(preset.promptDirective)
    } else {
      // Unknown verb segment — emit a custom_pose with the literal text.
      primitives.push({
        kind: 'custom_pose',
        description: seg.segment,
      })
      totalDuration += 1.5
      parts.push(seg.segment)
      directiveParts.push(`Then perform: "${seg.segment}" (interpret literally and faithfully).`)
    }
  }

  if (primitives.length === 0) return null

  return {
    id: 'custom.parsed',
    label: parts.join(' → '),
    description: `Sequence parsee depuis le prompt: ${parts.join(' puis ')}`,
    appliesTo: { subjectKind: ['character', 'creature'] },
    primitives,
    promptDirective: directiveParts.join(' Then ').slice(0, 1500),
    duration_seconds: Math.max(totalDuration, 0.5),
    loop: false,
    source: 'custom',
  }
}

// ---------------------------------------------------------------------------
//  PROMPT BLOCK BUILDER — emits a directive block to prepend to the FLUX
//  reference prompt for kinematic-aware subjects.
// ---------------------------------------------------------------------------

export function buildKinematicsDirectiveBlock(
  query: KinematicQuery,
  customMotion?: MotionDescriptor | null,
): string {
  if (customMotion) {
    return [
      'KINEMATIC MOTION CONTRACT (custom, parsed from user prompt):',
      `- Sequence: ${customMotion.label}`,
      `- Total duration: ${customMotion.duration_seconds.toFixed(1)}s, loop=${customMotion.loop}`,
      `- Primitives: ${customMotion.primitives.length} step(s)`,
      `- Reference pose: depict the most informative single frame of this sequence (typically mid-action) so the 3D pipeline can reconstruct the full motion downstream.`,
      `- Directive: ${customMotion.promptDirective}`,
    ].join('\n')
  }

  const presets = selectKinematicPresets(query)
  if (presets.length === 0) return ''

  const top = presets.slice(0, 3)
  return [
    'KINEMATIC MOTION CONTRACT (preset-aware):',
    `- Subject: ${query.subjectKind}, system: ${query.systemClass}`,
    `- ${presets.length} bakeable motion preset(s) available, top suggestions:`,
    ...top.map((p) => `  • ${p.id}: ${p.description}`),
    '- Reference image must depict the most informative kinematic frame (mid-cycle for loops, apex for ballistic actions).',
    '- All moving parts must be readable; static parts must remain anchored.',
  ].join('\n')
}
