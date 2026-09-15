import type {
  CameraState,
  ChemistryReactionConfig,
  ConstraintConfig,
  FluidConfig,
  ForceFieldConfig,
  ForceFieldKind,
  GeometryDescriptor,
  LightConfig,
  LightKind,
  MaterialDescriptor,
  ParticleEmitterConfig,
  PhysicsBody,
  PrimitiveKind,
  ReactionKind,
  SimulatorQuality,
  SoftBodyConfig,
  TimelineState,
  TransformState,
} from './types.ts'

export const DEFAULT_TRANSFORM: TransformState = {
  position: [0, 0, 0],
  rotation: [0, 0, 0],
  scale: [1, 1, 1],
}

export const DEFAULT_MATERIAL: MaterialDescriptor = {
  albedo: '#9aa4ff',
  roughness: 0.55,
  metalness: 0.1,
  emissive: '#000000',
  emissiveIntensity: 0,
  transmission: 0,
  ior: 1.5,
  thickness: 0.5,
  clearcoat: 0,
  clearcoatRoughness: 0.2,
  opacity: 1,
  wireframe: false,
  flatShading: false,
  normalScale: 1,
  albedoMap: null,
  normalMap: null,
  roughnessMap: null,
  side: 'front',
}

export const DEFAULT_PHYSICS: PhysicsBody = {
  enabled: false,
  kind: 'dynamic',
  mass: 1,
  friction: 0.4,
  restitution: 0.2,
  linearDamping: 0.04,
  angularDamping: 0.1,
  collider: 'convexHull',
  velocity: [0, 0, 0],
  angularVelocity: [0, 0, 0],
  gravityScale: 1,
  locked: { x: false, y: false, z: false, rx: false, ry: false, rz: false },
}

export const DEFAULT_SOFTBODY: SoftBodyConfig = {
  enabled: false,
  stiffness: 0.9,
  damping: 0.2,
  pressure: 0,
  iterations: 8,
  resolution: 12,
}

export const DEFAULT_CAMERA: CameraState = {
  position: [5, 4, 6],
  target: [0, 0, 0],
  fov: 45,
  near: 0.1,
  far: 500,
  orthographic: false,
}

export const DEFAULT_QUALITY: SimulatorQuality = {
  shadows: true,
  ssao: false,
  bloom: false,
  toneMapping: 'aces',
  environment: 'studio',
  environmentIntensity: 0.9,
  fogEnabled: false,
  fogColor: '#0b1220',
  fogDensity: 0.02,
  targetFps: 60,
}

export const DEFAULT_TIMELINE: TimelineState = {
  currentFrame: 0,
  totalFrames: 240,
  fps: 60,
  playing: false,
  loop: true,
  recording: false,
}

export function geometryDefaults(kind: PrimitiveKind): GeometryDescriptor {
  switch (kind) {
    case 'cube':
      return { kind, params: { size: 1 }, subdivisions: 0, bevelSegments: 0, beveled: false, remeshed: false }
    case 'sphere':
      return { kind, params: { radius: 0.75, widthSegments: 32, heightSegments: 24 }, subdivisions: 0, bevelSegments: 0, beveled: false, remeshed: false }
    case 'cylinder':
      return { kind, params: { radiusTop: 0.5, radiusBottom: 0.5, height: 1.5, radialSegments: 32 }, subdivisions: 0, bevelSegments: 0, beveled: false, remeshed: false }
    case 'cone':
      return { kind, params: { radius: 0.6, height: 1.2, radialSegments: 32 }, subdivisions: 0, bevelSegments: 0, beveled: false, remeshed: false }
    case 'torus':
      return { kind, params: { radius: 0.7, tube: 0.22, radialSegments: 16, tubularSegments: 48 }, subdivisions: 0, bevelSegments: 0, beveled: false, remeshed: false }
    case 'plane':
      return { kind, params: { width: 4, height: 4, widthSegments: 1, heightSegments: 1 }, subdivisions: 0, bevelSegments: 0, beveled: false, remeshed: false }
    case 'capsule':
      return { kind, params: { radius: 0.35, length: 1, capSegments: 12, radialSegments: 20 }, subdivisions: 0, bevelSegments: 0, beveled: false, remeshed: false }
    case 'icosahedron':
      return { kind, params: { radius: 0.75, detail: 0 }, subdivisions: 0, bevelSegments: 0, beveled: false, remeshed: false }
    case 'tetrahedron':
      return { kind, params: { radius: 0.75, detail: 0 }, subdivisions: 0, bevelSegments: 0, beveled: false, remeshed: false }
    case 'bezier':
      return { kind, params: { segments: 32 }, subdivisions: 0, bevelSegments: 0, beveled: false, remeshed: false }
    case 'line':
      return { kind, params: { segments: 1 }, subdivisions: 0, bevelSegments: 0, beveled: false, remeshed: false }
    case 'spline':
      return { kind, params: { segments: 48, tension: 0.5 }, subdivisions: 0, bevelSegments: 0, beveled: false, remeshed: false }
  }
}

export function lightDefaults(kind: LightKind): LightConfig {
  const base = { color: '#ffffff', intensity: 1, distance: 0, decay: 2, angle: Math.PI / 6, penumbra: 0.2, castShadow: true }
  switch (kind) {
    case 'point':
      return { kind, ...base, intensity: 1.2, distance: 12 }
    case 'spot':
      return { kind, ...base, intensity: 1.8, distance: 18 }
    case 'directional':
      return { kind, ...base, intensity: 1.1 }
    case 'area':
      return { kind, ...base, intensity: 2, width: 2, height: 1 }
    case 'hemisphere':
      return { kind, ...base, skyColor: '#aec6ff', groundColor: '#2b1f1a', intensity: 0.6 }
    case 'sun':
      return { kind, ...base, intensity: 1.3, sunAzimuth: 0.6, sunElevation: 0.7 }
    case 'ambient':
      return { kind, ...base, intensity: 0.4 }
  }
}

export function forceFieldDefaults(kind: ForceFieldKind): ForceFieldConfig {
  switch (kind) {
    case 'gravity':
      return { kind, strength: 9.81, radius: 0, falloff: 'none', direction: [0, -1, 0] }
    case 'radial':
      return { kind, strength: 5, radius: 4, falloff: 'quadratic', direction: [0, 0, 0] }
    case 'vortex':
      return { kind, strength: 3, radius: 5, falloff: 'linear', direction: [0, 1, 0] }
    case 'drag':
      return { kind, strength: 0.35, radius: 0, falloff: 'none', direction: [0, 0, 0] }
    case 'wind':
      return { kind, strength: 2.5, radius: 0, falloff: 'none', direction: [1, 0, 0] }
  }
}

export function emitterDefaults(preset: ParticleEmitterConfig['preset']): ParticleEmitterConfig {
  const base: ParticleEmitterConfig = {
    preset,
    rate: 120,
    lifetime: 1.6,
    startSize: 0.1,
    endSize: 0.02,
    startColor: '#ffaa40',
    endColor: '#331800',
    startAlpha: 1,
    endAlpha: 0,
    initialSpeed: 2.5,
    spread: 0.5,
    gravityInfluence: 0.1,
    drag: 0.15,
    turbulence: 0.8,
    rotationSpeed: 0,
    billboard: true,
    trail: false,
    meshInstancing: false,
    maxParticles: 2048,
  }
  switch (preset) {
    case 'fire':
      return { ...base, startColor: '#ffd35a', endColor: '#200700', initialSpeed: 2.2, gravityInfluence: -0.2, turbulence: 1.0 }
    case 'smoke':
      return { ...base, startColor: '#a7a7a7', endColor: '#202020', startAlpha: 0.6, endAlpha: 0, initialSpeed: 1.2, gravityInfluence: -0.05, lifetime: 3 }
    case 'sparks':
      return { ...base, startColor: '#ffee8a', endColor: '#ff3800', startSize: 0.02, endSize: 0, initialSpeed: 6, lifetime: 0.6, gravityInfluence: 1, drag: 0.02, trail: true }
    case 'snow':
      return { ...base, startColor: '#ffffff', endColor: '#cfd8ff', startSize: 0.08, endSize: 0.06, initialSpeed: 0.4, gravityInfluence: 0.05, lifetime: 6, turbulence: 0.3 }
    case 'dust':
      return { ...base, startColor: '#8c7b61', endColor: '#191512', startSize: 0.15, endSize: 0.4, startAlpha: 0.35, endAlpha: 0, initialSpeed: 0.8, gravityInfluence: -0.02, lifetime: 4 }
    case 'explosion':
      return { ...base, startColor: '#ffeecc', endColor: '#2b0a00', startSize: 0.4, endSize: 0.05, initialSpeed: 9, lifetime: 1.2, rate: 600, gravityInfluence: 0.2 }
    case 'rocket':
      return { ...base, startColor: '#88ccff', endColor: '#221133', initialSpeed: 4, lifetime: 0.8, rate: 300, gravityInfluence: -0.3 }
    case 'plasma':
      return { ...base, startColor: '#ff55ff', endColor: '#1a0033', initialSpeed: 2, lifetime: 1.4, gravityInfluence: 0, turbulence: 1.8 }
    case 'custom':
      return base
  }
}

export function fluidDefaults(preset: FluidConfig['preset']): FluidConfig {
  switch (preset) {
    case 'water':
      return { preset, particleCount: 600, viscosity: 0.02, surfaceTension: 0.15, density: 1000, temperature: 20, gravity: 9.81, containerKind: 'box', containerSize: [3, 2.5, 3], render: 'metaballs' }
    case 'lava':
      return { preset, particleCount: 400, viscosity: 0.6, surfaceTension: 0.25, density: 2800, temperature: 1200, gravity: 9.81, containerKind: 'box', containerSize: [3, 2, 3], render: 'shader' }
    case 'honey':
      return { preset, particleCount: 400, viscosity: 1.2, surfaceTension: 0.4, density: 1420, temperature: 30, gravity: 9.81, containerKind: 'box', containerSize: [2, 2, 2], render: 'metaballs' }
    case 'smoke2d':
      return { preset, particleCount: 512, viscosity: 0.1, surfaceTension: 0, density: 1.2, temperature: 80, gravity: 0, containerKind: 'box', containerSize: [4, 4, 0.1], render: 'points' }
    case 'custom':
      return { preset, particleCount: 500, viscosity: 0.05, surfaceTension: 0.2, density: 1000, temperature: 20, gravity: 9.81, containerKind: 'box', containerSize: [3, 3, 3], render: 'points' }
  }
}

export function reactionDefaults(kind: ReactionKind): ChemistryReactionConfig {
  switch (kind) {
    case 'combustion_gasoline':
      return { kind, ignitionTemperature: 280, heatRelease: 47000, fuelMass: 1, oxidizerMass: 3.4, productColor: '#ff6a20', smokeColor: '#1a1a1a', flameColor: '#ffb347', sparkRate: 30, running: false, equation: '2 C8H18 + 25 O2 -> 16 CO2 + 18 H2O + energie' }
    case 'combustion_wood':
      return { kind, ignitionTemperature: 260, heatRelease: 18000, fuelMass: 1, oxidizerMass: 1.2, productColor: '#ffb347', smokeColor: '#3a2a1f', flameColor: '#ffd27a', sparkRate: 18, running: false, equation: 'cellulose + O2 -> CO2 + H2O + cendres + energie' }
    case 'combustion_magnesium':
      return { kind, ignitionTemperature: 473, heatRelease: 25000, fuelMass: 0.5, oxidizerMass: 0.33, productColor: '#ffffff', smokeColor: '#dddddd', flameColor: '#ffffff', sparkRate: 80, running: false, equation: '2 Mg + O2 -> 2 MgO + lumiere intense' }
    case 'electrolysis_water':
      return { kind, ignitionTemperature: 0, heatRelease: -285, fuelMass: 1, oxidizerMass: 0, productColor: '#a0d8ff', smokeColor: '#ffffff', flameColor: '#88ccff', sparkRate: 2, running: false, equation: '2 H2O -> 2 H2 + O2 (apport energie)' }
    case 'dissolution_nacl':
      return { kind, ignitionTemperature: 0, heatRelease: 3.87, fuelMass: 1, oxidizerMass: 0, productColor: '#cfe7ff', smokeColor: '#ffffff', flameColor: '#ffffff', sparkRate: 0, running: false, equation: 'NaCl(s) -> Na+(aq) + Cl-(aq)' }
    case 'precipitation_agcl':
      return { kind, ignitionTemperature: 0, heatRelease: 0, fuelMass: 1, oxidizerMass: 1, productColor: '#f0f0f0', smokeColor: '#ffffff', flameColor: '#ffffff', sparkRate: 0, running: false, equation: 'Ag+ + Cl- -> AgCl(s)' }
    case 'neutralization':
      return { kind, ignitionTemperature: 0, heatRelease: 55.8, fuelMass: 1, oxidizerMass: 1, productColor: '#b6f0ff', smokeColor: '#ffffff', flameColor: '#ffffff', sparkRate: 0, running: false, equation: 'HCl + NaOH -> NaCl + H2O + chaleur' }
    case 'thermite':
      return { kind, ignitionTemperature: 900, heatRelease: 3677, fuelMass: 1, oxidizerMass: 0.5, productColor: '#ffeaa0', smokeColor: '#2b1306', flameColor: '#ff5a1f', sparkRate: 120, running: false, equation: '2 Al + Fe2O3 -> Al2O3 + 2 Fe + energie' }
    case 'crystallization_salt':
      return { kind, ignitionTemperature: 0, heatRelease: 0, fuelMass: 1, oxidizerMass: 0, productColor: '#e8f4ff', smokeColor: '#ffffff', flameColor: '#ffffff', sparkRate: 0, running: false, equation: 'Na+(aq) + Cl-(aq) -> NaCl(s)' }
    case 'custom':
      return { kind, ignitionTemperature: 300, heatRelease: 10000, fuelMass: 1, oxidizerMass: 1, productColor: '#ffaa40', smokeColor: '#202020', flameColor: '#ffd27a', sparkRate: 20, running: false, equation: 'A + B -> C + energie' }
  }
}

export function constraintDefaults(kind: ConstraintConfig['kind']): ConstraintConfig {
  const base = { bodyA: null, bodyB: null, anchorA: [0, 0, 0] as const, anchorB: [0, 0, 0] as const, axis: [0, 1, 0] as const, stiffness: 0.8, damping: 0.1, limitMin: -Math.PI, limitMax: Math.PI }
  return { kind, ...base, anchorA: [0, 0, 0], anchorB: [0, 0, 0], axis: [0, 1, 0] }
}
