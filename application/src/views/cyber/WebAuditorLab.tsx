import { useState } from 'react'
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Copy,
  Download,
  FileCode,
  Globe,
  Loader2,
  Lock,
  Play,
  RefreshCw,
  Search,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Zap,
} from 'lucide-react'
import {
  auditWebEndpoint,
  type SecurityHeaderCheck,
  type WebAuditResult,
} from '../../services/cyber/webEndpointAuditor'
import { triggerBrowserDownload } from '../../services/cyber/cyberOutputManager'
import VoicePushToTalk from '../../components/VoicePushToTalk'

const ACCENT = '#F43F5E'
const OK = '#4ADE80'
const WARN = '#F59E0B'
const BLUE = '#60A5FA'

export default function WebAuditorLab() {
  const [targetUrl, setTargetUrl] = useState('https://site-rep.vercel.app')
  const [isAuditing, setIsAuditing] = useState(false)
  const [auditResult, setAuditResult] = useState<WebAuditResult | null>(() =>
    auditWebEndpoint('https://site-rep.vercel.app'),
  )
  const [copiedKey, setCopiedKey] = useState<string | null>(null)

  const handleRunAudit = async () => {
    if (!targetUrl.trim() || isAuditing) return
    setIsAuditing(true)

    // Simulation de récupération passive des en-têtes et analyse
    setTimeout(() => {
      // Analyse locale déterministe avec en-têtes types de déploiement
      const result = auditWebEndpoint(targetUrl)
      setAuditResult(result)
      setIsAuditing(false)
    }, 500)
  }

  const handleCopyCode = async (key: string, code: string) => {
    try {
      await navigator.clipboard.writeText(code)
      setCopiedKey(key)
      setTimeout(() => setCopiedKey(null), 2000)
    } catch {
      // ignore
    }
  }

  const handleDownloadReport = () => {
    if (!auditResult) return
    triggerBrowserDownload(
      auditResult.exportPayload.filename,
      auditResult.exportPayload.content,
      'text/markdown;charset=utf-8',
    )
  }

  return (
    <div className="space-y-4">
      {/* Top Banner */}
      <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4 flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
              <Globe size={16} />
            </span>
            <h2 className="text-white text-[16px] font-bold">Auditeur de Sécurité Web & Résilience DoS</h2>
          </div>
          <p className="text-[12px] text-white/60 mt-1 max-w-2xl">
            Audit d'architecture, conformité des en-têtes HTTP de sécurité, analyse de résilience DoS et génération automatique de guides de durcissement exportés dans <code className="text-emerald-300">application/output/cyber/</code>.
          </p>
        </div>
        {auditResult && (
          <button
            type="button"
            onClick={handleDownloadReport}
            className="px-3 py-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-black text-[12px] font-bold flex items-center gap-1.5 transition-colors cursor-pointer self-start md:self-auto"
          >
            <Download size={13} /> Exporter Rapport .md
          </button>
        )}
      </div>

      {/* Target URL Input Bar */}
      <div className="rounded-xl border border-white/10 bg-black/40 p-3.5 flex items-center gap-2.5">
        <Globe size={16} className="text-emerald-400 shrink-0" />
        <input
          type="text"
          value={targetUrl}
          onChange={(e) => setTargetUrl(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') void handleRunAudit()
          }}
          placeholder="Entrez l'URL à auditer (ex: https://mon-site.vercel.app)..."
          className="flex-1 bg-transparent text-[13px] text-white font-mono outline-none placeholder:text-white/30"
        />
        <VoicePushToTalk
          onTranscript={(t) => setTargetUrl(t.replace(/\s+/g, ''))}
          label="Dicter l'URL"
          size={32}
        />
        <button
          type="button"
          onClick={handleRunAudit}
          disabled={!targetUrl.trim() || isAuditing}
          className="px-4 py-2 rounded-lg bg-rose-500 hover:bg-rose-400 text-black font-bold text-[12px] flex items-center gap-1.5 transition-colors disabled:opacity-40 cursor-pointer"
        >
          {isAuditing ? <Loader2 size={13} className="animate-spin" /> : <Search size={13} />}
          {isAuditing ? 'Audit en cours...' : 'Lancer l\'audit'}
        </button>
      </div>

      {/* Audit Results Grid */}
      {auditResult && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
          {/* Left Column: Scores & Headers Matrix */}
          <div className="lg:col-span-7 space-y-4">
            {/* Score & Grade Overview */}
            <div className="grid grid-cols-3 gap-3">
              <div className="p-3.5 rounded-xl border border-white/10 bg-white/[0.02] text-center font-mono">
                <div className="text-[10.5px] uppercase text-white/50">Score de Sécurité</div>
                <div className="text-[22px] font-bold mt-0.5" style={{ color: auditResult.securityScore >= 75 ? OK : WARN }}>
                  {auditResult.securityScore}/100
                </div>
              </div>
              <div className="p-3.5 rounded-xl border border-white/10 bg-white/[0.02] text-center font-mono">
                <div className="text-[10.5px] uppercase text-white/50">Grade Global</div>
                <div className="text-[22px] font-bold text-emerald-400 mt-0.5">
                  {auditResult.grade}
                </div>
              </div>
              <div className="p-3.5 rounded-xl border border-white/10 bg-white/[0.02] text-center font-mono">
                <div className="text-[10.5px] uppercase text-white/50">Résilience DoS</div>
                <div className="text-[22px] font-bold text-sky-400 mt-0.5">
                  {auditResult.dosResilienceScore}/100
                </div>
              </div>
            </div>

            {/* HTTP Security Headers Analysis Table */}
            <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4 space-y-3">
              <h3 className="text-[12px] font-semibold text-white/80 uppercase tracking-wider flex items-center gap-2">
                <ShieldCheck size={14} className="text-emerald-400" />
                Conformité des En-Têtes de Sécurité HTTP
              </h3>
              <div className="space-y-2">
                {auditResult.headersAnalysis.map((item: SecurityHeaderCheck, i: number) => {
                  const isPass = item.status === 'PASS'
                  return (
                    <div
                      key={i}
                      className={`p-3 rounded-lg border text-[11.5px] font-mono ${
                        isPass
                          ? 'border-emerald-500/30 bg-emerald-500/5 text-emerald-200'
                          : 'border-rose-500/30 bg-rose-500/5 text-rose-200'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-white text-[12px]">{item.header}</span>
                        <span
                          className={`text-[9.5px] font-bold px-1.5 py-0.5 rounded border ${
                            isPass
                              ? 'border-emerald-500/40 bg-emerald-500/20 text-emerald-300'
                              : 'border-rose-500/40 bg-rose-500/20 text-rose-300'
                          }`}
                        >
                          {item.status} ({item.severity})
                        </span>
                      </div>
                      <div className="text-white/70 text-[11px] mt-1">{item.explanation}</div>
                      {!isPass && (
                        <div className="text-white/50 text-[10px] mt-1 bg-black/40 p-1.5 rounded">
                          Recommandé : <code className="text-emerald-300">{item.recommended}</code>
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>

            {/* DoS & Rate Limiting Observations */}
            <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4 space-y-2.5">
              <h3 className="text-[12px] font-semibold text-sky-300 uppercase tracking-wider flex items-center gap-2">
                <Activity size={14} />
                Observations de Résilience DoS & Protection d'Infrastructure
              </h3>
              <div className="space-y-1.5 text-[11.5px] text-white/80">
                {auditResult.dosObservations.map((obs: string, idx: number) => (
                  <div key={idx} className="p-2 rounded bg-black/30 border border-white/5 flex items-start gap-2">
                    <span className="text-sky-400 font-bold shrink-0 mt-0.5">•</span>
                    <span>{obs}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Right Column: Instant Hardening Snippets (vercel.json / next.config.js / middleware.ts) */}
          <div className="lg:col-span-5 space-y-4">
            {/* vercel.json snippet */}
            <div className="rounded-xl border border-white/10 bg-black/50 p-4 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[11.5px] font-mono text-emerald-400 font-bold flex items-center gap-1.5">
                  <FileCode size={13} /> vercel.json (Headers)
                </span>
                <button
                  type="button"
                  onClick={() => handleCopyCode('vercel', auditResult.recommendedHardening.vercelJsonConfig)}
                  className="text-[11px] font-mono text-white/60 hover:text-white flex items-center gap-1 cursor-pointer"
                >
                  <Copy size={11} /> {copiedKey === 'vercel' ? 'Copié !' : 'Copier'}
                </button>
              </div>
              <pre className="p-2.5 rounded bg-black/70 border border-white/5 text-[10px] font-mono text-emerald-200/90 overflow-x-auto max-h-44">
                <code>{auditResult.recommendedHardening.vercelJsonConfig}</code>
              </pre>
            </div>

            {/* next.config.js snippet */}
            <div className="rounded-xl border border-white/10 bg-black/50 p-4 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[11.5px] font-mono text-sky-400 font-bold flex items-center gap-1.5">
                  <FileCode size={13} /> next.config.js (Sécurité)
                </span>
                <button
                  type="button"
                  onClick={() => handleCopyCode('next', auditResult.recommendedHardening.nextConfigJs)}
                  className="text-[11px] font-mono text-white/60 hover:text-white flex items-center gap-1 cursor-pointer"
                >
                  <Copy size={11} /> {copiedKey === 'next' ? 'Copié !' : 'Copier'}
                </button>
              </div>
              <pre className="p-2.5 rounded bg-black/70 border border-white/5 text-[10px] font-mono text-sky-200/90 overflow-x-auto max-h-44">
                <code>{auditResult.recommendedHardening.nextConfigJs}</code>
              </pre>
            </div>

            {/* middleware.ts snippet */}
            <div className="rounded-xl border border-white/10 bg-black/50 p-4 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[11.5px] font-mono text-purple-400 font-bold flex items-center gap-1.5">
                  <Lock size={13} /> middleware.ts (Rate-Limiting)
                </span>
                <button
                  type="button"
                  onClick={() => handleCopyCode('middleware', auditResult.recommendedHardening.middlewareRateLimit)}
                  className="text-[11px] font-mono text-white/60 hover:text-white flex items-center gap-1 cursor-pointer"
                >
                  <Copy size={11} /> {copiedKey === 'middleware' ? 'Copié !' : 'Copier'}
                </button>
              </div>
              <pre className="p-2.5 rounded bg-black/70 border border-white/5 text-[10px] font-mono text-purple-200/90 overflow-x-auto max-h-44">
                <code>{auditResult.recommendedHardening.middlewareRateLimit}</code>
              </pre>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
