import { useState } from 'react'
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Brain,
  CheckCircle2,
  Clock,
  Download,
  FileCode,
  Flame,
  Globe,
  Layers,
  ListOrdered,
  Loader2,
  Play,
  Radar,
  Radio,
  Search,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Zap,
} from 'lucide-react'
import {
  runAutonomousInvestigation,
  type DeepInvestigationDossier,
  type InvestigationHypothesis,
  type ThreatIntelligenceRecord,
} from '../../services/cyber/autonomousInvestigator.ts'
import { triggerBrowserDownload } from '../../services/cyber/cyberOutputManager.ts'
import VoicePushToTalk from '../../components/VoicePushToTalk'

const SAMPLE_INVESTIGATION_TOPICS = [
  'OpenSSH Signal Handler Race Condition (regreSSHion)',
  'Kubernetes Ingress-NGINX Lua Snippet Code Execution',
  'XZ Utils Liblzma Backdoor Supply Chain Compromise',
  'Architecture Serverless Vercel & Résilience Anti-DDoS',
]

export default function AutonomousInvestigatorLab() {
  const [query, setQuery] = useState(SAMPLE_INVESTIGATION_TOPICS[0]!)
  const [isInvestigating, setIsInvestigating] = useState(false)
  const [dossier, setDossier] = useState<DeepInvestigationDossier | null>(() =>
    runAutonomousInvestigation(SAMPLE_INVESTIGATION_TOPICS[0]!),
  )

  const handleLaunchInvestigation = () => {
    if (!query.trim() || isInvestigating) return
    setIsInvestigating(true)
    setTimeout(() => {
      setDossier(runAutonomousInvestigation(query))
      setIsInvestigating(false)
    }, 500)
  }

  const handleDownloadDossier = () => {
    if (!dossier) return
    triggerBrowserDownload(
      dossier.exportPayload.filename,
      dossier.exportPayload.content,
      'text/markdown;charset=utf-8',
    )
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4 flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-rose-500/20 text-rose-400 border border-rose-500/30">
              <Radar size={16} />
            </span>
            <h2 className="text-white text-[16px] font-bold">Investigateur Cyber Autonome & Recherche de Menaces</h2>
          </div>
          <p className="text-[12px] text-white/60 mt-1 max-w-2xl">
            Investigation approfondie par IA sur n'importe quel sujet, composant ou vecteur de menace. Corrélation de Threat Intel (CVE/NVD, EPSS, MITRE), déduction des causes racines et feuille de route de durcissement.
          </p>
        </div>
        {dossier && (
          <button
            type="button"
            onClick={handleDownloadDossier}
            className="px-3 py-1.5 rounded-lg bg-rose-500 hover:bg-rose-400 text-black text-[12px] font-bold flex items-center gap-1.5 transition-colors cursor-pointer self-start md:self-auto"
          >
            <Download size={13} /> Exporter Dossier .md
          </button>
        )}
      </div>

      {/* Query Bar */}
      <div className="rounded-xl border border-white/10 bg-black/50 p-4 space-y-3">
        <div className="flex items-center gap-2">
          <Search size={16} className="text-rose-400 shrink-0" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') void handleLaunchInvestigation()
            }}
            placeholder="Posez n'importe quelle question cyber, nom de faille, technologie ou architecture à investiguer..."
            className="flex-1 bg-transparent text-[13px] text-white font-mono outline-none placeholder:text-white/30"
          />
          <VoicePushToTalk
            onTranscript={(t) => setQuery(t)}
            label="Dicter sujet"
            size={32}
          />
          <button
            type="button"
            onClick={handleLaunchInvestigation}
            disabled={!query.trim() || isInvestigating}
            className="px-4 py-2 rounded-lg bg-rose-500 hover:bg-rose-400 text-black font-bold text-[12px] flex items-center gap-1.5 transition-colors disabled:opacity-40 cursor-pointer"
          >
            {isInvestigating ? <Loader2 size={13} className="animate-spin" /> : <Zap size={13} />}
            {isInvestigating ? 'Investigation en cours...' : 'Investiguer à Fond'}
          </button>
        </div>

        {/* Suggestion Chips */}
        <div className="flex items-center gap-1.5 flex-wrap pt-1">
          <span className="text-[10.5px] font-mono text-white/50">Suggestions :</span>
          {SAMPLE_INVESTIGATION_TOPICS.map((top, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => setQuery(top)}
              className="px-2 py-0.5 rounded-full bg-white/5 hover:bg-white/10 border border-white/10 text-[10.5px] font-mono text-white/75 transition-colors cursor-pointer"
            >
              {top}
            </button>
          ))}
        </div>
      </div>

      {dossier && (
        <div className="space-y-4">
          {/* Executive Summary Banner */}
          <div className="p-4 rounded-xl border border-rose-500/30 bg-rose-500/5 font-mono text-[12px] space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-bold text-white text-[13px]">{dossier.objective}</span>
              <span className="text-[10px] px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/30 font-bold">
                DOSSIER ID : {dossier.investigationId}
              </span>
            </div>
            <div className="text-white/80 text-[11.5px]">{dossier.executiveSummary}</div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
            {/* Left Column: Threat Intel Matches & Hypotheses */}
            <div className="lg:col-span-7 space-y-4">
              {/* Threat Intel Records */}
              <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4 space-y-3">
                <h3 className="text-[12px] font-semibold text-rose-300 uppercase tracking-wider flex items-center gap-2">
                  <Flame size={14} /> Corrélations Threat Intelligence ({dossier.threatIntelMatches.length})
                </h3>
                <div className="space-y-3">
                  {dossier.threatIntelMatches.map((t: ThreatIntelligenceRecord) => (
                    <div
                      key={t.cveId}
                      className="p-3.5 rounded-xl border border-white/10 bg-black/40 font-mono text-[11.5px] space-y-2"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-white text-[12.5px]">{t.cveId} · {t.title}</span>
                        <div className="flex items-center gap-1.5">
                          <span className="text-[9.5px] font-bold px-1.5 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/30">
                            CVSS {t.cvssScore}
                          </span>
                          <span className="text-[9.5px] font-bold px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">
                            EPSS {(t.epssProbability * 100).toFixed(0)}%
                          </span>
                        </div>
                      </div>
                      <div className="text-white/70 text-[11px]">{t.summary}</div>
                      <div className="text-emerald-400 text-[10.5px] bg-emerald-500/10 p-2 rounded border border-emerald-500/20">
                        <b>Remédiation :</b> {t.remediationSummary}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Ranked Hypotheses */}
              <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4 space-y-3">
                <h3 className="text-[12px] font-semibold text-amber-300 uppercase tracking-wider flex items-center gap-2">
                  <Brain size={14} /> Hypothèses d'Attaque & Déduction de Causes Racines
                </h3>
                <div className="space-y-3">
                  {dossier.hypothesesRanked.map((h: InvestigationHypothesis) => (
                    <div
                      key={h.id}
                      className="p-3 rounded-lg border border-amber-500/20 bg-amber-500/5 font-mono text-[11.5px] space-y-1.5"
                    >
                      <div className="flex items-center justify-between text-white font-bold">
                        <span>{h.hypothesis}</span>
                        <span className="text-[9.5px] text-amber-300">Confiance: {h.confidenceScore}%</span>
                      </div>
                      <div className="text-white/60 text-[11px]">{h.technicalEvidence}</div>
                      <div className="text-[10px] text-white/50">
                        Réf. MITRE : <span className="text-amber-300 font-bold">{h.mitreRef}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Right Column: Timeline & Actionable Hardening Roadmap */}
            <div className="lg:col-span-5 space-y-4">
              {/* Actionable Roadmap */}
              <div className="rounded-xl border border-white/10 bg-black/60 p-4 space-y-3">
                <h3 className="text-[12px] font-semibold text-emerald-400 uppercase tracking-wider flex items-center gap-2">
                  <ShieldCheck size={14} /> Plan d'Action & Remédiation Définitive
                </h3>
                <div className="space-y-3 font-mono text-[11px]">
                  <div>
                    <div className="text-rose-400 font-bold text-[10.5px] uppercase mb-1">Priorité P0 (Immédiat)</div>
                    <div className="space-y-1">
                      {dossier.actionableRoadmap.immediateP0.map((item, idx) => (
                        <div key={idx} className="p-2 rounded bg-black/50 border border-white/5 text-white/85 flex items-start gap-1.5">
                          <span className="text-rose-400 font-bold">•</span>
                          <span>{item}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div>
                    <div className="text-amber-400 font-bold text-[10.5px] uppercase mb-1">Priorité P1 (Structurel)</div>
                    <div className="space-y-1">
                      {dossier.actionableRoadmap.structuralP1.map((item, idx) => (
                        <div key={idx} className="p-2 rounded bg-black/50 border border-white/5 text-white/85 flex items-start gap-1.5">
                          <span className="text-amber-400 font-bold">•</span>
                          <span>{item}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div>
                    <div className="text-emerald-400 font-bold text-[10.5px] uppercase mb-1">Priorité P2 (Détection eBPF/Sigma)</div>
                    <div className="space-y-1">
                      {dossier.actionableRoadmap.detectionRulesP2.map((item, idx) => (
                        <div key={idx} className="p-2 rounded bg-black/50 border border-white/5 text-white/85 flex items-start gap-1.5">
                          <span className="text-emerald-400 font-bold">•</span>
                          <span>{item}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
