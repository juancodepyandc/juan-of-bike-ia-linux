import { useState } from 'react'
import {
  Activity,
  Binary,
  Cpu,
  Download,
  FileCode,
  Flame,
  Layers,
  Lock,
  RotateCcw,
  Search,
  Shield,
  ShieldCheck,
  Terminal,
  Zap,
} from 'lucide-react'
import {
  analyzeBinaryPayload,
  type BasicBlock,
  type BinaryAnalysisReport,
  type BinarySectionEntropy,
  type RopGadget,
} from '../../services/cyber/binaryAnalysisEngine.ts'
import { triggerBrowserDownload } from '../../services/cyber/cyberOutputManager.ts'

export default function BinaryDisassemblyLab() {
  const [binaryName, setBinaryName] = useState('kernel_dispatcher.elf')
  const [report, setReport] = useState<BinaryAnalysisReport>(() =>
    analyzeBinaryPayload('kernel_dispatcher.elf'),
  )

  const handleDownload = () => {
    triggerBrowserDownload(
      report.exportPayload.filename,
      report.exportPayload.content,
      'text/markdown;charset=utf-8',
    )
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4 flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-cyan-500/20 text-cyan-400 border border-cyan-500/30">
              <Binary size={16} />
            </span>
            <h2 className="text-white text-[16px] font-bold">Désassembleur x86_64, Graphe CFG & ROP Gadgets</h2>
          </div>
          <p className="text-[12px] text-white/60 mt-1 max-w-2xl">
            Inspection approfondie d'exécutables ELF/PE, extraction du graphe de flot de contrôle (CFG), recherche de gadgets ROP/JOP et cartographie d'entropie des sections.
          </p>
        </div>
        <button
          type="button"
          onClick={handleDownload}
          className="px-3 py-1.5 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-black text-[12px] font-bold flex items-center gap-1.5 transition-colors cursor-pointer self-start md:self-auto"
        >
          <Download size={13} /> Exporter Rapport Binaire .md
        </button>
      </div>

      {/* Mitigations Status Bar */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-2.5">
        <div className="p-2.5 rounded-lg border border-white/10 bg-black/40 text-center font-mono text-[11px]">
          <div className="text-white/50 text-[9.5px]">ASLR / PIE</div>
          <div className="text-emerald-400 font-bold mt-0.5">ACTIVÉ</div>
        </div>
        <div className="p-2.5 rounded-lg border border-white/10 bg-black/40 text-center font-mono text-[11px]">
          <div className="text-white/50 text-[9.5px]">STACK CANARIES</div>
          <div className="text-emerald-400 font-bold mt-0.5">PRÉSENT</div>
        </div>
        <div className="p-2.5 rounded-lg border border-white/10 bg-black/40 text-center font-mono text-[11px]">
          <div className="text-white/50 text-[9.5px]">NX / DEP</div>
          <div className="text-emerald-400 font-bold mt-0.5">ACTIVÉ (W^X)</div>
        </div>
        <div className="p-2.5 rounded-lg border border-white/10 bg-black/40 text-center font-mono text-[11px]">
          <div className="text-white/50 text-[9.5px]">RELRO</div>
          <div className="text-emerald-400 font-bold mt-0.5">FULL</div>
        </div>
        <div className="p-2.5 rounded-lg border border-white/10 bg-black/40 text-center font-mono text-[11px]">
          <div className="text-white/50 text-[9.5px]">ARCH</div>
          <div className="text-cyan-400 font-bold mt-0.5">x86_64 ABI</div>
        </div>
      </div>

      {/* Main Analysis Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Left Column: Disassembly & CFG Blocks */}
        <div className="lg:col-span-7 space-y-4">
          <div className="rounded-xl border border-white/10 bg-black/50 p-4 space-y-3">
            <h3 className="text-[12px] font-semibold text-cyan-300 uppercase tracking-wider flex items-center gap-2">
              <Layers size={14} /> Blocs de Base du Flot de Contrôle (CFG)
            </h3>
            <div className="space-y-3">
              {report.basicBlocks.map((bb: BasicBlock) => (
                <div key={bb.id} className="p-3 rounded-lg border border-white/10 bg-black/60 font-mono text-[11px] space-y-2">
                  <div className="flex items-center justify-between text-cyan-400 font-bold border-b border-white/10 pb-1.5">
                    <span>{bb.label}</span>
                    <span className="text-[9.5px] text-white/50">{bb.startAddress} ➔ {bb.endAddress}</span>
                  </div>
                  <div className="space-y-1">
                    {bb.instructions.map((inst, i) => (
                      <div key={i} className="flex items-center gap-2 hover:bg-white/5 p-0.5 rounded">
                        <span className="text-white/40 select-none w-20">{inst.address}</span>
                        <span className="text-amber-300/90 w-16">{inst.mnemonic}</span>
                        <span className="text-white/85 flex-1">{inst.operands}</span>
                        {inst.comment && <span className="text-rose-400/80 text-[10px] italic">; {inst.comment}</span>}
                      </div>
                    ))}
                  </div>
                  {bb.successors.length > 0 && (
                    <div className="text-[10px] text-white/50 pt-1 border-t border-white/5">
                      Successeurs : <span className="text-cyan-300">{bb.successors.join(', ')}</span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right Column: ROP Gadgets & Section Entropy */}
        <div className="lg:col-span-5 space-y-4">
          {/* ROP Gadget Finder */}
          <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4 space-y-3">
            <h3 className="text-[12px] font-semibold text-amber-400 uppercase tracking-wider flex items-center gap-2">
              <Zap size={14} /> ROP Gadgets Exploitables ({report.ropGadgets.length})
            </h3>
            <div className="space-y-2">
              {report.ropGadgets.map((g: RopGadget, idx: number) => (
                <div key={idx} className="p-2.5 rounded-lg border border-amber-500/20 bg-amber-500/5 font-mono text-[11px] space-y-1">
                  <div className="flex items-center justify-between text-white font-bold">
                    <span className="text-amber-300">{g.instructions}</span>
                    <span className="text-[9px] px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-200 border border-amber-500/30">{g.category}</span>
                  </div>
                  <div className="text-white/60 text-[10px] flex items-center justify-between">
                    <span>{g.address} (Bytes: <code>{g.bytesHex}</code>)</span>
                  </div>
                  <div className="text-white/80 text-[10px] italic">{g.usefulness}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Section Entropy Heatmap */}
          <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4 space-y-3">
            <h3 className="text-[12px] font-semibold text-purple-400 uppercase tracking-wider flex items-center gap-2">
              <Activity size={14} /> Entropie des Sections Binaires
            </h3>
            <div className="space-y-2">
              {report.sections.map((sec: BinarySectionEntropy, i: number) => (
                <div key={i} className="p-2.5 rounded-lg bg-black/40 border border-white/5 font-mono text-[11px] space-y-1.5">
                  <div className="flex items-center justify-between text-white font-bold">
                    <span className="text-purple-300">{sec.name}</span>
                    <span className="text-[10px] text-white/60">{sec.entropyScore} / 8.0</span>
                  </div>
                  <div className="w-full bg-white/10 h-1.5 rounded-full overflow-hidden">
                    <div
                      className="bg-purple-500 h-full rounded-full"
                      style={{ width: `${(sec.entropyScore / 8) * 100}%` }}
                    />
                  </div>
                  <div className="text-white/50 text-[10px]">{sec.analysis}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
