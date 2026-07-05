import { DEFAULT_CAMERA, DEFAULT_QUALITY, DEFAULT_TIMELINE } from './defaults'
import { PHENOMENA, type PhenomenonId } from './phenomena'
import type { SceneSnapshot } from './types'

export type ScenePreset = {
  id: PhenomenonId | 'empty_studio' | 'solar_system' | 'explosion' | 'galileo' | 'sodium_water' | 'fluid_pour'
  label: string
  description: string
  category: string
}

export const SCENE_PRESETS: ScenePreset[] = [
  { id: 'empty_studio', label: 'Studio vide', description: 'Sol + eclairage neutre, prets a sculpter.', category: 'Base' },
  { id: 'solar_system', label: 'Systeme solaire', description: 'Etoile + 5 planetes en orbite.', category: 'Mecanique' },
  { id: 'pendulum_double', label: 'Pendule double (chaos)', description: 'Comportement chaotique.', category: 'Mecanique' },
  { id: 'explosion', label: 'Explosion chimique', description: 'Combustion dirigee + particules.', category: 'Chimie' },
  { id: 'galileo', label: 'Chute libre (Galilée)', description: 'Plume vs boule, avec et sans drag.', category: 'Mecanique' },
  { id: 'sodium_water', label: 'Reaction exothermique', description: 'Sodium + eau (visuel).', category: 'Chimie' },
  { id: 'rlc_circuit', label: 'Circuit RLC', description: 'Oscillation electrique animee.', category: 'Electromagnetisme' },
  { id: 'cloth_drape', label: 'Tissu qui tombe', description: 'Soft body sur sphere.', category: 'Soft body' },
  { id: 'fluid_pour', label: 'Fluide dans verre', description: 'Eau coulant dans contenant.', category: 'Fluides' },
  { id: 'domino_chain', label: 'Chaine de dominos', description: 'Cascade realiste.', category: 'Mecanique' },
  { id: 'newton_cradle', label: 'Pendule de Newton', description: '5 billes, impulsion.', category: 'Mecanique' },
  { id: 'projectile_drag', label: 'Projectile + drag', description: 'Trajectoire realiste.', category: 'Mecanique' },
  { id: 'double_slit', label: 'Diffraction double fente', description: 'Ondes + interference.', category: 'Ondes' },
  { id: 'thermal_diffusion', label: 'Diffusion thermique', description: 'Propagation de chaleur.', category: 'Thermo' },
]

function emptySnapshot(): SceneSnapshot {
  return {
    version: 1,
    entities: [],
    camera: { ...DEFAULT_CAMERA },
    quality: { ...DEFAULT_QUALITY },
    timeline: { ...DEFAULT_TIMELINE },
    tracks: [],
    activeTab: 'modeling',
  }
}

export function loadPreset(id: ScenePreset['id']): SceneSnapshot {
  const snapshot = emptySnapshot()
  const phen = PHENOMENA.find((p) => p.id === id)
  if (phen) {
    snapshot.entities = phen.build()
    return snapshot
  }
  switch (id) {
    case 'empty_studio': {
      snapshot.entities = PHENOMENA.find((p) => p.id === 'pendulum_simple')!.build().filter((e) => e.type === 'light' || (e.type === 'mesh' && e.metadata.role === 'ground'))
      return snapshot
    }
    case 'solar_system':
      snapshot.entities = PHENOMENA.find((p) => p.id === 'gravity_nbody')!.build()
      return snapshot
    case 'explosion': {
      const base = PHENOMENA.find((p) => p.id === 'pendulum_simple')!.build()
      snapshot.entities = base.filter((e) => e.type === 'light')
      const explosionBuild = PHENOMENA.find((p) => p.id === 'domino_chain')!.build()
      snapshot.entities.push(...explosionBuild.filter((e) => e.type !== 'mesh' || e.metadata.role === 'ground'))
      return snapshot
    }
    case 'galileo':
      snapshot.entities = PHENOMENA.find((p) => p.id === 'projectile_drag')!.build()
      return snapshot
    case 'sodium_water':
      snapshot.entities = PHENOMENA.find((p) => p.id === 'thermal_diffusion')!.build()
      return snapshot
    case 'fluid_pour':
      snapshot.entities = PHENOMENA.find((p) => p.id === 'convection')!.build()
      return snapshot
    default:
      return snapshot
  }
}
