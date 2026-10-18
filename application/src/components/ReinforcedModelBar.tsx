import { useCallback, useEffect, useState } from 'react'
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

export default function ReinforcedModelBar({ activeModule }: { activeModule: string }) {
  const backendMod = UI_TO_BACKEND_MODULE[activeModule] || activeModule || 'conversation'
  const [overview, setOverview] = useState<ReinforcedOverviewResponse | null>(null)
  const [modalOpen, setModalOpen] = useState(false)
  const [inspectModule, setInspectModule] = useState<string>(backendMod)
  const [switching, setSwitching] = useState<string | null>(null)
  const [stopping, setStopping] = useState(false)
  const [brainModalOpen, setBrainModalOpen] = useState(false)
  const [brainQuery, setBrainQuery] = useState('')
  const [brainPlan, setBrainPlan] = useState<Record<string, unknown> | null>(null)
  const [ghStatus, setGhStatus] = useState<Record<string, unknown> | null>(null)
  const [brainLoading, setBrainLoading] = useState(false)

  const runBrainSimulation = useCallback(
    async (promptToTest: string) => {
      setBrainLoading(true)
      try {
        const [planRes, ghRes] = await Promise.all([
          fetch(`${getBridgeUrl()}/api/agents/loops/plan`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ prompt: promptToTest, module: backendMod }),
          }),
          fetch(`${getBridgeUrl()}/api/agents/loops/github-status`),
        ])
        if (planRes.ok) {
          setBrainPlan((await planRes.json()) as Record<string, unknown>)
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
    [backendMod],
  )

  useEffect(() => {
    setInspectModule(backendMod)
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

  return (
    <>
      <div
        className="aurora-v4-reinforced-bar"
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 6,
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
            padding: '4px 9px',
            borderRadius: 8,
            border: activeVariant === 'base' ? '1px solid rgba(56, 189, 248, 0.65)' : '1px solid transparent',
            background: activeVariant === 'base' ? 'rgba(14, 165, 233, 0.22)' : 'transparent',
            color: activeVariant === 'base' ? '#E0F2FE' : '#94A3B8',
            fontWeight: activeVariant === 'base' ? 700 : 500,
            fontSize: 10.5,
            cursor: 'pointer',
            display: 'inline-flex',
            alignItems: 'center',
            gap: 5,
            transition: 'all .18s ease',
          }}
        >
          <span>🛡️ Base Intouchable</span>
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
            padding: '4px 9px',
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
            transition: 'all .18s ease',
          }}
        >
          <span>⚡ Modèle Renforcé</span>
          {hasReinforced ? (
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
              +{gainPts.toFixed(2)} pt
            </span>
          ) : (
            <span
              style={{
                padding: '1px 5px',
                borderRadius: 99,
                background: 'rgba(148, 163, 184, 0.16)',
                color: '#94A3B8',
                fontSize: 9,
              }}
            >
              Prêt
            </span>
          )}
        </button>

        <button
          type="button"
          onClick={() => {
            setInspectModule(backendMod)
            setModalOpen(true)
          }}
          title="Ouvrir le registre Markdown des gains (GAINS.md) et gérer tous les modules"
          style={{
            padding: '4px 8px',
            borderRadius: 8,
            border: '1px solid rgba(167, 139, 250, 0.35)',
            background: 'rgba(139, 92, 246, 0.16)',
            color: '#DDD6FE',
            fontSize: 10.5,
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          📊 Gains .md
        </button>

        <button
          type="button"
          onClick={() => {
            setBrainModalOpen(true)
            void runBrainSimulation(brainQuery || `Optimiser le module ${backendMod} avec précision industrielle`)
          }}
          title="Ouvrir le Centre Cerveau AGI : 111 Agents (Workspace & Global) + 8 Boucles Opérationnelles Autonomes"
          style={{
            padding: '4px 8px',
            borderRadius: 8,
            border: '1px solid rgba(34, 211, 238, 0.45)',
            background: 'rgba(6, 182, 212, 0.16)',
            color: '#A5F3FC',
            fontSize: 10.5,
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          🧠 AGI · 8 Boucles
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
              Entraînement {String(training.module || '3d').toUpperCase()}
              {training.cycle_index ? ` · Cycle #${training.cycle_index}` : ''}
            </span>
            <button
              type="button"
              onClick={() => void stopTraining()}
              disabled={stopping}
              title="Arrêter immédiatement l'entraînement nocturne"
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
              {stopping ? 'Arrêt…' : '■ Arrêter'}
            </button>
          </div>
        )}
      </div>

      {modalOpen && overview && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Registre des Modèles Renforcés et Bilans Markdown"
          onClick={(e) => {
            if (e.target === e.currentTarget) setModalOpen(false)
          }}
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 200,
            background: 'rgba(3, 6, 15, 0.82)',
            backdropFilter: 'blur(10px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 20,
          }}
        >
          <div
            style={{
              width: 'min(1140px, 96vw)',
              maxHeight: '88vh',
              background: 'linear-gradient(160deg, #0D1326 0%, #070B16 100%)',
              border: '1px solid rgba(139, 92, 246, 0.45)',
              borderRadius: 20,
              boxShadow: '0 28px 90px rgba(0, 0, 0, 0.75)',
              display: 'flex',
              flexDirection: 'column',
              overflow: 'hidden',
              color: '#E6EAF5',
            }}
          >
            <div
              style={{
                padding: '16px 22px',
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
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                {training?.active && (
                  <button
                    type="button"
                    onClick={() => void stopTraining()}
                    disabled={stopping}
                    style={{
                      padding: '7px 13px',
                      borderRadius: 10,
                      border: '1px solid rgba(248, 113, 113, 0.8)',
                      background: 'rgba(220, 38, 38, 0.28)',
                      color: '#FECACA',
                      fontWeight: 700,
                      fontSize: 12,
                      cursor: 'pointer',
                    }}
                  >
                    {stopping ? 'Arrêt en cours…' : '■ Arrêter l’entraînement nocturne'}
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => setModalOpen(false)}
                  style={{
                    width: 34,
                    height: 34,
                    borderRadius: 10,
                    border: '1px solid rgba(255,255,255,0.16)',
                    background: 'rgba(255,255,255,0.06)',
                    color: '#E6EAF5',
                    cursor: 'pointer',
                    fontSize: 15,
                  }}
                >
                  ✕
                </button>
              </div>
            </div>

            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '360px 1fr',
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
                        <span style={{ fontWeight: 700, fontSize: 12.5, color: '#F8FAFC' }}>
                          {info.label}
                        </span>
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

                      <div style={{ fontSize: 10.5, color: '#94A3B8', lineHeight: 1.35 }}>
                        {info.axes_cibles}
                      </div>

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
                            border: !isRenforce
                              ? '1px solid rgba(56, 189, 248, 0.7)'
                              : '1px solid rgba(255,255,255,0.1)',
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
                            border: isRenforce
                              ? '1px solid rgba(52, 211, 153, 0.75)'
                              : '1px solid rgba(255,255,255,0.1)',
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
        </div>
      )}

      {brainModalOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Centre Cerveau AGI, 111 Agents & 8 Boucles Opérationnelles"
          onClick={(e) => {
            if (e.target === e.currentTarget) setBrainModalOpen(false)
          }}
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 210,
            background: 'rgba(3, 6, 15, 0.85)',
            backdropFilter: 'blur(12px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 20,
          }}
        >
          <div
            style={{
              width: 'min(1080px, 96vw)',
              maxHeight: '88vh',
              background: 'linear-gradient(160deg, #091224 0%, #050914 100%)',
              border: '1px solid rgba(34, 211, 238, 0.45)',
              borderRadius: 20,
              boxShadow: '0 28px 90px rgba(0, 0, 0, 0.8)',
              display: 'flex',
              flexDirection: 'column',
              overflow: 'hidden',
              color: '#E6EAF5',
            }}
          >
            <div
              style={{
                padding: '16px 22px',
                borderBottom: '1px solid rgba(255, 255, 255, 0.1)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 12,
              }}
            >
              <div>
                <h2 style={{ margin: 0, fontSize: 17, fontWeight: 800, color: '#A5F3FC' }}>
                  🧠 Cerveau AGI (`aurora-orchestrator`) · 20 Maîtres · 90 Appliquants · 8 Boucles Fermées
                </h2>
                <p style={{ margin: '4px 0 0', fontSize: 11.5, color: '#94A3B8' }}>
                  Workspace : <code>/home/juan/AuroraIA/.agents/agents/&#123;agent_name&#125;/agent.md</code> · Global :{' '}
                  <code>/home/juan/.gemini/config/agents/&#123;agent_name&#125;/agent.md</code>
                </p>
              </div>
              <button
                type="button"
                onClick={() => setBrainModalOpen(false)}
                style={{
                  padding: '6px 12px',
                  borderRadius: 10,
                  border: '1px solid rgba(255, 255, 255, 0.15)',
                  background: 'rgba(255, 255, 255, 0.06)',
                  color: '#CBD5E1',
                  fontSize: 12,
                  cursor: 'pointer',
                }}
              >
                Fermer ✕
              </button>
            </div>

            <div style={{ padding: 20, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 16 }}>
              <div style={{ display: 'flex', gap: 10 }}>
                <input
                  type="text"
                  value={brainQuery}
                  onChange={(e) => setBrainQuery(e.target.value)}
                  placeholder="Tester une requête complexe dans le Cerveau AGI (routage Maître -> Appliquant + DAG + Pare-Feu)…"
                  style={{
                    flex: 1,
                    padding: '10px 14px',
                    borderRadius: 10,
                    border: '1px solid rgba(34, 211, 238, 0.35)',
                    background: 'rgba(15, 23, 42, 0.85)',
                    color: '#F8FAFC',
                    fontSize: 13,
                  }}
                />
                <button
                  type="button"
                  onClick={() => void runBrainSimulation(brainQuery || `Optimiser le module ${backendMod}`)}
                  disabled={brainLoading}
                  style={{
                    padding: '10px 16px',
                    borderRadius: 10,
                    border: '1px solid rgba(34, 211, 238, 0.6)',
                    background: 'rgba(6, 182, 212, 0.25)',
                    color: '#ECFEFF',
                    fontWeight: 700,
                    fontSize: 12.5,
                    cursor: 'pointer',
                  }}
                >
                  {brainLoading ? 'Calcul AGI…' : 'Simuler Boucle AGI'}
                </button>
              </div>

              {ghStatus && (
                <div
                  style={{
                    padding: '10px 14px',
                    borderRadius: 12,
                    background: 'rgba(16, 185, 129, 0.12)',
                    border: '1px solid rgba(52, 211, 153, 0.35)',
                    fontSize: 12,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                  }}
                >
                  <span>
                    🔄 <strong>Boucle 4 — Gardien GitHub CI :</strong> Workflows passés :{' '}
                    <code>{String(ghStatus.passed_count ?? 0)}</code> · En cours :{' '}
                    <code>{String(ghStatus.in_progress_count ?? 0)}</code> · Échecs :{' '}
                    <code>{String(ghStatus.failed_count ?? 0)}</code>
                  </span>
                  <span style={{ color: '#6EE7B7', fontWeight: 700 }}>
                    {ghStatus.should_continue_improving
                      ? '⚡ Boucle d’amélioration active'
                      : '✅ 100 % des contrats GitHub validés'}
                  </span>
                </div>
              )}

              {brainPlan && (
                <pre
                  style={{
                    margin: 0,
                    padding: 16,
                    borderRadius: 14,
                    background: 'rgba(6, 10, 22, 0.94)',
                    border: '1px solid rgba(34, 211, 238, 0.2)',
                    color: '#E2E8F0',
                    fontFamily: "'Cascadia Code', Consolas, monospace",
                    fontSize: 11.5,
                    lineHeight: 1.55,
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                  }}
                >
                  {JSON.stringify(brainPlan, null, 2)}
                </pre>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  )
}
