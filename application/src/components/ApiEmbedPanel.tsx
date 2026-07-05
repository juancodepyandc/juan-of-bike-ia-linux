/**
 * ApiEmbedPanel — gère la clé d'API « site externe » et donne le snippet à
 * coller dans un site pour y embarquer le chat (et la génération 3D) Aurora.
 *
 * S'ouvre via l'event window `aurora:open-api-panel` (depuis Paramètres ou la
 * palette ⌘K). Appelle le bridge :
 *   GET  /api/ext/key/status     → { exists, label, origin, created, prefix }
 *   POST /api/ext/key/generate   → { ok, key }      (la clé n'est montrée QU'ICI)
 *   POST /api/ext/key/revoke     → { ok }
 */
import { useEffect, useState } from 'react'

type KeyStatus = { exists: boolean; label?: string; origin?: string; created?: string; prefix?: string }

function tunnelOrigin(): string {
  // En prod, l'app est servie via le tunnel ⇒ window.location.origin EST l'URL
  // que le site externe doit cibler.
  try { return window.location.origin } catch { return '' }
}

export default function ApiEmbedPanel() {
  const [open, setOpen] = useState(false)
  const [status, setStatus] = useState<KeyStatus | null>(null)
  const [freshKey, setFreshKey] = useState<string | null>(null)
  const [domain, setDomain] = useState('')
  const [label, setLabel] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [copied, setCopied] = useState<string | null>(null)

  useEffect(() => {
    const onOpen = () => { setOpen(true); setFreshKey(null); setErr(null); void refresh() }
    window.addEventListener('aurora:open-api-panel', onOpen)
    return () => window.removeEventListener('aurora:open-api-panel', onOpen)
  }, [])

  async function refresh() {
    try {
      const r = await fetch('/api/ext/key/status')
      setStatus(await r.json())
    } catch { setStatus(null) }
  }

  async function generate() {
    setBusy(true); setErr(null)
    try {
      const r = await fetch('/api/ext/key/generate', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        // replace_all : la régénération depuis ce panneau remplace l'ancienne
        // clé (mental model "1 clé"). Plusieurs clés actives = via l'API directe.
        body: JSON.stringify({ origin: domain.trim(), label: label.trim() || undefined, replace_all: true }),
      })
      const j = await r.json()
      if (!r.ok || !j.ok) { setErr(j.error || 'échec de la génération'); return }
      setFreshKey(j.key)
      await refresh()
    } catch (e) { setErr(String(e)) } finally { setBusy(false) }
  }

  async function revoke() {
    if (!confirm('Révoquer la clé ? Le site qui l\'utilise ne pourra plus appeler Aurora.')) return
    setBusy(true); setErr(null)
    try {
      const r = await fetch('/api/ext/key/revoke', { method: 'POST' })
      const j = await r.json()
      if (!r.ok || !j.ok) { setErr(j.error || 'échec'); return }
      setFreshKey(null); await refresh()
    } catch (e) { setErr(String(e)) } finally { setBusy(false) }
  }

  function copy(text: string, tag: string) {
    try { void navigator.clipboard.writeText(text); setCopied(tag); setTimeout(() => setCopied(null), 1500) } catch { /* noop */ }
  }

  if (!open) return null
  const url = tunnelOrigin()
  const keyForSnippet = freshKey || 'aur_TA_CLÉ_ICI'
  const snippetTag = `<script src="${url}/aurora-embed.js"\n        data-aurora-url="${url}"\n        data-aurora-key="${keyForSnippet}"\n        data-aurora-title="Assistant"></script>`
  const snippetJs = `import('${url}/aurora-embed.js').then(() => AuroraEmbed.init({\n  url: '${url}',\n  key: '${keyForSnippet}',\n  title: 'Assistant', accent: '#d97757'\n}))`
  const snippet3d = `// génération d'un GLB depuis ton code\nAuroraEmbed.generate3D('boîtier IP65 avec écran LCD 3.5" et 4 LED status', (s) => {\n  console.log(s.state, s.elapsed_s + 's', s.step)\n  if (s.state === 'done') loadGlbInMyViewer('${url}' + s.glb_url)\n})`

  const box: React.CSSProperties = { background: '#0c0a09', border: '1px solid rgba(255,255,255,0.12)', borderRadius: 8, padding: 12, fontFamily: 'ui-monospace, monospace', fontSize: 12, whiteSpace: 'pre-wrap', wordBreak: 'break-all', color: '#e8e0d4', position: 'relative' }
  const copyBtn = (text: string, tag: string): React.ReactElement => (
    <button type="button" onClick={() => copy(text, tag)} style={{ position: 'absolute', top: 6, right: 6, fontSize: 10, padding: '3px 8px', borderRadius: 5, border: '1px solid rgba(255,255,255,0.15)', background: 'rgba(255,255,255,0.06)', color: copied === tag ? '#3ddc84' : '#aaa', cursor: 'pointer' }}>{copied === tag ? '✓ copié' : 'copier'}</button>
  )

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 9000, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }} onClick={() => setOpen(false)}>
      <div onClick={(e) => e.stopPropagation()} style={{ width: 'min(640px, 100%)', maxHeight: '90vh', overflowY: 'auto', background: '#15110f', color: '#f3ede4', border: '1px solid rgba(255,255,255,0.12)', borderRadius: 14, padding: '20px 22px', fontFamily: 'system-ui, sans-serif' }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginBottom: 6 }}>
          <div style={{ fontSize: 11, letterSpacing: '0.18em', textTransform: 'uppercase', color: '#888', fontFamily: 'ui-monospace, monospace' }}>API · Site externe</div>
          <div style={{ flex: 1 }} />
          <button type="button" onClick={() => setOpen(false)} style={{ background: 'none', border: 'none', color: '#aaa', fontSize: 18, cursor: 'pointer' }}>✕</button>
        </div>
        <h2 style={{ margin: '0 0 4px', fontSize: 22, fontFamily: 'Georgia, serif', fontStyle: 'italic' }}>Appelle ton IA depuis ton site</h2>
        <p style={{ margin: '0 0 16px', fontSize: 13, color: '#bdb4a6', lineHeight: 1.5 }}>
          Génère une clé, colle le snippet dans ton site : un mini-chat apparaît (comme le module Conversation),
          et tu peux aussi demander un <b>GLB</b> (boîtier, composant…) par API. Tout passe par ton tunnel local —
          rien dans le cloud. La clé est durcie : seul son hash est stocké, comparaison constante, verrou de domaine, rate-limit.
        </p>

        {/* État actuel */}
        <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 14, fontSize: 12, fontFamily: 'ui-monospace, monospace' }}>
          <span style={{ width: 8, height: 8, borderRadius: 99, background: status?.exists ? '#3ddc84' : '#777', boxShadow: status?.exists ? '0 0 10px #3ddc84' : 'none' }} />
          {status?.exists
            ? <span>clé active{status.prefix ? ` · ${status.prefix}` : ''}{status.origin ? ` · domaine ${status.origin}` : ' · tous domaines'}{status.created ? ` · créée ${status.created}` : ''}</span>
            : <span style={{ color: '#999' }}>aucune clé — génère-en une</span>}
          {status?.exists && <button type="button" onClick={revoke} disabled={busy} style={{ marginLeft: 'auto', fontSize: 11, padding: '4px 10px', borderRadius: 5, border: '1px solid rgba(232,83,63,0.5)', background: 'rgba(232,83,63,0.12)', color: '#e0533f', cursor: 'pointer' }}>révoquer</button>}
        </div>

        {/* Génération */}
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 6 }}>
          <input value={domain} onChange={(e) => setDomain(e.target.value)} placeholder="domaine autorisé (optionnel, ex: https://mon-site.fr ou *.mon-site.fr)" style={{ flex: 2, minWidth: 220, padding: '8px 10px', borderRadius: 7, border: '1px solid rgba(255,255,255,0.12)', background: '#0c0a09', color: '#f3ede4', fontSize: 12 }} />
          <input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="nom (ex: mon site)" style={{ flex: 1, minWidth: 120, padding: '8px 10px', borderRadius: 7, border: '1px solid rgba(255,255,255,0.12)', background: '#0c0a09', color: '#f3ede4', fontSize: 12 }} />
          <button type="button" onClick={generate} disabled={busy} style={{ padding: '8px 16px', borderRadius: 7, border: 'none', background: '#d97757', color: '#fff', fontWeight: 600, fontSize: 13, cursor: busy ? 'default' : 'pointer', opacity: busy ? 0.6 : 1 }}>{busy ? '…' : status?.exists ? 'Régénérer' : 'Générer la clé'}</button>
        </div>
        <div style={{ fontSize: 11, color: '#8a8378', marginBottom: 14 }}>Régénérer révoque l'ancienne clé. Sans domaine, la clé marche depuis n'importe où (moins sûr).</div>

        {err && <div style={{ fontSize: 12, color: '#e0533f', marginBottom: 12, padding: '8px 10px', borderRadius: 6, background: 'rgba(232,83,63,0.10)', border: '1px solid rgba(232,83,63,0.4)' }}>⚠ {err}</div>}

        {freshKey && (
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 11, letterSpacing: '0.14em', textTransform: 'uppercase', color: '#d97757', marginBottom: 6 }}>Ta clé — copie-la maintenant, elle ne sera plus affichée</div>
            <div style={box}>{freshKey}{copyBtn(freshKey, 'key')}</div>
          </div>
        )}

        <div style={{ fontSize: 11, letterSpacing: '0.14em', textTransform: 'uppercase', color: '#888', margin: '4px 0 6px' }}>1 · Colle ça avant &lt;/body&gt; de ton site</div>
        <div style={{ ...box, marginBottom: 14 }}>{snippetTag}{copyBtn(snippetTag, 'tag')}</div>

        <div style={{ fontSize: 11, letterSpacing: '0.14em', textTransform: 'uppercase', color: '#888', margin: '4px 0 6px' }}>… ou en JS</div>
        <div style={{ ...box, marginBottom: 14 }}>{snippetJs}{copyBtn(snippetJs, 'js')}</div>

        <div style={{ fontSize: 11, letterSpacing: '0.14em', textTransform: 'uppercase', color: '#888', margin: '4px 0 6px' }}>2 · Demander un GLB par API (boîtiers, composants…)</div>
        <div style={{ ...box, marginBottom: 6 }}>{snippet3d}{copyBtn(snippet3d, '3d')}</div>
        <div style={{ fontSize: 11, color: '#8a8378', marginBottom: 6 }}>
          La génération 3D est asynchrone (FLUX → Hunyuan3D → auto-rescue) : tu reçois le temps écoulé en direct, et si le rendu
          est rejeté il est refait automatiquement. Tu charges le .glb dans <i>ton</i> viewer. Endpoints bruts :
          {' '}<code>POST /api/ext/chat</code>, <code>POST /api/ext/3d/generate</code>, <code>GET /api/ext/3d/status/&lt;id&gt;</code>.
        </div>
      </div>
    </div>
  )
}
