import { useEffect, useRef, useState } from 'react'
import { getBridgeUrl, isCloudRuntime } from '../utils/runtime'

type Profile = {
  name: string; process: 'FDM' | 'resin'; bed_mm: [number, number, number]
  clearance_mm: number; wall_mm: number; pin_diameter_mm: number; pin_depth_mm: number; margin_mm: number
  keyed_pins?: boolean; lead_in_mm?: number; color_capability?: 'single' | 'multi'
}
type Report = {
  dimensions_mm: number[]; source_watertight: boolean; size_applied: boolean
  piece_count?: number; pin_count?: number; cuts_mm?: number[]; cut_axis?: string
  textured_assembly_available?: boolean; fabrication?: { instructions: string; filament_plan: { part: string; name: string; color: string }[] }
}
type ExportResult = { ok: boolean; state: string; error?: string; report?: Report; download_url?: string }
const STORAGE = 'aurora.printProfiles.v1'
const initial: Profile = { name: '', process: 'FDM', bed_mm: [220, 220, 250], clearance_mm: 0.2,
  wall_mm: 2, pin_diameter_mm: 5, pin_depth_mm: 8, margin_mm: 5, keyed_pins: true, lead_in_mm: 0.2, color_capability: 'single' }

function profilesOnDevice(): Profile[] {
  try {
    const list: unknown = JSON.parse(localStorage.getItem(STORAGE) || '[]')
    return Array.isArray(list) ? list.filter((p): p is Profile => typeof p?.name === 'string'
      && ['FDM', 'resin'].includes(p.process) && Array.isArray(p.bed_mm) && p.bed_mm.length === 3
      && [...p.bed_mm, p.clearance_mm, p.wall_mm, p.pin_diameter_mm, p.pin_depth_mm, p.margin_mm]
        .every((v) => typeof v === 'number' && Number.isFinite(v))).slice(0, 30) : []
  } catch { return [] }
}

function selectedOnDevice(): Profile {
  const profiles = profilesOnDevice()
  try { return profiles.find((p) => p.name === localStorage.getItem(STORAGE + '.selected')) || profiles[0] || initial }
  catch { return profiles[0] || initial }
}

export default function EngineeringExportPanel({ modelUrl, assemblyOnly = false, active = true, onAssemblyRequested }: { modelUrl: string | null; assemblyOnly?: boolean; active?: boolean; onAssemblyRequested?: () => void }) {
  const [mode, setMode] = useState<'geometry' | 'textured' | 'assembly'>(assemblyOnly ? 'assembly' : 'geometry')
  const [profiles, setProfiles] = useState<Profile[]>(profilesOnDevice)
  const [profile, setProfile] = useState<Profile>(selectedOnDevice)
  const [size, setSize] = useState(200)
  const [axis, setAxis] = useState('auto')
  const [upAxis, setUpAxis] = useState('z')
  const [cuts, setCuts] = useState('')
  const [filaments, setFilaments] = useState('')
  const [previewExploded, setPreviewExploded] = useState(false)
  const filamentRows: { name: string; color: string }[] = (() => { try { const plan = JSON.parse(filaments || '[]'); return Array.isArray(plan) && plan.every((f) => typeof f?.name === 'string' && typeof f?.color === 'string') ? plan : [] } catch { return [] } })()
  const [constraints, setConstraints] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [result, setResult] = useState<ExportResult | null>(null)
  const [jobId, setJobId] = useState('')
  const [accessKey, setAccessKey] = useState('')
  const authHeaders = accessKey ? { Authorization: `Bearer ${accessKey}` } : undefined
  const requestRef = useRef<AbortController | null>(null)
  const mounted = useRef(true)
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; requestRef.current?.abort() } }, [])
  useEffect(() => {
    if (profiles.some((p) => p.name === profile.name)) {
      try { localStorage.setItem(STORAGE + '.selected', profile.name) } catch { /* profile remains usable in memory */ }
    }
  }, [profile.name, profiles])
  // A finished package keeps its own profile/variant even when the form changes.
  const [exportedMode, setExportedMode] = useState(mode)
  const inputClass = 'mt-1 w-full rounded-lg border border-aurora-border/50 bg-aurora-surface-2 px-2 py-1.5 text-xs text-aurora-text'

  function saveProfile() {
    const ranges = [[profile.clearance_mm, 0.01, 2], [profile.wall_mm, 0.5, 20],
      [profile.pin_diameter_mm, 1, 30], [profile.pin_depth_mm, 2, 60], [profile.margin_mm, 0, 30]]
    if ((profile.color_capability !== undefined && !['single','multi'].includes(profile.color_capability)) || (profile.keyed_pins !== undefined && typeof profile.keyed_pins !== 'boolean') || !profile.name.trim() || profile.bed_mm.some((v) => !Number.isFinite(v) || v < 10 || v > 2000)
      || ranges.some(([v, low, high]) => !Number.isFinite(v) || v < low || v > high)
      || Math.min(...profile.bed_mm) <= 2 * profile.margin_mm
      || !Number.isFinite(profile.lead_in_mm ?? 0.2) || (profile.lead_in_mm ?? 0.2) < 0 || (profile.lead_in_mm ?? 0.2) > 2
      || (profile.lead_in_mm ?? 0.2) >= Math.min(profile.pin_diameter_mm * ((profile.keyed_pins ?? true) ? 0.4 : 0.5), profile.pin_depth_mm / 2)
      || ((profile.keyed_pins ?? true) && profile.clearance_mm >= profile.pin_diameter_mm * 0.1)) {
      setError('Vérifier le nom, le volume, le jeu et le chanfrein du profil. Avec détrompage, le jeu radial doit rester inférieur à 10 % du diamètre du pion.'); return
    }
    const saved = { ...profile, name: profile.name.trim(), keyed_pins: profile.keyed_pins ?? true, lead_in_mm: profile.lead_in_mm ?? 0.2, color_capability: profile.color_capability ?? 'single' }
    const next = [...profiles.filter((p) => p.name !== saved.name), saved].slice(-30)
    try {
      localStorage.setItem(STORAGE, JSON.stringify(next)); setProfiles(next); setProfile(saved)
      setError(''); setMessage(`Profil « ${saved.name} » enregistré sur cet appareil.`)
    } catch { setError('Enregistrement du profil indisponible sur cet appareil.') }
  }

  async function prepare() {
    setError(''); setMessage(''); setResult(null); setJobId(''); setBusy(true); setPreviewExploded(false)
    const controller = new AbortController(); requestRef.current = controller
    const timer = setTimeout(() => controller.abort(), 210_000)
    try {
      const parsedCuts = cuts.trim() ? cuts.split(';').map((v) => Number(v.trim().replace(',', '.'))) : []
      if (!Number.isFinite(size) || size < 1 || size > 2000 || parsedCuts.some((v) => !Number.isFinite(v) || v <= 0))
        throw new Error('Taille et positions de coupe valides requises (séparer les coupes par « ; »).')
      let source: Blob | File
      let filename = file?.name || (modelUrl?.toLowerCase().includes('.stl') ? 'model.stl' : 'model.glb')
      if (file) source = file
      else {
        if (!modelUrl) throw new Error('Charger un maillage existant ou générer un modèle avant export.')
        const fetched = await fetch(modelUrl, { signal: controller.signal })
        if (!fetched.ok) throw new Error('Le maillage affiché ne peut pas être lu.')
        source = await fetched.blob()
        if (modelUrl.toLowerCase().includes('.obj')) filename = 'model.obj'
      }
      const body = new FormData(); body.append('mesh', source, filename)
      const rules = mode === 'assembly' && constraints.trim() ? JSON.parse(constraints) : {}
      if (!rules || typeof rules !== 'object' || Array.isArray(rules)
        || Object.keys(rules).some((k) => !['protected_zones_mm', 'connector_centers_mm'].includes(k)))
        throw new Error('Contraintes JSON : protected_zones_mm et connector_centers_mm uniquement.')
      const pieceFilaments = mode === 'assembly' && filaments.trim() ? JSON.parse(filaments) : []
      body.append('settings', JSON.stringify({ mode, size_mm: size, profile, axis, view_up_axis: upAxis, cuts_mm: parsedCuts, piece_filaments: pieceFilaments, ...rules }))
      const response = await fetch(`${getBridgeUrl()}/api/3d/engineering`, { method: 'POST', body, headers: authHeaders, signal: controller.signal })
      const accepted = await response.json()
      if (!response.ok || !accepted.ok) throw new Error(accepted.error || 'Export refusé.')
      setJobId(accepted.job_id); setExportedMode(mode)
      while (!controller.signal.aborted) {
        const poll = await fetch(`${getBridgeUrl()}/api/3d/engineering/${accepted.job_id}`, { headers: authHeaders, signal: controller.signal })
        const status: ExportResult = await poll.json()
        if (!poll.ok || !status.ok || status.state === 'error') throw new Error(status.error || 'Export échoué.')
        if (status.state === 'done') { if (mounted.current) setResult(status); return }
        await new Promise<void>((resolve) => setTimeout(resolve, 800))
      }
    } catch (e) {
      if (mounted.current) setError(e instanceof Error && e.name !== 'AbortError' ? e.message
        : 'Suivi interrompu. Le serveur peut encore terminer le fichier ; aucune nouvelle découpe n’est lancée automatiquement.')
    } finally {
      clearTimeout(timer); if (mounted.current) setBusy(false)
    }
  }

  async function download() {
    if (!result?.download_url) return
    try {
      const response = await fetch(`${getBridgeUrl()}${result.download_url}`, { headers: authHeaders })
      if (!response.ok) throw new Error('Archive indisponible.')
      const url = URL.createObjectURL(await response.blob())
      const a = document.createElement('a'); a.href = url; a.download = `aurora-${exportedMode}-${jobId}.zip`; a.click()
      setTimeout(() => URL.revokeObjectURL(url), 10_000)
    } catch (e) { setError(e instanceof Error ? e.message : 'Téléchargement échoué.') }
  }

  return <section className="rounded-[1.4rem] border border-aurora-border/35 bg-aurora-surface/70 p-4" aria-label={assemblyOnly ? "Préparation d’assemblage" : "Versions 3D et assemblage"}>
    <h3 className="text-sm font-semibold text-aurora-text">{assemblyOnly ? "Assemblage — assemblé / éclaté" : "Versions 3D / Assemblage"}</h3>
    <p className="mt-2 text-xs text-aurora-text-muted">Préparer le modèle existant pour le visuel ou l’impression, sans relancer sa génération.</p>
    <details open={!result || !assemblyOnly}><summary hidden={!assemblyOnly} className="mt-3 min-h-11 cursor-pointer text-sm">Préparer les pièces et le profil imprimante</summary>
    <fieldset disabled={busy} className="mt-3 space-y-3 disabled:opacity-60">
      {isCloudRuntime() && <label className="block text-xs text-aurora-text-muted">Clé d’accès au serveur distant
        <input type="password" autoComplete="off" value={accessKey} onChange={(e) => setAccessKey(e.target.value)} className={inputClass} />
      </label>}
      {!assemblyOnly && <div className="grid grid-cols-3 gap-1">
        {([['geometry', 'Géométrie pure'], ['textured', 'Texture'], ['assembly', 'Assemblage']] as const).map(([value, label]) =>
          <button key={value} type="button" aria-pressed={mode === value} onClick={() => value === 'assembly' && onAssemblyRequested ? onAssemblyRequested() : setMode(value)}
            className={`rounded-lg border px-1 py-2 text-[11px] ${mode === value ? 'border-aurora-accent bg-aurora-accent/15 text-aurora-accent' : 'border-aurora-border text-aurora-text-muted'}`}>{label}</button>)}
      </div>}
      <label className="block text-xs text-aurora-text-muted">Maillage GLB / STL / OBJ
        <input type="file" accept=".glb,.stl,.obj" className="mt-1 w-full text-xs" onChange={(e) => setFile(e.target.files?.[0] || null)} />
      </label>
      <p className="text-[11px] text-aurora-text-dim">{file ? `Source : ${file.name}` : modelUrl ? 'Source : modèle affiché.' : 'Importer un maillage pour commencer.'}</p>
      {file && modelUrl && <button className="text-xs text-aurora-accent" onClick={() => setFile(null)}>Utiliser le modèle affiché</button>}
      {mode === 'textured' ? <p className="text-xs text-aurora-text-muted">GLB original : matériaux, textures, animations et unités conservés. Les textures absentes ne sont pas inventées.</p>
        : <label className="block text-xs text-aurora-text-muted">Plus grande dimension finale (mm)
          <input aria-label="Dimension finale mm" type="number" min={1} max={2000} value={size} onChange={(e) => setSize(e.target.valueAsNumber)} className={inputClass} />
        </label>}
      {mode === 'assembly' && <>
        <label className="block text-xs text-aurora-text-muted">Profil imprimante enregistré
          <select aria-label="Profil imprimante enregistré" className={inputClass} value={profiles.some((p) => p.name === profile.name) ? profile.name : ''}
            onChange={(e) => setProfile(profiles.find((p) => p.name === e.target.value) || { ...initial })}>
            <option value="">Nouveau profil</option>{profiles.map((p) => <option key={p.name} value={p.name}>{p.name}</option>)}
          </select>
        </label>
        <button type="button" className="min-h-11 rounded-lg border border-aurora-border px-3 text-xs" onClick={() => { setProfile({ ...initial, name: 'Ender-3 V3 SE — PLA 0,4' }); setMessage('Volume constructeur 220 × 220 × 250 mm ; marge de 5 mm. Calibrer le jeu sur une éprouvette.'); }}>Préréglage Ender-3 V3 SE</button>
        <a href="https://www.creality.com/fr/support/creality-ender-3-v3-se" target="_blank" rel="noreferrer" className="block text-xs text-aurora-accent">Volume constructeur Ender-3 V3 SE</a>
        <label className="block text-xs text-aurora-text-muted">Couleurs de l’imprimante
          <select className={inputClass} value={profile.color_capability ?? 'single'} onChange={(e) => setProfile({ ...profile, color_capability: e.target.value as 'single' | 'multi' })}><option value="single">Un filament à la fois</option><option value="multi">Plusieurs couleurs prises en charge</option></select>
        </label>
        {(profile.color_capability ?? 'single') === 'single' && <details className="text-xs text-aurora-text-muted"><summary className="min-h-11">Pièces imprimées séparément par couleur</summary>
          <p className="mt-2">Prévoir les coupes aux limites des éléments colorés, puis affecter un filament à chaque pièce. Les pions et logements sont contrôlés comme pour toute découpe. Une texture ne peut pas définir automatiquement des volumes séparables.</p>
          <p className="mt-2">Une ligne par pièce, dans l’ordre du manifeste.</p>
          {filamentRows.map((f, index) => <div key={index} className="mt-3 rounded-lg border border-aurora-border p-2">
            <label className="block">Filament de la pièce {index + 1}<input aria-label={`Filament de la pièce ${index + 1}`} className={inputClass} value={f.name} maxLength={100} onChange={(e) => setFilaments(JSON.stringify(filamentRows.map((row, i) => i === index ? { ...row, name: e.target.value } : row)))} /></label>
            <label className="mt-2 flex items-center gap-2">Couleur de la pièce {index + 1}<input aria-label={`Couleur de la pièce ${index + 1}`} type="color" className="h-11 w-16" value={f.color} onChange={(e) => setFilaments(JSON.stringify(filamentRows.map((row, i) => i === index ? { ...row, color: e.target.value } : row)))} /></label>
            <button type="button" className="min-h-11 text-aurora-text-muted" onClick={() => setFilaments(JSON.stringify(filamentRows.filter((_, i) => i !== index)))}>Retirer la pièce {index + 1}</button>
          </div>)}
          <button type="button" className="my-2 min-h-11 rounded-lg border border-aurora-border px-3 text-aurora-accent" onClick={() => setFilaments(JSON.stringify([...filamentRows, { name: `PLA — pièce ${filamentRows.length + 1}`, color: '#eeeeee' }]))}>Ajouter un filament / une pièce</button>
          <details><summary className="min-h-11">Importer / éditer le plan en JSON</summary>
          <label className="block mt-2">Filaments par pièce, dans l’ordre du manifeste
            <textarea aria-label="Filaments par pièce JSON" rows={4} className={inputClass} value={filaments} onChange={(e) => setFilaments(e.target.value)} placeholder={'[{"name":"PLA ivoire","color":"#eee5d3"},{"name":"PLA bleu","color":"#245caa"}]'} />
          </label></details><p>Sans affectation : les couleurs servent uniquement à distinguer les pièces. Les pions sont imprimés séparément.</p>
        </details>}
        <label className="block text-xs text-aurora-text-muted">Nom / modèle d’imprimante
          <input aria-label="Nom du profil imprimante" value={profile.name} placeholder="Mon imprimante — PLA 0,4" maxLength={100} className={inputClass}
            onChange={(e) => setProfile({ ...profile, name: e.target.value })} />
        </label>
        <label className="block text-xs text-aurora-text-muted">Importer un profil JSON prédéfini
          <input type="file" accept=".json,application/json" className="mt-1 w-full text-xs" onChange={async (e) => {
            const selected = e.target.files?.[0]
            if (!selected) return
            try {
              if (selected.size > 100_000) throw new Error('Profil JSON trop volumineux.')
              const candidate: Profile = JSON.parse(await selected.text())
              if ((candidate?.color_capability !== undefined && !['single','multi'].includes(candidate.color_capability)) || (candidate?.keyed_pins !== undefined && typeof candidate.keyed_pins !== 'boolean')
                || (candidate?.lead_in_mm !== undefined && (typeof candidate.lead_in_mm !== 'number' || !Number.isFinite(candidate.lead_in_mm)))
                || typeof candidate?.name !== 'string' || !['FDM', 'resin'].includes(candidate.process)
                || !Array.isArray(candidate.bed_mm) || candidate.bed_mm.length !== 3
                || [...candidate.bed_mm, candidate.clearance_mm, candidate.wall_mm, candidate.pin_diameter_mm,
                    candidate.pin_depth_mm, candidate.margin_mm].some((v) => typeof v !== 'number' || !Number.isFinite(v)))
                throw new Error('Profil incompatible : nom, procédé, volume et paramètres de raccord requis.')
              setProfile(candidate); setError(''); setMessage('Profil importé. Vérifier ses paramètres puis l’enregistrer.')
            } catch (e) { setError(e instanceof Error ? e.message : 'Profil JSON invalide.') }
          }} />
        </label>
        <a className="block text-xs text-aurora-accent" target="_blank" rel="noreferrer"
          href={`https://www.google.com/search?q=${encodeURIComponent(`${profile.name || 'imprimante 3D'} fiche constructeur volume impression dimensions`)}`}>Trouver la fiche constructeur</a>
        <label className="block text-xs text-aurora-text-muted">Procédé
          <select className={inputClass} value={profile.process} onChange={(e) => setProfile({ ...profile, process: e.target.value as Profile['process'] })}>
            <option value="FDM">Filament FDM</option><option value="resin">Résine</option>
          </select>
        </label>
        <div className="grid grid-cols-3 gap-2">{(['X', 'Y', 'Z'] as const).map((label, i) => <label key={label} className="text-[11px] text-aurora-text-muted">Volume {label} (mm)
          <input type="number" min={10} max={2000} aria-label={`Volume ${label} mm`} className={inputClass} value={profile.bed_mm[i]}
            onChange={(e) => { const bed: Profile['bed_mm'] = [...profile.bed_mm]; bed[i] = e.target.valueAsNumber; setProfile({ ...profile, bed_mm: bed }) }} />
        </label>)}</div>
        <div className="grid grid-cols-2 gap-2">{([
          ['pin_diameter_mm', 'Diamètre pion (mm)'], ['pin_depth_mm', 'Profondeur par côté (mm)'],
          ['clearance_mm', 'Jeu radial (mm)'], ['wall_mm', 'Paroi autour du raccord (mm)'], ['margin_mm', 'Marge volume (mm)'],
        ] as const).map(([key, label]) => <label key={key} className="text-[11px] text-aurora-text-muted">{label}
          <input type="number" step="0.05" min={0} value={profile[key]} aria-label={label} className={inputClass}
            onChange={(e) => setProfile({ ...profile, [key]: e.target.valueAsNumber })} />
        </label>)}</div>
        <label className="block text-xs text-aurora-text-muted">Chanfrein d’entrée et des pions (mm)
          <input type="number" min={0} max={2} step="0.05" className={inputClass} value={profile.lead_in_mm ?? 0.2}
            onChange={(e) => setProfile({ ...profile, lead_in_mm: e.target.valueAsNumber })} />
        </label>
        <label className="block text-xs text-aurora-text-muted"><input type="checkbox" checked={profile.keyed_pins ?? true}
          onChange={(e) => setProfile({ ...profile, keyed_pins: e.target.checked })} /> Détrompage : deux diamètres de pions par jonction</label>
        <p className="text-[11px] leading-relaxed text-aurora-text-dim">Valeurs initiales à adapter : vérifier le volume constructeur et calibrer le jeu avec un essai imprimé. Un profil peut représenter une imprimante, une matière et un réglage.</p>
        <div className="flex flex-wrap gap-2">
          <button type="button" className="rounded-lg border border-aurora-border px-3 py-1.5 text-xs text-aurora-text" onClick={saveProfile}>Enregistrer le profil</button>
          <button type="button" className="text-xs text-aurora-accent" onClick={() => {
            const url = URL.createObjectURL(new Blob([JSON.stringify(profile, null, 2)], { type: 'application/json' }))
            const link = document.createElement('a'); link.href = url; link.download = 'printer-profile.json'; link.click()
            setTimeout(() => URL.revokeObjectURL(url), 1000)
          }}>Exporter le profil JSON</button>
          {profiles.some((p) => p.name === profile.name) && <button type="button" className="text-xs text-aurora-text-muted" onClick={() => {
            try { const next = profiles.filter((p) => p.name !== profile.name); localStorage.setItem(STORAGE, JSON.stringify(next)); setProfiles(next); setProfile({ ...initial }) }
            catch { setError('Suppression du profil indisponible.') }
          }}>Supprimer ce profil</button>}
        </div>
        <label className="block text-xs text-aurora-text-muted">Verticale du modèle dans le viewer d’assemblage
          <select className={inputClass} value={upAxis} onChange={(e) => setUpAxis(e.target.value)}>{['z','y','x'].map((v) => <option key={v} value={v}>{v.toUpperCase()} vertical</option>)}</select>
        </label>
        <label className="block text-xs text-aurora-text-muted">Axe de découpe
          <select aria-label="Axe de découpe" className={inputClass} value={axis} onChange={(e) => setAxis(e.target.value)}>
            <option value="auto">Automatique : volume, surface de raccord et logements</option>{['x', 'y', 'z'].map((v) => <option key={v} value={v}>{v.toUpperCase()}</option>)}
          </select>
        </label>
        <label className="block text-xs text-aurora-text-muted">Plans de coupe (mm depuis le minimum de l’axe)
          <input aria-label="Plans de coupe mm" value={cuts} onChange={(e) => setCuts(e.target.value)} placeholder="Automatique, ou 60 ; 120" className={inputClass} />
        </label>
        <details className="text-xs text-aurora-text-muted"><summary>Zones protégées et positions imposées</summary>
          <p className="mt-2">Coordonnées en mm après mise à l’échelle, origine au minimum du modèle. protected_zones_mm : liste de boîtes [minimum XYZ, maximum XYZ]. connector_centers_mm : une paire de centres XYZ par jonction, dans l’ordre des coupes puis des fragments. Les positions imposées subissent les mêmes contrôles.</p>
          <textarea aria-label="Contraintes d’assemblage JSON" rows={5} className={inputClass} value={constraints}
            placeholder={'{"protected_zones_mm": [[[50, 0, 0], [70, 15, 15]]]}'} onChange={(e) => setConstraints(e.target.value)} />
        </details>
        <p className="text-[11px] text-aurora-text-dim">Deux pions par jonction, placements comparés pour maximiser leur écartement. Paroi locale, zones protégées, profondeur et interférences contrôlées. Les fonctions mécaniques du modèle doivent être renseignées par ses contraintes.</p>
      </>}
      <button onClick={() => void prepare()} disabled={!file && !modelUrl} className="w-full rounded-xl bg-aurora-accent px-3 py-2 text-xs font-semibold text-white disabled:opacity-40">
        Préparer {mode === 'assembly' ? 'les pièces et raccords' : mode === 'textured' ? 'la version texturée' : 'la géométrie pure'}
      </button>
    </fieldset></details>
    {busy && <p role="status" className="mt-3 text-xs text-aurora-accent">Préparation et contrôles des pièces…</p>}
    {message && <p role="status" className="mt-3 text-xs text-aurora-accent">{message}</p>}
    {error && <p role="alert" className="mt-3 text-xs text-red-400">{error}</p>}
    {assemblyOnly && active && result?.report && <div className="mt-4"><div className="flex gap-2 mb-3"><button type="button" aria-pressed={!previewExploded} className="min-h-11 rounded-lg border border-aurora-border px-3" onClick={() => setPreviewExploded(false)}>Vue assemblée</button><button type="button" aria-pressed={previewExploded} className="min-h-11 rounded-lg border border-aurora-border px-3" onClick={() => setPreviewExploded(true)}>Vue éclatée</button></div><iframe title="Viewer d’assemblage" className="w-full h-[75dvh] min-h-[360px] rounded-xl border border-aurora-border" src={`${getBridgeUrl()}/api/asset/output/engineering/${jobId}/package/viewer.html${previewExploded ? '?exploded=1' : ''}`} /></div>}
    {result?.report && <div className="mt-3 space-y-2 text-xs text-aurora-text">
      <p>{result.report.size_applied ? `Dimensions : ${result.report.dimensions_mm.map((v) => v.toFixed(2)).join(' × ')} mm.` : 'GLB original conservé ; taille inchangée.'}</p>
      {exportedMode === 'assembly' ? <>
        <p>{result.report.piece_count} pièce(s), {result.report.pin_count} pion(s). Axe {result.report.cut_axis?.toUpperCase()} ; coupes {result.report.cuts_mm?.map((v) => v.toFixed(2)).join(' ; ') || 'inutiles : modèle dans le volume utile'}.</p>
        <div className="flex flex-wrap gap-3">
          <a target="_blank" rel="noreferrer" className="text-aurora-accent"
            href={`${getBridgeUrl()}/api/asset/output/engineering/${jobId}/package/viewer.html`}>Assemblage par couleurs</a>
          <a target="_blank" rel="noreferrer" className="text-aurora-accent"
            href={`${getBridgeUrl()}/api/asset/output/engineering/${jobId}/package/viewer.html?exploded=1${result.report.textured_assembly_available ? '&appearance=textured' : ''}`}>
            {result.report.textured_assembly_available ? 'Éclaté texturé' : 'Éclaté par couleurs'}</a>
        </div>
        {result.report.fabrication && <><p>{result.report.fabrication.instructions}</p>{result.report.fabrication.filament_plan.map((f) => <p key={f.part}><span style={{ color: f.color }}>■</span> {f.part} : {f.name}</p>)}</>}
        <p className="text-aurora-text-muted">Vérifications numériques réussies. L’ajustement physique et la résistance restent à vérifier sur les impressions.</p>
      </> : exportedMode === 'geometry' && <p className="text-aurora-text-muted">{result.report.source_watertight ? 'Maillage fermé.' : 'Maillage ouvert : cette géométrie nécessite une réparation avant assemblage.'}</p>}
      <button onClick={() => void download()} className="rounded-lg border border-aurora-accent px-3 py-2 text-aurora-accent">Télécharger le ZIP</button>
    </div>}
  </section>
}
