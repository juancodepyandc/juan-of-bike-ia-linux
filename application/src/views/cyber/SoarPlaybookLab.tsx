import { useState } from 'react'
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Clock,
  Download,
  Flame,
  Layers,
  Loader2,
  Play,
  RotateCcw,
  Server,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Zap,
} from 'lucide-react'
import {
  executeSoarPlaybook,
  SAMPLE_SOAR_PLAYBOOKS,
  type PlaybookStep,
  type SoarPlaybook,
} from '../../services/cyber/soarPlaybookEngine.ts'
import { triggerBrowserDownload } from '../../services/cyber/cyberOutputManager.ts'

export default function SoarPlaybookLab() {
  const [isRunning, setIsRunning] = useState(false)
  const [session, setSession] = useState<{ playbook: SoarPlaybook; exportPayload: any }>(() =>
    executeSoarPlaybook('soar-anti-ransomware'),
  )

  const handleRunPlaybook = () => {
    setIsRunning(true)
    setTimeout(() => {
      setSession(executeSoarPlaybook('soar-anti-ransomware'))
      setIsRunning(false)
    }, 500)
  }

  const handleDownload = () => {
    triggerBrowserDownload(
      session.exportPayload.filename,
      session.exportPayload.content,
      'text/markdown;charset=utf-8',
    )
  }

  const pb = session.playbook

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4 flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-indigo-500/20 text-indigo-400 border border-indigo-500/30">
              <Zap size={16} />
            </span>
            <h2 className="text-white text-[16px] font-bold">Orchestration & Automatisation SOAR de Riposte</h2>
          </div>
          <p className="text-[12px] text-white/60 mt-1 max-w-2xl">
            Exécution de graphes de réponse aux incidents (Playbooks) : Ingestion SIEM, enrichissement automatique d'IOCs, isolation réseau eBPF et génération post-mortem.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleRunPlaybook}
            disabled={isRunning}
            className="px-3.5 py-1.5 rounded-lg bg-indigo-500 hover:bg-indigo-400 text-white text-[12px] font-bold flex items-center gap-1.5 transition-colors cursor-pointer"
          >
            {isRunning ? <Loader2 size={13} className="animate-spin" /> : <Play size={13} />}
            Lancer le Playbook
          </button>
          <button
            type="button"
            onClick={handleDownload}
            className="px-3 py-1.5 rounded-lg bg-white/10 hover:bg-white/20 text-white text-[12px] font-bold flex items-center gap-1.5 transition-colors cursor-pointer"
          >
            <Download size={13} /> Exporter Rapport SOAR
          </button>
        </div>
      </div>

      {/* Incident Summary Card */}
      <div className="p-4 rounded-xl border border-indigo-500/30 bg-indigo-500/5 font-mono text-[12px] space-y-2">
        <div className="flex items-center justify-between">
          <span className="font-bold text-white text-[13px]">{pb.title}</span>
          <span className="text-[9.5px] px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/30 font-bold">
            SÉVÉRITÉ : {pb.severity}
          </span>
        </div>
        <div className="text-white/70 text-[11.5px]">
          <b>Déclencheur :</b> {pb.trigger}
        </div>
        <div className="text-emerald-400 text-[11px] flex items-center gap-2">
          <CheckCircle2 size={13} />
          <span>Statut : Incident contenu avec succès en <b>{pb.totalExecutionTimeMs} ms</b></span>
        </div>
      </div>

      {/* Playbook Steps Pipeline */}
      <div className="space-y-3">
        <h3 className="text-[12px] font-semibold text-white/80 uppercase tracking-wider flex items-center gap-2">
          <Activity size={14} className="text-indigo-400" />
          Chronologie des Actions Automatisées (Pipeline DAG)
        </h3>
        <div className="space-y-2.5">
          {pb.steps.map((step: PlaybookStep, idx: number) => (
            <div
              key={step.id}
              className="p-3.5 rounded-xl border border-white/10 bg-black/40 font-mono text-[11.5px] space-y-1.5"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 font-bold text-white">
                  <span className="flex h-5 w-5 items-center justify-center rounded-full bg-indigo-500/20 text-indigo-300 text-[10px]">
                    {idx + 1}
                  </span>
                  <span>{step.name}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-white/50 text-[10px] flex items-center gap-1">
                    <Clock size={11} /> {step.executionDurationMs} ms
                  </span>
                  <span className="text-[9px] px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 font-bold">
                    {step.status}
                  </span>
                </div>
              </div>
              <div className="text-white/70 text-[11px]">{step.actionDescription}</div>
              {step.outputLog && (
                <div className="p-2 rounded bg-black/70 border border-white/5 text-[10.5px] text-indigo-200/90">
                  <code>{step.outputLog}</code>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
