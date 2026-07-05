import { create } from 'zustand'
import {
  DEFAULT_CAMERA,
  DEFAULT_MATERIAL,
  DEFAULT_PHYSICS,
  DEFAULT_QUALITY,
  DEFAULT_SOFTBODY,
  DEFAULT_TIMELINE,
  DEFAULT_TRANSFORM,
  emitterDefaults,
  fluidDefaults,
  forceFieldDefaults,
  geometryDefaults,
  lightDefaults,
  reactionDefaults,
  constraintDefaults,
} from './defaults'
import type {
  CameraState,
  ChemistryReactionConfig,
  ConstraintConfig,
  ConstraintKind,
  EntityTrack,
  EntityType,
  FluidConfig,
  ForceFieldConfig,
  ForceFieldKind,
  Keyframe,
  LightConfig,
  LightKind,
  MaterialDescriptor,
  ParticleEmitterConfig,
  PhysicsBody,
  PrimitiveKind,
  ReactionKind,
  SceneEntity,
  SceneSnapshot,
  SelectionState,
  SimulatorQuality,
  SimulatorTab,
  SoftBodyConfig,
  TimelineState,
  TransformState,
  Vec3,
} from './types'

const MAX_HISTORY = 40

function uid(prefix = 'ent'): string {
  const rand = Math.random().toString(36).slice(2, 10)
  const ts = Date.now().toString(36).slice(-4)
  return `${prefix}_${ts}${rand}`
}

function cloneEntity(entity: SceneEntity): SceneEntity {
  return JSON.parse(JSON.stringify(entity)) as SceneEntity
}

function cloneSnapshot(snapshot: SceneSnapshot): SceneSnapshot {
  return JSON.parse(JSON.stringify(snapshot)) as SceneSnapshot
}

export type SimulatorStore = {
  entities: SceneEntity[]
  selection: SelectionState
  camera: CameraState
  quality: SimulatorQuality
  timeline: TimelineState
  tracks: EntityTrack[]
  activeTab: SimulatorTab
  transformMode: 'translate' | 'rotate' | 'scale'
  snapEnabled: boolean
  snapTranslation: number
  snapRotation: number
  physicsRunning: boolean
  physicsStepRate: number
  past: SceneSnapshot[]
  future: SceneSnapshot[]
  lastAction: string

  addPrimitive: (kind: PrimitiveKind, position?: Vec3) => string
  addLight: (kind: LightKind, position?: Vec3) => string
  addForceField: (kind: ForceFieldKind, position?: Vec3) => string
  addEmitter: (preset: ParticleEmitterConfig['preset'], position?: Vec3) => string
  addFluid: (preset: FluidConfig['preset'], position?: Vec3) => string
  addReaction: (kind: ReactionKind, position?: Vec3) => string
  addConstraint: (kind: ConstraintKind) => string
  addRigidBodyWrapper: (entityId: string) => void
  addSoftBodyWrapper: (entityId: string) => void

  duplicate: (entityId: string) => string | null
  remove: (entityId: string) => void
  rename: (entityId: string, name: string) => void
  setVisible: (entityId: string, visible: boolean) => void
  setLocked: (entityId: string, locked: boolean) => void
  setParent: (entityId: string, parentId: string | null) => void
  setTransform: (entityId: string, patch: Partial<TransformState>) => void
  setGeometryParam: (entityId: string, key: string, value: number) => void
  setSubdivisions: (entityId: string, count: number) => void
  applyBevel: (entityId: string) => void
  applyRemesh: (entityId: string) => void
  setMaterial: (entityId: string, patch: Partial<MaterialDescriptor>) => void
  setPhysics: (entityId: string, patch: Partial<PhysicsBody>) => void
  setSoftBody: (entityId: string, patch: Partial<SoftBodyConfig>) => void
  setLight: (entityId: string, patch: Partial<LightConfig>) => void
  setForceField: (entityId: string, patch: Partial<ForceFieldConfig>) => void
  setEmitter: (entityId: string, patch: Partial<ParticleEmitterConfig>) => void
  setFluid: (entityId: string, patch: Partial<FluidConfig>) => void
  setReaction: (entityId: string, patch: Partial<ChemistryReactionConfig>) => void
  setConstraint: (entityId: string, patch: Partial<ConstraintConfig>) => void

  select: (id: string | null, additive?: boolean) => void
  clearSelection: () => void
  setCamera: (patch: Partial<CameraState>) => void
  setQuality: (patch: Partial<SimulatorQuality>) => void
  setTimeline: (patch: Partial<TimelineState>) => void
  setActiveTab: (tab: SimulatorTab) => void
  setTransformMode: (mode: 'translate' | 'rotate' | 'scale') => void
  toggleSnap: () => void
  setSnap: (patch: { translation?: number; rotation?: number }) => void
  setPhysicsRunning: (running: boolean) => void

  addKeyframe: (entityId: string, kf: Keyframe) => void
  removeKeyframe: (entityId: string, time: number, property: string) => void

  undo: () => void
  redo: () => void
  pushHistory: (label: string) => void

  replaceScene: (snapshot: SceneSnapshot) => void
  exportSnapshot: () => SceneSnapshot
  resetScene: () => void
}

function initialSceneEntities(): SceneEntity[] {
  const floor: SceneEntity = {
    id: uid('ground'),
    name: 'Sol',
    type: 'mesh',
    visible: true,
    locked: false,
    parentId: null,
    transform: { position: [0, -0.05, 0], rotation: [0, 0, 0], scale: [1, 1, 1] },
    geometry: { ...geometryDefaults('plane'), params: { width: 20, height: 20, widthSegments: 1, heightSegments: 1 } },
    material: { ...DEFAULT_MATERIAL, albedo: '#1b2230', roughness: 0.9, metalness: 0.05 },
    physics: { ...DEFAULT_PHYSICS, enabled: true, kind: 'static', mass: 0, collider: 'plane', restitution: 0.1, friction: 0.7 },
    metadata: { role: 'ground' },
  }
  const sun: SceneEntity = {
    id: uid('light'),
    name: 'Soleil directionnel',
    type: 'light',
    visible: true,
    locked: false,
    parentId: null,
    transform: { position: [6, 8, 4], rotation: [0, 0, 0], scale: [1, 1, 1] },
    light: lightDefaults('sun'),
    metadata: {},
  }
  const ambient: SceneEntity = {
    id: uid('light'),
    name: 'Ambient',
    type: 'light',
    visible: true,
    locked: false,
    parentId: null,
    transform: { ...DEFAULT_TRANSFORM },
    light: lightDefaults('ambient'),
    metadata: {},
  }
  return [floor, sun, ambient]
}

function initialSelection(): SelectionState {
  return { selectedIds: [], primaryId: null }
}

function initialState() {
  return {
    entities: initialSceneEntities(),
    selection: initialSelection(),
    camera: { ...DEFAULT_CAMERA },
    quality: { ...DEFAULT_QUALITY },
    timeline: { ...DEFAULT_TIMELINE },
    tracks: [] as EntityTrack[],
    activeTab: 'modeling' as SimulatorTab,
    transformMode: 'translate' as const,
    snapEnabled: false,
    snapTranslation: 0.25,
    snapRotation: Math.PI / 36,
    physicsRunning: false,
    physicsStepRate: 60,
    past: [] as SceneSnapshot[],
    future: [] as SceneSnapshot[],
    lastAction: 'Initial',
  }
}

function buildSnapshot(state: SimulatorStore): SceneSnapshot {
  return {
    version: 1,
    entities: state.entities.map(cloneEntity),
    camera: { ...state.camera },
    quality: { ...state.quality },
    timeline: { ...state.timeline },
    tracks: state.tracks.map((track) => ({ entityId: track.entityId, keyframes: track.keyframes.map((kf) => ({ ...kf, value: Array.isArray(kf.value) ? [...kf.value] as Vec3 : kf.value })) })),
    activeTab: state.activeTab,
  }
}

export const useSimulatorStore = create<SimulatorStore>((set, get) => ({
  ...initialState(),

  addPrimitive: (kind, position = [0, 0.5, 0]) => {
    const id = uid(kind)
    const entity: SceneEntity = {
      id,
      name: kind.charAt(0).toUpperCase() + kind.slice(1),
      type: 'mesh',
      visible: true,
      locked: false,
      parentId: null,
      transform: { position: [...position], rotation: [0, 0, 0], scale: [1, 1, 1] },
      geometry: geometryDefaults(kind),
      material: { ...DEFAULT_MATERIAL },
      physics: { ...DEFAULT_PHYSICS },
      metadata: {},
    }
    get().pushHistory(`Ajout ${entity.name}`)
    set((state) => ({ entities: [...state.entities, entity], selection: { selectedIds: [id], primaryId: id } }))
    return id
  },

  addLight: (kind, position = [2, 3, 2]) => {
    const id = uid('light')
    const entity: SceneEntity = {
      id,
      name: `Lumiere ${kind}`,
      type: 'light',
      visible: true,
      locked: false,
      parentId: null,
      transform: { position: [...position], rotation: [0, 0, 0], scale: [1, 1, 1] },
      light: lightDefaults(kind),
      metadata: {},
    }
    get().pushHistory(`Ajout lumiere ${kind}`)
    set((state) => ({ entities: [...state.entities, entity], selection: { selectedIds: [id], primaryId: id } }))
    return id
  },

  addForceField: (kind, position = [0, 1, 0]) => {
    const id = uid('force')
    const entity: SceneEntity = {
      id,
      name: `Force ${kind}`,
      type: 'forceField',
      visible: true,
      locked: false,
      parentId: null,
      transform: { position: [...position], rotation: [0, 0, 0], scale: [1, 1, 1] },
      forceField: forceFieldDefaults(kind),
      metadata: {},
    }
    get().pushHistory(`Ajout champ ${kind}`)
    set((state) => ({ entities: [...state.entities, entity], selection: { selectedIds: [id], primaryId: id } }))
    return id
  },

  addEmitter: (preset, position = [0, 1, 0]) => {
    const id = uid('emit')
    const entity: SceneEntity = {
      id,
      name: `Emetteur ${preset}`,
      type: 'emitter',
      visible: true,
      locked: false,
      parentId: null,
      transform: { position: [...position], rotation: [0, 0, 0], scale: [1, 1, 1] },
      emitter: emitterDefaults(preset),
      metadata: {},
    }
    get().pushHistory(`Ajout emetteur ${preset}`)
    set((state) => ({ entities: [...state.entities, entity], selection: { selectedIds: [id], primaryId: id } }))
    return id
  },

  addFluid: (preset, position = [0, 1, 0]) => {
    const id = uid('fluid')
    const entity: SceneEntity = {
      id,
      name: `Fluide ${preset}`,
      type: 'fluid',
      visible: true,
      locked: false,
      parentId: null,
      transform: { position: [...position], rotation: [0, 0, 0], scale: [1, 1, 1] },
      fluid: fluidDefaults(preset),
      metadata: {},
    }
    get().pushHistory(`Ajout fluide ${preset}`)
    set((state) => ({ entities: [...state.entities, entity], selection: { selectedIds: [id], primaryId: id } }))
    return id
  },

  addReaction: (kind, position = [0, 0.5, 0]) => {
    const id = uid('rxn')
    const entity: SceneEntity = {
      id,
      name: `Reaction ${kind}`,
      type: 'reaction',
      visible: true,
      locked: false,
      parentId: null,
      transform: { position: [...position], rotation: [0, 0, 0], scale: [1, 1, 1] },
      reaction: reactionDefaults(kind),
      metadata: {},
    }
    get().pushHistory(`Ajout reaction ${kind}`)
    set((state) => ({ entities: [...state.entities, entity], selection: { selectedIds: [id], primaryId: id } }))
    return id
  },

  addConstraint: (kind) => {
    const id = uid('joint')
    const entity: SceneEntity = {
      id,
      name: `Contrainte ${kind}`,
      type: 'constraint',
      visible: true,
      locked: false,
      parentId: null,
      transform: { ...DEFAULT_TRANSFORM },
      constraint: constraintDefaults(kind),
      metadata: {},
    }
    get().pushHistory(`Ajout contrainte ${kind}`)
    set((state) => ({ entities: [...state.entities, entity], selection: { selectedIds: [id], primaryId: id } }))
    return id
  },

  addRigidBodyWrapper: (entityId) => {
    const entity = get().entities.find((e) => e.id === entityId)
    if (!entity) return
    get().pushHistory(`Activation rigid body ${entity.name}`)
    set((state) => ({
      entities: state.entities.map((e) => e.id === entityId ? { ...e, physics: { ...(e.physics ?? DEFAULT_PHYSICS), enabled: true, kind: 'dynamic' } } : e),
    }))
  },

  addSoftBodyWrapper: (entityId) => {
    const entity = get().entities.find((e) => e.id === entityId)
    if (!entity) return
    get().pushHistory(`Activation soft body ${entity.name}`)
    set((state) => ({
      entities: state.entities.map((e) => e.id === entityId ? { ...e, softBody: { ...(e.softBody ?? DEFAULT_SOFTBODY), enabled: true } } : e),
    }))
  },

  duplicate: (entityId) => {
    const entity = get().entities.find((e) => e.id === entityId)
    if (!entity) return null
    const clone = cloneEntity(entity)
    clone.id = uid(entity.type)
    clone.name = `${entity.name} (copie)`
    clone.transform.position = [entity.transform.position[0] + 0.5, entity.transform.position[1], entity.transform.position[2] + 0.5]
    get().pushHistory(`Duplication ${entity.name}`)
    set((state) => ({ entities: [...state.entities, clone], selection: { selectedIds: [clone.id], primaryId: clone.id } }))
    return clone.id
  },

  remove: (entityId) => {
    const entity = get().entities.find((e) => e.id === entityId)
    if (!entity) return
    get().pushHistory(`Suppression ${entity.name}`)
    set((state) => ({
      entities: state.entities.filter((e) => e.id !== entityId && e.parentId !== entityId),
      selection: state.selection.primaryId === entityId ? initialSelection() : { ...state.selection, selectedIds: state.selection.selectedIds.filter((id) => id !== entityId) },
      tracks: state.tracks.filter((t) => t.entityId !== entityId),
    }))
  },

  rename: (entityId, name) => {
    set((state) => ({ entities: state.entities.map((e) => e.id === entityId ? { ...e, name } : e) }))
  },

  setVisible: (entityId, visible) => {
    set((state) => ({ entities: state.entities.map((e) => e.id === entityId ? { ...e, visible } : e) }))
  },

  setLocked: (entityId, locked) => {
    set((state) => ({ entities: state.entities.map((e) => e.id === entityId ? { ...e, locked } : e) }))
  },

  setParent: (entityId, parentId) => {
    if (entityId === parentId) return
    set((state) => ({ entities: state.entities.map((e) => e.id === entityId ? { ...e, parentId } : e) }))
  },

  setTransform: (entityId, patch) => {
    set((state) => ({ entities: state.entities.map((e) => e.id === entityId ? { ...e, transform: { ...e.transform, ...patch } } : e) }))
  },

  setGeometryParam: (entityId, key, value) => {
    set((state) => ({
      entities: state.entities.map((e) => {
        if (e.id !== entityId || !e.geometry) return e
        return { ...e, geometry: { ...e.geometry, params: { ...e.geometry.params, [key]: value } } }
      }),
    }))
  },

  setSubdivisions: (entityId, count) => {
    set((state) => ({
      entities: state.entities.map((e) => {
        if (e.id !== entityId || !e.geometry) return e
        return { ...e, geometry: { ...e.geometry, subdivisions: Math.max(0, Math.min(5, count)) } }
      }),
    }))
  },

  applyBevel: (entityId) => {
    set((state) => ({
      entities: state.entities.map((e) => {
        if (e.id !== entityId || !e.geometry) return e
        return { ...e, geometry: { ...e.geometry, beveled: true, bevelSegments: Math.max(2, e.geometry.bevelSegments || 3) } }
      }),
    }))
  },

  applyRemesh: (entityId) => {
    set((state) => ({
      entities: state.entities.map((e) => {
        if (e.id !== entityId || !e.geometry) return e
        return { ...e, geometry: { ...e.geometry, remeshed: true, subdivisions: Math.max(1, e.geometry.subdivisions) } }
      }),
    }))
  },

  setMaterial: (entityId, patch) => {
    set((state) => ({
      entities: state.entities.map((e) => e.id === entityId && e.material ? { ...e, material: { ...e.material, ...patch } } : e),
    }))
  },

  setPhysics: (entityId, patch) => {
    set((state) => ({
      entities: state.entities.map((e) => e.id === entityId ? { ...e, physics: { ...(e.physics ?? DEFAULT_PHYSICS), ...patch } } : e),
    }))
  },

  setSoftBody: (entityId, patch) => {
    set((state) => ({
      entities: state.entities.map((e) => e.id === entityId ? { ...e, softBody: { ...(e.softBody ?? DEFAULT_SOFTBODY), ...patch } } : e),
    }))
  },

  setLight: (entityId, patch) => {
    set((state) => ({
      entities: state.entities.map((e) => {
        if (e.id !== entityId || !e.light) return e
        return { ...e, light: { ...e.light, ...patch } }
      }),
    }))
  },

  setForceField: (entityId, patch) => {
    set((state) => ({
      entities: state.entities.map((e) => {
        if (e.id !== entityId || !e.forceField) return e
        return { ...e, forceField: { ...e.forceField, ...patch } }
      }),
    }))
  },

  setEmitter: (entityId, patch) => {
    set((state) => ({
      entities: state.entities.map((e) => {
        if (e.id !== entityId || !e.emitter) return e
        return { ...e, emitter: { ...e.emitter, ...patch } }
      }),
    }))
  },

  setFluid: (entityId, patch) => {
    set((state) => ({
      entities: state.entities.map((e) => {
        if (e.id !== entityId || !e.fluid) return e
        return { ...e, fluid: { ...e.fluid, ...patch } }
      }),
    }))
  },

  setReaction: (entityId, patch) => {
    set((state) => ({
      entities: state.entities.map((e) => {
        if (e.id !== entityId || !e.reaction) return e
        return { ...e, reaction: { ...e.reaction, ...patch } }
      }),
    }))
  },

  setConstraint: (entityId, patch) => {
    set((state) => ({
      entities: state.entities.map((e) => {
        if (e.id !== entityId || !e.constraint) return e
        return { ...e, constraint: { ...e.constraint, ...patch } }
      }),
    }))
  },

  select: (id, additive = false) => {
    set((state) => {
      if (!id) return { selection: initialSelection() }
      if (additive) {
        const already = state.selection.selectedIds.includes(id)
        const next = already ? state.selection.selectedIds.filter((x) => x !== id) : [...state.selection.selectedIds, id]
        return { selection: { selectedIds: next, primaryId: next[next.length - 1] ?? null } }
      }
      return { selection: { selectedIds: [id], primaryId: id } }
    })
  },

  clearSelection: () => set({ selection: initialSelection() }),

  setCamera: (patch) => set((state) => ({ camera: { ...state.camera, ...patch } })),

  setQuality: (patch) => set((state) => ({ quality: { ...state.quality, ...patch } })),

  setTimeline: (patch) => set((state) => ({ timeline: { ...state.timeline, ...patch } })),

  setActiveTab: (tab) => set({ activeTab: tab }),

  setTransformMode: (mode) => set({ transformMode: mode }),

  toggleSnap: () => set((state) => ({ snapEnabled: !state.snapEnabled })),

  setSnap: (patch) => set((state) => ({ snapTranslation: patch.translation ?? state.snapTranslation, snapRotation: patch.rotation ?? state.snapRotation })),

  setPhysicsRunning: (running) => set({ physicsRunning: running }),

  addKeyframe: (entityId, kf) => {
    set((state) => {
      const existing = state.tracks.find((t) => t.entityId === entityId)
      if (existing) {
        const filtered = existing.keyframes.filter((k) => !(k.time === kf.time && k.property === kf.property))
        const updated = { ...existing, keyframes: [...filtered, kf].sort((a, b) => a.time - b.time) }
        return { tracks: state.tracks.map((t) => t.entityId === entityId ? updated : t) }
      }
      return { tracks: [...state.tracks, { entityId, keyframes: [kf] }] }
    })
  },

  removeKeyframe: (entityId, time, property) => {
    set((state) => ({
      tracks: state.tracks.map((t) => t.entityId === entityId ? { ...t, keyframes: t.keyframes.filter((k) => !(k.time === time && k.property === property)) } : t).filter((t) => t.keyframes.length > 0),
    }))
  },

  pushHistory: (label) => {
    const snapshot = buildSnapshot(get())
    set((state) => ({
      past: [...state.past.slice(-MAX_HISTORY + 1), snapshot],
      future: [],
      lastAction: label,
    }))
  },

  undo: () => {
    const { past, future } = get()
    if (past.length === 0) return
    const present = buildSnapshot(get())
    const last = past[past.length - 1]
    const remaining = past.slice(0, -1)
    const clone = cloneSnapshot(last)
    set({
      entities: clone.entities,
      camera: clone.camera,
      quality: clone.quality,
      timeline: clone.timeline,
      tracks: clone.tracks,
      activeTab: clone.activeTab,
      past: remaining,
      future: [present, ...future].slice(0, MAX_HISTORY),
      lastAction: 'Undo',
    })
  },

  redo: () => {
    const { past, future } = get()
    if (future.length === 0) return
    const present = buildSnapshot(get())
    const next = future[0]
    const remaining = future.slice(1)
    const clone = cloneSnapshot(next)
    set({
      entities: clone.entities,
      camera: clone.camera,
      quality: clone.quality,
      timeline: clone.timeline,
      tracks: clone.tracks,
      activeTab: clone.activeTab,
      past: [...past, present].slice(-MAX_HISTORY),
      future: remaining,
      lastAction: 'Redo',
    })
  },

  replaceScene: (snapshot) => {
    const present = buildSnapshot(get())
    const clone = cloneSnapshot(snapshot)
    set((state) => ({
      entities: clone.entities,
      camera: clone.camera,
      quality: clone.quality,
      timeline: clone.timeline,
      tracks: clone.tracks,
      activeTab: clone.activeTab,
      selection: initialSelection(),
      past: [...state.past, present].slice(-MAX_HISTORY),
      future: [],
      lastAction: 'Chargement scene',
    }))
  },

  exportSnapshot: () => buildSnapshot(get()),

  resetScene: () => {
    const present = buildSnapshot(get())
    set((state) => ({
      ...initialState(),
      past: [...state.past, present].slice(-MAX_HISTORY),
      lastAction: 'Reset scene',
    }))
  },
}))

export type { EntityType }
