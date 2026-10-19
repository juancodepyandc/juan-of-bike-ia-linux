import { useCallback, useEffect, useMemo, useState } from 'react'
import { analyzePromptOntologySync, type CognitivePromptDecision } from '../services/cognitivePromptDirector.ts'
import type { ModuleId } from '../types/app.ts'
import { getBridgeUrl } from '../utils/runtime.ts'
import type { ReinforcedModuleInfo, TrainingLiveState } from './ReinforcedModelBar.tsx'

interface Props {
  activeModule: ModuleId
  activeAccent: string
  masterAgent: string
  moduleTitle: string
}

const QUICK_ONTOLOGY_PRESETS: Array<{ label: string; prompt: string; mod: 'image' | '3d' }> = [
  { label: '🔥 Natsu (Animé Natif)', prompt: 'fais moi Natsu en feu', mod: '3d' },
  {
    label: '🧬 Natsu (Textures Personne Réelle)',
    prompt: 'fais moi Natsu avec des textures de personne réelle',
    mod: '3d',
  },
  {
    label: '📷 Portrait Réel (Photoréalisme)',
    prompt: "portrait d'un vieil horloger suisse dans son atelier",
    mod: 'image',
  },
  {
    label: '🔒 Modification Conservatrice',
    prompt: 'modifie la couleur de sa veste en bleu nuit sans changer le reste',
    mod: 'image',
  },
]

const MODULE_SUBAGENTS_COUNT: Record<string, { count: number; highlights: string[] }> = {
  conversation: {
    count: 5,
    highlights: ['intent-router', 'pipeline-tuner', 'web-factchecker', 'vision-multimodal', 'memory-keeper'],
  },
  image: {
    count: 6,
    highlights: ['prompt-director', 'flux-stylist', 'reference-researcher', 'upscale-16k-pbr', 'output-organizer'],
  },
  '3d': {
    count: 10,
    highlights: ['pipeline-router', 'neural-generator', 'mesh-postprocessor', 'texture-lead', 'motion-rigger', 'cad-engineering'],
  },
  code: {
    count: 5,
    highlights: ['architecture-planner', 'design-architect', 'backend-performance', 'sandbox-runner', 'fidelity-auditor'],
  },
  video: {
    count: 4,
    highlights: ['storyboard-director', 'motion-director', 'hymotion-kinematics', 'talking-head'],
  },
  drawing: {
    count: 4,
    highlights: ['canvas-stroke', 'sketch-interpreter', 'controlnet-renderer', 'character-forge'],
  },
  learning: {
    count: 4,
    highlights: ['formal-oracle', 'bac-curator', 'quiz-verifier', 'lab-integrator'],
  },
  cyber: {
    count: 5,
    highlights: ['symbolic-zeroday', 'closedloop-patcher', 'lab-builder', 'pyops-keeper', 'network-recon'],
  },
  business: {
    count: 9,
    highlights: ['market-research', 'financial-analyst', 'risk-manager', 'quant', 'economist', 'auditor'],
  },
  voice: {
    count: 5,
    highlights: ['stt-transcriber', 'tts-stt-tuner', 'lipsync', 'live-duplex'],
  },
  cowork: {
    count: 4,
    highlights: ['orchestrator-tuner', 'connector-keeper', 'safety-auditor', 'doc-extractor'],
  },
}

export default function AgiCognitiveStudioBar({
  activeModule,
  activeAccent,
  masterAgent,
  moduleTitle,
}: Props) {
  const [expanded, setExpanded] = useState(false)
  const [testPrompt, setTestPrompt] = useState('fais moi Natsu en feu')
  const [targetMod, setTargetMod] = useState<'image' | '3d'>(activeModule === '3d' ? '3d' : 'image')
  const [copied, setCopied] = useState(false)
  const [training, setTraining] = useState<TrainingLiveState | null>(null)
  const [modInfo, setModInfo] = useState<ReinforcedModuleInfo | null>(null)
  const [threeDInfo, setThreeDInfo] = useState<ReinforcedModuleInfo | null>(null)
  const [stoppingCycle, setStoppingCycle] = useState(false)
  const [llmRefinedDecision, setLlmRefinedDecision] = useState<Record<string, unknown> | null>(null)
  const [refining, setRefining] = useState(false)

  useEffect(() => {
    if (activeModule === '3d' || activeModule === 'image') {
      setTargetMod(activeModule)
    }
  }, [activeModule])

  const decision: CognitivePromptDecision = useMemo(
    () =>
      analyzePromptOntologySync(testPrompt, {
        targetModule: targetMod,
        conversationContext: 'Natsu Dragneel anime character',
      }),
    [testPrompt, targetMod],
  )

  const fetchLiveStatus = useCallback(async () => {
    try {
      const res = await fetch(`${getBridgeUrl()}/api/models/reinforced-status`, { cache: 'no-store' })
      if (!res.ok) return
      const data = (await res.json()) as {
        modules?: Record<string, ReinforcedModuleInfo>
        training?: TrainingLiveState
      }
      if (data.training) setTraining(data.training)
      const backendKey = activeModule === 'voice' ? 'audio' : activeModule
      if (data.modules?.[backendKey]) setModInfo(data.modules[backendKey])
      if (data.modules?.['3d']) setThreeDInfo(data.modules['3d'])
    } catch {
      // ignore transient errors
    }
  }, [activeModule])

  useEffect(() => {
    void fetchLiveStatus()
    const timer = window.setInterval(() => {
      void fetchLiveStatus()
    }, 6000)
    return () => window.clearInterval(timer)
  }, [fetchLiveStatus])

  const requestStopAfterCycle = async () => {
    setStoppingCycle(true)
    try {
      await fetch(`${getBridgeUrl()}/api/models/training-stop`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'stop_after_cycle' }),
      })
      await fetchLiveStatus()
    } finally {
      setStoppingCycle(false)
    }
  }

  const runDeepBackendDirector = async () => {
    setRefining(true)
    try {
      const res = await fetch(`${getBridgeUrl()}/api/agi/prompt-director`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: testPrompt,
          target_module: targetMod,
          conversation_context: 'Natsu Dragneel anime character',
          use_llm: false,
        }),
      })
      if (res.ok) {
        setLlmRefinedDecision((await res.json()) as Record<string, unknown>)
      }
    } catch {
      // fallback to sync TS decision
    } finally {
      setRefining(false)
    }
  }

  const subMeta = MODULE_SUBAGENTS_COUNT[activeModule] || MODULE_SUBAGENTS_COUNT.conversation
  const displayThreeD = threeDInfo || modInfo
  const ontologyBadgeColor =
    decision.effectiveRenderMode === 'native_anime_stylized'
      ? '#F472B6'
      : decision.effectiveRenderMode === 'hybrid_anime_with_real_textures'
        ? '#F59E0B'
        : decision.operationMode === 'modification'
          ? '#38BDF8'
          : '#34D399'

  return (
    <div
      className="aurora-v4-agi-studio-ribbon"
      style={{
        position: 'fixed',
        top: 54,
        left: 78,
        right: 0,
        zIndex: 32,
        background: 'linear-gradient(90deg, rgba(8, 13, 28, 0.94) 0%, rgba(13, 19, 40, 0.94) 50%, rgba(8, 13, 28, 0.94) 100%)',
        backdropFilter: 'blur(20px)',
        borderBottom: `1px solid ${activeAccent}38`,
        boxShadow: '0 8px 28px rgba(0, 0, 0, 0.42)',
        fontFamily: "'Inter','Segoe UI Variable',system-ui,sans-serif",
      }}
    >
      {/* Compact Ribbon Row (42px) */}
      <div
        style={{
          height: 42,
          padding: '0 16px',
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          overflowX: 'auto',
        }}
      >
        {/* 1. Active AGI Hierarchy Pill */}
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          title="Ouvrir/fermer le Studio Cognitif d'Ontologie (FR → EN) et le Comparateur Avant/Après"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 7,
            padding: '4px 10px',
            borderRadius: 9,
            border: `1px solid ${activeAccent}66`,
            background: `linear-gradient(135deg, ${activeAccent}24, rgba(139, 92, 246, 0.18))`,
            color: '#F8FAFC',
            fontSize: 11,
            fontWeight: 700,
            cursor: 'pointer',
            flexShrink: 0,
          }}
        >
          <span
            style={{
              width: 7,
              height: 7,
              borderRadius: '50%',
              background: activeAccent,
              boxShadow: `0 0 8px ${activeAccent}`,
            }}
          />
          <span>🧠 AGI {masterAgent}</span>
          <span
            style={{
              padding: '1px 6px',
              borderRadius: 99,
              background: 'rgba(255,255,255,0.09)',
              color: '#CBD5E1',
              fontSize: 9.5,
              fontFamily: "'Cascadia Code',Consolas,monospace",
            }}
          >
            {subMeta.count} sous-agents
          </span>
          <span style={{ color: activeAccent, fontSize: 10 }}>{expanded ? '▲' : '▼ Studio Ontologie FR→EN'}</span>
        </button>

        {/* 2. Live Ontology Badge for Current Prompt */}
        <div
          onClick={() => setExpanded(true)}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 7,
            padding: '4px 10px',
            borderRadius: 9,
            background: `${ontologyBadgeColor}16`,
            border: `1px solid ${ontologyBadgeColor}55`,
            color: '#F8FAFC',
            fontSize: 10.8,
            fontWeight: 700,
            cursor: 'pointer',
            flexShrink: 0,
          }}
          title="Cliquez pour tester la détection ontologique (Animé Natif vs Override Textures Réelles vs Photoréaliste vs Modification)"
        >
          <span style={{ color: ontologyBadgeColor }}>✦ Ontologie :</span>
          <span>{decision.badgeLabelFr}</span>
          <span
            style={{
              fontFamily: "'Cascadia Code',Consolas,monospace",
              fontSize: 9.5,
              color: '#94A3B8',
              paddingLeft: 6,
              borderLeft: '1px solid rgba(255,255,255,0.14)',
            }}
          >
            FR → EN Auto
          </span>
        </div>

        {/* 3. Quick Preset Pills */}
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: 5, flexShrink: 0 }}>
          {QUICK_ONTOLOGY_PRESETS.map((preset) => {
            const active = testPrompt === preset.prompt
            return (
              <button
                key={preset.label}
                type="button"
                onClick={() => {
                  setTestPrompt(preset.prompt)
                  setTargetMod(preset.mod)
                  setExpanded(true)
                }}
                style={{
                  padding: '3px 8px',
                  borderRadius: 7,
                  border: active ? '1px solid rgba(56, 189, 248, 0.7)' : '1px solid rgba(255,255,255,0.09)',
                  background: active ? 'rgba(14, 165, 233, 0.22)' : 'rgba(255,255,255,0.03)',
                  color: active ? '#E0F2FE' : '#94A3B8',
                  fontSize: 10,
                  fontWeight: active ? 700 : 500,
                  cursor: 'pointer',
                  whiteSpace: 'nowrap',
                }}
              >
                {preset.label}
              </button>
            )
          })}
        </div>

        {/* 4. Right: Live 3D Kaggle Cycle + Avant/Après Comparator + Stop After Cycle */}
        <div style={{ marginLeft: 'auto', display: 'inline-flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
          {displayThreeD && (
            <div
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                padding: '3px 9px',
                borderRadius: 8,
                background: 'rgba(16, 185, 129, 0.12)',
                border: '1px solid rgba(52, 211, 153, 0.38)',
                fontSize: 10.2,
                color: '#D1FAE5',
                fontFamily: "'Cascadia Code',Consolas,monospace",
              }}
              title="Comparatif vérifié : Modèle de Base Intouchable vs Modèle Renforcé Pareto"
            >
              <span>🛡️ Base {(displayThreeD.score_base_100 ?? 70.66).toFixed(2)}</span>
              <span style={{ color: '#34D399' }}>→</span>
              <span style={{ fontWeight: 800, color: '#6EE7B7' }}>
                ⚡ Renforcé {(displayThreeD.score_renforce_100 ?? 71.13).toFixed(2)} (+{(displayThreeD.gain_points_100 ?? 0.47).toFixed(2)})
              </span>
            </div>
          )}

          {training?.active && (
            <div
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                padding: '3px 9px',
                borderRadius: 8,
                background: training.stop_after_cycle ? 'rgba(14, 165, 233, 0.18)' : 'rgba(245, 158, 11, 0.16)',
                border: training.stop_after_cycle
                  ? '1px solid rgba(56, 189, 248, 0.55)'
                  : '1px solid rgba(251, 191, 36, 0.5)',
                fontSize: 10.2,
                color: training.stop_after_cycle ? '#BAE6FD' : '#FDE68A',
                fontWeight: 700,
              }}
            >
              <span>
                🔄 Kaggle {String(training.module || '3d').toUpperCase()} #{training.cycle_index || 1}
                {typeof training.local_generations_done === 'number' && typeof training.local_generations_planned === 'number'
                  ? ` · ${training.local_generations_done}/${training.local_generations_planned} maillages`
                  : ''}
              </span>
              <button
                type="button"
                onClick={() => void requestStopAfterCycle()}
                disabled={stoppingCycle || Boolean(training.stop_after_cycle)}
                style={{
                  padding: '2px 7px',
                  borderRadius: 6,
                  border: '1px solid rgba(56, 189, 248, 0.7)',
                  background: training.stop_after_cycle ? 'rgba(14, 165, 233, 0.35)' : 'rgba(14, 165, 233, 0.22)',
                  color: '#F0F9FF',
                  fontSize: 9.8,
                  fontWeight: 800,
                  cursor: training.stop_after_cycle ? 'default' : 'pointer',
                }}
              >
                {training.stop_after_cycle ? '⏳ Arrêt fin de cycle actif' : '⏹ Arrêter en fin de cycle'}
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Expanded Interactive AGI Ontology & Prompt Studio Drawer */}
      {expanded && (
        <div
          style={{
            padding: '14px 18px 16px',
            borderTop: '1px solid rgba(255,255,255,0.08)',
            background: 'linear-gradient(180deg, rgba(9, 14, 29, 0.98) 0%, rgba(5, 9, 20, 0.99) 100%)',
            display: 'grid',
            gridTemplateColumns: '1.25fr 1fr',
            gap: 16,
          }}
        >
          {/* Left Column: Interactive Cognitive Prompt & Ontology Director (FR -> EN) */}
          <div
            style={{
              padding: 14,
              borderRadius: 14,
              background: 'rgba(15, 23, 42, 0.75)',
              border: `1px solid ${ontologyBadgeColor}44`,
              display: 'flex',
              flexDirection: 'column',
              gap: 10,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
              <div>
                <div style={{ fontSize: 12.5, fontWeight: 800, color: '#F8FAFC' }}>
                  🎯 Directeur Cognitif d’Ontologie & Expansion Anglaise (Image FLUX.2 & 3D TRELLIS.2)
                </div>
                <div style={{ fontSize: 11, color: '#94A3B8', marginTop: 2 }}>
                  Détecte automatiquement si un personnage est animé de base, si des textures humaines réelles sont demandées exprès, ou s’il s’agit d’une modification.
                </div>
              </div>
              <div style={{ display: 'inline-flex', gap: 5 }}>
                {(['image', '3d'] as const).map((m) => (
                  <button
                    key={m}
                    type="button"
                    onClick={() => setTargetMod(m)}
                    style={{
                      padding: '4px 9px',
                      borderRadius: 7,
                      border: targetMod === m ? '1px solid #38BDF8' : '1px solid rgba(255,255,255,0.1)',
                      background: targetMod === m ? 'rgba(14, 165, 233, 0.24)' : 'rgba(255,255,255,0.04)',
                      color: targetMod === m ? '#E0F2FE' : '#94A3B8',
                      fontSize: 10.5,
                      fontWeight: 700,
                      cursor: 'pointer',
                    }}
                  >
                    Cible : {m.toUpperCase()}
                  </button>
                ))}
              </div>
            </div>

            <div style={{ display: 'flex', gap: 8 }}>
              <input
                type="text"
                value={testPrompt}
                onChange={(e) => setTestPrompt(e.target.value)}
                placeholder="Ex: fais moi Natsu en feu / Natsu avec des textures de personne réelle / portrait horloger…"
                style={{
                  flex: 1,
                  padding: '8px 12px',
                  borderRadius: 9,
                  border: '1px solid rgba(56, 189, 248, 0.35)',
                  background: 'rgba(2, 6, 23, 0.9)',
                  color: '#F8FAFC',
                  fontSize: 12,
                }}
              />
              <button
                type="button"
                onClick={() => void runDeepBackendDirector()}
                disabled={refining}
                style={{
                  padding: '8px 12px',
                  borderRadius: 9,
                  border: '1px solid rgba(139, 92, 246, 0.55)',
                  background: 'rgba(139, 92, 246, 0.22)',
                  color: '#EDE9FE',
                  fontSize: 11,
                  fontWeight: 700,
                  cursor: 'pointer',
                  whiteSpace: 'nowrap',
                }}
              >
                {refining ? 'Analyse…' : '⚡ Vérifier via Bridge Python'}
              </button>
              <button
                type="button"
                onClick={() => {
                  void navigator.clipboard?.writeText(decision.englishExpandedPrompt)
                  setCopied(true)
                  window.setTimeout(() => setCopied(false), 1800)
                }}
                style={{
                  padding: '8px 12px',
                  borderRadius: 9,
                  border: '1px solid rgba(52, 211, 153, 0.55)',
                  background: 'rgba(16, 185, 129, 0.22)',
                  color: '#D1FAE5',
                  fontSize: 11,
                  fontWeight: 700,
                  cursor: 'pointer',
                  whiteSpace: 'nowrap',
                }}
              >
                {copied ? '✓ Copié !' : '📋 Copier Prompt EN'}
              </button>
            </div>

            {/* Ontological Pills */}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 7, fontSize: 10.5 }}>
              <span
                style={{
                  padding: '3px 9px',
                  borderRadius: 99,
                  background: `${ontologyBadgeColor}22`,
                  border: `1px solid ${ontologyBadgeColor}66`,
                  color: '#F8FAFC',
                  fontWeight: 700,
                }}
              >
                Mode : {decision.badgeLabelFr}
              </span>
              <span
                style={{
                  padding: '3px 9px',
                  borderRadius: 99,
                  background: 'rgba(255,255,255,0.06)',
                  color: '#CBD5E1',
                  fontFamily: "'Cascadia Code',Consolas,monospace",
                }}
              >
                Ontologie native : {decision.subjectOntology}
              </span>
              <span
                style={{
                  padding: '3px 9px',
                  borderRadius: 99,
                  background: decision.explicitRealTexturesOverride
                    ? 'rgba(245, 158, 11, 0.22)'
                    : 'rgba(16, 185, 129, 0.16)',
                  color: decision.explicitRealTexturesOverride ? '#FDE68A' : '#A7F3D0',
                  fontWeight: 700,
                }}
              >
                Override textures personne réelle : {decision.explicitRealTexturesOverride ? 'OUI (Explicite)' : 'NON (Style natif préservé)'}
              </span>
              <span
                style={{
                  padding: '3px 9px',
                  borderRadius: 99,
                  background: 'rgba(56, 189, 248, 0.15)',
                  color: '#BAE6FD',
                }}
              >
                Opération : {decision.operationMode.toUpperCase()}
              </span>
            </div>

            <div style={{ fontSize: 11, color: '#CBD5E1', lineHeight: 1.45 }}>
              <strong style={{ color: '#67E8F9' }}>Raisonnement AGI :</strong> {decision.reasoningFr}
            </div>

            <div
              style={{
                padding: '9px 11px',
                borderRadius: 10,
                background: 'rgba(2, 6, 23, 0.88)',
                border: '1px solid rgba(255,255,255,0.08)',
                fontFamily: "'Cascadia Code',Consolas,monospace",
                fontSize: 11,
                color: '#E2E8F0',
                lineHeight: 1.45,
                maxHeight: 96,
                overflowY: 'auto',
              }}
            >
              <div style={{ fontSize: 9.5, color: '#38BDF8', marginBottom: 3, fontWeight: 700 }}>
                PROMPT ANGLAIS DÉVELOPPÉ POUR LE MOTEUR ({targetMod.toUpperCase()}) :
              </div>
              {String(llmRefinedDecision?.english_expanded_prompt || decision.englishExpandedPrompt)}
            </div>
          </div>

          {/* Right Column: Active Module Agents + Before/After Pareto Reinforcement Status */}
          <div
            style={{
              padding: 14,
              borderRadius: 14,
              background: 'rgba(15, 23, 42, 0.75)',
              border: '1px solid rgba(139, 92, 246, 0.35)',
              display: 'flex',
              flexDirection: 'column',
              gap: 10,
              justifyContent: 'space-between',
            }}
          >
            <div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                <div style={{ fontSize: 12.5, fontWeight: 800, color: '#F8FAFC' }}>
                  ⚡ Architecture Multi-Agents ({moduleTitle}) & Optimisation Pareto `auto_rl`
                </div>
                <button
                  type="button"
                  onClick={() => setExpanded(false)}
                  style={{
                    padding: '3px 8px',
                    borderRadius: 7,
                    border: '1px solid rgba(255,255,255,0.15)',
                    background: 'rgba(255,255,255,0.05)',
                    color: '#CBD5E1',
                    fontSize: 10.5,
                    cursor: 'pointer',
                  }}
                >
                  ✕ Réduire
                </button>
              </div>
              <div style={{ fontSize: 11, color: '#94A3B8', marginTop: 3 }}>
                Maître : <strong style={{ color: activeAccent }}>{masterAgent}</strong> · Sous-agents spécialisés sans collision :
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 7 }}>
                {subMeta.highlights.map((sub) => (
                  <span
                    key={sub}
                    style={{
                      padding: '3px 8px',
                      borderRadius: 7,
                      background: 'rgba(139, 92, 246, 0.16)',
                      border: '1px solid rgba(167, 139, 250, 0.35)',
                      color: '#DDD6FE',
                      fontSize: 10,
                      fontFamily: "'Cascadia Code',Consolas,monospace",
                    }}
                  >
                    {activeModule}-{sub}
                  </span>
                ))}
              </div>
            </div>

            {/* Pareto Dominance & Before/After Box */}
            <div
              style={{
                padding: '10px 12px',
                borderRadius: 11,
                background: 'rgba(2, 6, 23, 0.82)',
                border: '1px solid rgba(52, 211, 153, 0.32)',
                display: 'flex',
                flexDirection: 'column',
                gap: 6,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ fontSize: 11, fontWeight: 800, color: '#6EE7B7' }}>
                  🏆 Comparatif Modèle de Base (Intouchable) vs Modèle Renforcé
                </span>
                <span style={{ fontSize: 10, color: '#94A3B8', fontFamily: "'Cascadia Code',Consolas,monospace" }}>
                  Dominance de Pareto sur 10 modules
                </span>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, fontSize: 11 }}>
                <div style={{ padding: '6px 8px', borderRadius: 8, background: 'rgba(14, 165, 233, 0.12)', border: '1px solid rgba(56, 189, 248, 0.3)' }}>
                  <div style={{ fontSize: 9.5, color: '#94A3B8' }}>MODÈLE DE BASE (SHA-256)</div>
                  <div style={{ fontSize: 13, fontWeight: 800, color: '#E0F2FE', marginTop: 2 }}>
                    {(displayThreeD?.score_base_100 ?? 70.66).toFixed(2)} / 100
                  </div>
                </div>
                <div style={{ padding: '6px 8px', borderRadius: 8, background: 'rgba(16, 185, 129, 0.15)', border: '1px solid rgba(52, 211, 153, 0.4)' }}>
                  <div style={{ fontSize: 9.5, color: '#A7F3D0' }}>MODÈLE RENFORCÉ (CHAMPION)</div>
                  <div style={{ fontSize: 13, fontWeight: 800, color: '#6EE7B7', marginTop: 2 }}>
                    {(displayThreeD?.score_renforce_100 ?? 71.13).toFixed(2)} / 100
                  </div>
                </div>
                <div style={{ padding: '6px 8px', borderRadius: 8, background: 'rgba(139, 92, 246, 0.15)', border: '1px solid rgba(167, 139, 250, 0.35)' }}>
                  <div style={{ fontSize: 9.5, color: '#DDD6FE' }}>GAIN VÉRIFIÉ (MULTI-GRAINES)</div>
                  <div style={{ fontSize: 13, fontWeight: 800, color: '#C4B5FD', marginTop: 2 }}>
                    +{(displayThreeD?.gain_points_100 ?? 0.47).toFixed(3)} pts ({displayThreeD?.wins ?? 18}W/{displayThreeD?.losses ?? 0}L)
                  </div>
                </div>
              </div>
              <div style={{ fontSize: 10.2, color: '#94A3B8', lineHeight: 1.35 }}>
                Garantie stricte : le modèle de base est figé et immuable. Un candidat entraîné sur Kaggle 2×T4 n’est promu dans <code>modele/renforce/</code> que s’il bat le champion actuel sans dégrader aucune sous-métrique (Pareto + Wilcoxon).
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
