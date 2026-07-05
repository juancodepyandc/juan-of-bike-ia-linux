/**
 * KeyboardCheatsheet — press ? (or Shift+/) anywhere to see the keyboard
 * shortcuts. Includes a per-module section so the help is relevant.
 */
import { useEffect, useMemo, useState } from 'react'
import { createPortal } from 'react-dom'

const GROUPS: Array<{ title: string; rows: Array<[string, string]> }> = [
  {
    title: 'Global',
    rows: [
      ['Ctrl / ⌘ + K', 'Palette de modules · recherche & saut'],
      ['Ctrl / ⌘ + ,', 'Panneau Réglages'],
      ['Ctrl / ⌘ + Shift + U', 'Bascule skin UI · Editorial ↔ Ricochet'],
      ['?  ou  Ctrl / ⌘ + /', 'Afficher cette aide'],
      ['Esc', 'Fermer un panneau'],
      ['Drag & drop fichier', 'Ingestion directe (txt/pdf/docx/image) sur le module'],
      ['Ctrl / ⌘ + Shift + P', 'Revenir au module précédemment visité'],
      ['Ctrl / ⌘ + Shift + R', 'Re-ping services backend (sans recharger la page)'],
      ['Ctrl / ⌘ + J', 'Focus 1er input du module actuel (cross-module)'],
    ],
  },
  {
    title: 'Modules (saut direct)',
    rows: [
      ['Ctrl / ⌘ + 1', 'Conversation'],
      ['Ctrl / ⌘ + 2', 'Image (FLUX)'],
      ['Ctrl / ⌘ + 3', 'Code'],
      ['Ctrl / ⌘ + 4', 'Vidéo (Wan2.2)'],
      ['Ctrl / ⌘ + 5', 'Dessin (sumi-e)'],
      ['Ctrl / ⌘ + 6', '3D (Hunyuan/DG)'],
      ['Ctrl / ⌘ + 7', 'Cyber (9 labs)'],
      ['Ctrl / ⌘ + 8', 'Academy'],
      ['Ctrl / ⌘ + V', 'Voice (overlay)'],
      ['Ctrl / ⌘ + `', 'Cowork (chrome ext)'],
    ],
  },
  {
    title: 'Nav rapide (tape g puis la lettre)',
    rows: [
      ['g g', 'Chat (home, vim-style)'],
      ['g c', 'Chat'],
      ['g i', 'Image'],
      ['g o', 'Code (fOrge)'],
      ['g v', 'Vidéo'],
      ['g d', 'Dessin'],
      ['g t', 'Atelier 3D (Three-D)'],
      ['g a', 'Académie'],
      ['g s', 'Voix (Speech)'],
      ['g y', 'Cyber'],
    ],
  },
  {
    title: 'Chat',
    rows: [
      ['Ctrl / ⌘ + F', 'Chercher dans la conversation (3 skins)'],
      ['Ctrl / ⌘ + I', 'Focus composer (3 skins)'],
      ['Ctrl / ⌘ + Entrée', 'Envoyer le message'],
      ['⇧ + Entrée', 'Nouvelle ligne'],
      ['/<cmd>', 'Slash-commands (fiche, explain, translate…)'],
      ['↑↓ + Tab/Entrée (slash menu)', 'Naviguer + sélectionner une commande'],
      ['Esc (slash menu)', 'Annuler la saisie slash'],
      ['Alt + R / C / W (modal doc)', 'Toggle regex / case-sensitive / mots entiers'],
      ['Ctrl + Entrée (éditeur)', 'Enregistrer l\'édition d\'un message'],
      ['End', 'Aller en bas du transcript'],
      ['Home', 'Aller en haut du transcript'],
      ['PageDown / PageUp', 'Scroll par chunk de 85% du viewport'],
    ],
  },
  {
    title: 'Dessin',
    rows: [
      ['Ctrl / ⌘ + Z', 'Annuler le trait'],
      ['Ctrl / ⌘ + Y', 'Rétablir'],
      ['⇧ + Ctrl + Z', 'Rétablir (variante)'],
      ['1 / 2 / 3 / 4 / 5', 'Brush size preset (1, 2, 4, 6, 12 px)'],
      ['B / E / S', 'Brush · Eraser · Symétrie toggle'],
      ['X', 'Swap brush ↔ eraser (Photoshop)'],
      ['[  /  ]', 'Brush size −1px / +1px (Photoshop)'],
    ],
  },
  {
    title: 'Modal aperçu document (leçon / notes)',
    rows: [
      ['Ctrl / ⌘ + F', 'Rechercher dans le doc'],
      ['Entrée  /  ⇧ + Entrée', 'Match suivante / précédente'],
      ['Alt + R', 'Toggle regex mode (flags gimu)'],
      ['Alt + C', 'Toggle case-sensitive'],
      ['Alt + W', 'Toggle whole-word (\\b…\\b)'],
      ['Ctrl / ⌘ + Z', 'Annuler la dernière replace'],
      ['Ctrl / ⌘ + Shift + Z  /  Ctrl + Y', 'Refaire'],
      ['Double-clic section', 'Copier le contenu de la section'],
      ['Drag pill section', 'Réorganiser l\'ordre des sources'],
    ],
  },
  {
    title: 'Grimoire mobile',
    rows: [
      ['2 doigts (swipe ↑)', 'Page suivante'],
      ['2 doigts (swipe ↓)', 'Page précédente'],
      ['1 doigt', 'Scroll naturel dans la page'],
    ],
  },
]

export default function KeyboardCheatsheet() {
  const [open, setOpen] = useState(false)
  // v82fx : filtre/recherche dans la cheatsheet
  const [query, setQuery] = useState('')

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      // Skip when typing inside an input / textarea so `?` in text isn't hijacked
      const tag = (e.target as HTMLElement | null)?.tagName
      const inField = tag === 'INPUT' || tag === 'TEXTAREA' || (e.target as HTMLElement | null)?.isContentEditable
      if (!inField && e.key === '?') { e.preventDefault(); setOpen((v) => !v) }
      // v82gb : Cmd+/ ou Ctrl+/ alternative shortcut (cohérent avec d'autres apps)
      else if ((e.ctrlKey || e.metaKey) && e.key === '/' && !e.shiftKey) {
        if (inField) return
        e.preventDefault()
        setOpen((v) => !v)
      }
      else if (open && e.key === 'Escape') setOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open])

  // Reset query à la fermeture (évite confusion à la prochaine ouverture)
  useEffect(() => { if (!open) setQuery('') }, [open])

  // v82fx : groupes filtrés par query (case-insensitive sur combo + action + title)
  const filteredGroups = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return GROUPS
    return GROUPS.map((g) => {
      const titleMatch = g.title.toLowerCase().includes(q)
      const matchedRows = g.rows.filter(([combo, action]) =>
        titleMatch
        || combo.toLowerCase().includes(q)
        || action.toLowerCase().includes(q),
      )
      return { ...g, rows: matchedRows }
    }).filter((g) => g.rows.length > 0)
  }, [query])

  const totalRows = useMemo(() => filteredGroups.reduce((a, g) => a + g.rows.length, 0), [filteredGroups])
  const totalAll = useMemo(() => GROUPS.reduce((a, g) => a + g.rows.length, 0), [])

  if (!open) return null
  return createPortal(
    <div className="kbd-overlay" onClick={() => setOpen(false)}>
      <div className="kbd-panel" onClick={(e) => e.stopPropagation()}>
        <header className="kbd-head">
          <div>
            <div className="kbd-kicker">AIDE</div>
            <div className="kbd-title">Raccourcis clavier</div>
          </div>
          <button type="button" className="kbd-close" onClick={() => setOpen(false)}>✕</button>
        </header>
        {/* v82fx : barre de recherche dans la cheatsheet */}
        <div style={{
          padding: '8px 14px',
          borderBottom: '1px solid var(--line, rgba(255,255,255,0.10))',
          display: 'flex', alignItems: 'center', gap: 8,
        }}>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Filtrer les raccourcis…"
            autoFocus
            style={{
              flex: 1, padding: '5px 10px',
              background: 'var(--bg-card, rgba(255,255,255,0.04))',
              color: 'var(--fg, #f5f5f5)',
              border: '1px solid var(--line, rgba(255,255,255,0.18))',
              borderRadius: 4, fontSize: 12,
              fontFamily: 'var(--font-mono, monospace)', outline: 'none',
            }} />
          <span style={{
            fontSize: 10, color: 'var(--fg-mute, #777)',
            fontFamily: 'var(--font-mono, monospace)',
            fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap',
          }}>
            {query ? `${totalRows} / ${totalAll}` : `${totalAll} raccourcis`}
          </span>
        </div>
        <div className="kbd-body">
          {filteredGroups.length === 0 && (
            <div style={{
              padding: '20px 14px', fontSize: 12,
              color: 'var(--fg-mute, #777)',
              fontFamily: 'var(--font-mono, monospace)', textAlign: 'center',
            }}>
              aucun raccourci ne match « {query} »
            </div>
          )}
          {filteredGroups.map((g) => (
            <section key={g.title} className="kbd-group">
              <h3>{g.title}</h3>
              <ul>
                {g.rows.map(([combo, action]) => (
                  <li key={combo}>
                    <kbd>{combo}</kbd>
                    <span>{action}</span>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
        <footer className="kbd-foot" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>Appuie sur <kbd>?</kbd> à nouveau pour fermer</span>
          {/* v82ja : commit hash visible footer cheatsheet */}
          <span title={`Build · ${typeof __AURORA_BRANCH__ !== 'undefined' ? __AURORA_BRANCH__ : 'unknown'}`}
            style={{ opacity: 0.55, fontFamily: 'var(--font-mono, monospace)', fontSize: 9 }}>
            Aurora {typeof __AURORA_COMMIT__ !== 'undefined' ? __AURORA_COMMIT__ : 'dev'}
          </span>
        </footer>
      </div>
    </div>,
    document.body,
  )
}
