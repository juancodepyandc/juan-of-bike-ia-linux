import { useState } from 'react'
import {
  Activity,
  Code2,
  Copy,
  Cpu,
  Download,
  FileCode,
  Layers,
  Lock,
  Radio,
  Server,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Terminal,
  Zap,
} from 'lucide-react'
import {
  EBPF_KERNEL_PROBES,
  generateEbpfPolicyBundle,
  type EbpfProbeDefinition,
} from '../../services/cyber/ebpfKernelEngine.ts'
import { triggerBrowserDownload } from '../../services/cyber/cyberOutputManager.ts'

export default function EbpfKernelLab() {
  const [selectedProbeId, setSelectedProbeId] = useState<string>(EBPF_KERNEL_PROBES[0]!.id)
  const [copied, setCopied] = useState(false)

  const activeProbe =
    EBPF_KERNEL_PROBES.find((p) => p.id === selectedProbeId) ?? EBPF_KERNEL_PROBES[0]!

  const handleDownloadBundle = () => {
    const bundle = generateEbpfPolicyBundle()
    triggerBrowserDownload(
      bundle.exportPayload.filename,
      bundle.exportPayload.content,
      'text/markdown;charset=utf-8',
    )
  }

  const handleCopyCode = async () => {
    try {
      await navigator.clipboard.writeText(activeProbe.cSourceCode)
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
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
              <Server size={16} />
            </span>
            <h2 className="text-white text-[16px] font-bold">Observabilité & Sécurité Noyau Linux eBPF / LSM</h2>
          </div>
          <p className="text-[12px] text-white/60 mt-1 max-w-2xl">
            Sondes de sécurité Ring 0, hooks LSM (Linux Security Modules) pour empêcher le spawn de shell, et filtres réseau XDP pour neutraliser les attaques en amont.
          </p>
        </div>
        <button
          type="button"
          onClick={handleDownloadBundle}
          className="px-3 py-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-black text-[12px] font-bold flex items-center gap-1.5 transition-colors cursor-pointer self-start md:self-auto"
        >
          <Download size={13} /> Exporter Bundle eBPF .md
        </button>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Left: Probe Selector */}
        <div className="lg:col-span-5 space-y-3">
          <h3 className="text-[12px] font-semibold text-white/80 uppercase tracking-wider flex items-center gap-2">
            <Layers size={14} className="text-emerald-400" />
            Catalogue de Sondes eBPF Disponibles
          </h3>
          <div className="space-y-2">
            {EBPF_KERNEL_PROBES.map((probe: EbpfProbeDefinition) => {
              const isSelected = probe.id === selectedProbeId
              return (
                <button
                  key={probe.id}
                  type="button"
                  onClick={() => setSelectedProbeId(probe.id)}
                  className={`w-full p-3 rounded-xl border text-left transition-all cursor-pointer font-mono ${
                    isSelected
                      ? 'border-emerald-500 bg-emerald-500/10 text-white'
                      : 'border-white/10 bg-white/[0.02] text-white/70 hover:bg-white/5'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-[12px]">{probe.name}</span>
                    <span className="text-[9.5px] uppercase px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                      {probe.hookType}
                    </span>
                  </div>
                  <div className="text-[11px] text-white/50 mt-1 line-clamp-2">{probe.description}</div>
                  <div className="text-[10px] text-emerald-400/90 mt-1.5 flex items-center gap-2">
                    <span>Hook: <code>{probe.targetHook}</code></span>
                    <span>• {probe.mitreTechnique}</span>
                  </div>
                </button>
              )
            })}
          </div>
        </div>

        {/* Right: Code Inspector & Hook Properties */}
        <div className="lg:col-span-7 space-y-4">
          <div className="rounded-xl border border-white/10 bg-black/50 p-4 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-[12px] font-mono text-emerald-400 font-bold flex items-center gap-2">
                <Code2 size={15} /> Code Source Sonde eBPF C ({activeProbe.hookType})
              </span>
              <button
                type="button"
                onClick={handleCopyCode}
                className="text-[11px] font-mono text-white/60 hover:text-white flex items-center gap-1 cursor-pointer"
              >
                <Copy size={11} /> {copied ? 'Copié !' : 'Copier Code C'}
              </button>
            </div>

            <pre className="p-3.5 rounded-lg bg-black/80 border border-emerald-500/20 text-[11px] font-mono text-emerald-200/90 overflow-x-auto max-h-[380px] leading-relaxed">
              <code>{activeProbe.cSourceCode}</code>
            </pre>

            <div className="p-3 rounded-lg bg-emerald-500/5 border border-emerald-500/20 text-[11.5px] font-mono space-y-1">
              <div className="text-emerald-300 font-bold">Objectif Défensif :</div>
              <div className="text-white/80 text-[11px]">{activeProbe.mitigationGoal}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
