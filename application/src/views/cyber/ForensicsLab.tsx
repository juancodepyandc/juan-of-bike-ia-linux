import { useCallback, useState } from 'react'
import { FileSearch, Fingerprint, Loader2, Scan, Upload } from 'lucide-react'
import {
  cyberEntropy,
  cyberExif,
  cyberFileHashes,
  cyberMagic,
  cyberMemScan,
  cyberStrings,
  type EntropyResult,
  type ExifResult,
  type FileHashesResult,
  type MagicResult,
  type MemScanResult,
  type StringsResult,
} from '../../services/cyber/pythonClient'
import { detectMagic, extractStrings, hexDump, parseExif } from '../../services/cyber/forensicsTools'

type Tab = 'magic' | 'hashes' | 'strings' | 'exif' | 'entropy' | 'memscan' | 'hex' | 'browser'

const TABS: Array<{ id: Tab; label: string }> = [
  { id: 'browser', label: 'Browser analyzer (offline)' },
  { id: 'magic', label: 'File magic' },
  { id: 'hashes', label: 'Hash du fichier' },
  { id: 'strings', label: 'Strings' },
  { id: 'exif', label: 'EXIF' },
  { id: 'entropy', label: 'Entropie' },
  { id: 'memscan', label: 'Memory scan' },
  { id: 'hex', label: 'Hex viewer' },
]

export default function ForensicsLab() {
  const [tab, setTab] = useState<Tab>('magic')
  const [path, setPath] = useState('')

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4">
        <h2 className="text-white text-[15px] font-semibold mb-1">Forensics — analyser un fichier</h2>
        <p className="text-[12px] text-white/60">
          Identifier le vrai format d'un fichier malgré son extension, extraire métadonnées et strings,
          mesurer l'entropie pour détecter chiffrement/packing.
        </p>
      </div>
      <FilePicker path={path} onPath={setPath} />
      <div className="flex gap-1 overflow-x-auto no-scrollbar border-b border-white/10 pb-2">
        {TABS.map((t) => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`whitespace-nowrap rounded-lg px-3 py-1.5 text-[12px] transition-colors ${
              tab === t.id
                ? 'bg-violet-500/20 text-violet-200 border border-violet-500/40'
                : 'text-white/55 hover:text-white/80 hover:bg-white/5'
            }`}>
            {t.label}
          </button>
        ))}
      </div>
      {tab === 'browser' && <BrowserAnalyzer />}
      {!path && tab !== 'browser' && <p className="text-white/50 text-[12px]">→ Choisis d'abord un chemin de fichier (ou utilise « Browser analyzer » pour drag-drop).</p>}
      {path && tab === 'magic' && <MagicTool path={path} />}
      {path && tab === 'hashes' && <HashesTool path={path} />}
      {path && tab === 'strings' && <StringsTool path={path} />}
      {path && tab === 'exif' && <ExifTool path={path} />}
      {path && tab === 'entropy' && <EntropyTool path={path} />}
      {path && tab === 'memscan' && <MemScanTool path={path} />}
      {path && tab === 'hex' && <HexViewer path={path} />}
    </div>
  )
}

function FilePicker({ path, onPath }: { path: string; onPath: (p: string) => void }) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4">
      <label className="text-[11px] uppercase tracking-wider text-white/60 flex items-center gap-2 mb-2">
        <Upload size={12} /> Chemin du fichier à analyser dans le workspace Aurora
      </label>
      <input value={path} onChange={(e) => onPath(e.target.value)}
        placeholder="uploads\sample.bin ou C:\...\AuroraIA-v2\application\uploads\sample.bin"
        className="w-full rounded-lg bg-black/40 border border-white/10 px-3 py-2 text-[12px] text-white/90 font-mono" />
      <p className="text-[10px] text-white/45 mt-2">Le backend Python lit uniquement dans application/. Pour un fichier ailleurs sur la machine, utilise « Browser analyzer » : tout reste local dans le navigateur.</p>
    </div>
  )
}

function useRun<T>() {
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [data, setData] = useState<T | null>(null)
  const run = async (fn: () => Promise<T>) => {
    setBusy(true); setErr('')
    try { setData(await fn()) }
    catch (e) { setErr(String(e)) }
    finally { setBusy(false) }
  }
  return { busy, err, data, run }
}

function ToolBox({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4">
      <h3 className="text-[12px] font-semibold text-white/80 uppercase tracking-wider mb-3">{title}</h3>
      {children}
    </div>
  )
}

function RunButton({ busy, onClick, icon, label }: { busy: boolean; onClick: () => void; icon: React.ReactNode; label: string }) {
  return (
    <button disabled={busy} onClick={onClick}
      className="inline-flex items-center gap-2 rounded-lg bg-violet-500/20 border border-violet-500/40 text-violet-200 px-3 py-1.5 text-[12px] hover:bg-violet-500/30 disabled:opacity-50 mb-3">
      {busy ? <Loader2 size={13} className="animate-spin" /> : icon} {label}
    </button>
  )
}

function MagicTool({ path }: { path: string }) {
  const { busy, err, data, run } = useRun<MagicResult>()
  return (
    <ToolBox title="File magic — vrai format du fichier">
      <RunButton busy={busy} onClick={() => run(() => cyberMagic(path))} icon={<Scan size={13} />} label="analyser" />
      {err && <ErrorBox message={err} />}
      {data && <JsonBox value={data as unknown as Record<string, unknown>} />}
    </ToolBox>
  )
}

function HashesTool({ path }: { path: string }) {
  const { busy, err, data, run } = useRun<FileHashesResult>()
  return (
    <ToolBox title="Hash (MD5, SHA1, SHA256)">
      <RunButton busy={busy} onClick={() => run(() => cyberFileHashes(path))} icon={<Fingerprint size={13} />} label="calculer" />
      {err && <ErrorBox message={err} />}
      {data && <JsonBox value={data as unknown as Record<string, unknown>} />}
    </ToolBox>
  )
}

function StringsTool({ path }: { path: string }) {
  const { busy, err, data, run } = useRun<StringsResult>()
  return (
    <ToolBox title="Extraction de strings">
      <RunButton busy={busy} onClick={() => run(() => cyberStrings(path))} icon={<FileSearch size={13} />} label="extraire" />
      {err && <ErrorBox message={err} />}
      {data?.strings && (
        <div className="rounded-lg bg-black/50 border border-white/5 p-3 text-[10px] font-mono max-h-96 overflow-auto">
          {data.strings.slice(0, 500).map((s, i) => (
            <div key={i} className="flex gap-3 py-0.5 border-b border-white/5">
              <span className="text-white/40 w-20 shrink-0">0x{s.offset.toString(16).padStart(8, '0')}</span>
              <span className="text-white/40 w-8 shrink-0">{s.encoding}</span>
              <span className="text-white/85 break-all">{s.value}</span>
            </div>
          ))}
          {data.strings.length > 500 && <p className="text-white/50 mt-2">…{data.strings.length - 500} autres omis</p>}
        </div>
      )}
    </ToolBox>
  )
}

function ExifTool({ path }: { path: string }) {
  const { busy, err, data, run } = useRun<ExifResult>()
  return (
    <ToolBox title="EXIF — métadonnées image">
      <RunButton busy={busy} onClick={() => run(() => cyberExif(path))} icon={<FileSearch size={13} />} label="extraire EXIF" />
      {err && <ErrorBox message={err} />}
      {data && <JsonBox value={data as unknown as Record<string, unknown>} />}
    </ToolBox>
  )
}

function EntropyTool({ path }: { path: string }) {
  const { busy, err, data, run } = useRun<EntropyResult>()
  return (
    <ToolBox title="Entropie par blocs (détecter chiffrement/compression)">
      <RunButton busy={busy} onClick={() => run(() => cyberEntropy(path))} icon={<Scan size={13} />} label="analyser" />
      {err && <ErrorBox message={err} />}
      {data?.global !== undefined && (
        <div className="rounded-lg bg-black/30 border border-white/10 p-3 mb-3">
          <p className="text-[11px] text-white/60">Entropie globale</p>
          <p className="text-[24px] font-mono text-white">{data.global.toFixed(3)} / 8</p>
          <p className="text-[11px] text-white/50 mt-1">
            {data.global > 7.5 ? '⚠ très haute — chiffré/compressé probable' :
             data.global > 6.5 ? 'haute — code exécutable ou compressé' :
             data.global > 4.5 ? 'moyenne — texte/binaire mixte' : 'basse — texte clair ou données structurées'}
          </p>
        </div>
      )}
      {data?.blocks && (
        <div className="rounded-lg bg-black/50 border border-white/5 p-3">
          <p className="text-[11px] text-white/60 mb-2">Profil par blocs (64 KiB)</p>
          <div className="flex items-end gap-0.5 h-20">
            {data.blocks.map((b, i) => (
              <div key={i} className="flex-1 bg-violet-400/70" style={{ height: `${(b.entropy / 8) * 100}%` }}
                title={`offset 0x${b.offset.toString(16)}: ${b.entropy.toFixed(2)}`} />
            ))}
          </div>
        </div>
      )}
    </ToolBox>
  )
}

function MemScanTool({ path }: { path: string }) {
  const { busy, err, data, run } = useRun<MemScanResult>()
  return (
    <ToolBox title="Memory scan — patterns suspects">
      <RunButton busy={busy} onClick={() => run(() => cyberMemScan(path))} icon={<FileSearch size={13} />} label="scanner" />
      {err && <ErrorBox message={err} />}
      {data?.matches && (
        <div className="rounded-lg bg-black/50 border border-white/5 p-3 text-[10px] font-mono max-h-96 overflow-auto">
          {data.matches.map((m, i) => (
            <div key={i} className="flex gap-3 py-0.5 border-b border-white/5">
              <span className="text-white/40 w-20 shrink-0">0x{m.offset.toString(16).padStart(8, '0')}</span>
              <span className="text-amber-300 w-20 shrink-0">{m.pattern}</span>
              <span className="text-white/85 break-all">{m.value}</span>
            </div>
          ))}
        </div>
      )}
    </ToolBox>
  )
}

function HexViewer({ path }: { path: string }) {
  const [bytes, setBytes] = useState<Uint8Array | null>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  const load = useCallback(async () => {
    setBusy(true); setErr('')
    try {
      const { fsReadBinary } = await import('../../hooks/useTauri')
      const buf = await fsReadBinary(path)
      setBytes(buf instanceof Uint8Array ? buf : new Uint8Array(buf))
    } catch (e) { setErr(String(e)) }
    finally { setBusy(false) }
  }, [path])

  return (
    <ToolBox title="Hex viewer (premiers 4 KiB)">
      <RunButton busy={busy} onClick={load} icon={<FileSearch size={13} />} label="charger" />
      {err && <ErrorBox message={err} />}
      {bytes && <HexDump bytes={bytes.slice(0, 4096)} />}
    </ToolBox>
  )
}

function HexDump({ bytes }: { bytes: Uint8Array }) {
  const rows: React.ReactNode[] = []
  for (let i = 0; i < bytes.length; i += 16) {
    const slice = bytes.slice(i, i + 16)
    const hex = Array.from(slice).map((b) => b.toString(16).padStart(2, '0')).join(' ')
    const ascii = Array.from(slice).map((b) => (b >= 32 && b < 127 ? String.fromCharCode(b) : '.')).join('')
    rows.push(
      <div key={i} className="flex gap-4 font-mono text-[10px]">
        <span className="text-white/40 w-20 shrink-0">{i.toString(16).padStart(8, '0')}</span>
        <span className="text-white/85 w-[30ch]">{hex}</span>
        <span className="text-violet-200 break-all">{ascii}</span>
      </div>
    )
  }
  return (
    <div className="rounded-lg bg-black/60 border border-white/5 p-3 max-h-[60vh] overflow-auto">
      {rows}
    </div>
  )
}

function JsonBox({ value }: { value: Record<string, unknown> }) {
  return (
    <pre className="rounded-lg bg-black/50 border border-white/5 p-3 text-[10px] text-white/80 font-mono overflow-auto max-h-96 whitespace-pre-wrap">
      {JSON.stringify(value, null, 2)}
    </pre>
  )
}

function ErrorBox({ message }: { message: string }) {
  return <div className="rounded-lg bg-rose-500/10 border border-rose-500/30 p-2 text-[11px] text-rose-200 font-mono mb-2">{message}</div>
}

// v84o — Browser-side analyzer : drag-drop d'un fichier, tout est analysé
// en local sans backend (magic / strings / EXIF / hexdump).
function BrowserAnalyzer() {
  const [file, setFile] = useState<File | null>(null)
  const [bytes, setBytes] = useState<Uint8Array | null>(null)
  const [activeView, setActiveView] = useState<'magic' | 'strings' | 'exif' | 'hex'>('magic')

  const onDrop = useCallback(async (f: File) => {
    setFile(f)
    const buf = await f.arrayBuffer()
    setBytes(new Uint8Array(buf))
  }, [])

  const magicHits = bytes ? detectMagic(bytes) : []
  const exifTags = bytes ? parseExif(bytes) : []
  const strings = bytes ? extractStrings(bytes, 5).slice(0, 200) : []
  const hex = bytes ? hexDump(bytes, 32) : ''

  return (
    <div className="space-y-3">
      <label
        className="block rounded-xl border-2 border-dashed border-white/15 bg-white/[0.02] p-6 text-center cursor-pointer hover:border-white/30 transition-colors"
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => { e.preventDefault(); const f = e.dataTransfer.files?.[0]; if (f) void onDrop(f) }}
      >
        <input
          id="forensics-file" name="forensicsFile"
          type="file"
          onChange={(e) => { const f = e.target.files?.[0]; if (f) void onDrop(f) }}
          className="hidden"
        />
        <div className="text-[12px] text-white/70">
          {file
            ? <>📄 <strong>{file.name}</strong> · {file.size.toLocaleString()} bytes — Aurora analyse localement.</>
            : <>Glisse un fichier ici · ou clique pour choisir. Tout est analysé OFFLINE dans ton browser.</>}
        </div>
      </label>
      {bytes && (
        <>
          <div className="flex gap-1">
            {[
              { id: 'magic' as const, label: 'Magic bytes' },
              { id: 'strings' as const, label: `Strings (${strings.length})` },
              { id: 'exif' as const, label: `EXIF (${exifTags.length})` },
              { id: 'hex' as const, label: 'Hexdump' },
            ].map((t) => (
              <button key={t.id} onClick={() => setActiveView(t.id)}
                className={`rounded-md px-3 py-1 text-[11px] border ${activeView === t.id ? 'bg-amber-500/20 border-amber-500/40 text-amber-200' : 'bg-white/5 border-white/10 text-white/60'}`}>
                {t.label}
              </button>
            ))}
          </div>
          {activeView === 'magic' && (
            <div className="rounded-lg bg-black/40 border border-white/10 p-3 text-[12px] font-mono">
              {magicHits.length === 0 ? (
                <span className="text-white/55">Aucune signature reconnue (fichier exotique ou texte pur).</span>
              ) : magicHits.map((m, i) => (
                <div key={i} className="text-emerald-200">
                  ✓ <strong>{m.type}</strong> — {m.description}
                </div>
              ))}
            </div>
          )}
          {activeView === 'strings' && (
            <div className="rounded-lg bg-black/40 border border-white/10 p-3 max-h-80 overflow-auto font-mono text-[10px]">
              {strings.map((s, i) => (
                <div key={i}>
                  <span className="text-white/40">[0x{s.offset.toString(16).padStart(6, '0')}]</span>{' '}
                  <span className="text-amber-200">{s.text}</span>
                </div>
              ))}
              {strings.length === 0 && <span className="text-white/55">Aucune chaîne printable ≥5 chars.</span>}
            </div>
          )}
          {activeView === 'exif' && (
            <div className="rounded-lg bg-black/40 border border-white/10 p-3 font-mono text-[11px]">
              {exifTags.length === 0 ? (
                <span className="text-white/55">Pas d'EXIF (fichier non-JPEG ou EXIF strippé).</span>
              ) : (
                <table className="w-full">
                  <tbody>
                    {exifTags.map((t, i) => (
                      <tr key={i} className="border-b border-white/5">
                        <td className="text-white/55 py-1 pr-3">{t.tag}</td>
                        <td className="text-emerald-200 py-1 break-all">{t.value}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}
          {activeView === 'hex' && (
            <pre className="rounded-lg bg-black/60 border border-white/10 p-3 max-h-96 overflow-auto font-mono text-[10px] text-emerald-200 whitespace-pre">
              {hex}
            </pre>
          )}
        </>
      )}
    </div>
  )
}
