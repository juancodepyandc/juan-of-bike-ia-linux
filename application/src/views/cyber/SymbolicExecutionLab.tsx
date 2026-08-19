import { useState } from 'react'
import {
  Brain,
  CheckCircle2,
  Code2,
  Copy,
  Cpu,
  Download,
  FileCode,
  Flame,
  Layers,
  Loader2,
  Play,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Zap,
} from 'lucide-react'
import {
  runSymbolicExecution,
  type SymbolicExecutionReport,
  type SymbolicPath,
} from '../../services/cyber/symbolicExecutionEngine.ts'
import { triggerBrowserDownload } from '../../services/cyber/cyberOutputManager.ts'

export default function SymbolicExecutionLab() {
  const [functionName, setFunctionName] = useState('process_payload')
  const [isRunning, setIsRunning] = useState(false)
  const [report, setReport] = useState<SymbolicExecutionReport | null>(() =>
    runSymbolicExecution('', 'process_payload'),
  )
  const [copied, setCopied] = useState(false)

  const handleRun = () => {
    setIsRunning(true)
    setTimeout(() => {
      setReport(runSymbolicExecution('', functionName))
      setIsRunning(false)
    }, 400)
  }

  const handleDownload = () => {
    if (!report) return
    triggerBrowserDownload(
      report.exportPayload.filename,
      report.exportPayload.content,
      'text/markdown;charset=utf-8',
    )
  }

  const handleCopyCode = async () => {
    if (!report) return
    try {
      await navigator.clipboard.writeText(report.provablyCorrectCode)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // ignore
    }
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4 flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-amber-500/20 text-amber-400 border border-amber-500/30">
              <Cpu size={16} />
            </span>
            <h2 className="text-white text-[16px] font-bold">Exécution Symbolique & Solveur SMT (Z3-Style)</h2>
          </div>
          <p className="text-[12px] text-white/60 mt-1 max-w-2xl">
            Vérification formelle et exploration mathématique exhaustive des chemins d'exécution. Détection de conditions de crash et synthèse de preuves de non-interférence.
          </p>
        </div>
        {report && (
          <button
            type="button"
            onClick={handleDownload}
            className="px-3 py-1.5 rounded-lg bg-amber-500 hover:bg-amber-400 text-black text-[12px] font-bold flex items-center gap-1.5 transition-colors cursor-pointer self-start md:self-auto"
          >
            <Download size={13} /> Exporter Preuve .md
          </button>
        )}
      </div>

      {/* Control bar */}
      <div className="rounded-xl border border-white/10 bg-black/40 p-3.5 flex items-center gap-3">
        <span className="text-[12px] font-mono text-white/70 font-bold uppercase">Fonction Cible :</span>
        <input
          type="text"
          value={functionName}
          onChange={(e) => setFunctionName(e.target.value)}
          className="flex-1 bg-black/50 border border-white/10 rounded-lg px-3 py-1.5 text-[12px] font-mono text-white outline-none"
        />
        <button
          type="button"
          onClick={handleRun}
          disabled={isRunning}
          className="px-4 py-2 rounded-lg bg-amber-500 hover:bg-amber-400 text-black font-bold text-[12px] flex items-center gap-1.5 transition-colors cursor-pointer"
        >
          {isRunning ? <Loader2 size={13} className="animate-spin" /> : <Play size={13} />}
          Résoudre Contraintes SMT
        </button>
      </div>

      {report && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
          {/* Left Column: Explored Paths */}
          <div className="lg:col-span-7 space-y-3">
            <h3 className="text-[12px] font-semibold text-amber-300 uppercase tracking-wider flex items-center gap-2">
              <Layers size={14} /> Chemins d'Exécution Symboliques Découverts ({report.exploredPaths.length})
            </h3>
            <div className="space-y-3">
              {report.exploredPaths.map((p: SymbolicPath) => {
                const isSafe = p.reachedState === 'SAFE'
                return (
                  <div
                    key={p.id}
                    className={`p-3.5 rounded-xl border space-y-2 text-[11.5px] font-mono ${
                      isSafe
                        ? 'border-emerald-500/30 bg-emerald-500/5 text-emerald-100'
                        : 'border-rose-500/30 bg-rose-500/5 text-rose-100'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-white text-[12.5px]">{p.name}</span>
                      <span
                        className={`text-[9.5px] font-bold px-2 py-0.5 rounded border ${
                          isSafe
                            ? 'border-emerald-500/40 bg-emerald-500/20 text-emerald-300'
                            : 'border-rose-500/40 bg-rose-500/20 text-rose-300'
                        }`}
                      >
                        {p.reachedState}
                      </span>
                    </div>
                    <div className="text-white/70 text-[11px]">
                      <b>Contraintes :</b> <code>{p.conditions.join(' ∧ ')}</code>
                    </div>
                    {p.counterExampleInput && (
                      <div className="p-2 rounded bg-black/60 border border-white/10 text-[10.5px]">
                        <span className="text-amber-300 font-bold">Contre-Exemple SMT : </span>
                        <code>{JSON.stringify(p.counterExampleInput)}</code>
                      </div>
                    )}
                    {p.proofOfViolation && (
                      <div className="text-rose-200/90 text-[10.5px] bg-rose-500/10 p-2 rounded border border-rose-500/20">
                        {p.proofOfViolation}
                      </div>
                    )}
                    <div className="text-emerald-300 text-[10.5px]">
                      <b>Remédiation :</b> {p.invariantRemedy}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Right Column: Mathematical Proof & Provably Safe Code */}
          <div className="lg:col-span-5 space-y-4">
            <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4 space-y-2.5">
              <h3 className="text-[12px] font-semibold text-white/80 uppercase tracking-wider flex items-center gap-2">
                <Brain size={14} className="text-amber-400" />
                Preuve Formelle SMT
              </h3>
              <div className="p-3 rounded-lg bg-black/60 border border-white/10 text-[11px] font-mono text-amber-200/90 leading-relaxed whitespace-pre-wrap">
                {report.mathematicalProof}
              </div>
            </div>

            <div className="rounded-xl border border-emerald-500/30 bg-black/60 p-4 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[11.5px] font-mono uppercase text-emerald-400 font-bold flex items-center gap-1.5">
                  <ShieldCheck size={14} /> Code Vérifié Formellement
                </span>
                <button
                  type="button"
                  onClick={handleCopyCode}
                  className="text-[11px] font-mono text-white/60 hover:text-white flex items-center gap-1 cursor-pointer"
                >
                  <Copy size={11} /> {copied ? 'Copié !' : 'Copier'}
                </button>
              </div>
              <pre className="p-3 rounded-lg bg-black/80 border border-emerald-500/20 text-[10.5px] font-mono text-emerald-200 overflow-x-auto max-h-56">
                <code>{report.provablyCorrectCode}</code>
              </pre>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
