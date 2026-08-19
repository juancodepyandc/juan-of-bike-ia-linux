import { useState } from 'react'
import {
  Activity,
  ArrowRight,
  Brain,
  Bug,
  CheckCircle2,
  Clock,
  Cpu,
  Layers,
  Lightbulb,
  Loader2,
  Radar,
  Send,
  Share2,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Zap,
} from 'lucide-react'
import MarkdownPro from '../../components/MarkdownPro'
import VoicePushToTalk from '../../components/VoicePushToTalk'
import {
  DEEP_REASONING_PRESETS,
  DEEP_REASONING_PROMPT_SYSTEM,
  type CyberInvestigationScenario,
} from '../../services/cyber/cyberDeepReasoning'
import { ollamaChatStream } from '../../hooks/useTauri'
import { useAppStore } from '../../stores/appStore'

const ACCENT = '#F43F5E'
const OK = '#4ADE80'
const WARN = '#F59E0B'
const BLUE = '#60A5FA'

export default function DeepReasoningLab() {
  const mainModel = useAppStore((s) => s.mainModel)
  const [selectedScenarioIdx, setSelectedScenarioIdx] = useState<number>(0)
  const [customPrompt, setCustomPrompt] = useState('')
  const [customResult, setCustomResult] = useState('')
  const [isThinking, setIsThinking] = useState(false)
  const [activeStepId, setActiveStepId] = useState<number>(1)

  const activeScenario: CyberInvestigationScenario =
    DEEP_REASONING_PRESETS[selectedScenarioIdx] ?? DEEP_REASONING_PRESETS[0]!

  const handleRunCustomReasoning = async () => {
    if (!customPrompt.trim() || isThinking) return
    setIsThinking(true)
    setCustomResult('')
    try {
      await ollamaChatStream(
        mainModel,
        [
          { role: 'system', content: DEEP_REASONING_PROMPT_SYSTEM },
          { role: 'user', content: customPrompt.trim() },
        ],
        (token) => {
          setCustomResult((prev) => prev + token)
        },
        () => undefined,
        { temperature: 0.3, num_ctx: 8192, num_predict: 3500 },
      )
    } catch (err) {
      setCustomResult(`❌ Erreur de raisonnement IA : ${err instanceof Error ? err.message : String(err)}`)
    } finally {
      setIsThinking(false)
    }
  }

  return (
    <div className="space-y-4">
      {/* Header Banner */}
      <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4 flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-purple-500/20 text-purple-400 border border-purple-500/30">
              <Brain size={16} />
            </span>
            <h2 className="text-white text-[16px] font-bold">Raisonnement Cognitif Approfondi & Analyse 0-Day</h2>
          </div>
          <p className="text-[12px] text-white/60 mt-1 max-w-2xl">
            Dissection dialectique Attaque vs Défense : chaîne de pensée (Tree of Thoughts), analyse de causes racines, et formulation de stratégies défensives pérennes.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-mono px-2.5 py-1 rounded bg-purple-500/10 border border-purple-500/30 text-purple-300 flex items-center gap-1.5">
            <Sparkles size={12} /> Modèle : {mainModel || 'Local'}
          </span>
        </div>
      </div>

      {/* Preset Scenarios Switcher */}
      <div className="flex flex-wrap gap-2">
        {DEEP_REASONING_PRESETS.map((sc, i) => (
          <button
            key={sc.id}
            type="button"
            onClick={() => {
              setSelectedScenarioIdx(i)
              setActiveStepId(1)
              setCustomResult('')
            }}
            className={`px-3 py-1.5 rounded-lg text-[12px] font-medium border transition-all cursor-pointer ${
              selectedScenarioIdx === i && !customResult
                ? 'border-purple-500 bg-purple-500/20 text-purple-200 shadow-md'
                : 'border-white/10 bg-white/5 text-white/70 hover:bg-white/10'
            }`}
          >
            {sc.title}
          </button>
        ))}
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Left Column: Cognitive Steps Navigation & Custom Prompt Box */}
        <div className="lg:col-span-4 space-y-4">
          <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4 space-y-3">
            <h3 className="text-[12px] font-semibold text-white/80 uppercase tracking-wider flex items-center gap-2">
              <Layers size={14} className="text-purple-400" />
              Étapes de Raisonnement Cognitif
            </h3>
            <div className="space-y-2">
              {activeScenario.steps.map((st) => {
                const active = st.id === activeStepId && !customResult
                return (
                  <button
                    key={st.id}
                    type="button"
                    onClick={() => {
                      setActiveStepId(st.id)
                      setCustomResult('')
                    }}
                    className={`w-full text-left p-3 rounded-lg border transition-all cursor-pointer ${
                      active
                        ? 'border-purple-500/50 bg-purple-500/15 text-white shadow-lg'
                        : 'border-white/5 bg-black/30 text-white/70 hover:border-white/15'
                    }`}
                  >
                    <div className="text-[11px] font-bold text-purple-300">{st.title}</div>
                    <div className="text-[10.5px] text-white/50 mt-1 leading-snug">{st.subtitle}</div>
                  </button>
                )
              })}
            </div>
          </div>

          {/* Interactive AI Prompt Box */}
          <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4 space-y-3">
            <h3 className="text-[12px] font-semibold text-white/80 uppercase tracking-wider flex items-center gap-2">
              <Zap size={14} className="text-amber-400" />
              Soumettre un Cas / 0-Day Personnalisé
            </h3>
            <textarea
              rows={3}
              value={customPrompt}
              onChange={(e) => setCustomPrompt(e.target.value)}
              placeholder="Ex : Analyse cognitive de la vulnérabilité Log4Shell JNDI ou d'un UAF dans le kernel Linux..."
              className="w-full rounded-lg bg-black/50 border border-white/10 p-2.5 text-[12px] text-white font-mono placeholder:text-white/30 resize-none outline-none focus:border-purple-500"
            />
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleRunCustomReasoning}
                disabled={!customPrompt.trim() || isThinking}
                className="flex-1 px-3 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-500 text-white text-[12px] font-bold flex items-center justify-center gap-1.5 disabled:opacity-40 cursor-pointer transition-colors"
              >
                {isThinking ? <Loader2 size={13} className="animate-spin" /> : <Send size={13} />}
                {isThinking ? 'Raisonnement en cours...' : 'Analyser avec l\'IA'}
              </button>
              <VoicePushToTalk
                onTranscript={(txt) => setCustomPrompt((p) => (p ? `${p} ${txt}` : txt))}
                label="Dicter"
                disabled={isThinking}
                size={32}
              />
            </div>
          </div>
        </div>

        {/* Right Column: Deep Investigation Step Details / Live AI Output */}
        <div className="lg:col-span-8 space-y-4">
          {customResult ? (
            <div className="rounded-xl border border-purple-500/30 bg-black/50 p-5 space-y-3">
              <div className="flex items-center justify-between pb-2 border-b border-white/10">
                <span className="text-[12px] font-mono uppercase text-purple-300 font-bold flex items-center gap-2">
                  <Brain size={14} /> Synthèse Cognitive IA
                </span>
                <button
                  type="button"
                  onClick={() => setCustomResult('')}
                  className="text-[11px] font-mono text-white/50 hover:text-white"
                >
                  Revenir aux fiches
                </button>
              </div>
              <div className="text-[13px] text-white/90 leading-relaxed font-sans max-h-[500px] overflow-y-auto pr-2">
                <MarkdownPro content={customResult} idPrefix="custom-reasoning" />
              </div>
            </div>
          ) : (
            (() => {
              const currentStep = activeScenario.steps.find((s) => s.id === activeStepId) ?? activeScenario.steps[0]!
              return (
                <div className="rounded-xl border border-white/10 bg-white/[0.02] p-5 space-y-4">
                  <div>
                    <div className="flex items-center justify-between">
                      <span className="text-[11px] font-mono text-purple-400 font-bold uppercase">{activeScenario.targetProduct}</span>
                      <span className="text-[10.5px] font-mono text-rose-300 bg-rose-500/10 border border-rose-500/30 px-2 py-0.5 rounded">
                        CVSS {activeScenario.cvss} · {activeScenario.vulnerabilityType}
                      </span>
                    </div>
                    <h3 className="text-[17px] font-bold text-white mt-1">{currentStep.title}</h3>
                    <p className="text-[12px] text-white/60 mt-0.5">{currentStep.subtitle}</p>
                  </div>

                  {/* Dual Perspective Grid: Red vs Blue */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
                    {/* Red Team Perspective */}
                    <div className="p-3.5 rounded-lg border border-rose-500/20 bg-rose-500/5 space-y-2">
                      <div className="text-[11px] font-mono font-bold text-rose-400 flex items-center gap-1.5 uppercase">
                        <Bug size={13} /> Perspective Offensive (Exploit Vector)
                      </div>
                      <p className="text-[11.5px] text-white/80 leading-relaxed">
                        {currentStep.redPerspective}
                      </p>
                    </div>

                    {/* Blue Team Perspective */}
                    <div className="p-3.5 rounded-lg border border-blue-500/20 bg-blue-500/5 space-y-2">
                      <div className="text-[11px] font-mono font-bold text-blue-400 flex items-center gap-1.5 uppercase">
                        <ShieldCheck size={13} /> Perspective Défensive (Containment)
                      </div>
                      <p className="text-[11.5px] text-white/80 leading-relaxed">
                        {currentStep.bluePerspective}
                      </p>
                    </div>
                  </div>

                  {/* Technical Insight */}
                  <div className="p-3.5 rounded-lg border border-white/10 bg-black/40 space-y-1.5">
                    <div className="text-[11px] font-mono font-bold text-amber-300 flex items-center gap-1.5 uppercase">
                      <Lightbulb size={13} /> Insight Architectural & Cause Profonde
                    </div>
                    <p className="text-[12px] text-white/85 leading-relaxed font-mono">
                      {currentStep.technicalInsight}
                    </p>
                  </div>

                  {/* Actionable Defense Checklist */}
                  <div className="space-y-2 pt-1">
                    <div className="text-[11px] font-mono uppercase text-emerald-400 font-bold flex items-center gap-1.5">
                      <CheckCircle2 size={13} /> Checklist de Durcissement & Vérification
                    </div>
                    <div className="space-y-1.5">
                      {currentStep.actionableChecklist.map((item, idx) => (
                        <div
                          key={idx}
                          className="flex items-start gap-2 text-[11.5px] text-white/85 p-2 rounded bg-emerald-500/5 border border-emerald-500/15"
                        >
                          <span className="text-emerald-400 font-bold shrink-0 mt-0.5">✓</span>
                          <span>{item}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )
            })()
          )}
        </div>
      </div>
    </div>
  )
}
