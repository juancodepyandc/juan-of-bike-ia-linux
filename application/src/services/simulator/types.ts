import type { Color } from 'three'

export type Vec3 = [number, number, number]
export type Vec4 = [number, number, number, number]

export type PrimitiveKind =
  | 'cube'
  | 'sphere'
  | 'cylinder'
  | 'cone'
  | 'torus'
  | 'plane'
  | 'capsule'
  | 'icosahedron'
  | 'tetrahedron'
  | 'bezier'
  | 'line'
  | 'spline'

export type LightKind =
  | 'point'
  | 'spot'
  | 'directional'
  | 'area'
  | 'hemisphere'
  | 'sun'
  | 'ambient'

export type ForceFieldKind =
  | 'gravity'
  | 'radial'
  | 'vortex'
  | 'drag'
  | 'wind'

export type EntityType =
  | 'mesh'
  | 'light'
  | 'camera'
  | 'emitter'
  | 'forceField'
  | 'rigidBody'
  | 'softBody'
  | 'fluid'
  | 'particle'
  | 'constraint'
  | 'reaction'
  | 'group'
  | 'curve'

export type TransformState = {
  position: Vec3
  rotation: Vec3
  scale: Vec3
}

export type MaterialDescriptor = {
  albedo: string
  roughness: number
  metalness: number
  emissive: string
  emissiveIntensity: number
  transmission: number
  ior: number
  thickness: number
  clearcoat: number
  clearcoatRoughness: number
  opacity: number
  wireframe: boolean
  flatShading: boolean
  normalScale: number
  albedoMap: string | null
  normalMap: string | null
  roughnessMap: string | null
  side: 'front' | 'back' | 'double'
}

export type GeometryDescriptor = {
  kind: PrimitiveKind
  params: Record<string, number>
  subdivisions: number
  bevelSegments: number
  beveled: boolean
  remeshed: boolean
  externalUrl?: string
}

export type ColliderShape = 'box' | 'sphere' | 'capsule' | 'cylinder' | 'convexHull' | 'mesh' | 'plane'

export type PhysicsBody = {
  enabled: boolean
  kind: 'static' | 'dynamic' | 'kinematic'
  mass: number
  friction: number
  restitution: number
  linearDamping: number
  angularDamping: number
  collider: ColliderShape
  velocity: Vec3
  angularVelocity: Vec3
  gravityScale: number
  locked: { x: boolean; y: boolean; z: boolean; rx: boolean; ry: boolean; rz: boolean }
}

export type SoftBodyConfig = {
  enabled: boolean
  stiffness: number
  damping: number
  pressure: number
  iterations: number
  resolution: number
}

export type LightConfig = {
  kind: LightKind
  color: string
  intensity: number
  distance: number
  decay: number
  angle: number
  penumbra: number
  castShadow: boolean
  skyColor?: string
  groundColor?: string
  sunAzimuth?: number
  sunElevation?: number
  width?: number
  height?: number
}

export type ForceFieldConfig = {
  kind: ForceFieldKind
  strength: number
  radius: number
  falloff: 'linear' | 'quadratic' | 'inverse' | 'none'
  direction: Vec3
}

export type ReactionKind =
  | 'combustion_gasoline'
  | 'combustion_wood'
  | 'combustion_magnesium'
  | 'electrolysis_water'
  | 'dissolution_nacl'
  | 'precipitation_agcl'
  | 'neutralization'
  | 'thermite'
  | 'crystallization_salt'
  | 'custom'

export type ChemistryReactionConfig = {
  kind: ReactionKind
  ignitionTemperature: number
  heatRelease: number
  fuelMass: number
  oxidizerMass: number
  productColor: string
  smokeColor: string
  flameColor: string
  sparkRate: number
  running: boolean
  equation: string
}

export type ParticleEmitterConfig = {
  preset:
    | 'fire'
    | 'smoke'
    | 'sparks'
    | 'snow'
    | 'dust'
    | 'explosion'
    | 'rocket'
    | 'plasma'
    | 'custom'
  rate: number
  lifetime: number
  startSize: number
  endSize: number
  startColor: string
  endColor: string
  startAlpha: number
  endAlpha: number
  initialSpeed: number
  spread: number
  gravityInfluence: number
  drag: number
  turbulence: number
  rotationSpeed: number
  billboard: boolean
  trail: boolean
  meshInstancing: boolean
  maxParticles: number
}

export type FluidConfig = {
  preset: 'water' | 'lava' | 'honey' | 'smoke2d' | 'custom'
  particleCount: number
  viscosity: number
  surfaceTension: number
  density: number
  temperature: number
  gravity: number
  containerKind: 'box' | 'sphere'
  containerSize: Vec3
  render: 'points' | 'metaballs' | 'shader'
}

export type ConstraintKind = 'fixed' | 'pointToPoint' | 'hinge' | 'slider' | 'spring'

export type ConstraintConfig = {
  kind: ConstraintKind
  bodyA: string | null
  bodyB: string | null
  anchorA: Vec3
  anchorB: Vec3
  axis: Vec3
  stiffness: number
  damping: number
  limitMin: number
  limitMax: number
}

export type Keyframe = {
  time: number
  property: string
  value: number | Vec3 | string
  interpolation: 'linear' | 'bezier' | 'step'
}

export type EntityTrack = {
  entityId: string
  keyframes: Keyframe[]
}

export type SceneEntity = {
  id: string
  name: string
  type: EntityType
  visible: boolean
  locked: boolean
  parentId: string | null
  transform: TransformState
  geometry?: GeometryDescriptor
  material?: MaterialDescriptor
  physics?: PhysicsBody
  softBody?: SoftBodyConfig
  light?: LightConfig
  forceField?: ForceFieldConfig
  reaction?: ChemistryReactionConfig
  emitter?: ParticleEmitterConfig
  fluid?: FluidConfig
  constraint?: ConstraintConfig
  metadata: Record<string, string | number | boolean>
}

export type CameraState = {
  position: Vec3
  target: Vec3
  fov: number
  near: number
  far: number
  orthographic: boolean
}

export type SimulatorQuality = {
  shadows: boolean
  ssao: boolean
  bloom: boolean
  toneMapping: 'none' | 'linear' | 'aces' | 'reinhard'
  environment: 'studio' | 'sunset' | 'dawn' | 'night' | 'warehouse' | 'forest' | 'city' | 'park'
  environmentIntensity: number
  fogEnabled: boolean
  fogColor: string
  fogDensity: number
  targetFps: number
}

export type TimelineState = {
  currentFrame: number
  totalFrames: number
  fps: number
  playing: boolean
  loop: boolean
  recording: boolean
}

export type HistoryEntry = {
  label: string
  snapshot: string
  timestamp: number
}

export type SelectionState = {
  selectedIds: string[]
  primaryId: string | null
}

export type SimulatorTab =
  | 'modeling'
  | 'physics'
  | 'fluids'
  | 'particles'
  | 'reactions'
  | 'shader'
  | 'animation'

export type SceneSnapshot = {
  version: number
  entities: SceneEntity[]
  camera: CameraState
  quality: SimulatorQuality
  timeline: TimelineState
  tracks: EntityTrack[]
  activeTab: SimulatorTab
}

export type ColorTriplet = { r: number; g: number; b: number }

export function colorToHex(color: Color): string {
  return `#${color.getHexString()}`
}
