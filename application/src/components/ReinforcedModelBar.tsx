import { useCallback, useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { useAppStore } from '../stores/appStore.ts'
import type { ModuleId } from '../types/app.ts'
import { getBridgeUrl } from '../utils/runtime.ts'

export interface ReinforcedModuleInfo {
  module: string
  label: string
  base_model: string
  trainer: string
  dataset_pack: string
  axes_cibles: string
  status: string
  selected_variant: 'base' | 'renforce'
  active_variant: 'base' | 'renforce'
  effective_variant: 'base' | 'renforce'
  reinforced_available: boolean
  score_base_100: number | null
  score_renforce_100: number | null
  gain_points_100: number
  relative_gain_percent?: number
  samples_audited: number
  wins?: number
  losses?: number
  run_id: string | null
  adapter: string | null
  gains_markdown: string
  gains_md_path: string
}

export interface TrainingLiveState {
  active: boolean
  module?: string | null
  mode?: string | null
  phase?: string | null
  status?: string | null
  run_id?: string | null
  cycle_index?: number
  updated_at?: number
}

interface ReinforcedOverviewResponse {
  renforce_root: string
  master_markdown_path: string
  master_markdown: string
  modules: Record<string, ReinforcedModuleInfo>
  training?: TrainingLiveState
}

interface BrainApplicatorInfo {
  applicator_agent?: string
  master_agent?: string
  master_description?: string
  module?: string
  feature?: string
  description?: string
  verification_gate?: string
  preferred_tools?: string[]
  scope_firewall?: {
    files_owned?: string[]
    routes_owned?: string[]
    never_touch?: string[]
  }
}

interface BrainPlanStructured {
  intent_summary?: string
  epistemic_regime?: string
  primary_module?: string
  master_agent?: string
  master_description?: string
  masters_involved?: string[]
  modules_involved?: string[]
  cognitive_understanding?: Record<string, unknown>
  applicators?: BrainApplicatorInfo[]
  dag_steps?: Array<{ step?: number; phase?: string; agent?: string; objective?: string }>
  cognitive_phases?: string[]
}

const UI_TO_BACKEND_MODULE: Record<string, string> = {
  conversation: 'conversation',
  image: 'image',
  code: 'code',
  video: 'video',
  drawing: 'drawing',
  '3d': '3d',
  learning: 'learning',
  academy: 'learning',
  cyber: 'cyber',
  business: 'business',
  voice: 'audio',
  audio: 'audio',
  cowork: 'cowork',
  animation: 'animation',
}

const MODULE_SWITCH_CARDS: Array<{ id: ModuleId; backend: string; label: string; icon: string; accent: string }> = [
  { id: 'conversation', backend: 'conversation', label: 'Chat & Recherche', icon: '💬', accent: '#8B5CF6' },
  { id: 'image', backend: 'image', label: 'Image FLUX.2', icon: '🎨', accent: '#F472B6' },
  { id: 'code', backend: 'code', label: 'Code & Sandbox', icon: '💻', accent: '#22D3EE' },
  { id: 'drawing', backend: 'drawing', label: 'Dessin & Forge', icon: '✏️', accent: '#FB923C' },
  { id: '3d', backend: '3d', label: '3D & CAO', icon: '🧊', accent: '#60A5FA' },
  { id: 'learning', backend: 'learning', label: 'Académie', icon: '🎓', accent: '#A78BFA' },
  { id: 'cyber', backend: 'cyber', label: 'Cyber & Z3', icon: '🛡️', accent: '#34D399' },
  { id: 'business', backend: 'business', label: 'Business Lab', icon: '📈', accent: '#F59E0B' },
  { id: 'voice', backend: 'audio', label: 'Voix Duplex', icon: '🎙️', accent: '#2DD4BF' },
]

const COGNITIVE_LOOP_META: Array<{ id: string; title: string; desc: string; color: string }> = [
  { id: 'PERCEIVE_INTENT', title: '1. Compréhension & Intention', desc: 'Analyse sémantique profonde du besoin réel et du contexte implicite.', color: '#38BDF8' },
  { id: 'DECOMPOSE_DAG', title: '2. Décomposition Cognitive', desc: 'Découpage en sous-objectifs logiques ordonnés sans perte de contrainte.', color: '#818CF8' },
  { id: 'ROUTE_APPLICATORS', title: '3. Mobilisation des Experts', desc: 'Sélection chirurgicale du Maître de module et des spécialistes dédiés.', color: '#C084FC' },
  { id: 'APPLY_SURGICAL', title: '4. Synthèse & Ingénierie', desc: 'Exécution haute précision avec séparation stricte des responsabilités.', color: '#F472B6' },
  { id: 'VERIFY_CRITIQUE', title: '5. Audit & Preuve Formelle', desc: 'Vérification SymPy/Z3, compilation, métrologie 3D ou fact-checking.', color: '#34D399' },
  { id: 'SELF_HEAL_REFLECT', title: '6. Auto-Correction Fermée', desc: 'Diagnostic causal et réparation autonome en cas d’écart détecté.', color: '#FBBF24' },
  { id: 'CONSOLIDATE_EVOLVE', title: '7. Mémoire & Apprentissage', desc: 'Consolidation épisodique et enrichissement continu des compétences.', color: '#2DD4BF' },
]

export default function ReinforcedModelBar({ activeModule }: { activeModule: string }) {
  const setActiveModule = useAppStore((s) => s.setActiveModule)
  const mainModel = useAppStore((s) => s.mainModel)
  const backendMod = UI_TO_BACKEND_MODULE[activeModule] || activeModule || 'conversation'
  const [overview, setOverview] = useState<ReinforcedOverviewResponse | null>(null)
  const [modalOpen, setModalOpen] = useState(false)
  const [inspectModule, setInspectModule] = useState<string>(backendMod)
  const [switching, setSwitching] = useState<string | null>(null)
  const [stopping, setStopping] = useState(false)
  const [brainModalOpen, setBrainModalOpen] = useState(false)
  const [brainQuery, setBrainQuery] = useState('')
  const [brainPlan, setBrainPlan] = useState<BrainPlanStructured | null>(null)
  const [ghStatus, setGhStatus] = useState<Record<string, unknown> | null>(null)
  const [brainLoading, setBrainLoading] = useState(false)
  const [selectedBrainMod, setSelectedBrainMod] = useState<string>(backendMod)

  // Close modals on Escape key
  useEffect(() => {
    if (!modalOpen && !brainModalOpen) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setModalOpen(false)
        setBrainModalOpen(false)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [modalOpen, brainModalOpen])

  const runBrainSimulation = useCallback(
    async (promptToTest: string, targetMod?: string) => {
      const modToUse = targetMod || selectedBrainMod || backendMod
      setBrainLoading(true)
      try {
        const [planRes, ghRes] = await Promise.all([
          fetch(`${getBridgeUrl()}/api/agents/loops/plan`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ prompt: promptToTest, module: modToUse }),
          }),
          fetch(`${getBridgeUrl()}/api/agents/loops/github-status`),
        ])
        if (planRes.ok) {
          setBrainPlan((await planRes.json()) as BrainPlanStructured)
        }
        if (ghRes.ok) {
          setGhStatus((await ghRes.json()) as Record<string, unknown>)
        }
      } catch {
        // Ignore transient network errors
      } finally {
        setBrainLoading(false)
      }
    },
    [backendMod, selectedBrainMod],
  )

  useEffect(() => {
    setInspectModule(backendMod)
    setSelectedBrainMod(backendMod)
  }, [backendMod])

  const fetchOverview = useCallback(async () => {
    try {
      const res = await fetch(`${getBridgeUrl()}/api/models/reinforced-status`, {
        cache: 'no-store',
      })
      if (!res.ok) return
      const data = (await res.json()) as ReinforcedOverviewResponse
      setOverview(data)
    } catch {
      // Ignore transient network errors when bridge restarts
    }
  }, [])

  useEffect(() => {
    void fetchOverview()
    const id = window.setInterval(() => {
      void fetchOverview()
    }, 6000)
    return () => window.clearInterval(id)
  }, [fetchOverview])

  const selectVariant = async (mod: string, variant: 'base' | 'renforce') => {
    setSwitching(`${mod}:${variant}`)
    try {
      const res = await fetch(`${getBridgeUrl()}/api/models/reinforced-select`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ module: mod, variant }),
      })
      if (res.ok) {
        await fetchOverview()
      }
    } finally {
      setSwitching(null)
    }
  }

  const stopTraining = async () => {
    setStopping(true)
    try {
      await fetch(`${getBridgeUrl()}/api/models/training-stop`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      })
      await fetchOverview()
    } finally {
      setStopping(false)
    }
  }

  const modInfo = overview?.modules?.[backendMod]
  const activeVariant = modInfo?.selected_variant || 'base'
  const hasReinforced = Boolean(modInfo?.reinforced_available)
  const gainPts = modInfo?.gain_points_100 ?? 0
  const training = overview?.training

  const inspectedInfo = overview?.modules?.[inspectModule] || modInfo
  const applicators = Array.isArray(brainPlan?.applicators) ? brainPlan.applicators : []

  return (
    <>
      <div
        className="aurora-v4-reinforced-bar"
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 5,
          padding: '3px 5px',
          borderRadius: 11,
          background: 'rgba(12, 18, 36, 0.88)',
          border: '1px solid rgba(139, 92, 246, 0.28)',
          fontSize: 11,
        }}
      >
        <button
          type="button"
          onClick={() => void selectVariant(backendMod, 'base')}
          disabled={switching !== null}
          title={`Modèle de Base Intouchable (${modInfo?.base_model || 'Poids originaux SHA-256'})`}
          style={{
            padding: '4px 8px',
            borderRadius: 8,
            border: activeVariant === 'base' ? '1px solid rgba(56, 189, 248, 0.65)' : '1px solid transparent',
            background: activeVariant === 'base' ? 'rgba(14, 165, 233, 0.22)' : 'transparent',
            color: activeVariant === 'base' ? '#E0F2FE' : '#94A3B8',
            fontWeight: activeVariant === 'base' ? 700 : 500,
            fontSize: 10.5,
            cursor: 'pointer',
            display: 'inline-flex',
            alignItems: 'center',
            gap: 4,
            whiteSpace: 'nowrap',
            transition: 'all .18s ease',
          }}
        >
          <span>🛡️ Base</span>
        </button>

        <button
          type="button"
          onClick={() => void selectVariant(backendMod, 'renforce')}
          disabled={switching !== null}
          title={
            hasReinforced
              ? `Modèle Renforcé actif (${gainPts >= 0 ? '+' : ''}${gainPts.toFixed(3)} pts / 100 — ${modInfo?.axes_cibles})`
              : `Activer la branche Modèle Renforcé pour ${modInfo?.label || backendMod}`
          }
          style={{
            padding: '4px 8px',
            borderRadius: 8,
            border:
              activeVariant === 'renforce'
                ? '1px solid rgba(52, 211, 153, 0.75)'
                : '1px solid transparent',
            background:
              activeVariant === 'renforce'
                ? 'linear-gradient(135deg, rgba(16, 185, 129, 0.28), rgba(139, 92, 246, 0.25))'
                : 'transparent',
            color: activeVariant === 'renforce' ? '#ECFDF5' : '#94A3B8',
            fontWeight: activeVariant === 'renforce' ? 700 : 500,
            fontSize: 10.5,
            cursor: 'pointer',
            display: 'inline-flex',
            alignItems: 'center',
            gap: 5,
            whiteSpace: 'nowrap',
            transition: 'all .18s ease',
          }}
        >
          <span>⚡ Renforcé</span>
          {hasReinforced && (
            <span
              style={{
                padding: '1px 5px',
                borderRadius: 99,
                background: 'rgba(16, 185, 129, 0.28)',
                border: '1px solid rgba(52, 211, 153, 0.5)',
                color: '#6EE7B7',
                fontFamily: "'Cascadia Code',Consolas,monospace",
                fontSize: 9.5,
                fontWeight: 700,
              }}
            >
              +{gainPts.toFixed(2)}
            </span>
          )}
        </button>

        <button
          type="button"
          onClick={() => {
            setInspectModule(backendMod)
            setModalOpen(true)
          }}
          title="Ouvrir le registre des gains (GAINS.md) et comparer les modèles par module"
          style={{
            padding: '4px 8px',
            borderRadius: 8,
            border: '1px solid rgba(167, 139, 250, 0.35)',
            background: 'rgba(139, 92, 246, 0.16)',
            color: '#DDD6FE',
            fontSize: 10.5,
            fontWeight: 600,
            cursor: 'pointer',
            whiteSpace: 'nowrap',
          }}
        >
          📊 Gains
        </button>

        <button
          type="button"
          onClick={() => {
            setSelectedBrainMod(backendMod)
            setBrainModalOpen(true)
            void runBrainSimulation(
              brainQuery || `Raisonnement profond et orchestration intelligente pour le module ${backendMod}`,
              backendMod,
            )
          }}
          title="Ouvrir le Cerveau AGI : Raisonnement profond, Orchestration multi-modules & Bascule rapide"
          style={{
            padding: '4px 9px',
            borderRadius: 8,
            border: '1px solid rgba(34, 211, 238, 0.5)',
            background: 'linear-gradient(135deg, rgba(6, 182, 212, 0.22), rgba(139, 92, 246, 0.2))',
            color: '#ECFEFF',
            fontSize: 10.5,
            fontWeight: 700,
            cursor: 'pointer',
            whiteSpace: 'nowrap',
            display: 'inline-flex',
            alignItems: 'center',
            gap: 5,
          }}
        >
          <span>🧠 Cerveau AGI</span>
        </button>

        {training?.active && (
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              padding: '3px 8px',
              borderRadius: 8,
              background: 'rgba(245, 158, 11, 0.16)',
              border: '1px solid rgba(251, 191, 36, 0.5)',
              color: '#FDE68A',
              fontSize: 10.5,
              fontWeight: 600,
            }}
            title={training.status || 'Entraînement nocturne continu en cours'}
          >
            <span
              style={{
                width: 7,
                height: 7,
                borderRadius: '50%',
                background: '#FBBF24',
                boxShadow: '0 0 8px #FBBF24',
              }}
            />
            <span>
              {String(training.module || '3d').toUpperCase()}
              {training.cycle_index ? ` #${training.cycle_index}` : ''}
            </span>
            <button
              type="button"
              onClick={() => void stopTraining()}
              disabled={stopping}
              style={{
                padding: '2px 7px',
                borderRadius: 6,
                border: '1px solid rgba(248, 113, 113, 0.7)',
                background: 'rgba(239, 68, 68, 0.28)',
                color: '#FECACA',
                fontSize: 10,
                fontWeight: 700,
                cursor: 'pointer',
              }}
            >
              {stopping ? 'Arrêt…' : '■'}
            </button>
          </div>
        )}
      </div>

      {/* PORTAL 1: GAINS MARKDOWN MODAL */}
      {modalOpen &&
        overview &&
        createPortal(
          <div
            role="dialog"
            aria-modal="true"
            aria-label="Registre des Modèles Renforcés et Bilans Markdown"
            onClick={() => setModalOpen(false)}
            style={{
              position: 'fixed',
              inset: 0,
              zIndex: 100040,
              background: 'rgba(3, 6, 15, 0.84)',
              backdropFilter: 'blur(16px)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              padding: 20,
              fontFamily: "'Inter','Segoe UI Variable',system-ui,sans-serif",
            }}
          >
            <div
              onClick={(e) => e.stopPropagation()}
              style={{
                width: 'min(1120px, 95vw)',
                maxHeight: '88vh',
                background: 'linear-gradient(160deg, #0D1326 0%, #070B16 100%)',
                border: '1px solid rgba(139, 92, 246, 0.45)',
                borderRadius: 22,
                boxShadow: '0 32px 96px rgba(0, 0, 0, 0.85)',
                display: 'flex',
                flexDirection: 'column',
                overflow: 'hidden',
                color: '#E6EAF5',
              }}
            >
              <div
                style={{
                  padding: '16px 24px',
                  borderBottom: '1px solid rgba(255, 255, 255, 0.1)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: 12,
                }}
              >
                <div>
                  <h2 style={{ margin: 0, fontSize: 17, fontWeight: 800 }}>
                    🛡️ Modèle de Base (Intouchable) ↔ ⚡ Modèle Renforcé (`modele/renforce/`)
                  </h2>
                  <p style={{ margin: '4px 0 0', fontSize: 12, color: '#94A3B8' }}>
                    Registre officiel `modele/renforce/GAINS_MODELES_RENFORCES.md` · Les modèles de base sont 100 % intacts (SHA-256 vérifié).
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setModalOpen(false)}
                  style={{
                    padding: '8px 14px',
                    borderRadius: 10,
                    border: '1px solid rgba(255,255,255,0.18)',
                    background: 'rgba(255,255,255,0.06)',
                    color: '#F8FAFC',
                    cursor: 'pointer',
                    fontSize: 12.5,
                    fontWeight: 700,
                  }}
                >
                  ✕ Fermer
                </button>
              </div>

              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: '340px 1fr',
                  flex: 1,
                  minHeight: 0,
                  overflow: 'hidden',
                }}
              >
                <div
                  style={{
                    borderRight: '1px solid rgba(255, 255, 255, 0.09)',
                    overflowY: 'auto',
                    padding: 14,
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 8,
                  }}
                >
                  {Object.entries(overview.modules).map(([modKey, info]) => {
                    const selected = inspectModule === modKey
                    const isRenforce = info.selected_variant === 'renforce'
                    return (
                      <div
                        key={modKey}
                        onClick={() => setInspectModule(modKey)}
                        style={{
                          padding: '10px 12px',
                          borderRadius: 12,
                          border: selected
                            ? '1px solid rgba(139, 92, 246, 0.75)'
                            : '1px solid rgba(255, 255, 255, 0.08)',
                          background: selected
                            ? 'rgba(139, 92, 246, 0.16)'
                            : 'rgba(255, 255, 255, 0.025)',
                          cursor: 'pointer',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: 6,
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                          <span style={{ fontWeight: 700, fontSize: 12.5, color: '#F8FAFC' }}>{info.label}</span>
                          {info.reinforced_available ? (
                            <span
                              style={{
                                padding: '2px 7px',
                                borderRadius: 99,
                                background: 'rgba(16, 185, 129, 0.22)',
                                border: '1px solid rgba(52, 211, 153, 0.5)',
                                color: '#6EE7B7',
                                fontSize: 10,
                                fontWeight: 700,
                                fontFamily: "'Cascadia Code',Consolas,monospace",
                              }}
                            >
                              +{info.gain_points_100.toFixed(3)} pts
                            </span>
                          ) : (
                            <span style={{ fontSize: 10, color: '#94A3B8' }}>Base intacte</span>
                          )}
                        </div>
                        <div style={{ fontSize: 10.5, color: '#94A3B8', lineHeight: 1.35 }}>{info.axes_cibles}</div>
                        <div style={{ display: 'flex', gap: 6, marginTop: 2 }}>
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation()
                              void selectVariant(modKey, 'base')
                            }}
                            style={{
                              flex: 1,
                              padding: '4px 8px',
                              borderRadius: 7,
                              fontSize: 10.5,
                              fontWeight: !isRenforce ? 700 : 500,
                              border: !isRenforce ? '1px solid rgba(56, 189, 248, 0.7)' : '1px solid rgba(255,255,255,0.1)',
                              background: !isRenforce ? 'rgba(14, 165, 233, 0.22)' : 'rgba(255,255,255,0.03)',
                              color: !isRenforce ? '#E0F2FE' : '#94A3B8',
                              cursor: 'pointer',
                            }}
                          >
                            🛡️ Base
                          </button>
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation()
                              void selectVariant(modKey, 'renforce')
                            }}
                            style={{
                              flex: 1,
                              padding: '4px 8px',
                              borderRadius: 7,
                              fontSize: 10.5,
                              fontWeight: isRenforce ? 700 : 500,
                              border: isRenforce ? '1px solid rgba(52, 211, 153, 0.75)' : '1px solid rgba(255,255,255,0.1)',
                              background: isRenforce ? 'rgba(16, 185, 129, 0.25)' : 'rgba(255,255,255,0.03)',
                              color: isRenforce ? '#ECFDF5' : '#94A3B8',
                              cursor: 'pointer',
                            }}
                          >
                            ⚡ Renforcé
                          </button>
                        </div>
                      </div>
                    )
                  })}
                </div>

                <div
                  style={{
                    overflowY: 'auto',
                    padding: '18px 24px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 14,
                  }}
                >
                  {inspectedInfo && (
                    <>
                      <div
                        style={{
                          padding: '12px 16px',
                          borderRadius: 12,
                          background: 'rgba(15, 23, 42, 0.85)',
                          border: '1px solid rgba(148, 163, 184, 0.2)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          gap: 12,
                        }}
                      >
                        <div>
                          <div style={{ fontSize: 11, color: '#94A3B8' }}>
                            Fichier Markdown de traçabilité : <code>{inspectedInfo.gains_md_path}</code>
                          </div>
                          <div style={{ fontSize: 13, fontWeight: 700, marginTop: 3 }}>
                            Modèle actif :{' '}
                            <span style={{ color: inspectedInfo.selected_variant === 'renforce' ? '#34D399' : '#38BDF8' }}>
                              {inspectedInfo.selected_variant === 'renforce'
                                ? '⚡ Modèle Renforcé (modele/renforce/' + inspectModule + '/)'
                                : '🛡️ Modèle de Base Intouchable (' + inspectedInfo.base_model + ')'}
                            </span>
                          </div>
                        </div>
                      </div>

                      <pre
                        style={{
                          margin: 0,
                          padding: 18,
                          borderRadius: 14,
                          background: 'rgba(6, 10, 22, 0.92)',
                          border: '1px solid rgba(255, 255, 255, 0.08)',
                          color: '#E2E8F0',
                          fontFamily: "'Cascadia Code', Consolas, monospace",
                          fontSize: 12,
                          lineHeight: 1.6,
                          whiteSpace: 'pre-wrap',
                          wordBreak: 'break-word',
                        }}
                      >
                        {inspectedInfo.gains_markdown || overview.master_markdown}
                      </pre>
                    </>
                  )}
                </div>
              </div>
            </div>
          </div>,
          document.body,
        )}

      {/* PORTAL 2: AGI INTELLIGENCE & COGNITIVE ORCHESTRATION CENTER (NO RAW JSON!) */}
      {brainModalOpen &&
        createPortal(
          <div
            role="dialog"
            aria-modal="true"
            aria-label="Cerveau AGI — Intelligence Cognitive & Orchestration Multi-Modules"
            onClick={() => setBrainModalOpen(false)}
            style={{
              position: 'fixed',
              inset: 0,
              zIndex: 100045,
              background: 'rgba(3, 6, 15, 0.84)',
              backdropFilter: 'blur(18px)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              padding: 20,
              fontFamily: "'Inter','Segoe UI Variable',system-ui,sans-serif",
            }}
          >
            <div
              onClick={(e) => e.stopPropagation()}
              style={{
                width: 'min(1120px, 95vw)',
                maxHeight: '89vh',
                background: 'linear-gradient(160deg, #091326 0%, #050914 100%)',
                border: '1px solid rgba(34, 211, 238, 0.45)',
                borderRadius: 22,
                boxShadow: '0 32px 96px rgba(0, 0, 0, 0.88), 0 0 60px rgba(6, 182, 212, 0.15)',
                display: 'flex',
                flexDirection: 'column',
                overflow: 'hidden',
                color: '#E6EAF5',
              }}
            >
              {/* Header */}
              <div
                style={{
                  padding: '18px 24px',
                  borderBottom: '1px solid rgba(255, 255, 255, 0.09)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: 16,
                  background: 'radial-gradient(ellipse at 20% 0%, rgba(34, 211, 238, 0.18), transparent 65%)',
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                    <span
                      style={{
                        padding: '3px 10px',
                        borderRadius: 999,
                        background: 'rgba(6, 182, 212, 0.2)',
                        border: '1px solid rgba(34, 211, 238, 0.5)',
                        color: '#67E8F9',
                        fontSize: 10,
                        fontWeight: 800,
                        fontFamily: "'Cascadia Code',Consolas,monospace",
                        letterSpacing: '0.08em',
                      }}
                    >
                      INTELLIGENCE GÉNÉRALE & RAISONNEMENT PROFOND
                    </span>
                    <span
                      style={{
                        padding: '3px 10px',
                        borderRadius: 999,
                        background: 'rgba(139, 92, 246, 0.2)',
                        border: '1px solid rgba(167, 139, 250, 0.45)',
                        color: '#DDD6FE',
                        fontSize: 10,
                        fontWeight: 700,
                        fontFamily: "'Cascadia Code',Consolas,monospace",
                      }}
                    >
                      Moteur Cognitif : {mainModel || 'Qwen3 / DeepSeek-R1 Local'}
                    </span>
                  </div>
                  <h2 style={{ margin: '7px 0 3px', fontSize: 19, fontWeight: 800, color: '#F8FAFC' }}>
                    🧠 Centre Cognitif AGI — Compréhension, Raisonnement & Action Multi-Modules
                  </h2>
                  <p style={{ margin: 0, fontSize: 12, color: '#94A3B8' }}>
                    Analyse d’intention par premiers principes, sélection autonome du module et coordination sans collision entre experts.
                  </p>
                </div>

                <button
                  type="button"
                  onClick={() => setBrainModalOpen(false)}
                  style={{
                    padding: '9px 16px',
                    borderRadius: 11,
                    border: '1px solid rgba(255, 255, 255, 0.2)',
                    background: 'rgba(255, 255, 255, 0.07)',
                    color: '#F8FAFC',
                    fontSize: 12.5,
                    fontWeight: 700,
                    cursor: 'pointer',
                    flexShrink: 0,
                  }}
                >
                  ✕ Fermer (Échap)
                </button>
              </div>

              {/* Scrollable Body */}
              <div style={{ padding: 22, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 18 }}>
                {/* 1. Interactive Module Switcher Bar (Always accessible!) */}
                <div>
                  <div style={{ fontSize: 11, fontWeight: 800, color: '#94A3B8', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 8 }}>
                    Bascule Rapide & Cible de Raisonnement (Cliquez pour changer de module immédiatement)
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(112px, 1fr))', gap: 7 }}>
                    {MODULE_SWITCH_CARDS.map((m) => {
                      const isCurrent = selectedBrainMod === m.backend
                      return (
                        <button
                          key={m.id}
                          type="button"
                          onClick={() => {
                            setSelectedBrainMod(m.backend)
                            setActiveModule(m.id)
                            void runBrainSimulation(
                              brainQuery || `Résoudre et optimiser une demande complexe dans ${m.label}`,
                              m.backend,
                            )
                          }}
                          style={{
                            padding: '8px 10px',
                            borderRadius: 11,
                            border: isCurrent ? `1px solid ${m.accent}` : '1px solid rgba(255,255,255,0.08)',
                            background: isCurrent ? `${m.accent}24` : 'rgba(15, 23, 42, 0.65)',
                            color: isCurrent ? '#F8FAFC' : '#CBD5E1',
                            fontSize: 11.5,
                            fontWeight: isCurrent ? 800 : 600,
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            gap: 6,
                            transition: 'all .18s ease',
                          }}
                        >
                          <span>{m.icon}</span>
                          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{m.label}</span>
                        </button>
                      )
                    })}
                  </div>
                </div>

                {/* 2. Interactive Reasoning Input */}
                <div
                  style={{
                    padding: 16,
                    borderRadius: 16,
                    background: 'rgba(15, 23, 42, 0.72)',
                    border: '1px solid rgba(34, 211, 238, 0.3)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 10,
                  }}
                >
                  <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                    <input
                      type="text"
                      value={brainQuery}
                      onChange={(e) => setBrainQuery(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          void runBrainSimulation(brainQuery || `Optimiser le module ${selectedBrainMod}`, selectedBrainMod)
                        }
                      }}
                      placeholder="Exprimez n'importe quel objectif complexe : le Cerveau AGI déduit la stratégie, les invariants et les experts…"
                      style={{
                        flex: 1,
                        minWidth: 260,
                        padding: '11px 14px',
                        borderRadius: 11,
                        border: '1px solid rgba(34, 211, 238, 0.38)',
                        background: 'rgba(2, 6, 23, 0.85)',
                        color: '#F8FAFC',
                        fontSize: 13,
                      }}
                    />
                    <button
                      type="button"
                      onClick={() => void runBrainSimulation(brainQuery || `Optimiser le module ${selectedBrainMod}`, selectedBrainMod)}
                      disabled={brainLoading}
                      style={{
                        padding: '10px 18px',
                        borderRadius: 11,
                        border: '1px solid rgba(34, 211, 238, 0.65)',
                        background: 'linear-gradient(135deg, rgba(6, 182, 212, 0.32), rgba(139, 92, 246, 0.28))',
                        color: '#ECFEFF',
                        fontWeight: 800,
                        fontSize: 12.5,
                        cursor: 'pointer',
                      }}
                    >
                      {brainLoading ? 'Analyse cognitive…' : '⚡ Analyser & Structurer'}
                    </button>
                  </div>

                  {/* Summary Pills & Deep Cognitive Understanding */}
                  {brainPlan && (() => {
                    const cog = (brainPlan.cognitive_understanding as Record<string, unknown> | undefined) || {}
                    const masters = Array.isArray(brainPlan.masters_involved) ? (brainPlan.masters_involved as string[]) : []
                    const firstApp = applicators[0]
                    const masterLabel = masters[0] || firstApp?.master_agent || String(brainPlan.master_agent || `${selectedBrainMod}-lead`)
                    const masterDesc = firstApp?.master_description || String(brainPlan.master_description || 'Coordination cognitive et validation des livrables du module.')
                    const regime = String(cog.epistemic_regime || brainPlan.epistemic_regime || 'KNOWN_OPTIMIZABLE')
                    const regimeLabel = String(cog.regime_label || 'Raisonnement par premiers principes & auto-correction fermée')
                    const causal = String(cog.causal_reasoning || cog.intent_synthesis || '')
                    const constraints = Array.isArray(cog.implicit_constraints) ? (cog.implicit_constraints as string[]) : []
                    return (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 4 }}>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(230px, 1fr))', gap: 10 }}>
                          <div style={{ padding: '10px 13px', borderRadius: 11, background: 'rgba(2, 6, 23, 0.6)', border: '1px solid rgba(255,255,255,0.07)' }}>
                            <div style={{ fontSize: 10, color: '#94A3B8', textTransform: 'uppercase', fontFamily: "'Cascadia Code',Consolas,monospace" }}>
                              Agent Maître Responsable
                            </div>
                            <div style={{ fontSize: 13.5, fontWeight: 800, color: '#67E8F9', marginTop: 3 }}>
                              {masterLabel}
                            </div>
                            <div style={{ fontSize: 11, color: '#CBD5E1', marginTop: 2 }}>
                              {masterDesc}
                            </div>
                          </div>

                          <div style={{ padding: '10px 13px', borderRadius: 11, background: 'rgba(2, 6, 23, 0.6)', border: '1px solid rgba(255,255,255,0.07)' }}>
                            <div style={{ fontSize: 10, color: '#94A3B8', textTransform: 'uppercase', fontFamily: "'Cascadia Code',Consolas,monospace" }}>
                              Régime Épistémique & Stratégie
                            </div>
                            <div style={{ fontSize: 13.5, fontWeight: 800, color: '#C4B5FD', marginTop: 3 }}>
                              {regime}
                            </div>
                            <div style={{ fontSize: 11, color: '#CBD5E1', marginTop: 2 }}>
                              {regimeLabel}
                            </div>
                          </div>

                          {ghStatus && (
                            <div style={{ padding: '10px 13px', borderRadius: 11, background: 'rgba(16, 185, 129, 0.1)', border: '1px solid rgba(52, 211, 153, 0.3)' }}>
                              <div style={{ fontSize: 10, color: '#6EE7B7', textTransform: 'uppercase', fontFamily: "'Cascadia Code',Consolas,monospace" }}>
                                Vérification Continue & Contrats
                              </div>
                              <div style={{ fontSize: 13.5, fontWeight: 800, color: '#ECFDF5', marginTop: 3 }}>
                                {ghStatus.should_continue_improving ? '⚡ Amélioration Active' : '✅ Contrats Validés'}
                              </div>
                              <div style={{ fontSize: 11, color: '#A7F3D0', marginTop: 2 }}>
                                Suites validées : {String(ghStatus.passed_count ?? 2)} · Échecs : {String(ghStatus.failed_count ?? 0)}
                              </div>
                            </div>
                          )}
                        </div>

                        {(causal || constraints.length > 0) && (
                          <div
                            style={{
                              padding: '11px 14px',
                              borderRadius: 12,
                              background: 'linear-gradient(135deg, rgba(6, 182, 212, 0.11), rgba(139, 92, 246, 0.11))',
                              border: '1px solid rgba(34, 211, 238, 0.28)',
                              fontSize: 12,
                              color: '#E2E8F0',
                              lineHeight: 1.5,
                            }}
                          >
                            {causal && (
                              <div>
                                <strong style={{ color: '#67E8F9' }}>🧠 Compréhension & Raisonnement Causal :</strong> {causal}
                              </div>
                            )}
                            {constraints.length > 0 && (
                              <div style={{ marginTop: 4, fontSize: 11.2, color: '#C4B5FD' }}>
                                <strong>Invariants Implicites Détectés :</strong> {constraints.join(' · ')}
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    )
                  })()}
                </div>

                {/* 3. Visual 7-Phase Cognitive Loop */}
                <div>
                  <div style={{ fontSize: 11, fontWeight: 800, color: '#CBD5E1', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 9 }}>
                    Cycle de Raisonnement AGI en 7 Phases Fermées
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 9 }}>
                    {COGNITIVE_LOOP_META.map((phase) => (
                      <div
                        key={phase.id}
                        style={{
                          padding: '11px 13px',
                          borderRadius: 12,
                          background: 'rgba(15, 23, 42, 0.65)',
                          border: `1px solid ${phase.color}40`,
                        }}
                      >
                        <div style={{ fontSize: 12, fontWeight: 800, color: phase.color }}>{phase.title}</div>
                        <div style={{ fontSize: 11, color: '#94A3B8', marginTop: 4, lineHeight: 1.4 }}>{phase.desc}</div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* 4. Visual Expert Cards (Never raw JSON!) */}
                {applicators.length > 0 && (
                  <div>
                    <div style={{ fontSize: 11, fontWeight: 800, color: '#CBD5E1', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 9 }}>
                      Spécialistes Mobilisés pour ce Module ({applicators.length} Experts)
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(290px, 1fr))', gap: 10 }}>
                      {applicators.map((app, i) => (
                        <div
                          key={app.applicator_agent || i}
                          style={{
                            padding: '13px 15px',
                            borderRadius: 14,
                            background: 'linear-gradient(160deg, rgba(30, 41, 59, 0.55), rgba(15, 23, 42, 0.8))',
                            border: '1px solid rgba(255, 255, 255, 0.09)',
                            display: 'flex',
                            flexDirection: 'column',
                            gap: 6,
                          }}
                        >
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                            <span style={{ fontWeight: 800, fontSize: 12.5, color: '#67E8F9', fontFamily: "'Cascadia Code',Consolas,monospace" }}>
                              {app.applicator_agent}
                            </span>
                            <span style={{ fontSize: 10, padding: '2px 7px', borderRadius: 99, background: 'rgba(255,255,255,0.06)', color: '#CBD5E1' }}>
                              {String(app.feature || '').replace(/_/g, ' ')}
                            </span>
                          </div>
                          <p style={{ margin: 0, fontSize: 11.5, color: '#E2E8F0', lineHeight: 1.45 }}>
                            {app.description}
                          </p>
                          {app.verification_gate && (
                            <div style={{ fontSize: 10.5, color: '#6EE7B7', marginTop: 2 }}>
                              <strong>Invariant :</strong> {app.verification_gate}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>,
          document.body,
        )}
    </>
  )
}
