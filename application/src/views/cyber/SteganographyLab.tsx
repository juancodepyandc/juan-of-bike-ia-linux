import { useCallback, useEffect, useRef, useState } from 'react'
import { Binary, FileDown, Loader2, Scan } from 'lucide-react'
import {
  cyberAudDecode,
  cyberAudEncode,
  cyberImgDecode,
  cyberImgDiff,
  cyberImgEncode,
  cyberLsbStats,
} from '../../services/cyber/pythonClient.ts'

export default function SteganographyLab() {
  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4">
        <h2 className="text-white text-[15px] font-semibold mb-1">Stéganographie — cacher dans les bits faibles</h2>
        <p className="text-[12px] text-white/60">
          LSB (Least Significant Bit) : on remplace le bit de poids faible de chaque pixel par un bit du message.
          Invisible à l'œil mais détectable par analyse statistique.
        </p>
      </div>
      <BrowserLsbVisualizer />
      <ImageLSB />
      <AudioLSB />
      <LSBStats />
      <ImageDiff />
      <WhitespaceStego />
    </div>
  )
}

// v84p — Browser-side LSB visualizer : drag-drop image, montre les plans de
// bits individuels (bit 0, 1, 2, 3) pour révéler ce qui est caché en LSB.
function BrowserLsbVisualizer() {
  const [bit, setBit] = useState(0)
  const [channel, setChannel] = useState<'r' | 'g' | 'b' | 'all'>('all')
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const previewRef = useRef<HTMLCanvasElement | null>(null)
  const [info, setInfo] = useState<string>('')

  const onFile = async (f: File) => {
    const url = URL.createObjectURL(f)
    const img = new Image()
    img.onload = () => {
      const c = canvasRef.current
      const p = previewRef.current
      if (!c || !p) return
      const w = Math.min(640, img.width)
      const h = Math.round((w / img.width) * img.height)
      c.width = w; c.height = h
      p.width = w; p.height = h
      const ctx = c.getContext('2d')!
      const pctx = p.getContext('2d')!
      ctx.drawImage(img, 0, 0, w, h)
      pctx.drawImage(img, 0, 0, w, h)
      URL.revokeObjectURL(url)
      setInfo(`${f.name} · ${w}×${h}px`)
      render()
    }
    img.src = url
  }

  const render = useCallback(() => {
    const c = canvasRef.current
    const p = previewRef.current
    if (!c || !p) return
    const ctx = c.getContext('2d')!
    const pctx = p.getContext('2d')!
    // Re-draw from preview (original).
    const orig = pctx.getImageData(0, 0, p.width, p.height)
    const out = ctx.createImageData(c.width, c.height)
    for (let i = 0; i < orig.data.length; i += 4) {
      const r = orig.data[i]
      const g = orig.data[i + 1]
      const b = orig.data[i + 2]
      const mask = 1 << bit
      let outR = 0, outG = 0, outB = 0
      if (channel === 'all') {
        outR = (r & mask) ? 255 : 0
        outG = (g & mask) ? 255 : 0
        outB = (b & mask) ? 255 : 0
      } else {
        const v = channel === 'r' ? r : channel === 'g' ? g : b
        const on = (v & mask) ? 255 : 0
        outR = outG = outB = on
      }
      out.data[i] = outR
      out.data[i + 1] = outG
      out.data[i + 2] = outB
      out.data[i + 3] = 255
    }
    ctx.putImageData(out, 0, 0)
  }, [bit, channel])

  useEffect(() => { render() }, [render])

  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4">
      <h3 className="text-[12px] font-semibold text-white/80 uppercase tracking-wider mb-3 flex items-center gap-2">
        <Binary size={13} /> Browser LSB visualizer · drag-drop image
      </h3>
      <p className="text-[11px] text-white/55 mb-3">
        Affiche un plan de bits spécifique (0 = LSB, 7 = MSB). Si quelque chose est caché en LSB,
        tu le verras dans le plan bit 0 (motifs réguliers, texte visible). L'image elle reste inchangée.
      </p>
      <label className="block rounded-lg border border-dashed border-white/15 bg-white/[0.02] p-4 cursor-pointer hover:border-white/30 mb-3">
        <input
          id="stego-file" name="stegoFile" type="file" accept="image/*"
          onChange={(e) => { const f = e.target.files?.[0]; if (f) void onFile(f) }}
          className="hidden"
        />
        <div className="text-center text-[12px] text-white/70">
          {info || 'Glisse ou clique pour charger une image PNG/JPG…'}
        </div>
      </label>
      <div className="flex items-center gap-3 mb-3 text-[11px]">
        <label className="flex items-center gap-2 text-white/70">
          Bit
          <input type="range" min={0} max={7} value={bit} onChange={(e) => setBit(Number(e.target.value))} className="w-32" />
          <span className="font-mono text-white/85 w-6">{bit}</span>
        </label>
        <div className="flex gap-1">
          {(['all', 'r', 'g', 'b'] as const).map((c) => (
            <button key={c} onClick={() => setChannel(c)}
              className={`rounded-md px-2 py-0.5 text-[10px] font-mono border ${channel === c ? 'bg-amber-500/25 border-amber-500/45 text-amber-100' : 'bg-white/5 border-white/10 text-white/55'}`}>
              {c.toUpperCase()}
            </button>
          ))}
        </div>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <div>
          <div className="text-[10px] uppercase tracking-wider text-white/50 mb-1">Originale</div>
          <canvas ref={previewRef} className="w-full rounded border border-white/10 bg-black" />
        </div>
        <div>
          <div className="text-[10px] uppercase tracking-wider text-white/50 mb-1">Plan de bit {bit} · canal {channel.toUpperCase()}</div>
          <canvas ref={canvasRef} className="w-full rounded border border-white/10 bg-black" />
        </div>
      </div>
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

function ImageLSB() {
  const [cover, setCover] = useState('')
  const [secret, setSecret] = useState('Aurora cache un message ici.')
  const [out, setOut] = useState('stego_out.png')
  const { busy, err, data, run } = useRun<{ out?: string; capacity?: number; error?: string }>()
  const dec = useRun<{ secret?: string; bytes?: number; error?: string }>()

  return (
    <ToolBox title="Image LSB — encoder / décoder">
      <Row label="Cover (PNG)" value={cover} onChange={setCover} placeholder="C:\...\cover.png" />
      <textarea value={secret} onChange={(e) => setSecret(e.target.value)} rows={2}
        className="w-full rounded-lg bg-black/40 border border-white/10 px-3 py-2 text-[12px] text-white/90 mb-2" />
      <Row label="Sortie" value={out} onChange={setOut} placeholder="stego_out.png" />
      <div className="flex gap-2 mt-2">
        <button disabled={busy || !cover} onClick={() => run(() => cyberImgEncode(cover, secret, out))}
          className="inline-flex items-center gap-2 rounded-lg bg-cyan-500/20 border border-cyan-500/40 text-cyan-200 px-3 py-1.5 text-[12px] hover:bg-cyan-500/30 disabled:opacity-50">
          {busy ? <Loader2 size={13} className="animate-spin" /> : <FileDown size={13} />} encoder
        </button>
        <button disabled={dec.busy || !out} onClick={() => dec.run(() => cyberImgDecode(out))}
          className="inline-flex items-center gap-2 rounded-lg bg-emerald-500/20 border border-emerald-500/40 text-emerald-200 px-3 py-1.5 text-[12px] hover:bg-emerald-500/30 disabled:opacity-50">
          {dec.busy ? <Loader2 size={13} className="animate-spin" /> : <Binary size={13} />} décoder stego
        </button>
      </div>
      {err && <ErrorBox message={err} />}
      {data && <JsonBox value={data as unknown as Record<string, unknown>} />}
      {dec.err && <ErrorBox message={dec.err} />}
      {dec.data && <JsonBox value={dec.data as unknown as Record<string, unknown>} />}
    </ToolBox>
  )
}

function AudioLSB() {
  const [cover, setCover] = useState('')
  const [secret, setSecret] = useState('audio secret')
  const [out, setOut] = useState('stego_out.wav')
  const { busy, err, data, run } = useRun<{ out?: string; capacity?: number; error?: string }>()
  const dec = useRun<{ secret?: string; error?: string }>()

  return (
    <ToolBox title="Audio LSB (WAV 16-bit)">
      <Row label="Cover (WAV)" value={cover} onChange={setCover} placeholder="C:\...\cover.wav" />
      <textarea value={secret} onChange={(e) => setSecret(e.target.value)} rows={2}
        className="w-full rounded-lg bg-black/40 border border-white/10 px-3 py-2 text-[12px] text-white/90 mb-2" />
      <Row label="Sortie" value={out} onChange={setOut} />
      <div className="flex gap-2 mt-2">
        <button disabled={busy || !cover} onClick={() => run(() => cyberAudEncode(cover, secret, out))}
          className="inline-flex items-center gap-2 rounded-lg bg-cyan-500/20 border border-cyan-500/40 text-cyan-200 px-3 py-1.5 text-[12px] hover:bg-cyan-500/30 disabled:opacity-50">
          {busy ? <Loader2 size={13} className="animate-spin" /> : <FileDown size={13} />} encoder
        </button>
        <button disabled={dec.busy || !out} onClick={() => dec.run(() => cyberAudDecode(out))}
          className="inline-flex items-center gap-2 rounded-lg bg-emerald-500/20 border border-emerald-500/40 text-emerald-200 px-3 py-1.5 text-[12px] hover:bg-emerald-500/30 disabled:opacity-50">
          {dec.busy ? <Loader2 size={13} className="animate-spin" /> : <Binary size={13} />} décoder
        </button>
      </div>
      {err && <ErrorBox message={err} />}
      {data && <JsonBox value={data as unknown as Record<string, unknown>} />}
      {dec.data && <JsonBox value={dec.data as unknown as Record<string, unknown>} />}
    </ToolBox>
  )
}

function LSBStats() {
  const [path, setPath] = useState('')
  const { busy, err, data, run } = useRun<{ lsbHistogram?: Record<string, number>; chiSquare?: number; suspicionScore?: number }>()
  return (
    <ToolBox title="Détecter stego — statistiques LSB">
      <Row label="Fichier suspect" value={path} onChange={setPath} />
      <button disabled={busy || !path} onClick={() => run(() => cyberLsbStats(path))}
        className="inline-flex items-center gap-2 rounded-lg bg-violet-500/20 border border-violet-500/40 text-violet-200 px-3 py-1.5 text-[12px] hover:bg-violet-500/30 disabled:opacity-50 mt-2">
        {busy ? <Loader2 size={13} className="animate-spin" /> : <Scan size={13} />} analyser
      </button>
      {err && <ErrorBox message={err} />}
      {data?.suspicionScore !== undefined && (
        <div className={`mt-3 rounded-lg p-3 ${data.suspicionScore > 0.5 ? 'bg-rose-500/10 border border-rose-500/30' : 'bg-emerald-500/10 border border-emerald-500/30'}`}>
          <p className="text-[11px] font-semibold mb-1">
            Score de suspicion : <span className="font-mono">{data.suspicionScore.toFixed(3)}</span>
          </p>
          <p className="text-[10px] text-white/60">
            {data.suspicionScore > 0.5 ? 'Distribution LSB anormale — stéganographie probable.' : 'Distribution LSB proche du bruit naturel.'}
          </p>
          {data.chiSquare !== undefined && <p className="text-[10px] text-white/50 mt-1">χ² = {data.chiSquare.toFixed(3)}</p>}
        </div>
      )}
    </ToolBox>
  )
}

function ImageDiff() {
  const [cover, setCover] = useState('')
  const [stego, setStego] = useState('')
  const [out, setOut] = useState('diff.png')
  const { busy, err, data, run } = useRun<{ out?: string; changedPixels?: number }>()
  return (
    <ToolBox title="Comparer cover vs stego (heatmap)">
      <Row label="Cover" value={cover} onChange={setCover} />
      <Row label="Stego" value={stego} onChange={setStego} />
      <Row label="Sortie diff" value={out} onChange={setOut} />
      <button disabled={busy || !cover || !stego} onClick={() => run(() => cyberImgDiff(cover, stego, out))}
        className="inline-flex items-center gap-2 rounded-lg bg-violet-500/20 border border-violet-500/40 text-violet-200 px-3 py-1.5 text-[12px] hover:bg-violet-500/30 disabled:opacity-50 mt-2">
        {busy ? <Loader2 size={13} className="animate-spin" /> : <Scan size={13} />} générer heatmap
      </button>
      {err && <ErrorBox message={err} />}
      {data && <JsonBox value={data as unknown as Record<string, unknown>} />}
    </ToolBox>
  )
}

function WhitespaceStego() {
  const [text, setText] = useState('Voici un texte apparemment anodin.')
  const [secret, setSecret] = useState('TOP')
  const enc = encodeWhitespace(text, secret)
  const dec = decodeWhitespace(enc)
  return (
    <ToolBox title="Whitespace / zero-width — cacher dans l'invisible">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-2">
        <div>
          <label className="text-[10px] uppercase text-white/45">Texte porteur</label>
          <textarea value={text} onChange={(e) => setText(e.target.value)} rows={4}
            className="w-full rounded-lg bg-black/40 border border-white/10 px-3 py-2 text-[12px] text-white/90 resize-none mt-1" />
          <label className="text-[10px] uppercase text-white/45 mt-2 block">Secret</label>
          <input value={secret} onChange={(e) => setSecret(e.target.value)}
            className="w-full rounded-lg bg-black/40 border border-white/10 px-3 py-2 text-[12px] text-white/90 mt-1" />
        </div>
        <div>
          <label className="text-[10px] uppercase text-white/45">Texte stego (copier/coller ailleurs)</label>
          <textarea readOnly value={enc} rows={4}
            className="w-full rounded-lg bg-black/40 border border-white/10 px-3 py-2 text-[12px] text-white/90 resize-none mt-1" />
          <label className="text-[10px] uppercase text-white/45 mt-2 block">Décodé depuis stego</label>
          <input readOnly value={dec}
            className="w-full rounded-lg bg-black/40 border border-white/10 px-3 py-2 text-[12px] text-white/90 mt-1 font-mono" />
        </div>
      </div>
    </ToolBox>
  )
}

function encodeWhitespace(text: string, secret: string) {
  const bits = Array.from(secret).flatMap((ch) => {
    const b = ch.charCodeAt(0).toString(2).padStart(8, '0')
    return b.split('').map(Number)
  })
  // Encoder chaque bit via zero-width-space (0) / zero-width-joiner (1) inséré après le texte
  const suffix = bits.map((b) => b ? '\u200D' : '\u200B').join('')
  return text + suffix
}

function decodeWhitespace(stego: string) {
  const bits: number[] = []
  for (const ch of stego) {
    if (ch === '\u200B') bits.push(0)
    else if (ch === '\u200D') bits.push(1)
  }
  const bytes: number[] = []
  for (let i = 0; i + 8 <= bits.length; i += 8) {
    let b = 0
    for (let j = 0; j < 8; j++) b = (b << 1) | bits[i + j]
    bytes.push(b)
  }
  return String.fromCharCode(...bytes)
}

function Row({ label, value, onChange, placeholder }: { label: string; value: string; onChange: (v: string) => void; placeholder?: string }) {
  return (
    <div className="mb-2">
      <label className="text-[10px] uppercase text-white/45 tracking-wider">{label}</label>
      <input value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder}
        className="w-full mt-1 rounded-lg bg-black/40 border border-white/10 px-3 py-1.5 text-[12px] text-white/90 font-mono" />
    </div>
  )
}

function ToolBox({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4">
      <h3 className="text-[12px] font-semibold text-white/80 uppercase tracking-wider mb-3">{title}</h3>
      {children}
    </div>
  )
}

function JsonBox({ value }: { value: Record<string, unknown> }) {
  return (
    <pre className="mt-2 rounded-lg bg-black/50 border border-white/5 p-3 text-[10px] text-white/80 font-mono overflow-auto max-h-60 whitespace-pre-wrap">
      {JSON.stringify(value, null, 2)}
    </pre>
  )
}

function ErrorBox({ message }: { message: string }) {
  return <div className="mt-2 rounded-lg bg-rose-500/10 border border-rose-500/30 p-2 text-[11px] text-rose-200 font-mono">{message}</div>
}
