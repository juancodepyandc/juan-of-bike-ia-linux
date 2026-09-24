import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type {
  AvatarEntry,
  GenerationJobState,
  ModuleId,
  ModuleAssetDefinition,
  ModuleAssetPackState,
  HardwareProfile,
  RuntimeServiceId,
  RuntimeServiceInfo,
  RuntimeTaskState,
  ServiceStatus,
  UserProfile,
} from '../types/app.ts'
import {
  DEFAULT_MAIN_MODEL,
  DEFAULT_VISION_MODEL,
  VISION_HIGH_QUALITY_MODEL,
  MAIN_FALLBACK_MODEL,
  detectBestMainModel,
  selectCodeModelForHardware,
  selectAdaptiveVisionModel,
  resolveConfiguredModel,
  selectAdaptiveReasoningModel,
  shouldPromoteToPrimaryMainModel,
} from '../config/models.ts'

const INITIAL_RUNTIME_SERVICES: Record<RuntimeServiceId, RuntimeServiceInfo> = {
  ollama: {
    id: 'ollama',
    label: 'Ollama',
    available: false,
    running: false,
    startedByApp: false,
    progress: 0,
    detail: 'Detection en attente.',
    path: null,
    processId: null,
  },
  comfyui: {
    id: 'comfyui',
    label: 'ComfyUI',
    available: false,
    running: false,
    startedByApp: false,
    progress: 0,
    detail: 'Detection en attente.',
    path: null,
    processId: null,
  },
}

const INITIAL_RUNTIME_TASK: RuntimeTaskState = {
  active: false,
  module: null,
  title: '',
  phase: 'idle',
  detail: 'Aucune session active.',
  progress: 0,
  startedAt: null,
  finishedAt: null,
  services: [],
  error: null,
  history: [],
}

function sanitizeRuntimeTaskForPersistence(_task?: RuntimeTaskState | null): RuntimeTaskState {
  return INITIAL_RUNTIME_TASK
}

function sanitizeGenerationJobsForPersistence(jobs?: GenerationJobState[] | null): GenerationJobState[] {
  return (jobs ?? [])
    .map((job) => {
      if (job.status !== 'queued' && job.status !== 'running') {
        return job
      }

      return {
        ...job,
        status: 'cancelled' as const,
        phase: 'done' as const,
        progress: 100,
        finishedAt: job.finishedAt ?? Date.now(),
        error: null,
        detail: 'Execution interrompue par un redemarrage de l application. La reprise doit etre relancee proprement.',
      }
    })
    .slice(0, 12)
}

function createInitialModuleAssetPack(module: ModuleId): ModuleAssetPackState {
  return {
    module,
    title: '',
    detail: 'Scan du pack modele en attente pour cette session.',
    status: 'idle',
    progress: 0,
    assets: [],
    lastCheckedAt: null,
    lastError: null,
  }
}

const INITIAL_MODULE_ASSET_PACKS: Record<ModuleId, ModuleAssetPackState> = {
  conversation: createInitialModuleAssetPack('conversation'),
  image: createInitialModuleAssetPack('image'),
  code: createInitialModuleAssetPack('code'),
  video: createInitialModuleAssetPack('video'),
  drawing: createInitialModuleAssetPack('drawing'),
  '3d': createInitialModuleAssetPack('3d'),
  learning: createInitialModuleAssetPack('learning'),
  voice: createInitialModuleAssetPack('voice'),
  cyber: createInitialModuleAssetPack('cyber'),
}

interface AppState {
  // Navigation
  activeModule: ModuleId
  setActiveModule: (id: ModuleId) => void
  sidebarCollapsed: boolean
  toggleSidebar: () => void
  focusMode: boolean
  setFocusMode: (value: boolean) => void
  toggleFocusMode: () => void

  // System
  hardware: HardwareProfile | null
  setHardware: (hw: HardwareProfile) => void
  services: ServiceStatus
  setServices: (s: ServiceStatus) => void
  checkingConfig: boolean
  setCheckingConfig: (v: boolean) => void
  runtimeServices: Record<RuntimeServiceId, RuntimeServiceInfo>
  setRuntimeServices: (next: Partial<Record<RuntimeServiceId, RuntimeServiceInfo>>) => void
  mergeRuntimeService: (id: RuntimeServiceId, patch: Partial<RuntimeServiceInfo>) => void
  runtimeTask: RuntimeTaskState
  setRuntimeTask: (patch: Partial<RuntimeTaskState>) => void
  resetRuntimeTask: () => void
  generationJobs: GenerationJobState[]
  addGenerationJob: (job: GenerationJobState) => void
  setGenerationJob: (jobId: string, patch: Partial<GenerationJobState>) => void
  pruneGenerationJobs: () => void
  moduleAssetPacks: Record<ModuleId, ModuleAssetPackState>
  hydrateModuleAssetPack: (module: ModuleId, title: string, assets: ModuleAssetDefinition[]) => void
  setModuleAssetPack: (module: ModuleId, patch: Partial<ModuleAssetPackState>) => void
  setModuleAssetState: (module: ModuleId, assetId: string, patch: Partial<ModuleAssetPackState['assets'][number]>) => void
  resetModuleAssetPack: (module: ModuleId) => void

  // User profile
  profile: UserProfile | null
  setProfile: (p: UserProfile) => void

  // Wizard
  wizardVisible: boolean
  wizardStep: number
  setWizardVisible: (v: boolean) => void
  setWizardStep: (s: number) => void

  // Models
  installedModels: string[]
  setInstalledModels: (m: string[]) => void
  mainModel: string
  codeModel: string
  visionModel: string
  // Avatar
  selectedAvatarId: string
  avatarList: AvatarEntry[]
  setSelectedAvatar: (id: string) => void
  addAvatar: (entry: AvatarEntry) => void
  removeAvatar: (id: string) => void
  setMainModel: (m: string) => void
  setCodeModel: (m: string) => void
  setVisionModel: (m: string) => void
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      activeModule: 'conversation',
      setActiveModule: (id) => set({ activeModule: id === 'voice' ? 'conversation' : id }),
      sidebarCollapsed: false,
      toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
      focusMode: false,
      setFocusMode: (value) => set({ focusMode: value }),
      toggleFocusMode: () => set((state) => ({ focusMode: !state.focusMode })),

      hardware: null,
      setHardware: (hw) => set({ hardware: hw }),
      services: { ollama: false, comfyui: false },
      setServices: (s) => set({ services: s }),
      checkingConfig: false,
      setCheckingConfig: (v) => set({ checkingConfig: v }),
      runtimeServices: INITIAL_RUNTIME_SERVICES,
      setRuntimeServices: (next) => set({ runtimeServices: {
        ollama: { ...INITIAL_RUNTIME_SERVICES.ollama, ...next.ollama },
        comfyui: { ...INITIAL_RUNTIME_SERVICES.comfyui, ...next.comfyui },
      } }),
      mergeRuntimeService: (id, patch) =>
        set((state) => ({
          runtimeServices: {
            ...state.runtimeServices,
            [id]: {
              ...state.runtimeServices[id],
              ...patch,
            },
          },
        })),
      runtimeTask: INITIAL_RUNTIME_TASK,
      setRuntimeTask: (patch) =>
        set((state) => {
          const nextTask = {
            ...state.runtimeTask,
            ...patch,
          }

          const shouldTrackHistory =
            nextTask.active &&
            Boolean(nextTask.detail) &&
            (
              patch.detail !== undefined ||
              patch.phase !== undefined ||
              patch.progress !== undefined
            )

          if (shouldTrackHistory) {
            const lastEntry = state.runtimeTask.history[state.runtimeTask.history.length - 1]
            const phase = nextTask.phase
            const detail = nextTask.detail
            const progress = nextTask.progress

            if (
              !lastEntry ||
              lastEntry.phase !== phase ||
              lastEntry.detail !== detail ||
              lastEntry.progress !== progress
            ) {
              nextTask.history = [
                ...state.runtimeTask.history,
                {
                  id: `runtime-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
                  phase,
                  detail,
                  progress,
                  timestamp: Date.now(),
                },
              ].slice(-14)
            } else {
              nextTask.history = state.runtimeTask.history
            }
          } else if (!nextTask.active) {
            nextTask.history = []
          } else {
            nextTask.history = state.runtimeTask.history
          }

          return {
            runtimeTask: nextTask,
          }
        }),
      resetRuntimeTask: () => set({ runtimeTask: INITIAL_RUNTIME_TASK }),
      generationJobs: [],
      addGenerationJob: (job) =>
        set((state) => ({
          generationJobs: [job, ...state.generationJobs].slice(0, 20),
        })),
      setGenerationJob: (jobId, patch) =>
        set((state) => ({
          generationJobs: state.generationJobs.map((job) => {
            if (job.id !== jobId) {
              return job
            }

            const nextJob = {
              ...job,
              ...patch,
            }

            const shouldTrackHistory =
              nextJob.status !== 'queued'
              && Boolean(nextJob.detail)
              && (
                patch.detail !== undefined
                || patch.phase !== undefined
                || patch.progress !== undefined
              )

            if (shouldTrackHistory) {
              const lastEntry = job.history[job.history.length - 1]
              const phase = nextJob.phase
              const detail = nextJob.detail
              const progress = nextJob.progress

              if (
                !lastEntry
                || lastEntry.phase !== phase
                || lastEntry.detail !== detail
                || lastEntry.progress !== progress
              ) {
                nextJob.history = [
                  ...job.history,
                  {
                    id: `job-${Date.now()}-${job.history.length}`,
                    phase,
                    detail,
                    progress,
                    timestamp: Date.now(),
                  },
                ].slice(-16)
              } else {
                nextJob.history = job.history
              }
            } else {
              nextJob.history = job.history
            }

            return nextJob
          }),
        })),
      pruneGenerationJobs: () =>
        set((state) => ({
          generationJobs: [...state.generationJobs]
            .sort((a, b) => {
              const aTime = a.finishedAt || a.startedAt || a.createdAt
              const bTime = b.finishedAt || b.startedAt || b.createdAt
              return bTime - aTime
            })
            .slice(0, 12),
        })),
      moduleAssetPacks: INITIAL_MODULE_ASSET_PACKS,
      hydrateModuleAssetPack: (module, title, assets) =>
        set((state) => {
          const currentPack = state.moduleAssetPacks[module] || createInitialModuleAssetPack(module)
          const previousById = new Map(currentPack.assets.map((asset) => [asset.id, asset]))
          const nextAssets = assets.map((asset) => {
            const previous = previousById.get(asset.id)
            const assetChanged =
              !previous
              || previous.target !== asset.target
              || previous.destination !== asset.destination
              || previous.repoId !== asset.repoId
              || previous.filename !== asset.filename

            if (!previous || assetChanged) {
              return {
                ...asset,
                status: 'idle' as const,
                progress: 0,
                path: null,
                lastCheckedAt: null,
                error: null,
              }
            }

            return {
              ...previous,
              ...asset,
            }
          })

          const packUnchanged =
            currentPack.title === title
            && currentPack.assets.length === nextAssets.length
            && currentPack.assets.every((asset, index) => {
              const nextAsset = nextAssets[index]
              return (
                asset.id === nextAsset.id
                && asset.label === nextAsset.label
                && asset.kind === nextAsset.kind
                && asset.target === nextAsset.target
                && asset.detail === nextAsset.detail
                && asset.repoId === nextAsset.repoId
                && asset.filename === nextAsset.filename
                && asset.destination === nextAsset.destination
                && asset.path === nextAsset.path
                && asset.status === nextAsset.status
                && asset.progress === nextAsset.progress
                && asset.lastCheckedAt === nextAsset.lastCheckedAt
                && asset.error === nextAsset.error
              )
            })

          if (packUnchanged) {
            return state
          }

          return {
            moduleAssetPacks: {
              ...state.moduleAssetPacks,
              [module]: {
                ...currentPack,
                title,
                assets: nextAssets,
                detail: currentPack.detail || 'Scan du pack modele en attente pour cette session.',
              },
            },
          }
        }),
      setModuleAssetPack: (module, patch) =>
        set((state) => ({
          moduleAssetPacks: {
            ...state.moduleAssetPacks,
            [module]: {
              ...(state.moduleAssetPacks[module] || createInitialModuleAssetPack(module)),
              ...patch,
            },
          },
        })),
      setModuleAssetState: (module, assetId, patch) =>
        set((state) => ({
          moduleAssetPacks: {
            ...state.moduleAssetPacks,
            [module]: {
              ...(state.moduleAssetPacks[module] || createInitialModuleAssetPack(module)),
              assets: (state.moduleAssetPacks[module]?.assets || []).map((asset) =>
                asset.id === assetId
                  ? {
                      ...asset,
                      ...patch,
                    }
                  : asset,
              ),
            },
          },
        })),
      resetModuleAssetPack: (module) =>
        set((state) => ({
          moduleAssetPacks: {
            ...state.moduleAssetPacks,
            [module]: createInitialModuleAssetPack(module),
          },
        })),

      profile: null,
      setProfile: (p) => set({ profile: p }),

      wizardVisible: false,
      wizardStep: 0,
      setWizardVisible: (v) => set({ wizardVisible: v }),
      setWizardStep: (s) => set({ wizardStep: s }),

      installedModels: [],
      setInstalledModels: (m) => set((state) => {
        const bestMain = detectBestMainModel(m)
        const userExplicitlyChose = state.mainModel !== DEFAULT_MAIN_MODEL
          && state.mainModel !== selectAdaptiveReasoningModel(state.hardware, DEFAULT_MAIN_MODEL, MAIN_FALLBACK_MODEL)
        return {
          installedModels: m,
          mainModel: userExplicitlyChose ? state.mainModel : bestMain,
          codeModel: selectCodeModelForHardware(state.hardware, m, state.codeModel),
        }
      }),
      mainModel: selectAdaptiveReasoningModel(null, DEFAULT_MAIN_MODEL, MAIN_FALLBACK_MODEL),
      codeModel: selectCodeModelForHardware(null),
      visionModel: VISION_HIGH_QUALITY_MODEL,  // qwen3-vl:30b par defaut (qualite max)
      // Avatar
      selectedAvatarId: 'aurora-procedural',
      avatarList: [
        {
          id: 'aurora-procedural',
          label: 'Aurora',
          type: 'procedural' as const,
          path: JSON.stringify({ skin: '#f0c9a0', eyes: '#4a9eff', hair: '#2c1b0e' }),
          thumbnail: null,
          builtIn: true,
          createdAt: null,
        },
        {
          id: 'pixel-procedural',
          label: 'Pixel',
          type: 'procedural' as const,
          path: JSON.stringify({ skin: '#c68a56', eyes: '#22c55e', hair: '#0f0f0f' }),
          thumbnail: null,
          builtIn: true,
          createdAt: null,
        },
        {
          id: 'stella-procedural',
          label: 'Stella',
          type: 'procedural' as const,
          path: JSON.stringify({ skin: '#f8dac8', eyes: '#a855f7', hair: '#daa520' }),
          thumbnail: null,
          builtIn: true,
          createdAt: null,
        },
        {
          id: 'natsu-dragneel',
          label: 'Natsu',
          type: 'glb-static' as const,
          path: '/avatars/natsu-dragneel.glb',
          thumbnail: null,
          builtIn: true,
          createdAt: null,
        },
      ],
      setSelectedAvatar: (id) => set({ selectedAvatarId: id }),
      addAvatar: (entry) => set((s) => ({ avatarList: [...s.avatarList, entry] })),
      removeAvatar: (id) => set((s) => ({
        avatarList: s.avatarList.filter(a => a.id !== id),
        selectedAvatarId: s.selectedAvatarId === id ? 'aurora-procedural' : s.selectedAvatarId,
      })),
      setMainModel: (m) => set((state) => ({
        mainModel: resolveConfiguredModel(
          m,
          selectAdaptiveReasoningModel(state.hardware, DEFAULT_MAIN_MODEL, MAIN_FALLBACK_MODEL),
        ),
      })),
      setCodeModel: (m) => set((state) => ({
        codeModel: selectCodeModelForHardware(state.hardware, state.installedModels, m),
      })),
      setVisionModel: (m) => set({ visionModel: m }),
    }),
    {
      name: 'juan-bike-app-store',
      version: 8,
      migrate: (persistedState) => {
        const state = (persistedState ?? {}) as Partial<AppState> & { profile?: UserProfile | null }

        const safeMainFallback = selectAdaptiveReasoningModel(
          state.hardware || state.profile?.hardware || null,
          DEFAULT_MAIN_MODEL,
          MAIN_FALLBACK_MODEL,
        )
        const mainModel = shouldPromoteToPrimaryMainModel(state.mainModel)
          ? safeMainFallback
          : resolveConfiguredModel(state.mainModel, safeMainFallback)
        const codeModel = selectCodeModelForHardware(
          state.hardware || state.profile?.hardware || null,
          state.installedModels ?? [],
          state.codeModel,
        )
        const visionModel = selectAdaptiveVisionModel(
          state.hardware || state.profile?.hardware || null,
          state.visionModel,
          { preferQuality: true },
        )

        const profile = state.profile
          ? {
              ...state.profile,
              preferAdminMode: state.profile.preferAdminMode ?? true,
              preferredMainModel: shouldPromoteToPrimaryMainModel(state.profile.preferredMainModel)
                ? safeMainFallback
                : resolveConfiguredModel(state.profile.preferredMainModel, safeMainFallback),
              preferredCodeModel: selectCodeModelForHardware(
                state.hardware || state.profile?.hardware || null,
                state.installedModels ?? [],
                state.profile.preferredCodeModel,
              ),
              preferredVisionModel: selectAdaptiveVisionModel(
                state.hardware || state.profile?.hardware || null,
                state.profile.preferredVisionModel,
                { preferQuality: true },
              ),
            }
          : state.profile

        return {
          ...state,
          mainModel,
          codeModel,
          visionModel,
          profile,
          runtimeTask: sanitizeRuntimeTaskForPersistence(state.runtimeTask),
          generationJobs: sanitizeGenerationJobsForPersistence(state.generationJobs),
        } as AppState
      },
      partialize: (state) => ({
        activeModule: state.activeModule,
        sidebarCollapsed: state.sidebarCollapsed,
        profile: state.profile,
        mainModel: state.mainModel,
        codeModel: state.codeModel,
        visionModel: state.visionModel,
        selectedAvatarId: state.selectedAvatarId,
        avatarList: state.avatarList,
        focusMode: state.focusMode,
        runtimeTask: sanitizeRuntimeTaskForPersistence(state.runtimeTask),
        generationJobs: sanitizeGenerationJobsForPersistence(state.generationJobs),
      }),
    }
  )
)
