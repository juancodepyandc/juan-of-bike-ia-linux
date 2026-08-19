import { useMemo, useState } from 'react'
import {
  Activity,
  AlertTriangle,
  Bug,
  CheckCircle2,
  Cpu,
  Layers,
  Play,
  RotateCcw,
  Shield,
  ShieldCheck,
  Sparkles,
  Terminal,
  Zap,
} from 'lucide-react'
import {
  runFuzzingSimulation,
  ZERO_DAY_CATALOG,
  type ZeroDayArchetype,
  type ZeroDayVulnerability,
} from '../../services/cyber/zeroDayEngine'

const ACCENT = '#F43F5E'
const OK = '#4ADE80'
const WARN = '#F59E0B'
const BLUE = '#60A5FA'

export default function ZeroDayLab() {
  const [selectedVulnId, setSelectedVulnId] = useState<string>(ZERO_DAY_CATALOG[0]?.id || '')
  const [fuzzingTarget, setFuzzingTarget] = useState<ZeroDayArchetype>('use-after-free')
  const [fuzzIterations, setFuzzIterations] = useState<number>(2000)
  const [fuzzResult, setFuzzResult] = useState(() => runFuzzingSimulation('use-after-free', 2000))
  const [isFuzzing, setIsFuzzing] = useState(false)

  // Mitigations toggles
  const [aslrEnabled, setAslrEnabled] = useState(true)
  const [stackCanaryEnabled, setStackCanaryEnabled] = useState(true)
  const [nxBitEnabled, setNxBitEnabled] = useState(true)
  const [safeMemoryAlloc, setSafeMemoryAlloc] = useState(false)

  const currentVuln = useMemo<ZeroDayVulnerability>(() => {
    return ZERO_DAY_CATALOG.find((v) => v.id === selectedVulnId) ?? ZERO_DAY_CATALOG[0]!
  }, [selectedVulnId])

  const handleRunFuzzer = () => {
    setIsFuzzing(true)
    setTimeout(() => {
      const res = runFuzzingSimulation(fuzzingTarget, fuzzIterations)
      setFuzzResult(res)
      setIsFuzzing(false)
    }, 600)
  }

  // Compute overall memory exploitability status based on active mitigations
  const exploitabilityScore = useMemo(() => {
    let score = 100
    if (aslrEnabled) score -= 30
    if (stackCanaryEnabled) score -= 25
    if (nxBitEnabled) score -= 25
    if (safeMemoryAlloc) score -= 20
    return Math.max(0, score)
  }, [aslrEnabled, stackCanaryEnabled, nxBitEnabled, safeMemoryAlloc])

  return (
    <div className="space-y-4">
      {/* Header Banner */}
      <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4 flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-rose-500/20 text-rose-400 border border-rose-500/30">
              <Bug size={16} />
            </span>
            <h2 className="text-white text-[16px] font-bold">Laboratoire 0-Day & Découverte de Failles</h2>
          </div>
          <p className="text-[12px] text-white/60 mt-1 max-w-2xl">
            Analyse des primitives d'exploitation (UAF, Stack Overflow, TOCTOU, ROP), banc de fuzzing automatisé, inspection de mémoire et vérification des mitigations préventives.
          </p>
        </div>
        <div className="flex items-center gap-2 self-start md:self-auto">
          <span className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-1 text-[11px] font-mono text-rose-300 flex items-center gap-1.5">
            <Zap size={12} /> Fuzzing IPS: {fuzzResult.fuzzSpeedIps.toLocaleString()}
          </span>
        </div>
      </div>

      {/* Main Tabs / Archetype selector */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Left Column: Vulnerability Catalog & Memory Inspector */}
        <div className="space-y-4 lg:col-span-1">
          <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4 space-y-3">
            <h3 className="text-[12px] font-semibold text-white/80 uppercase tracking-wider flex items-center gap-2">
              <Cpu size={14} className="text-rose-400" />
              Catalogue de Failles 0-Day
            </h3>
            <div className="space-y-2">
              {ZERO_DAY_CATALOG.map((v) => {
                const active = v.id === selectedVulnId
                return (
                  <button
                    key={v.id}
                    type="button"
                    onClick={() => {
                      setSelectedVulnId(v.id)
                      setFuzzingTarget(v.archetype)
                    }}
                    className={`w-full text-left p-3 rounded-lg border transition-all ${
                      active
                        ? 'border-rose-500/50 bg-rose-500/15 text-white shadow-lg shadow-rose-950/40'
                        : 'border-white/5 bg-white/[0.02] text-white/70 hover:border-white/20 hover:bg-white/[0.05]'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-[11px] font-mono font-bold text-rose-300">{v.id}</span>
                      <span
                        className={`text-[9px] font-mono uppercase px-1.5 py-0.5 rounded border ${
                          v.severity === 'CRITICAL'
                            ? 'border-rose-500/40 bg-rose-500/20 text-rose-200'
                            : 'border-amber-500/40 bg-amber-500/20 text-amber-200'
                        }`}
                      >
                        CVSS {v.cvss}
                      </span>
                    </div>
                    <div className="text-[12px] font-semibold mt-1 text-white/95">{v.title}</div>
                    <div className="text-[10px] text-white/50 mt-1 flex items-center gap-2">
                      <span>{v.targetLanguage}</span>
                      <span>•</span>
                      <span>{v.targetLayer}</span>
                    </div>
                  </button>
                )
              })}
            </div>
          </div>

          {/* Memory Protection Matrix */}
          <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-[12px] font-semibold text-white/80 uppercase tracking-wider flex items-center gap-2">
                <Shield size={14} className="text-emerald-400" />
                Matrice de Mitigations
              </h3>
              <span className="text-[11px] font-mono font-bold" style={{ color: exploitabilityScore > 50 ? ACCENT : OK }}>
                Exploitabilité: {exploitabilityScore}%
              </span>
            </div>
            <div className="space-y-2">
              <label className="flex items-center justify-between p-2 rounded-lg bg-black/30 border border-white/5 cursor-pointer text-[12px]">
                <span className="text-white/80">ASLR (Randomisation Adresses)</span>
                <input
                  type="checkbox"
                  checked={aslrEnabled}
                  onChange={(e) => setAslrEnabled(e.target.checked)}
                  className="rounded border-white/20"
                />
              </label>
              <label className="flex items-center justify-between p-2 rounded-lg bg-black/30 border border-white/5 cursor-pointer text-[12px]">
                <span className="text-white/80">Stack Canaries (GCC -fstack-protector)</span>
                <input
                  type="checkbox"
                  checked={stackCanaryEnabled}
                  onChange={(e) => setStackCanaryEnabled(e.target.checked)}
                  className="rounded border-white/20"
                />
              </label>
              <label className="flex items-center justify-between p-2 rounded-lg bg-black/30 border border-white/5 cursor-pointer text-[12px]">
                <span className="text-white/80">Bit NX / DEP (Pile Non Exécutable)</span>
                <input
                  type="checkbox"
                  checked={nxBitEnabled}
                  onChange={(e) => setNxBitEnabled(e.target.checked)}
                  className="rounded border-white/20"
                />
              </label>
              <label className="flex items-center justify-between p-2 rounded-lg bg-black/30 border border-white/5 cursor-pointer text-[12px]">
                <span className="text-white/80">Rust Memory Safety / Safe Allocator</span>
                <input
                  type="checkbox"
                  checked={safeMemoryAlloc}
                  onChange={(e) => setSafeMemoryAlloc(e.target.checked)}
                  className="rounded border-white/20"
                />
              </label>
            </div>
          </div>
        </div>

        {/* Center & Right Columns: Code Diff, Root Cause & Fuzzing Playground */}
        <div className="space-y-4 lg:col-span-2">
          {/* Detailed Vulnerability Dissection */}
          <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-[13px] font-mono text-rose-300 font-bold">{currentVuln.cwe}</span>
              <span className="text-[11px] font-mono text-white/50">Méthode : {currentVuln.discoveryMethod}</span>
            </div>
            <h3 className="text-[15px] font-bold text-white">{currentVuln.title}</h3>
            <p className="text-[12px] text-white/80 leading-relaxed bg-black/40 p-3 rounded-lg border border-white/5">
              <b className="text-rose-400">Cause racine :</b> {currentVuln.rootCause}
            </p>
            <div className="text-[12px] text-white/70 bg-black/30 p-2.5 rounded-lg border border-white/5 flex items-start gap-2">
              <AlertTriangle size={14} className="text-amber-400 shrink-0 mt-0.5" />
              <span>
                <b className="text-white/90">Primitive d'exploitation :</b> {currentVuln.exploitPrimitive}
              </span>
            </div>

            {/* Side-by-Side Code Diff */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2">
              <div className="space-y-1.5">
                <div className="text-[11px] font-mono font-bold text-rose-400 flex items-center gap-1.5">
                  <AlertTriangle size={12} /> Code Vulnérable ({currentVuln.targetLanguage})
                </div>
                <pre className="p-3 rounded-lg bg-black/60 border border-rose-500/20 text-[10.5px] font-mono text-rose-200 overflow-x-auto leading-relaxed max-h-60">
                  <code>{currentVuln.vulnerableCode}</code>
                </pre>
              </div>
              <div className="space-y-1.5">
                <div className="text-[11px] font-mono font-bold text-emerald-400 flex items-center gap-1.5">
                  <ShieldCheck size={12} /> Correctif Sécurisé (Patched)
                </div>
                <pre className="p-3 rounded-lg bg-black/60 border border-emerald-500/20 text-[10.5px] font-mono text-emerald-200 overflow-x-auto leading-relaxed max-h-60">
                  <code>{currentVuln.patchedCode}</code>
                </pre>
              </div>
            </div>

            {/* Reproduction steps */}
            <div className="pt-2">
              <div className="text-[11px] font-mono uppercase tracking-wider text-white/60 mb-1.5">Étapes de Reproduction & Preuve</div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px] font-mono text-white/75">
                {currentVuln.reproductionSteps.map((step, idx) => (
                  <div key={idx} className="p-2 rounded bg-black/30 border border-white/5">
                    {step}
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Fuzzing Engine Simulator */}
          <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-[12px] font-semibold text-white/80 uppercase tracking-wider flex items-center gap-2">
                <Terminal size={14} className="text-rose-400" />
                Simulateur de Fuzzing Mutatif en Direct
              </h3>
              <div className="flex items-center gap-2">
                <span className="text-[11px] font-mono text-white/50">{fuzzIterations} itérations</span>
                <button
                  type="button"
                  onClick={handleRunFuzzer}
                  disabled={isFuzzing}
                  className="px-3 py-1 rounded-lg bg-rose-500 text-black text-[11px] font-bold flex items-center gap-1.5 hover:bg-rose-400 transition-colors disabled:opacity-50 cursor-pointer"
                >
                  {isFuzzing ? <RotateCcw size={12} className="animate-spin" /> : <Play size={12} fill="currentColor" />}
                  {isFuzzing ? 'Fuzzing en cours...' : 'Lancer Fuzzer'}
                </button>
              </div>
            </div>

            {/* Metrics */}
            <div className="grid grid-cols-3 gap-2 text-center font-mono">
              <div className="p-2.5 rounded-lg bg-black/40 border border-white/5">
                <div className="text-[10px] text-white/50 uppercase">Couverture Code</div>
                <div className="text-[15px] font-bold text-emerald-400 mt-0.5">{fuzzResult.codeCoveragePct}%</div>
              </div>
              <div className="p-2.5 rounded-lg bg-black/40 border border-white/5">
                <div className="text-[10px] text-white/50 uppercase">Crashes Détectés</div>
                <div className="text-[15px] font-bold text-rose-400 mt-0.5">{fuzzResult.uniqueCrashes}</div>
              </div>
              <div className="p-2.5 rounded-lg bg-black/40 border border-white/5">
                <div className="text-[10px] text-white/50 uppercase">Vitesse Exécution</div>
                <div className="text-[15px] font-bold text-sky-400 mt-0.5">{fuzzResult.fuzzSpeedIps} ips</div>
              </div>
            </div>

            {/* Crash Dumps Log */}
            <div className="space-y-1.5 max-h-48 overflow-y-auto font-mono text-[11px]">
              {fuzzResult.crashLogs.map((log, idx) => (
                <div key={idx} className="p-2 rounded bg-black/50 border border-rose-500/20 text-white/80 space-y-1">
                  <div className="flex items-center justify-between text-[10px]">
                    <span className="text-rose-400 font-bold">CRASH #{log.iteration} · {log.signal}</span>
                    <span className="text-white/40">Addr: {log.faultAddress}</span>
                  </div>
                  <div className="text-white/70 text-[10.5px]">{log.inferredVuln}</div>
                  <div className="text-emerald-300/80 text-[10px]">Fix suggéré: {log.remedy}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
