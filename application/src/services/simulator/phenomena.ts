import type { SceneEntity, Vec3 } from './types'
import { DEFAULT_MATERIAL, DEFAULT_PHYSICS, DEFAULT_TRANSFORM, emitterDefaults, fluidDefaults, forceFieldDefaults, geometryDefaults, lightDefaults, reactionDefaults, DEFAULT_SOFTBODY } from './defaults'

export type PhenomenonId =
  | 'pendulum_simple'
  | 'pendulum_double'
  | 'spring_damped'
  | 'projectile_drag'
  | 'elastic_collision'
  | 'gravity_nbody'
  | 'cloth_drape'
  | 'jello'
  | 'domino_chain'
  | 'newton_cradle'
  | 'light_prism'
  | 'wave_string'
  | 'wave_water'
  | 'double_slit'
  | 'thermal_diffusion'
  | 'convection'
  | 'rlc_circuit'
  | 'magnet_field'

export type PhenomenonDefinition = {
  id: PhenomenonId
  label: string
  category: 'Mecanique' | 'Fluides' | 'Thermo' | 'Ondes' | 'Electromagnetisme' | 'Optique'
  description: string
  build: () => SceneEntity[]
}

let nextId = 1
function id(prefix: string) {
  nextId += 1
  return `${prefix}_${Date.now().toString(36)}${nextId}`
}

function mesh(name: string, kind: Parameters<typeof geometryDefaults>[0], position: Vec3, opts: Partial<SceneEntity> = {}): SceneEntity {
  return {
    id: id(kind),
    name,
    type: 'mesh',
    visible: true,
    locked: false,
    parentId: null,
    transform: { ...DEFAULT_TRANSFORM, position: [...position] },
    geometry: geometryDefaults(kind),
    material: { ...DEFAULT_MATERIAL },
    physics: { ...DEFAULT_PHYSICS },
    metadata: {},
    ...opts,
  }
}

function ground(size = 20): SceneEntity {
  return {
    id: id('ground'),
    name: 'Sol',
    type: 'mesh',
    visible: true,
    locked: false,
    parentId: null,
    transform: { position: [0, -0.05, 0], rotation: [0, 0, 0], scale: [1, 1, 1] },
    geometry: { ...geometryDefaults('plane'), params: { width: size, height: size, widthSegments: 1, heightSegments: 1 } },
    material: { ...DEFAULT_MATERIAL, albedo: '#141822', roughness: 0.95 },
    physics: { ...DEFAULT_PHYSICS, enabled: true, kind: 'static', collider: 'plane' },
    metadata: {},
  }
}

function sun(): SceneEntity {
  return { id: id('sun'), name: 'Soleil', type: 'light', visible: true, locked: false, parentId: null, transform: { ...DEFAULT_TRANSFORM, position: [5, 8, 4] }, light: lightDefaults('sun'), metadata: {} }
}

function ambient(): SceneEntity {
  return { id: id('amb'), name: 'Ambient', type: 'light', visible: true, locked: false, parentId: null, transform: DEFAULT_TRANSFORM, light: lightDefaults('ambient'), metadata: {} }
}

export const PHENOMENA: PhenomenonDefinition[] = [
  {
    id: 'pendulum_simple',
    label: 'Pendule simple',
    category: 'Mecanique',
    description: 'Masse suspendue a une corde, amortissement visible.',
    build: () => {
      const base = mesh('Pivot', 'sphere', [0, 3, 0], { physics: { ...DEFAULT_PHYSICS, enabled: true, kind: 'static' }, material: { ...DEFAULT_MATERIAL, albedo: '#888888' } })
      base.geometry = { ...geometryDefaults('sphere'), params: { radius: 0.1, widthSegments: 16, heightSegments: 12 } }
      const bob = mesh('Bob', 'sphere', [1.6, 1.5, 0], { physics: { ...DEFAULT_PHYSICS, enabled: true, kind: 'dynamic', mass: 1.5, collider: 'sphere' }, material: { ...DEFAULT_MATERIAL, albedo: '#ff5a1f' } })
      const joint: SceneEntity = { id: id('hinge'), name: 'Corde', type: 'constraint', visible: true, locked: false, parentId: null, transform: DEFAULT_TRANSFORM, constraint: { kind: 'pointToPoint', bodyA: base.id, bodyB: bob.id, anchorA: [0, 0, 0], anchorB: [0, 0, 0], axis: [0, 1, 0], stiffness: 1, damping: 0.02, limitMin: 0, limitMax: 0 }, metadata: {} }
      return [sun(), ambient(), base, bob, joint]
    },
  },
  {
    id: 'pendulum_double',
    label: 'Pendule double (chaos)',
    category: 'Mecanique',
    description: 'Deux segments articules, comportement chaotique.',
    build: () => {
      const pivot = mesh('Pivot', 'sphere', [0, 3.5, 0], { physics: { ...DEFAULT_PHYSICS, enabled: true, kind: 'static' }, material: { ...DEFAULT_MATERIAL, albedo: '#888' } })
      pivot.geometry = { ...geometryDefaults('sphere'), params: { radius: 0.1, widthSegments: 16, heightSegments: 12 } }
      const m1 = mesh('Masse 1', 'sphere', [1.2, 2.6, 0], { physics: { ...DEFAULT_PHYSICS, enabled: true, kind: 'dynamic', mass: 1, collider: 'sphere' }, material: { ...DEFAULT_MATERIAL, albedo: '#3aa4ff' } })
      const m2 = mesh('Masse 2', 'sphere', [2.4, 1.8, 0], { physics: { ...DEFAULT_PHYSICS, enabled: true, kind: 'dynamic', mass: 1, collider: 'sphere' }, material: { ...DEFAULT_MATERIAL, albedo: '#ff5a1f' } })
      return [sun(), ambient(), pivot, m1, m2]
    },
  },
  {
    id: 'spring_damped',
    label: 'Ressort amorti',
    category: 'Mecanique',
    description: 'Masse-ressort avec dissipation.',
    build: () => {
      const anchor = mesh('Point fixe', 'cube', [0, 3, 0], { physics: { ...DEFAULT_PHYSICS, enabled: true, kind: 'static' } })
      const bob = mesh('Masse', 'sphere', [0, 1, 0], { physics: { ...DEFAULT_PHYSICS, enabled: true, kind: 'dynamic', mass: 0.5, collider: 'sphere' }, material: { ...DEFAULT_MATERIAL, albedo: '#37c7bf' } })
      const joint: SceneEntity = { id: id('spring'), name: 'Ressort', type: 'constraint', visible: true, locked: false, parentId: null, transform: DEFAULT_TRANSFORM, constraint: { kind: 'spring', bodyA: anchor.id, bodyB: bob.id, anchorA: [0, 0, 0], anchorB: [0, 0, 0], axis: [0, 1, 0], stiffness: 120, damping: 2, limitMin: 0.5, limitMax: 3 }, metadata: {} }
      return [sun(), ambient(), ground(), anchor, bob, joint]
    },
  },
  {
    id: 'projectile_drag',
    label: 'Projectile avec drag',
    category: 'Mecanique',
    description: 'Balle lancee avec trainee d air.',
    build: () => {
      const ball = mesh('Projectile', 'sphere', [-4, 1, 0], { physics: { ...DEFAULT_PHYSICS, enabled: true, kind: 'dynamic', mass: 0.5, collider: 'sphere', velocity: [8, 6, 0], linearDamping: 0.2 } })
      const drag: SceneEntity = { id: id('drag'), name: 'Drag air', type: 'forceField', visible: true, locked: false, parentId: null, transform: DEFAULT_TRANSFORM, forceField: forceFieldDefaults('drag'), metadata: {} }
      return [sun(), ambient(), ground(), ball, drag]
    },
  },
  {
    id: 'elastic_collision',
    label: 'Collision elastique',
    category: 'Mecanique',
    description: 'Deux masses s entrechoquent.',
    build: () => {
      const a = mesh('Masse A', 'sphere', [-2, 0.5, 0], { physics: { ...DEFAULT_PHYSICS, enabled: true, kind: 'dynamic', mass: 2, collider: 'sphere', velocity: [3, 0, 0], restitution: 0.95 }, material: { ...DEFAULT_MATERIAL, albedo: '#ff5a1f' } })
      const b = mesh('Masse B', 'sphere', [2, 0.5, 0], { physics: { ...DEFAULT_PHYSICS, enabled: true, kind: 'dynamic', mass: 1, collider: 'sphere', restitution: 0.95 }, material: { ...DEFAULT_MATERIAL, albedo: '#3aa4ff' } })
      return [sun(), ambient(), ground(), a, b]
    },
  },
  {
    id: 'gravity_nbody',
    label: 'Systeme solaire (N corps)',
    category: 'Mecanique',
    description: 'Plusieurs corps en attraction mutuelle.',
    build: () => {
      const star = mesh('Etoile', 'sphere', [0, 0, 0], { physics: { ...DEFAULT_PHYSICS, enabled: true, kind: 'static', mass: 2000, collider: 'sphere' }, material: { ...DEFAULT_MATERIAL, albedo: '#ffd166', emissive: '#ffa730', emissiveIntensity: 1.5 } })
      star.geometry = { ...geometryDefaults('sphere'), params: { radius: 0.6, widthSegments: 32, heightSegments: 24 } }
      const planets: SceneEntity[] = []
      for (let i = 0; i < 5; i += 1) {
        const r = 2 + i * 0.8
        const angle = (i / 5) * Math.PI * 2
        const p = mesh(`Planete ${i + 1}`, 'sphere', [Math.cos(angle) * r, 0, Math.sin(angle) * r], { physics: { ...DEFAULT_PHYSICS, enabled: true, kind: 'dynamic', mass: 1, collider: 'sphere', velocity: [Math.sin(angle) * 2.5, 0, -Math.cos(angle) * 2.5], gravityScale: 0 }, material: { ...DEFAULT_MATERIAL, albedo: ['#37c7bf', '#ff6a3d', '#9aa4ff', '#ffd166', '#4dd5a4'][i] } })
        p.geometry = { ...geometryDefaults('sphere'), params: { radius: 0.25, widthSegments: 16, heightSegments: 12 } }
        planets.push(p)
      }
      return [ambient(), star, ...planets]
    },
  },
  {
    id: 'cloth_drape',
    label: 'Tissu qui tombe (Verlet)',
    category: 'Mecanique',
    description: 'Soft body tissu sur une sphere.',
    build: () => {
      const cloth = mesh('Tissu', 'plane', [0, 3, 0], { softBody: { ...DEFAULT_SOFTBODY, enabled: true, resolution: 20, stiffness: 0.95 }, material: { ...DEFAULT_MATERIAL, albedo: '#ff8aa0', side: 'double' } })
      cloth.geometry = { ...geometryDefaults('plane'), params: { width: 3, height: 3, widthSegments: 20, heightSegments: 20 } }
      const ball = mesh('Sphere', 'sphere', [0, 1, 0], { physics: { ...DEFAULT_PHYSICS, enabled: true, kind: 'static', collider: 'sphere' }, material: { ...DEFAULT_MATERIAL, albedo: '#9aa4ff' } })
      return [sun(), ambient(), ground(), ball, cloth]
    },
  },
  {
    id: 'jello',
    label: 'Jello (soft body)',
    category: 'Mecanique',
    description: 'Cube gelatineux qui rebondit.',
    build: () => {
      const jello = mesh('Jello', 'cube', [0, 4, 0], { softBody: { ...DEFAULT_SOFTBODY, enabled: true, stiffness: 0.6, resolution: 6 }, material: { ...DEFAULT_MATERIAL, albedo: '#ff88cc', transmission: 0.3, roughness: 0.2 } })
      return [sun(), ambient(), ground(), jello]
    },
  },
  {
    id: 'domino_chain',
    label: 'Chaine de dominos',
    category: 'Mecanique',
    description: '12 dominos en serie, premiere piece poussee.',
    build: () => {
      const dominos: SceneEntity[] = []
      for (let i = 0; i < 12; i += 1) {
        const d = mesh(`Domino ${i + 1}`, 'cube', [-4 + i * 0.6, 0.75, 0], { physics: { ...DEFAULT_PHYSICS, enabled: true, kind: 'dynamic', mass: 0.5, friction: 0.7, restitution: 0.05, velocity: i === 0 ? [2.5, 0, 0] : [0, 0, 0] }, material: { ...DEFAULT_MATERIAL, albedo: i === 0 ? '#ff5a1f' : '#f4f1ea' } })
        d.geometry = { ...geometryDefaults('cube'), params: { size: 1 } }
        d.transform.scale = [0.2, 1.4, 0.7]
        dominos.push(d)
      }
      return [sun(), ambient(), ground(), ...dominos]
    },
  },
  {
    id: 'newton_cradle',
    label: 'Pendule de Newton',
    category: 'Mecanique',
    description: '5 billes en ligne, conservation d impulsion.',
    build: () => {
      const balls: SceneEntity[] = []
      for (let i = 0; i < 5; i += 1) {
        const b = mesh(`Bille ${i + 1}`, 'sphere', [-0.8 + i * 0.4, 1, 0], { physics: { ...DEFAULT_PHYSICS, enabled: true, kind: 'dynamic', mass: 1, collider: 'sphere', restitution: 0.98, friction: 0.02, velocity: i === 0 ? [2, 0, 0] : [0, 0, 0] }, material: { ...DEFAULT_MATERIAL, albedo: '#c0c6d0', metalness: 0.9, roughness: 0.15 } })
        b.geometry = { ...geometryDefaults('sphere'), params: { radius: 0.2, widthSegments: 24, heightSegments: 18 } }
        balls.push(b)
      }
      return [sun(), ambient(), ground(), ...balls]
    },
  },
  {
    id: 'light_prism',
    label: 'Prisme (dispersion)',
    category: 'Optique',
    description: 'Prisme triangulaire et rayon incident.',
    build: () => {
      const prism = mesh('Prisme', 'tetrahedron', [0, 1, 0], { material: { ...DEFAULT_MATERIAL, albedo: '#ccddff', transmission: 0.9, roughness: 0.02, ior: 1.5, thickness: 1 } })
      prism.geometry = { ...geometryDefaults('tetrahedron'), params: { radius: 0.9, detail: 0 } }
      const source = mesh('Source', 'sphere', [-3, 1, 0], { material: { ...DEFAULT_MATERIAL, albedo: '#ffffff', emissive: '#ffffff', emissiveIntensity: 2.5 } })
      source.geometry = { ...geometryDefaults('sphere'), params: { radius: 0.1, widthSegments: 12, heightSegments: 8 } }
      return [ambient(), ground(), source, prism]
    },
  },
  {
    id: 'wave_string',
    label: 'Corde vibrante',
    category: 'Ondes',
    description: 'Soft body corde excitee.',
    build: () => {
      const rope = mesh('Corde', 'plane', [0, 2, 0], { softBody: { ...DEFAULT_SOFTBODY, enabled: true, resolution: 32, stiffness: 0.98 }, material: { ...DEFAULT_MATERIAL, albedo: '#ffcc00' } })
      rope.geometry = { ...geometryDefaults('plane'), params: { width: 6, height: 0.1, widthSegments: 32, heightSegments: 1 } }
      return [sun(), ambient(), ground(), rope]
    },
  },
  {
    id: 'wave_water',
    label: 'Onde sur eau',
    category: 'Ondes',
    description: 'Plan d eau module par sinus.',
    build: () => {
      const water = mesh('Eau', 'plane', [0, 0.2, 0], { material: { ...DEFAULT_MATERIAL, albedo: '#2a7dff', transmission: 0.6, roughness: 0.08, metalness: 0.2 }, metadata: { wave: 'sine' } })
      water.geometry = { ...geometryDefaults('plane'), params: { width: 6, height: 6, widthSegments: 48, heightSegments: 48 } }
      return [sun(), ambient(), water]
    },
  },
  {
    id: 'double_slit',
    label: 'Double fente',
    category: 'Ondes',
    description: 'Diffraction ondulatoire simulee.',
    build: () => {
      const wall = mesh('Paroi fentes', 'cube', [0, 1, 0], { material: { ...DEFAULT_MATERIAL, albedo: '#333333' } })
      wall.transform.scale = [0.1, 2, 3]
      const screen = mesh('Ecran', 'plane', [3, 1, 0], { material: { ...DEFAULT_MATERIAL, albedo: '#ffffff' } })
      screen.transform.rotation = [0, Math.PI / 2, 0]
      screen.geometry = { ...geometryDefaults('plane'), params: { width: 4, height: 4, widthSegments: 1, heightSegments: 1 } }
      return [sun(), ambient(), ground(), wall, screen]
    },
  },
  {
    id: 'thermal_diffusion',
    label: 'Diffusion thermique',
    category: 'Thermo',
    description: 'Barre avec source chaude a une extremite.',
    build: () => {
      const bar = mesh('Barre', 'cube', [0, 0.6, 0], { material: { ...DEFAULT_MATERIAL, albedo: '#888888', metalness: 0.9, roughness: 0.3 } })
      bar.transform.scale = [4, 0.4, 0.4]
      const source: SceneEntity = { id: id('rxn'), name: 'Source chaude', type: 'reaction', visible: true, locked: false, parentId: null, transform: { ...DEFAULT_TRANSFORM, position: [-1.8, 0.6, 0] }, reaction: { ...reactionDefaults('combustion_wood'), running: true, fuelMass: 100 }, metadata: {} }
      return [sun(), ambient(), ground(), bar, source]
    },
  },
  {
    id: 'convection',
    label: 'Convection thermique',
    category: 'Thermo',
    description: 'Fluide chauffe par le bas.',
    build: () => {
      const water: SceneEntity = { id: id('fluid'), name: 'Eau chauffee', type: 'fluid', visible: true, locked: false, parentId: null, transform: { ...DEFAULT_TRANSFORM, position: [0, 1, 0] }, fluid: fluidDefaults('water'), metadata: {} }
      const heat = mesh('Plaque chaude', 'cube', [0, 0.1, 0], { material: { ...DEFAULT_MATERIAL, albedo: '#ff5a1f', emissive: '#ff3300', emissiveIntensity: 1.5 } })
      heat.transform.scale = [3, 0.1, 3]
      return [sun(), ambient(), ground(), heat, water]
    },
  },
  {
    id: 'rlc_circuit',
    label: 'Circuit RLC',
    category: 'Electromagnetisme',
    description: 'Representation visuelle d un circuit oscillant.',
    build: () => {
      const r = mesh('R (resistance)', 'cylinder', [-2, 0.5, 0], { material: { ...DEFAULT_MATERIAL, albedo: '#d97a1f' } })
      const l = mesh('L (bobine)', 'torus', [0, 0.5, 0], { material: { ...DEFAULT_MATERIAL, albedo: '#37c7bf', metalness: 0.7 } })
      const c = mesh('C (condo)', 'cylinder', [2, 0.5, 0], { material: { ...DEFAULT_MATERIAL, albedo: '#ffd166' } })
      return [sun(), ambient(), ground(), r, l, c]
    },
  },
  {
    id: 'magnet_field',
    label: 'Champ magnetique',
    category: 'Electromagnetisme',
    description: 'Aimant + emetteur de particules chargees.',
    build: () => {
      const magnet = mesh('Aimant', 'cube', [0, 0.5, 0], { material: { ...DEFAULT_MATERIAL, albedo: '#b3001b' } })
      magnet.transform.scale = [1.2, 0.4, 0.4]
      const emitter: SceneEntity = { id: id('emit'), name: 'Particules chargees', type: 'emitter', visible: true, locked: false, parentId: null, transform: { ...DEFAULT_TRANSFORM, position: [-3, 1, 0] }, emitter: { ...emitterDefaults('plasma'), initialSpeed: 4 }, metadata: {} }
      const vortex: SceneEntity = { id: id('vortex'), name: 'Vortex magnetique', type: 'forceField', visible: true, locked: false, parentId: null, transform: { ...DEFAULT_TRANSFORM, position: [0, 1, 0] }, forceField: forceFieldDefaults('vortex'), metadata: {} }
      return [sun(), ambient(), ground(), magnet, emitter, vortex]
    },
  },
]

export function getPhenomenon(id: PhenomenonId): PhenomenonDefinition | undefined {
  return PHENOMENA.find((p) => p.id === id)
}
