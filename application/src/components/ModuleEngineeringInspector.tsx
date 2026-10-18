import { useEffect, useMemo, useState } from 'react'
import { createPortal } from 'react-dom'
import {
  MODULE_FEATURE_SUBAGENTS,
  MODULE_MASTER_IDS,
  getModuleFeatureSubAgents,
  type AuroraFeatureSubAgent,
} from '../services/auroraAgents.ts'
import { engineerDecision } from '../services/threeDAutonomousEngineer.ts'
import type { ThreeDIntent } from '../services/threeDIntent.ts'
import { useAppStore } from '../stores/appStore.ts'
import type { ModuleId } from '../types/app.ts'

interface ModuleEngineeringSpec {
  id: string
  title: string
  subtitle: string
  accent: string
  engineStack: string[]
  precisionGates: Array<{ label: string; metric: string; detail: string }>
  pipelineStages: string[]
}

const MODULE_SPECS: Record<string, ModuleEngineeringSpec> = {
  conversation: {
    id: 'conversation',
    title: 'Copilote Conversationnel & Fact-Checking',
    subtitle: 'Boucle 6 étapes · Recherche Web Sourcée · Vision Qwen3-VL · Mémoire Épisodique',
    accent: '#8B5CF6',
    engineStack: ['Qwen3-Coder / Main LLM', 'Qwen3-VL Multimodal', 'ChromaDB Vector Memory', 'DuckDuckGo / Web Verifier'],
    precisionGates: [
      { label: 'Anti-Hallucination', metric: 'Citations obligatoires', detail: 'Toute affirmation factuelle externe est croisée avec les preuves récupérées.' },
      { label: 'Routage Épistémique', metric: '3 régimes formels', detail: 'KNOWN_CANONICAL · KNOWN_OPTIMIZABLE · UNKNOWN_EXPLORATORY.' },
      { label: 'Continuité Contexte', metric: 'Compression sans perte', detail: 'Préservation des contraintes utilisateur sur les longues sessions.' },
    ],
    pipelineStages: ['1. Analyse Intention', '2. Planification', '3. Brouillon', '4. Vérification Factuelle', '5. Raffinement', '6. Livraison'],
  },
  image: {
    id: 'image',
    title: 'Studio Image FLUX.2-dev & Super-Résolution PBR 16K',
    subtitle: 'Conditionnement ReferenceLatent · Prompt Director · Rangement strict Créations / Modifications',
    accent: '#F472B6',
    engineStack: ['FLUX.2-dev (Q4_K_M.gguf)', 'Mistral-3-Small FP8 Text Encoder', 'ReferenceLatent Conditioning', 'Ultra-Master 16K PBR Synthesizer'],
    precisionGates: [
      { label: 'Fidélité Prompt', metric: '100% préservé', detail: 'Expansion intelligente des prompts courts et conservation intégrale des prompts détaillés.' },
      { label: 'Rangement Disque', metric: '2 dossiers stricts', detail: 'Séparation automatique dans output/image/creations/ et output/image/modifications/.' },
      { label: 'Cartes Matériaux PBR', metric: 'Jusqu’à 16384×16384', detail: 'Synthèse Albedo, Normal (Scharr+Sobel), Roughness et AO Cavity.' },
    ],
    pipelineStages: ['1. Analyse Contexte LLM', '2. Direction Prompt', '3. Graphe FLUX.2-dev', '4. Garde-fou Anatomique', '5. Upscale 8K/16K PBR', '6. Persistance Classée'],
  },
  code: {
    id: 'code',
    title: 'Ingénierie Logicielle Polyglotte & Sandbox 22 Langages',
    subtitle: 'Raisonnement <think> obligatoire · Zéro Placeholder · Vérification SymPy/Z3 · Live Preview',
    accent: '#22D3EE',
    engineStack: ['Architecte → Codeur → Auditeur', 'Sandbox 22 Langages (TS/Py/Rust/Go/C++)', 'SymPy / Z3 Invariant Prover', 'Vite Live Dev Server'],
    precisionGates: [
      { label: 'Zéro Placeholder', metric: '0 TODO / 0 Stub', detail: 'Rejet immédiat par Pare-Feu AGI de tout code incomplet ou non relié.' },
      { label: 'Raisonnement Structuré', metric: 'Bloc <think> exigé', detail: 'Analyse préalable des cas limites, de la complexité et du graphe d’imports.' },
      { label: 'Auto-Réparation', metric: 'Boucle compilateur', detail: 'Compilation tsc / py_compile / cargo et correction autonome jusqu’à 0 erreur.' },
    ],
    pipelineStages: ['1. Classification & Préflight', '2. Plan Architecture', '3. Raisonnement <think>', '4. Émission Multi-Fichiers', '5. Sandbox & Tests', '6. Audit Design & Livraison'],
  },
  '3d': {
    id: '3d',
    title: 'Studio 3D Neural, Rigging Anatomique & CAO Paramétrique',
    subtitle: 'TRELLIS.2-4B · Ingénieur Autonome Monoview/Multiview · Taubin λ/μ · PBR 16K · Manifold64',
    accent: '#60A5FA',
    engineStack: ['microsoft/TRELLIS.2-4B', 'Hunyuan3D-2mv Fallback', 'Blender 5.1 MIA / Rigify', 'Manifold64 CAD & Boolean Solver', 'PBR 16K Texture Baker'],
    precisionGates: [
      { label: 'Perfection Gate 5 Axes', metric: 'Score ≥ 92/100', detail: 'Contrôle géométrique, topologique, UV sans recouvrement, PBR et proportions.' },
      { label: 'Topologie & Lissage', metric: 'Taubin λ/μ verrouillé', detail: 'Soudure des îlots UV (weld_fragmented_mesh) sans perte de volume ni retrait.' },
      { label: 'Métrologie CAO / STL', metric: 'Zéro interférence', detail: 'Vérification booléenne Manifold64, contrôle continu d’insertion et nomenclature BOM.' },
    ],
    pipelineStages: ['1. Ingénieur 3D Autonome', '2. Vues de Référence', '3. Génération TRELLIS.2', '4. Soudure & Taubin λ/μ', '5. Bake PBR 8K/16K', '6. Rigging MIA / Export CAO'],
  },
  drawing: {
    id: 'drawing',
    title: 'Atelier Dessin Vectoriel/Matriciel & Character Forge',
    subtitle: 'Interprétation Qwen3-VL · ControlNet Sketch-to-Image · Handoff 3D & Animation',
    accent: '#A3E635',
    engineStack: ['Toile HTML5/WebGL Pression', 'Qwen3-VL Sketch Interpreter', 'ControlNet Lineart/Canny', 'Character Forge Multi-Vues'],
    precisionGates: [
      { label: 'Respect du Trait', metric: 'Alignement structurel', detail: 'Préservation des proportions et des lignes maîtresses de l’esquisse.' },
      { label: 'Character Forge', metric: 'Turnaround cohérent', detail: 'File persistante avec admission atomique et passage direct vers le Studio 3D.' },
      { label: 'Explication Visuelle', metric: 'Analyse de composition', detail: 'Diagnostic d’anatomie, perspective et valeurs lumineuses.' },
    ],
    pipelineStages: ['1. Capture Trait & Calques', '2. Lecture Qwen3-VL', '3. Conditionnement ControlNet', '4. Rendu Encré/Colorisé', '5. Handoff Forge 3D'],
  },
  video: {
    id: 'video',
    title: 'Studio Vidéo Cinématographique & Cinématique Temporelle',
    subtitle: 'Wan2.2-TI2V-5B · Storyboard Multi-Plans · HY-Motion 1.0 · Lip-Sync MuseTalk/Kokoro',
    accent: '#F59E0B',
    engineStack: ['Wan-AI/Wan2.2-TI2V-5B', 'tencent/HY-Motion-1.0', 'MuseTalk / SadTalker Lip-Sync', 'Kokoro-82M Audio Muxer'],
    precisionGates: [
      { label: 'Cohérence Temporelle', metric: 'Inter-trames stable', detail: 'Préservation de l’identité visuelle et fluidité des trajectoires caméra.' },
      { label: 'Cinématique 3D', metric: 'Squelette physique', detail: 'Synthèse de mouvements humains sans patinage des appuis au sol.' },
      { label: 'Synchronisation Labiale', metric: 'Visèmes A-X calés', detail: 'Alignement temporel précis entre la voix Kokoro et le flux MP4.' },
    ],
    pipelineStages: ['1. Découpage Storyboard', '2. Presets Caméra', '3. Synthèse Wan2.2 / HY-Motion', '4. Lip-Sync & Audio', '5. Multiplexage MP4'],
  },
  learning: {
    id: 'learning',
    title: 'Académie Scientifique & Oracle Formel SymPy / Z3',
    subtitle: 'Vérification Mathématique Formelle · 4 Laboratoires Interactifs · Parcours Bac & FSRS',
    accent: '#10B981',
    engineStack: ['Oracle Formel SymPy + Z3', 'Labs Physique / Chimie / Astro / Élec', 'Algorithme FSRS Spaced Repetition', 'Export Anki .apkg'],
    precisionGates: [
      { label: 'Exactitude Mathématique', metric: 'Preuve SymPy / Z3', detail: 'Aucune équation ou démonstration n’est validée sans vérification symbolique.' },
      { label: 'Simulation Physique', metric: 'Conservation d’énergie', detail: 'Intégration numérique stable dans les 4 laboratoires scientifiques.' },
      { label: 'Mémorisation FSRS', metric: 'Planification optimale', detail: 'Calcul d’intervalles de révision basé sur la courbe d’oubli réelle.' },
    ],
    pipelineStages: ['1. Diagnostic Niveau', '2. Cours & Preuve SymPy/Z3', '3. Laboratoire Interactif', '4. Évaluation Sémantique', '5. Consolidation FSRS'],
  },
  cyber: {
    id: 'cyber',
    title: 'Cybersécurité Offensive/Défensive & Découverte 0-Day Z3',
    subtitle: '9 Laboratoires Spécialisés · Solveur SMT Z3 AST/CFG · Patch en Boucle Fermée UNSAT',
    accent: '#F43F5E',
    engineStack: ['Z3 SMT Symbolic Engine', 'Closed-Loop Patch Engine', '9 Labs (WebSec, Crypto, Forensics, CTF, Network…)', 'PyOps Safety Guard (_safety.py)'],
    precisionGates: [
      { label: 'Preuve d’Atteignabilité', metric: 'SAT / UNSAT formel', detail: 'Extraction AST/CFG et résolution des contraintes SMT pour prouver une faille.' },
      { label: 'Correctif Minimal', metric: 'Vérifié UNSAT', detail: 'Le patch généré est re-testé contre le PoC jusqu’à élimination prouvée de l’exploit.' },
      { label: 'Cloisonnement PyOps', metric: 'Garde-fou _safety.py', detail: 'Interdiction des actions destructrices hors périmètre autorisé.' },
    ],
    pipelineStages: ['1. Extraction AST/CFG', '2. Résolution SMT Z3', '3. Preuve PoC', '4. Synthèse Patch Minimal', '5. Contre-Preuve UNSAT'],
  },
  business: {
    id: 'business',
    title: 'Business Intelligence, Quant Lab & Risk Manager Indépendant',
    subtitle: 'CEO Agent + 9 Experts · Walk-Forward 60/20/20 · Monte-Carlo Fat-Tails · Audit SHA-256',
    accent: '#38BDF8',
    engineStack: ['IndependentRiskManager (Non-LLM)', 'Walk-Forward 60/20/20 + Monte-Carlo', 'Flux BCE / Binance / Yahoo Finance', 'Chaîne d’Audit SQLite SHA-256'],
    precisionGates: [
      { label: 'Droit de Veto Risque', metric: 'Réserve ≥ 25% · Ruine ≤ 2%', detail: 'Moteur déterministe non-LLM bloquant toute allocation dangereuse.' },
      { label: 'Validation Quant', metric: 'Walk-Forward 60/20/20', detail: 'Zéro fuite du futur (look-ahead bias) et stress tests macro (2008, 2022).' },
      { label: 'Intégrité Audit', metric: 'Chaîne SHA-256', detail: 'Traçabilité cryptographique de chaque décision et cotation.' },
    ],
    pipelineStages: ['1. Étude Marché & Macro', '2. Modélisation Financière', '3. Backtest Walk-Forward', '4. Red-Team Critic', '5. Veto Risk Manager', '6. Scellement SHA-256'],
  },
}

export default function ModuleEngineeringInspector({ activeModule }: { activeModule: string }) {
  const [open, setOpen] = useState(false)
  const [simPrompt, setSimPrompt] = useState('Armure cybernétique articulée avec textures PBR 16K et tolérance mécanique')
  const { hardware, runtimeServices, services, installedModels } = useAppStore()

  useEffect(() => {
    const toggle = () => setOpen((v) => !v)
    window.addEventListener('aurora:toggle-engineering-inspector', toggle)
    return () => window.removeEventListener('aurora:toggle-engineering-inspector', toggle)
  }, [])

  const spec = MODULE_SPECS[activeModule] || MODULE_SPECS.conversation
  const master = useMemo(
    () => ({ name: MODULE_MASTER_IDS[(activeModule as ModuleId) || 'conversation'] || 'aurora-orchestrator' }),
    [activeModule],
  )
  const subAgents = useMemo<AuroraFeatureSubAgent[]>(() => {
    const list = getModuleFeatureSubAgents((activeModule as ModuleId) || 'conversation')
    return list.length > 0 ? list : MODULE_FEATURE_SUBAGENTS.conversation
  }, [activeModule])

  const threeDSimulation = useMemo(() => {
    const dummyIntent = {
      purpose: 'visual_preview',
      subjectKind: 'object',
      systemClass: 'generic',
      representationGoal: 'static_shape',
      referenceFraming: 'isolated_subject',
      motionReadiness: 'static_only',
      pipelineRouting: {
        pipeline: 'ai_generation',
        justifications: [],
        fallbackPipeline: 'ai_generation',
        blenderRequired: false,
        meshoomRequired: false,
        dreamgaussianPreferred: false,
        proceduralTemplate: null,
        validationChecks: [],
        postProcessing: [],
      },
      requiresDimensionalPrecision: /tolérance|mécanique|iso|engrenage|CAO/i.test(simPrompt),
      wantsNeutralPose: true,
      wantsSymmetry: true,
      needsResearch: true,
      needsClarification: false,
      clarificationQuestion: null,
      clarificationCategory: null,
      clarificationOptions: [],
      referencePromptAdditions: [],
      meshConstraints: [],
      motionGuidance: [],
      motionRisks: [],
      movingPartsFocus: [],
      anchoredPartsFocus: [],
      researchQueries: [],
      motionPresets: [],
      summary: '',
    } as ThreeDIntent
    return engineerDecision(simPrompt, dummyIntent, [], true)
  }, [simPrompt])

  const ollamaUp = Boolean(services?.ollama || runtimeServices?.ollama?.running)
  const comfyUp = Boolean(services?.comfyui || runtimeServices?.comfyui?.running)

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        title="Ouvrir le Cockpit d’Ingénierie, Précision & Qualité du module actif"
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 6,
          padding: '5px 11px',
          borderRadius: 10,
          border: `1px solid ${spec.accent}55`,
          background: `linear-gradient(135deg, ${spec.accent}22, rgba(15, 23, 42, 0.85))`,
          color: '#F1F5F9',
          fontSize: 11,
          fontWeight: 700,
          cursor: 'pointer',
          whiteSpace: 'nowrap',
          boxShadow: `0 2px 12px ${spec.accent}26`,
          transition: 'all .2s cubic-bezier(.22,1,.36,1)',
        }}
      >
        <span
          style={{
            width: 7,
            height: 7,
            borderRadius: '50%',
            background: spec.accent,
            boxShadow: `0 0 8px ${spec.accent}`,
          }}
        />
        <span>Ingénierie & Précision</span>
        <span
          style={{
            padding: '1px 6px',
            borderRadius: 999,
            background: 'rgba(255,255,255,0.08)',
            color: spec.accent,
            fontFamily: "'Cascadia Code',Consolas,monospace",
            fontSize: 9.5,
          }}
        >
          {subAgents.length} agents
        </span>
      </button>

      {open &&
        createPortal(
          <div
            role="dialog"
            aria-modal="true"
            aria-label={`Cockpit d'Ingénierie — ${spec.title}`}
            onClick={() => setOpen(false)}
            style={{
              position: 'fixed',
              inset: 0,
              zIndex: 100025,
              background: 'rgba(3, 6, 14, 0.82)',
              backdropFilter: 'blur(16px)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              padding: 18,
            }}
          >
            <div
              onClick={(e) => e.stopPropagation()}
              style={{
                width: 'min(1080px, 96vw)',
                maxHeight: '89vh',
                display: 'flex',
                flexDirection: 'column',
                borderRadius: 22,
                background: 'linear-gradient(165deg, #0D1428 0%, #070B16 100%)',
                border: `1px solid ${spec.accent}55`,
                boxShadow: `0 32px 96px rgba(0,0,0,0.85), 0 0 60px ${spec.accent}1F`,
                color: '#E2E8F0',
                overflow: 'hidden',
                fontFamily: "'Inter','Segoe UI Variable',system-ui,sans-serif",
              }}
            >
              {/* Header */}
              <div
                style={{
                  padding: '18px 24px',
                  borderBottom: '1px solid rgba(255,255,255,0.08)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: 16,
                  background: `radial-gradient(ellipse at 15% 0%, ${spec.accent}24, transparent 65%)`,
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <span
                      style={{
                        padding: '3px 9px',
                        borderRadius: 999,
                        background: `${spec.accent}24`,
                        border: `1px solid ${spec.accent}66`,
                        color: spec.accent,
                        fontFamily: "'Cascadia Code',Consolas,monospace",
                        fontSize: 10,
                        fontWeight: 800,
                        letterSpacing: '0.1em',
                        textTransform: 'uppercase',
                      }}
                    >
                      COCKPIT INGÉNIERIE & QUALITÉ · {activeModule.toUpperCase()}
                    </span>
                    <span
                      style={{
                        padding: '3px 9px',
                        borderRadius: 999,
                        background: 'rgba(16, 185, 129, 0.14)',
                        border: '1px solid rgba(52, 211, 153, 0.4)',
                        color: '#6EE7B7',
                        fontFamily: "'Cascadia Code',Consolas,monospace",
                        fontSize: 10,
                        fontWeight: 700,
                      }}
                    >
                      Maître : {master?.name || 'aurora-orchestrator'}
                    </span>
                  </div>
                  <h2 style={{ margin: '7px 0 3px', fontSize: 19, fontWeight: 800, color: '#F8FAFC' }}>
                    {spec.title}
                  </h2>
                  <p style={{ margin: 0, fontSize: 12, color: '#94A3B8' }}>{spec.subtitle}</p>
                </div>

                <button
                  type="button"
                  onClick={() => setOpen(false)}
                  style={{
                    padding: '8px 14px',
                    borderRadius: 11,
                    border: '1px solid rgba(255,255,255,0.15)',
                    background: 'rgba(255,255,255,0.05)',
                    color: '#E2E8F0',
                    fontSize: 12,
                    fontWeight: 700,
                    cursor: 'pointer',
                  }}
                >
                  ✕ Fermer
                </button>
              </div>

              {/* Body */}
              <div style={{ padding: 22, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 18 }}>
                {/* Row 1: Hardware & Runtime Telemetry + Engine Stack */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 12 }}>
                  <div
                    style={{
                      padding: 14,
                      borderRadius: 14,
                      background: 'rgba(15, 23, 42, 0.65)',
                      border: '1px solid rgba(255,255,255,0.08)',
                    }}
                  >
                    <div style={{ fontSize: 10, fontFamily: "'Cascadia Code',Consolas,monospace", color: '#94A3B8', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
                      Accélération Matérielle
                    </div>
                    <div style={{ marginTop: 6, fontSize: 13.5, fontWeight: 800, color: '#F8FAFC' }}>
                      {hardware?.gpu || 'NVIDIA RTX 5070 Ti (16 Go VRAM)'}
                    </div>
                    <div style={{ marginTop: 4, fontSize: 11, color: '#64748B' }}>
                      RAM Système : {hardware?.ram_gb ? `${Math.round(hardware.ram_gb)} Go` : '30 Go'} · {hardware?.cores || 16} cœurs
                    </div>
                  </div>

                  <div
                    style={{
                      padding: 14,
                      borderRadius: 14,
                      background: 'rgba(15, 23, 42, 0.65)',
                      border: '1px solid rgba(255,255,255,0.08)',
                    }}
                  >
                    <div style={{ fontSize: 10, fontFamily: "'Cascadia Code',Consolas,monospace", color: '#94A3B8', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
                      Moteurs Locaux & Services
                    </div>
                    <div style={{ marginTop: 7, display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                      <span style={{ padding: '3px 8px', borderRadius: 6, fontSize: 11, fontWeight: 700, background: ollamaUp ? 'rgba(16,185,129,0.16)' : 'rgba(245,158,11,0.15)', color: ollamaUp ? '#6EE7B7' : '#FCD34D', border: `1px solid ${ollamaUp ? 'rgba(52,211,153,0.4)' : 'rgba(251,191,36,0.35)'}` }}>
                        ● Ollama :11434 ({installedModels.length || 'Actif'})
                      </span>
                      <span style={{ padding: '3px 8px', borderRadius: 6, fontSize: 11, fontWeight: 700, background: comfyUp ? 'rgba(16,185,129,0.16)' : 'rgba(148,163,184,0.12)', color: comfyUp ? '#6EE7B7' : '#CBD5E1', border: `1px solid ${comfyUp ? 'rgba(52,211,153,0.4)' : 'rgba(255,255,255,0.12)'}` }}>
                        ● ComfyUI FLUX.2 :8188
                      </span>
                    </div>
                  </div>

                  <div
                    style={{
                      padding: 14,
                      borderRadius: 14,
                      background: 'rgba(15, 23, 42, 0.65)',
                      border: '1px solid rgba(255,255,255,0.08)',
                    }}
                  >
                    <div style={{ fontSize: 10, fontFamily: "'Cascadia Code',Consolas,monospace", color: '#94A3B8', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
                      Pile Technologique du Module
                    </div>
                    <div style={{ marginTop: 6, display: 'flex', flexWrap: 'wrap', gap: 5 }}>
                      {spec.engineStack.map((eng) => (
                        <span
                          key={eng}
                          style={{
                            padding: '2px 7px',
                            borderRadius: 6,
                            background: `${spec.accent}18`,
                            border: `1px solid ${spec.accent}44`,
                            color: '#E2E8F0',
                            fontSize: 10.5,
                            fontWeight: 600,
                          }}
                        >
                          {eng}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Row 2: Pipeline Stages */}
                <div
                  style={{
                    padding: 16,
                    borderRadius: 16,
                    background: 'rgba(15, 23, 42, 0.5)',
                    border: '1px solid rgba(255,255,255,0.07)',
                  }}
                >
                  <div style={{ fontSize: 11, fontWeight: 800, color: '#CBD5E1', marginBottom: 10, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                    Chaîne d’Exécution Déterministe ({spec.pipelineStages.length} Étapes)
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(145px, 1fr))', gap: 8 }}>
                    {spec.pipelineStages.map((stage) => (
                      <div
                        key={stage}
                        style={{
                          padding: '9px 11px',
                          borderRadius: 10,
                          background: 'rgba(2, 6, 23, 0.65)',
                          border: `1px solid ${spec.accent}33`,
                          fontSize: 11.5,
                          fontWeight: 700,
                          color: '#F1F5F9',
                        }}
                      >
                        {stage}
                      </div>
                    ))}
                  </div>
                </div>

                {/* Row 3: Precision Gates */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 12 }}>
                  {spec.precisionGates.map((gate) => (
                    <div
                      key={gate.label}
                      style={{
                        padding: 15,
                        borderRadius: 15,
                        background: 'linear-gradient(160deg, rgba(30, 41, 59, 0.55), rgba(15, 23, 42, 0.75))',
                        border: '1px solid rgba(255,255,255,0.09)',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                        <span style={{ fontSize: 12.5, fontWeight: 800, color: '#F8FAFC' }}>{gate.label}</span>
                        <span
                          style={{
                            padding: '2px 8px',
                            borderRadius: 999,
                            background: `${spec.accent}24`,
                            border: `1px solid ${spec.accent}55`,
                            color: spec.accent,
                            fontFamily: "'Cascadia Code',Consolas,monospace",
                            fontSize: 10,
                            fontWeight: 700,
                          }}
                        >
                          {gate.metric}
                        </span>
                      </div>
                      <p style={{ margin: '8px 0 0', fontSize: 11.5, color: '#94A3B8', lineHeight: 1.5 }}>{gate.detail}</p>
                    </div>
                  ))}
                </div>

                {/* Row 4: Interactive 3D Autonomous Engineer Diagnostic */}
                <div
                  style={{
                    padding: 16,
                    borderRadius: 16,
                    background: 'rgba(30, 58, 138, 0.14)',
                    border: '1px solid rgba(96, 165, 250, 0.32)',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8, marginBottom: 10 }}>
                    <div>
                      <span style={{ fontSize: 12, fontWeight: 800, color: '#93C5FD', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                        🔧 Simulateur d’Ingénieur 3D & CAO Autonome (Monoview vs Multiview + Tolérances)
                      </span>
                      <p style={{ margin: '2px 0 0', fontSize: 11, color: '#94A3B8' }}>
                        Testez un brief pour observer la décision d’ingénierie (stratégie de vues, résolution PBR, étanchéité Manifold64 et plan de repli OOM).
                      </p>
                    </div>
                    <span
                      style={{
                        padding: '3px 10px',
                        borderRadius: 999,
                        background: threeDSimulation.strategy.monoview ? 'rgba(56, 189, 248, 0.2)' : 'rgba(168, 85, 247, 0.2)',
                        border: '1px solid rgba(147, 197, 253, 0.45)',
                        color: '#E0F2FE',
                        fontFamily: "'Cascadia Code',Consolas,monospace",
                        fontSize: 10.5,
                        fontWeight: 700,
                      }}
                    >
                      {threeDSimulation.strategy.monoview ? 'MONOVIEW HAUTE FIDÉLITÉ' : `MULTIVIEW (${threeDSimulation.strategy.targetImageCount} VUES)`} · Succès estimé {(threeDSimulation.strategy.estimatedSuccessRate * 100).toFixed(0)}%
                    </span>
                  </div>

                  <input
                    type="text"
                    value={simPrompt}
                    onChange={(e) => setSimPrompt(e.target.value)}
                    placeholder="Décrivez un sujet 3D, un mécanisme CAO ou un personnage…"
                    style={{
                      width: '100%',
                      boxSizing: 'border-box',
                      padding: '9px 13px',
                      borderRadius: 10,
                      border: '1px solid rgba(96, 165, 250, 0.35)',
                      background: 'rgba(2, 6, 23, 0.75)',
                      color: '#F8FAFC',
                      fontSize: 12.5,
                      marginBottom: 10,
                    }}
                  />

                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', gap: 8 }}>
                    <div style={{ padding: '8px 11px', borderRadius: 9, background: 'rgba(2,6,23,0.55)', border: '1px solid rgba(255,255,255,0.06)', fontSize: 11 }}>
                      <strong style={{ color: '#93C5FD' }}>Sujet & Complexité :</strong>{' '}
                      {threeDSimulation.analysis.likelySubject} ({threeDSimulation.analysis.estimatedComplexity})
                    </div>
                    <div style={{ padding: '8px 11px', borderRadius: 9, background: 'rgba(2,6,23,0.55)', border: '1px solid rgba(255,255,255,0.06)', fontSize: 11 }}>
                      <strong style={{ color: '#93C5FD' }}>Tolérances :</strong>{' '}
                      {threeDSimulation.analysis.tolerances?.targetWatertight ? 'Manifold64 Étanche' : 'Topologie Standard'} · PBR {threeDSimulation.analysis.tolerances?.recommendedPbrResolution || '8K'}
                    </div>
                    <div style={{ padding: '8px 11px', borderRadius: 9, background: 'rgba(2,6,23,0.55)', border: '1px solid rgba(255,255,255,0.06)', fontSize: 11 }}>
                      <strong style={{ color: '#93C5FD' }}>Justification :</strong>{' '}
                      {threeDSimulation.strategy.whyMonoview}
                    </div>
                  </div>
                </div>

                {/* Row 5: Surgical Applicator Sub-Agents for this Module */}
                <div>
                  <div style={{ fontSize: 11.5, fontWeight: 800, color: '#CBD5E1', marginBottom: 10, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                    Sous-Agents Appliquants Chirurgicaux du Module ({subAgents.length})
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 10 }}>
                    {subAgents.map((ag) => (
                      <div
                        key={ag.id}
                        style={{
                          padding: '12px 14px',
                          borderRadius: 13,
                          background: 'rgba(15, 23, 42, 0.72)',
                          border: '1px solid rgba(255,255,255,0.08)',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                          <span style={{ fontFamily: "'Cascadia Code',Consolas,monospace", fontSize: 12, fontWeight: 800, color: spec.accent }}>
                            {ag.id}
                          </span>
                          <span style={{ fontSize: 9.5, padding: '2px 6px', borderRadius: 5, background: 'rgba(255,255,255,0.06)', color: '#94A3B8', fontFamily: "'Cascadia Code',Consolas,monospace" }}>
                            {ag.feature}
                          </span>
                        </div>
                        <p style={{ margin: '6px 0', fontSize: 11.5, color: '#E2E8F0', lineHeight: 1.4 }}>{ag.role}</p>
                        <div style={{ fontSize: 10.5, color: '#6EE7B7', marginTop: 6 }}>
                          <strong>Périmètre :</strong> {(ag.filesOwned.slice(0, 2).join(', ') || ag.routesOwned.slice(0, 2).join(', ')) || 'Contrat module'}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>,
          document.body,
        )}
    </>
  )
}
