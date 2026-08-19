import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Activity,
  AlertOctagon,
  Download,
  Flame,
  Pause,
  Play,
  RefreshCw,
  Server,
  Shield,
  ShieldAlert,
  ShieldCheck,
  SkipForward,
  Swords,
  Terminal,
  Zap,
} from 'lucide-react'
import {
  createInitialWarRoomState,
  executeWarRoomStep,
  WAR_ROOM_SCENARIOS,
  type TargetNode,
  type WarRoomEvent,
  type WarRoomPhase,
  type WarRoomState,
} from '../../services/cyber/autonomousWarRoom'

const ACCENT = '#F43F5E'
const OK = '#4ADE80'
const WARN = '#F59E0B'
const BLUE = '#60A5FA'

const PHASE_LABELS: Record<WarRoomPhase, string> = {
  idle: 'En Attente',
  reconnaissance: 'Reconnaissance Réseau',
  'initial-compromise': 'Compromission Initiale (0-Day)',
  'lateral-movement': 'Mouvement Latéral & Pivot',
  'privilege-escalation': 'Élévation de Privilèges',
  'data-exfiltration': 'Tentative d\'Exfiltration',
  'mitigated-contained': 'Menace Contenue (eBPF / Patch)',
  'post-mortem': 'Incident Clôturé & Post-Mortem',
}

export default function WarRoomLab() {
  const [scenarioIdx, setScenarioIdx] = useState(0)
  const [state, setState] = useState<WarRoomState>(() => createInitialWarRoomState(0))
  const [autoPlay, setAutoPlay] = useState(false)
  const [speedMs, setSpeedMs] = useState(1500)
  const [selectedNode, setSelectedNode] = useState<TargetNode | null>(null)
  const eventsEndRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    eventsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [state.events])

  useEffect(() => {
    if (!autoPlay) return
    const timer = window.setInterval(() => {
      setState((prev) => {
        if (!prev.running && prev.tick > 0 && prev.phase === 'post-mortem') {
          setAutoPlay(false)
          return prev
        }
        return executeWarRoomStep(prev)
      })
    }, speedMs)
    return () => window.clearInterval(timer)
  }, [autoPlay, speedMs])

  const handleStep = () => {
    setState((prev) => executeWarRoomStep(prev))
  }

  const handleReset = (idx = scenarioIdx) => {
    setAutoPlay(false)
    setScenarioIdx(idx)
    setState(createInitialWarRoomState(idx))
    setSelectedNode(null)
  }

  const handleExportPostMortem = () => {
    if (!state.postMortemReport) return
    const blob = new Blob([state.postMortemReport], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `incident_report_${state.scenarioId}_${Date.now()}.md`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  return (
    <div className="space-y-4">
      {/* Top Cockpit Header */}
      <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-red-500/20 text-red-400 border border-red-500/30">
              <Swords size={16} />
            </span>
            <h2 className="text-white text-[16px] font-bold">War Room Autonome · Attaque vs Défense IA</h2>
          </div>
          <p className="text-[12px] text-white/60 mt-1 max-w-2xl">
            Simulation en temps réel d'un engagement Red Team contre Blue Team : corrélation SIEM, génération dynamique de règles Sigma/YARA, et isolation eBPF.
          </p>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2 flex-wrap">
          <button
            type="button"
            onClick={() => setAutoPlay((v) => !v)}
            className={`px-3 py-1.5 rounded-lg font-bold text-[12px] flex items-center gap-1.5 cursor-pointer transition-colors ${
              autoPlay ? 'bg-amber-500 text-black' : 'bg-rose-500 text-black hover:bg-rose-400'
            }`}
          >
            {autoPlay ? <Pause size={13} /> : <Play size={13} fill="currentColor" />}
            {autoPlay ? 'Pause' : 'Engager Simulation'}
          </button>
          <button
            type="button"
            onClick={handleStep}
            disabled={autoPlay || state.phase === 'post-mortem'}
            className="px-3 py-1.5 rounded-lg border border-white/10 bg-white/5 hover:bg-white/10 text-[12px] text-white flex items-center gap-1.5 disabled:opacity-40 cursor-pointer"
          >
            <SkipForward size={13} /> Étape suivante
          </button>
          <button
            type="button"
            onClick={() => handleReset()}
            className="p-1.5 rounded-lg border border-white/10 bg-white/5 hover:bg-white/10 text-white/70 hover:text-white cursor-pointer"
            title="Réinitialiser le scénario"
          >
            <RefreshCw size={14} />
          </button>
        </div>
      </div>

      {/* Scenario Selector & Score Bar */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 items-center">
        <div className="flex gap-2">
          {WAR_ROOM_SCENARIOS.map((sc, i) => (
            <button
              key={sc.id}
              type="button"
              onClick={() => handleReset(i)}
              className={`px-3 py-1.5 rounded-lg text-[11px] font-mono border transition-all cursor-pointer ${
                scenarioIdx === i
                  ? 'border-rose-500/50 bg-rose-500/15 text-rose-200'
                  : 'border-white/10 bg-white/[0.02] text-white/60 hover:bg-white/5'
              }`}
            >
              Scénario #{i + 1}
            </button>
          ))}
        </div>

        {/* Phase Indicator */}
        <div className="flex items-center justify-center gap-2 p-2 rounded-lg bg-black/40 border border-white/10 font-mono text-[11px]">
          <span className="h-2 w-2 rounded-full bg-rose-500 animate-pulse" />
          <span className="text-white/50">Phase active :</span>
          <span className="text-rose-300 font-bold">{PHASE_LABELS[state.phase]}</span>
        </div>

        {/* Scores */}
        <div className="flex items-center justify-end gap-3 font-mono text-[12px]">
          <span className="px-2.5 py-1 rounded bg-rose-500/10 border border-rose-500/30 text-rose-300">
            Red Score: <b>{state.redScore}</b>
          </span>
          <span className="px-2.5 py-1 rounded bg-blue-500/10 border border-blue-500/30 text-blue-300">
            Blue Score: <b>{state.blueScore}</b>
          </span>
        </div>
      </div>

      {/* Topology & Events Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Network Infrastructure Nodes */}
        <div className="lg:col-span-7 space-y-3">
          <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4 space-y-3">
            <h3 className="text-[12px] font-semibold text-white/80 uppercase tracking-wider flex items-center justify-between">
              <span className="flex items-center gap-2">
                <Server size={14} className="text-sky-400" />
                Infrastructure & Télémétrie des Nœuds
              </span>
              <span className="text-[10px] font-mono text-white/50">Tick: {state.tick}/8</span>
            </h3>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
              {state.nodes.map((node) => {
                const isSelected = selectedNode?.id === node.id
                let statusColor = OK
                let badgeLabel = 'SÉCURISÉ'
                if (node.status === 'scanned') {
                  statusColor = WARN
                  badgeLabel = 'SONDÉ (SCAN)'
                } else if (node.status === 'suspicious') {
                  statusColor = WARN
                  badgeLabel = 'SUSPECT'
                } else if (node.status === 'compromised') {
                  statusColor = ACCENT
                  badgeLabel = 'COMPROMIS'
                } else if (node.status === 'isolated') {
                  statusColor = BLUE
                  badgeLabel = 'ISOLÉ (eBPF)'
                } else if (node.status === 'patched') {
                  statusColor = OK
                  badgeLabel = 'DURCI / PATCHÉ'
                }

                return (
                  <button
                    key={node.id}
                    type="button"
                    onClick={() => setSelectedNode(node)}
                    className={`p-3 rounded-lg border text-left transition-all cursor-pointer ${
                      isSelected
                        ? 'border-rose-500 bg-rose-500/10 shadow-lg'
                        : 'border-white/10 bg-black/30 hover:border-white/20'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-mono text-white/50">{node.layer}</span>
                      <span
                        className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded border"
                        style={{ borderColor: `${statusColor}55`, backgroundColor: `${statusColor}15`, color: statusColor }}
                      >
                        {badgeLabel}
                      </span>
                    </div>
                    <div className="text-[13px] font-bold text-white mt-1">{node.label}</div>
                    <div className="text-[11px] font-mono text-white/60 mt-1 flex items-center justify-between">
                      <span>{node.ip}</span>
                      <span className="text-[10px] text-white/40">Ports: {node.openPorts.join(',')}</span>
                    </div>
                  </button>
                )
              })}
            </div>

            {/* Selected Node Details Drawer */}
            {selectedNode && (
              <div className="p-3 rounded-lg bg-black/60 border border-white/10 space-y-1.5 text-[11px] font-mono text-white/80">
                <div className="flex items-center justify-between text-white font-bold">
                  <span>Détail Nœud : {selectedNode.label} ({selectedNode.ip})</span>
                  <button type="button" onClick={() => setSelectedNode(null)} className="text-white/40 hover:text-white">✕</button>
                </div>
                <div className="text-white/60">Services : {selectedNode.services.join(' · ')}</div>
                {selectedNode.vulnerability && (
                  <div className="text-rose-300">Vulnérabilité : {selectedNode.vulnerability} ({selectedNode.cveOrZeroDay})</div>
                )}
                <div className="text-emerald-300">Statut Défense : {selectedNode.status.toUpperCase()}</div>
              </div>
            )}
          </div>

          {/* Generated Defense Rules (Sigma & YARA) */}
          {(state.activeSigmaRules.length > 0 || state.activeYaraRules.length > 0) && (
            <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4 space-y-3">
              <h3 className="text-[12px] font-semibold text-emerald-300 uppercase tracking-wider flex items-center gap-2">
                <ShieldCheck size={14} />
                Règles de Détection & Signatures Générées
              </h3>
              <div className="space-y-2 max-h-48 overflow-y-auto">
                {state.activeSigmaRules.map((rule, idx) => (
                  <div key={idx} className="p-2.5 rounded-lg bg-black/50 border border-blue-500/20">
                    <div className="text-[10px] font-mono uppercase text-blue-400 font-bold mb-1">Règle Sigma Active</div>
                    <pre className="text-[10px] font-mono text-blue-200 overflow-x-auto">
                      <code>{rule}</code>
                    </pre>
                  </div>
                ))}
                {state.activeYaraRules.map((rule, idx) => (
                  <div key={idx} className="p-2.5 rounded-lg bg-black/50 border border-emerald-500/20">
                    <div className="text-[10px] font-mono uppercase text-emerald-400 font-bold mb-1">Signature YARA Active</div>
                    <pre className="text-[10px] font-mono text-emerald-200 overflow-x-auto">
                      <code>{rule}</code>
                    </pre>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Live Attack / Defense Timeline Stream */}
        <div className="lg:col-span-5 space-y-3">
          <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4 flex flex-col h-[520px]">
            <div className="flex items-center justify-between pb-3 border-b border-white/10">
              <h3 className="text-[12px] font-semibold text-white/80 uppercase tracking-wider flex items-center gap-2">
                <Terminal size={14} className="text-rose-400" />
                Journal d'Engagement en Direct
              </h3>
              {state.postMortemReport && (
                <button
                  type="button"
                  onClick={handleExportPostMortem}
                  className="text-[11px] font-mono text-emerald-300 flex items-center gap-1 hover:underline cursor-pointer"
                >
                  <Download size={11} /> Rapport .md
                </button>
              )}
            </div>

            <div className="flex-1 overflow-y-auto space-y-2 py-3 pr-1 font-mono text-[11px]">
              {state.events.map((ev) => {
                const isRed = ev.actor === 'RED'
                const isBlue = ev.actor === 'BLUE'
                return (
                  <div
                    key={ev.id}
                    className={`p-2.5 rounded-lg border ${
                      isRed
                        ? 'border-rose-500/30 bg-rose-500/10 text-rose-100'
                        : isBlue
                        ? 'border-blue-500/30 bg-blue-500/10 text-blue-100'
                        : 'border-white/10 bg-black/40 text-white/70'
                    }`}
                  >
                    <div className="flex items-center justify-between text-[10px] opacity-80">
                      <span className="font-bold">{ev.actor === 'RED' ? '⚔ RED AGENT' : ev.actor === 'BLUE' ? '🛡 BLUE AGENT' : '⚙ SYSTEM'}</span>
                      <span>{new Date(ev.timestamp).toLocaleTimeString()}</span>
                    </div>
                    <div className="font-bold text-[12px] mt-1 text-white">{ev.title}</div>
                    <div className="mt-1 text-[11px] leading-relaxed text-white/80">{ev.detail}</div>
                    {ev.mitreTechnique && (
                      <div className="mt-1 text-[9.5px] text-amber-300/80 bg-amber-500/10 border border-amber-500/20 px-1.5 py-0.5 rounded inline-block">
                        {ev.mitreTechnique}
                      </div>
                    )}
                  </div>
                )
              })}
              <div ref={eventsEndRef} />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
