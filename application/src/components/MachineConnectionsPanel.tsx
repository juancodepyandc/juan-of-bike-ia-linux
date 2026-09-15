// MachineConnectionsPanel — drop-in panel for AuroraV*CodeView and
// AuroraV*CoworkView to manage SSH / machine targets (Raspberry Pi, VPS, NAS,
// localhost). Lists targets, adds new ones (host/user/port + password OR key),
// probes connectivity, generates SSH keypairs, deletes targets.
//
// All actions go through the bridge /api/connect/* endpoints (machineConnectors.ts).
import { useEffect, useState } from 'react'
import {
  type MachineTarget,
  deleteTarget,
  keygen,
  listTargets,
  probe,
  saveTarget,
  tcpProbe,
} from '../services/machineConnectors.ts'

type Platform = NonNullable<MachineTarget['platform']>

const PLATFORMS: { value: Platform; label: string; hints: string }[] = [
  { value: 'raspberry_pi', label: 'Raspberry Pi', hints: 'Pi 4 ARMv7, Bookworm, RPi.GPIO + picamera2 + lgpio' },
  { value: 'linux_x86', label: 'Linux x86 server / VPS', hints: 'Ubuntu/Debian, Python 3.12, Node 20, systemd' },
  { value: 'linux_arm', label: 'Linux ARM (autre que Pi)', hints: 'ARM64, libc standard' },
  { value: 'linux_wsl', label: 'WSL Ubuntu', hints: 'Ubuntu sous Windows, pas de GPIO' },
  { value: 'macos', label: 'macOS', hints: 'BSD userland, Homebrew dispo' },
  { value: 'unknown', label: 'Autre', hints: 'à préciser' },
]

type LogLine = { level: 'info' | 'ok' | 'err'; text: string; at: number }

export function MachineConnectionsPanel({ embed = false }: { embed?: boolean }) {
  const [targets, setTargets] = useState<MachineTarget[]>([])
  const [loading, setLoading] = useState(true)
  const [log, setLog] = useState<LogLine[]>([])
  const [editing, setEditing] = useState<Partial<MachineTarget> & {
    password?: string; save_password?: boolean
  } | null>(null)

  const push = (level: LogLine['level'], text: string) =>
    setLog(l => [...l, { level, text, at: Date.now() }].slice(-30))

  const refresh = async () => {
    setLoading(true)
    try {
      const t = await listTargets()
      setTargets(t)
    } catch (e) {
      push('err', `liste cibles: ${e instanceof Error ? e.message : String(e)}`)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void refresh() }, [])

  const handleProbe = async (t: MachineTarget) => {
    push('info', `probe ${t.name}…`)
    try {
      const r = await probe({ target_name: t.name })
      if (r.ok) push('ok', `${t.name}: ${(r.out || '').split('\n').slice(0, 2).join(' | ').slice(0, 200)}`)
      else push('err', `${t.name}: ${r.error || r.err || 'auth refused'}`)
    } catch (e) { push('err', `${t.name}: ${e instanceof Error ? e.message : String(e)}`) }
  }

  const handleDelete = async (t: MachineTarget) => {
    if (!confirm(`Supprimer la cible "${t.name}" ?`)) return
    await deleteTarget(t.name)
    push('ok', `${t.name} supprimé`)
    await refresh()
  }

  const handleSave = async () => {
    if (!editing) return
    if (!editing.name || !editing.host || !editing.user) {
      push('err', 'nom + host + user requis')
      return
    }
    try {
      const saved = await saveTarget({
        name: editing.name,
        host: editing.host,
        user: editing.user,
        port: editing.port ?? 22,
        deploy_path: editing.deploy_path || `/home/${editing.user}/aurora_deploys`,
        platform: editing.platform ?? 'linux_x86',
        platform_hints: editing.platform_hints || '',
        preview_url_base: editing.preview_url_base,
        key_path: editing.key_path,
        save_password: !!editing.save_password,
        password: editing.password,
      })
      push('ok', `${saved.name} enregistré`)
      setEditing(null)
      await refresh()
    } catch (e) {
      push('err', `save: ${e instanceof Error ? e.message : String(e)}`)
    }
  }

  const handleKeygen = async () => {
    const comment = prompt('Commentaire pour la clé (ex: aurora-pi):', 'aurora') || 'aurora'
    push('info', `genere paire de cles ed25519…`)
    const r = await keygen(comment)
    if (r.ok && r.public_key) {
      push('ok', `paire creee dans ${r.private_key_path}`)
      push('info', `COLLE CETTE LIGNE dans ~/.ssh/authorized_keys de la cible:`)
      push('info', r.public_key)
      try { await navigator.clipboard.writeText(r.public_key) } catch (_) {}
    } else {
      push('err', `keygen: ${r.error || 'echec'}`)
    }
  }

  const handleTcpProbe = async () => {
    const hp = prompt('host:port (ex: 192.168.1.42:22):')?.trim()
    if (!hp) return
    const [h, ps] = hp.split(':')
    const port = parseInt(ps || '0', 10)
    if (!h || !port) { push('err', 'format host:port requis'); return }
    push('info', `probe TCP ${h}:${port}…`)
    const r = await tcpProbe(h, port, 4)
    push(r.ok ? 'ok' : 'err', `${h}:${port} ${r.ok ? 'reachable' : 'unreachable'} (${r.rtt_ms}ms)${r.error ? ' — ' + r.error : ''}`)
  }

  return (
    <div className={embed ? 'machine-conn-embed' : 'machine-conn-panel'} style={{
      padding: 12, borderRadius: 10, background: 'rgba(20,22,28,.7)',
      border: '1px solid rgba(255,255,255,.08)', color: '#e6e8eb',
      fontFamily: 'system-ui, sans-serif', fontSize: 13,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 10 }}>
        <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>Connections — Machines distantes</h3>
        <span style={{ opacity: .6, fontSize: 11 }}>{targets.length} cible(s)</span>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 6 }}>
          <button onClick={() => setEditing({ port: 22, platform: 'linux_x86' })}
                    style={btn('primary')}>+ Ajouter</button>
          <button onClick={handleKeygen} style={btn()}>Generer cle SSH</button>
          <button onClick={handleTcpProbe} style={btn()}>TCP probe</button>
          <button onClick={refresh} style={btn()}>↻</button>
        </div>
      </div>

      {loading && <div style={{ opacity: .7 }}>chargement…</div>}
      {!loading && targets.length === 0 && (
        <div style={{ opacity: .6, padding: 8, fontStyle: 'italic' }}>
          Aucune cible configurée. Clique "+ Ajouter" pour connecter un Pi / VPS / NAS.
        </div>
      )}

      <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 6 }}>
        {targets.map(t => (
          <li key={t.name} style={{
            display: 'flex', gap: 10, alignItems: 'center',
            padding: '6px 10px', borderRadius: 6,
            background: 'rgba(255,255,255,.04)',
          }}>
            <strong style={{ minWidth: 100 }}>{t.name}</strong>
            <span style={{ fontFamily: 'monospace', fontSize: 12, opacity: .85 }}>
              {t.user}@{t.host}:{t.port ?? 22}
            </span>
            <span style={{ fontSize: 11, opacity: .6 }}>{t.platform ?? 'unknown'}</span>
            <span style={{ marginLeft: 'auto', display: 'flex', gap: 4 }}>
              <button onClick={() => handleProbe(t)} style={btn('small')}>probe</button>
              <button onClick={() => setEditing(t)} style={btn('small')}>edit</button>
              <button onClick={() => handleDelete(t)} style={btn('danger')}>×</button>
            </span>
          </li>
        ))}
      </ul>

      {editing && (
        <div style={{ marginTop: 10, padding: 10, background: 'rgba(255,255,255,.05)', borderRadius: 8 }}>
          <div style={{ display: 'grid', gridTemplateColumns: '110px 1fr', gap: 6, alignItems: 'center' }}>
            <label>Nom</label>
            <input value={editing.name || ''} onChange={e => setEditing({ ...editing, name: e.target.value })}
                     placeholder="ex: my-pi" style={inp()} />
            <label>Host</label>
            <input value={editing.host || ''} onChange={e => setEditing({ ...editing, host: e.target.value })}
                     placeholder="192.168.1.42 ou domain.com" style={inp()} />
            <label>User</label>
            <input value={editing.user || ''} onChange={e => setEditing({ ...editing, user: e.target.value })}
                     placeholder="pi / ubuntu / root" style={inp()} />
            <label>Port</label>
            <input type="number" value={editing.port ?? 22} onChange={e => setEditing({ ...editing, port: parseInt(e.target.value, 10) || 22 })}
                     style={inp()} />
            <label>Deploy path</label>
            <input value={editing.deploy_path || ''} onChange={e => setEditing({ ...editing, deploy_path: e.target.value })}
                     placeholder="/home/pi/aurora_deploys" style={inp()} />
            <label>Plateforme</label>
            <select value={editing.platform || 'linux_x86'}
                      onChange={e => {
                        const v = e.target.value as Platform
                        const p = PLATFORMS.find(x => x.value === v)
                        setEditing({ ...editing, platform: v, platform_hints: p?.hints || editing.platform_hints })
                      }} style={inp()}>
              {PLATFORMS.map(p => <option key={p.value} value={p.value}>{p.label}</option>)}
            </select>
            <label>Hints</label>
            <input value={editing.platform_hints || ''} onChange={e => setEditing({ ...editing, platform_hints: e.target.value })}
                     placeholder="libs disponibles, version OS…" style={inp()} />
            <label>Cle SSH (.pem path)</label>
            <input value={editing.key_path || ''} onChange={e => setEditing({ ...editing, key_path: e.target.value })}
                     placeholder="C:/Users/Juan/.ssh/id_ed25519 (optionnel)" style={inp()} />
            <label>Password</label>
            <input type="password" value={editing.password || ''}
                     onChange={e => setEditing({ ...editing, password: e.target.value })}
                     placeholder="(laisser vide si cle SSH)" style={inp()} />
            <label></label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, opacity: .85 }}>
              <input type="checkbox" checked={!!editing.save_password}
                       onChange={e => setEditing({ ...editing, save_password: e.target.checked })} />
              Sauvegarder le mot de passe (sinon par-requete uniquement)
            </label>
          </div>
          <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
            <button onClick={handleSave} style={btn('primary')}>Enregistrer</button>
            <button onClick={() => setEditing(null)} style={btn()}>Annuler</button>
          </div>
        </div>
      )}

      {log.length > 0 && (
        <div style={{ marginTop: 12, padding: 8, background: 'rgba(0,0,0,.3)', borderRadius: 6,
                       maxHeight: 160, overflowY: 'auto', fontFamily: 'monospace', fontSize: 11 }}>
          {log.map(l => (
            <div key={l.at + l.text} style={{
              color: l.level === 'ok' ? '#7fef9d' : l.level === 'err' ? '#ff8b8b' : '#cfd2d6',
            }}>{l.text}</div>
          ))}
        </div>
      )}
    </div>
  )
}

function btn(variant: 'primary' | 'danger' | 'small' | '' = ''): React.CSSProperties {
  const base: React.CSSProperties = {
    cursor: 'pointer', border: '1px solid rgba(255,255,255,.15)',
    borderRadius: 5, padding: variant === 'small' ? '2px 8px' : '5px 10px',
    background: 'rgba(255,255,255,.05)', color: '#e6e8eb',
    fontSize: variant === 'small' ? 11 : 12,
  }
  if (variant === 'primary') return { ...base, background: 'rgba(94,124,222,.4)', borderColor: 'rgba(94,124,222,.6)' }
  if (variant === 'danger') return { ...base, background: 'rgba(222,80,80,.25)', borderColor: 'rgba(222,80,80,.4)', padding: '2px 8px' }
  return base
}

function inp(): React.CSSProperties {
  return {
    width: '100%', padding: '4px 8px', borderRadius: 5,
    border: '1px solid rgba(255,255,255,.12)',
    background: 'rgba(0,0,0,.25)', color: '#e6e8eb',
    fontFamily: 'inherit', fontSize: 12,
  }
}

export default MachineConnectionsPanel
