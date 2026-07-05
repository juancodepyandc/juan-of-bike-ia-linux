/**
 * v82eu : preview text avec bouton "voir tout" qui ouvre un modal
 * de lecture complète. Réutilisé par Academy (lessonText) et Cyber
 * (notesText) pour parité totale.
 */
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'

interface Props {
  /** Nom du fichier source affiché en header */
  name: string
  /** Texte complet (peut faire 50+ KB) */
  text: string
  /** Glyph en début de header (ex: 📄 ou 📑) */
  glyph?: string
  /** Label header (ex: "leçon active") */
  label?: string
  /** v82fc : callback pour appliquer find & replace côté parent.
   *  Si absent, le mode replace est masqué (read-only). */
  onTextChange?: (newText: string) => void
  /** v82fh : texte d'origine pour détecter les modifs locales.
   *  Si fourni et différent de text, affiche un badge "● edited". */
  originalText?: string
}

export default function TextPreviewExpander({ name, text, glyph = '📄', label = 'document actif', onTextChange, originalText }: Props) {
  // v82fh : badge "edited" si text != originalText (length === text déjà
  // optimisé en first comparator pour skip les comparaisons de big string).
  const isEdited = originalText !== undefined && originalText.length !== text.length
    || (originalText !== undefined && originalText !== text)
  const [open, setOpen] = useState(false)
  // v82ev : feedback temporaire copy-to-clipboard
  const [copied, setCopied] = useState(false)
  // v82ex : recherche texte interne au modal
  const [query, setQuery] = useState('')
  const [currentMatch, setCurrentMatch] = useState(0)
  const searchRef = useRef<HTMLInputElement | null>(null)
  // v82ey : mode regex (case-insensitive par défaut, multiline, unicode).
  const [regexMode, setRegexMode] = useState(false)
  // v82ez : toggle case-sensitive séparé du regex mode.
  const [caseSensitive, setCaseSensitive] = useState(false)
  // v82fa : toggle whole-word — wrap la query avec \b...\b en regex
  // (avec escape automatique si plain mode).
  const [wholeWord, setWholeWord] = useState(false)
  // v82fc : mode replace + champ remplacement
  const [replaceMode, setReplaceMode] = useState(false)
  const [replaceWith, setReplaceWith] = useState('')
  // v82fd : history stack pour undo des dernières replaces (cap 10)
  const [history, setHistory] = useState<string[]>([])
  // v82ff : redoStack pour ré-appliquer un undo annulé (cap 10).
  // Vidée à chaque nouvelle replace (sinon redo désynchronisé).
  const [redoStack, setRedoStack] = useState<string[]>([])
  // Reset l'history + redo quand le modal se ferme (évite confusion
  // entre sessions de replace différentes).
  useEffect(() => {
    if (!open) { setHistory([]); setRedoStack([]) }
  }, [open])
  // Esc pour fermer le modal + Ctrl+F pour focus la recherche
  // v82fb : Alt+R/C/W pour toggler regex/case/whole word sans souris
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (query) { setQuery(''); return }
        setOpen(false)
      }
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'f') {
        e.preventDefault()
        searchRef.current?.focus()
        searchRef.current?.select()
      }
      // v82fb : Alt+R/C/W (sans Ctrl ni Meta pour éviter conflit OS)
      if (e.altKey && !e.ctrlKey && !e.metaKey) {
        const k = e.key.toLowerCase()
        if (k === 'r') { e.preventDefault(); setRegexMode((v) => !v) }
        else if (k === 'c') { e.preventDefault(); setCaseSensitive((v) => !v) }
        else if (k === 'w') { e.preventDefault(); setWholeWord((v) => !v) }
      }
      // v82fe : Ctrl+Z / Cmd+Z (sans Shift) pour undo replace.
      // v82ff : Ctrl+Shift+Z / Cmd+Shift+Z OU Ctrl+Y pour redo.
      // Skip si focus sur INPUT/TEXTAREA pour laisser le navigateur
      // gérer l'undo/redo natif du champ courant.
      const isUndo = (e.ctrlKey || e.metaKey) && !e.shiftKey && e.key.toLowerCase() === 'z'
      const isRedo = ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === 'z')
        || ((e.ctrlKey || e.metaKey) && !e.shiftKey && e.key.toLowerCase() === 'y')
      if (isUndo || isRedo) {
        const target = e.target as HTMLElement | null
        const tag = target?.tagName?.toUpperCase()
        if (tag === 'INPUT' || tag === 'TEXTAREA') return
        e.preventDefault()
        if (isUndo) {
          setHistory((h) => {
            if (h.length === 0) return h
            const restored = h[h.length - 1]
            setRedoStack((r) => {
              const next = [...r, text]
              return next.length > 10 ? next.slice(next.length - 10) : next
            })
            if (onTextChange) onTextChange(restored)
            return h.slice(0, -1)
          })
        } else {
          setRedoStack((r) => {
            if (r.length === 0) return r
            const restored = r[r.length - 1]
            setHistory((h) => {
              const next = [...h, text]
              return next.length > 10 ? next.slice(next.length - 10) : next
            })
            if (onTextChange) onTextChange(restored)
            return r.slice(0, -1)
          })
        }
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, query, onTextChange, text])
  // Reset query quand on ferme le modal
  useEffect(() => { if (!open) { setQuery(''); setCurrentMatch(0) } }, [open])
  // v82ex/v82ey : compute matches — texte plain ou regex (gimu flags).
  // Renvoie {matches, invalid} : matches[].length variable en regex.
  const searchResult = useMemo(() => {
    if (!query || !open) return { matches: [] as { start: number; length: number }[], invalid: false }
    const matches: { start: number; length: number }[] = []
    // v82fa : si regexMode OU wholeWord, on passe par RegExp.
    if (regexMode || wholeWord) {
      try {
        // Échappe les chars regex si on n'est pas en regexMode (utile
        // pour wholeWord plain).
        const escape = (s: string) => s.replace(/[-/\\^$*+?.()|[\]{}]/g, '\\$&')
        const corePattern = regexMode ? query : escape(query)
        const pattern = wholeWord ? `\\b${corePattern}\\b` : corePattern
        const flags = caseSensitive ? 'gmu' : 'gimu'
        const re = new RegExp(pattern, flags)
        let m = re.exec(text)
        let lastIndex = -1
        while (m && matches.length < 500) {
          if (re.lastIndex === lastIndex) break
          matches.push({ start: m.index, length: m[0].length || 1 })
          lastIndex = re.lastIndex
          m = re.exec(text)
        }
        return { matches, invalid: false }
      } catch {
        return { matches: [], invalid: true }
      }
    }
    // Plain text + !wholeWord : indexOf rapide
    const haystack = caseSensitive ? text : text.toLowerCase()
    const q = caseSensitive ? query : query.toLowerCase()
    let i = haystack.indexOf(q, 0)
    while (i !== -1 && matches.length < 500) {
      matches.push({ start: i, length: q.length })
      i = haystack.indexOf(q, i + Math.max(1, q.length))
    }
    return { matches, invalid: false }
  }, [query, open, text, regexMode, caseSensitive, wholeWord])
  const matches = searchResult.matches
  const regexInvalid = searchResult.invalid
  useEffect(() => {
    setCurrentMatch((prev) => matches.length === 0 ? 0 : Math.min(prev, matches.length - 1))
  }, [matches])
  const goPrev = () => setCurrentMatch((i) => matches.length === 0 ? 0 : (i - 1 + matches.length) % matches.length)
  const goNext = () => setCurrentMatch((i) => matches.length === 0 ? 0 : (i + 1) % matches.length)
  // v82fd : push l'état courant dans l'history avant chaque replace,
  // cap à 10 entrées pour ne pas exploser la mémoire sur gros docs.
  const pushHistory = (snapshot: string) => {
    setHistory((h) => {
      const next = [...h, snapshot]
      return next.length > 10 ? next.slice(next.length - 10) : next
    })
  }
  // v82fc : remplace la match courante (1×) puis avance
  const handleReplaceCurrent = () => {
    if (!onTextChange || matches.length === 0) return
    pushHistory(text)
    setRedoStack([]) // v82ff : nouvelle edit invalide le redo
    const m = matches[currentMatch]
    const newText = text.slice(0, m.start) + replaceWith + text.slice(m.start + m.length)
    onTextChange(newText)
  }
  const handleReplaceAll = () => {
    if (!onTextChange || matches.length === 0) return
    pushHistory(text)
    setRedoStack([])
    let newText = ''
    let cursor = 0
    for (const m of matches) {
      newText += text.slice(cursor, m.start) + replaceWith
      cursor = m.start + m.length
    }
    newText += text.slice(cursor)
    onTextChange(newText)
  }
  // v82fd : pop le dernier snapshot et restaure ; push le current
  // dans le redoStack pour permettre Ctrl+Shift+Z (v82ff).
  const handleUndo = () => {
    if (!onTextChange || history.length === 0) return
    setHistory((h) => {
      const restored = h[h.length - 1]
      setRedoStack((r) => {
        const next = [...r, text]
        return next.length > 10 ? next.slice(next.length - 10) : next
      })
      onTextChange(restored)
      return h.slice(0, -1)
    })
  }
  // v82ff : pop le redoStack + push current dans history + restaure.
  const handleRedo = () => {
    if (!onTextChange || redoStack.length === 0) return
    setRedoStack((r) => {
      const restored = r[r.length - 1]
      setHistory((h) => {
        const next = [...h, text]
        return next.length > 10 ? next.slice(next.length - 10) : next
      })
      onTextChange(restored)
      return r.slice(0, -1)
    })
  }
  // v82fr : détection des sections concatenées par v82fk.
  // Pattern `=== filename ===\n\n{content}` — split l'index sur les
  // headers, garde les bornes pour que la suppression sache où couper.
  const sections = useMemo(() => {
    const headerRe = /^=== (.+?) ===\s*$/gm
    const out: { name: string; start: number; end: number }[] = []
    let m: RegExpExecArray | null
    const positions: { name: string; start: number; headerEnd: number }[] = []
    while ((m = headerRe.exec(text)) !== null) {
      positions.push({ name: m[1], start: m.index, headerEnd: m.index + m[0].length })
    }
    for (let i = 0; i < positions.length; i++) {
      const p = positions[i]
      const next = positions[i + 1]
      out.push({ name: p.name, start: p.start, end: next ? next.start : text.length })
    }
    return out
  }, [text])

  // v82fr : retire une section (et son séparateur) puis appelle
  // onTextChange. Push history avant pour permettre l'annulation.
  const handleDeleteSection = (index: number) => {
    if (!onTextChange) return
    const sec = sections[index]
    if (!sec) return
    pushHistory(text)
    setRedoStack([])
    // Trim aussi les \n\n autour pour ne pas laisser de double-saut.
    const before = text.slice(0, sec.start).replace(/\n+$/, '')
    const after = text.slice(sec.end).replace(/^\n+/, '')
    const next = before + (before && after ? '\n\n' : '') + after
    onTextChange(next)
  }

  // v82fs : réordonne les sections par drag-and-drop des pills.
  // Move section[from] vers position[to] et reconstruit le texte
  // en concaténant les morceaux dans le nouvel ordre.
  const [draggingSection, setDraggingSection] = useState<number | null>(null)
  // v82ft : feedback temporaire "✓ copié" sur la pill section
  // double-cliquée. Stocke l'index pendant 1.4s.
  const [copiedSectionIdx, setCopiedSectionIdx] = useState<number | null>(null)
  useEffect(() => {
    if (copiedSectionIdx === null) return
    const t = window.setTimeout(() => setCopiedSectionIdx(null), 1400)
    return () => window.clearTimeout(t)
  }, [copiedSectionIdx])
  const handleCopySection = async (index: number) => {
    const sec = sections[index]
    if (!sec) return
    // Extrait le contenu sans le header `=== nom ===` pour copier
    // juste la matière utile.
    const slice = text.slice(sec.start, sec.end)
    const content = slice.replace(/^=== .+? ===\s*\n*/m, '').replace(/^\n+|\n+$/g, '')
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(content)
      } else {
        const ta = document.createElement('textarea')
        ta.value = content
        ta.style.position = 'fixed'; ta.style.left = '-9999px'
        document.body.appendChild(ta); ta.select()
        document.execCommand('copy'); document.body.removeChild(ta)
      }
      setCopiedSectionIdx(index)
    } catch { /* silent */ }
  }

  // v82fu : renomme une section via prompt natif.
  // Push history + clear redo pour permettre l'annulation.
  // Le nouveau nom est sanitized (== triple-equal sont remplacés
  // par '=' simples pour ne pas casser le pattern de détection).
  const handleRenameSection = (index: number) => {
    if (!onTextChange) return
    const sec = sections[index]
    if (!sec) return
    const next = window.prompt(`Renommer la section "${sec.name}" :`, sec.name)
    if (next === null) return // annulé
    const sanitized = next.trim().replace(/=+/g, '=').slice(0, 120)
    if (!sanitized || sanitized === sec.name) return
    pushHistory(text)
    setRedoStack([])
    // Replace seulement le header de cette section précise (start..headerEnd)
    const newHeader = `=== ${sanitized} ===`
    // Trouve la fin du header (premier \n après start)
    const headerEndOffset = text.indexOf('\n', sec.start)
    const headerActualEnd = headerEndOffset === -1 ? sec.end : headerEndOffset
    const before = text.slice(0, sec.start)
    const after = text.slice(headerActualEnd)
    onTextChange(before + newHeader + after)
  }
  const handleReorderSection = (from: number, to: number) => {
    if (!onTextChange || from === to) return
    if (sections.length < 2) return
    // Préambule = tout ce qui précède la première section (rare mais
    // possible si l'user a tapé du texte avant la première === ===).
    const preamble = text.slice(0, sections[0].start).replace(/\n+$/, '')
    // Extrait chaque section en string (avec son header `=== nom ===`)
    const slices = sections.map((s) => text.slice(s.start, s.end).replace(/^\n+|\n+$/g, ''))
    // Reorder
    const reordered = [...slices]
    const [moved] = reordered.splice(from, 1)
    reordered.splice(to, 0, moved)
    pushHistory(text)
    setRedoStack([])
    const merged = reordered.join('\n\n')
    const next = preamble ? `${preamble}\n\n${merged}` : merged
    onTextChange(next)
  }

  // v82fi : revert au texte d'origine (restaure originalText).
  // Push current dans history pour permettre annulation via undo.
  const handleRevert = () => {
    if (!onTextChange || originalText === undefined) return
    if (originalText === text) return // idempotent
    pushHistory(text)
    setRedoStack([])
    onTextChange(originalText)
  }
  // Reset feedback après 1.6s
  useEffect(() => {
    if (!copied) return
    const t = window.setTimeout(() => setCopied(false), 1600)
    return () => window.clearTimeout(t)
  }, [copied])
  // v82ew : télécharge le contenu en .txt — utile quand le PDF/DOCX
  // d'origine est lourd ou si l'utilisateur veut éditer le texte
  // extrait dans un éditeur externe.
  const handleDownload = () => {
    try {
      const blob = new Blob([text], { type: 'text/plain;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      // dérive un nom de fichier .txt depuis name (remplace extension)
      const base = name.replace(/\.[^.]+$/, '') || 'export'
      a.download = `${base}.txt`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      // libère l'objet URL après tick suivant
      setTimeout(() => URL.revokeObjectURL(url), 100)
    } catch {
      // silent
    }
  }
  const handleCopy = async () => {
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text)
        setCopied(true)
        return
      }
      // Fallback execCommand pour navigateurs sans clipboard API
      const ta = document.createElement('textarea')
      ta.value = text
      ta.style.position = 'fixed'
      ta.style.left = '-9999px'
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
      setCopied(true)
    } catch {
      // silent — pas de feedback en cas d'échec navigator (rare)
    }
  }
  if (!name || text.trim().length === 0) return null
  const wordCount = text.split(/\s+/).filter(Boolean).length
  return (
    <>
      <div style={{
        padding: '6px 10px', marginBottom: 6, borderRadius: 6,
        background: 'oklch(0.74 0.13 60 / 0.04)',
        border: '1px dashed oklch(0.74 0.13 60 / 0.22)',
        fontFamily: 'var(--font-mono, monospace)', fontSize: 10,
        color: 'var(--fg-dim, #aaa)',
        display: 'flex', flexDirection: 'column', gap: 4,
      }}
        title={text.slice(0, 1500)}>
        <div style={{
          fontSize: 9, color: 'oklch(0.74 0.13 60)',
          letterSpacing: '0.14em', textTransform: 'uppercase',
          display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap',
        }}>
          <span>{glyph} {label}</span>
          <span style={{
            letterSpacing: 0, textTransform: 'none',
            color: 'var(--fg, #f5f5f5)', fontWeight: 400,
          }}>
            · {name.length > 32 ? name.slice(0, 30) + '…' : name}
          </span>
          {/* v82fh : badge "● edited" si modifié localement */}
          {isEdited && (
            <span
              title={`Texte modifié (${(text.length - (originalText?.length ?? 0))} car. de delta vs original) — utilise le bouton "voir tout" pour annuler.`}
              style={{
                letterSpacing: 0, textTransform: 'none',
                padding: '0 6px', borderRadius: 99,
                background: 'oklch(0.72 0.14 25 / 0.15)',
                border: '1px solid oklch(0.72 0.14 25 / 0.45)',
                color: 'oklch(0.72 0.14 25)',
                fontWeight: 700, fontSize: 8,
              }}>
              ● edited
            </span>
          )}
          <span style={{ flex: 1 }} />
          <span style={{
            letterSpacing: 0, textTransform: 'none',
            color: 'var(--fg-mute, #777)', fontWeight: 400,
          }}>
            {text.length.toLocaleString('fr-FR')} car · {wordCount} mots
          </span>
          <button type="button"
            onClick={() => setOpen(true)}
            title="Ouvrir le contenu complet dans un modal"
            style={{
              padding: '1px 6px', fontSize: 9,
              fontFamily: 'var(--font-mono, monospace)',
              background: 'oklch(0.74 0.13 60 / 0.10)',
              color: 'oklch(0.74 0.13 60)',
              border: '1px solid oklch(0.74 0.13 60 / 0.40)',
              borderRadius: 3, cursor: 'pointer',
              letterSpacing: '0.1em', textTransform: 'uppercase',
            }}>
            ⤢ voir tout
          </button>
        </div>
        <div style={{
          fontSize: 10, lineHeight: 1.5,
          color: 'var(--fg-dim, #ccc)',
          display: '-webkit-box',
          WebkitLineClamp: 3,
          WebkitBoxOrient: 'vertical',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}>
          {text.slice(0, 280).replace(/\n+/g, ' ')}
          {text.length > 280 ? '…' : ''}
        </div>
      </div>
      {open && (
        <div
          onClick={() => setOpen(false)}
          style={{
            position: 'fixed', inset: 0, zIndex: 1000,
            background: 'rgba(0,0,0,0.78)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            padding: 20, animation: 'fadeIn 0.18s ease-out',
          }}>
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              background: 'var(--bg, #0c0a09)',
              border: '1px solid oklch(0.74 0.13 60 / 0.45)',
              borderRadius: 10,
              maxWidth: 920, width: '100%', maxHeight: '88vh',
              display: 'flex', flexDirection: 'column',
              boxShadow: '0 20px 60px rgba(0,0,0,0.6), 0 0 1px oklch(0.74 0.13 60 / 0.4)',
            }}>
            <div style={{
              padding: '12px 16px',
              borderBottom: '1px solid var(--line, rgba(255,255,255,0.10))',
              display: 'flex', alignItems: 'center', gap: 10,
              fontFamily: 'var(--font-mono, monospace)', fontSize: 11,
            }}>
              <span style={{
                color: 'oklch(0.74 0.13 60)',
                letterSpacing: '0.14em', textTransform: 'uppercase',
              }}>
                {glyph} {label}
              </span>
              <span style={{ color: 'var(--fg, #f5f5f5)', fontWeight: 700 }}>{name}</span>
              <span style={{ color: 'var(--fg-mute, #777)' }}>
                {text.length.toLocaleString('fr-FR')} car · {wordCount} mots
              </span>
              <span style={{ flex: 1 }} />
              {/* v82ex : recherche interne au modal */}
              <input
                ref={searchRef}
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault()
                    if (e.shiftKey) goPrev(); else goNext()
                  }
                }}
                placeholder={regexMode ? '/regex/ · gimu' : 'Ctrl+F · rechercher…'}
                style={{
                  padding: '4px 8px', fontSize: 11,
                  fontFamily: 'var(--font-mono, monospace)',
                  background: 'rgba(255,255,255,0.04)',
                  color: regexInvalid ? 'oklch(0.55 0.18 25)' : 'var(--fg, #f5f5f5)',
                  border: `1px solid ${regexInvalid ? 'oklch(0.55 0.18 25)' : query && matches.length === 0 ? 'oklch(0.55 0.18 25)' : 'var(--line, rgba(255,255,255,0.18))'}`,
                  borderRadius: 4, minWidth: 160, outline: 'none',
                }} />
              {/* v82ey : toggle regex mode */}
              <button type="button"
                onClick={() => setRegexMode((v) => !v)}
                title={regexMode ? 'Mode regex actif · Alt+R pour désactiver' : 'Activer le mode regex (flags gimu) · Alt+R'}
                style={{
                  padding: '2px 8px', fontSize: 9,
                  fontFamily: 'var(--font-mono, monospace)',
                  background: regexMode ? 'oklch(0.74 0.13 60 / 0.20)' : 'transparent',
                  color: regexMode ? 'oklch(0.74 0.13 60)' : 'var(--fg-mute, #777)',
                  border: `1px ${regexMode ? 'solid' : 'dashed'} ${regexMode ? 'oklch(0.74 0.13 60 / 0.55)' : 'var(--line, rgba(255,255,255,0.18))'}`,
                  borderRadius: 4, cursor: 'pointer',
                  letterSpacing: '0.1em',
                  fontWeight: regexMode ? 700 : 400,
                }}>
                .* re
              </button>
              {/* v82fa : toggle whole word */}
              <button type="button"
                onClick={() => setWholeWord((v) => !v)}
                title={wholeWord ? 'Mots entiers uniquement · Alt+W pour désactiver' : 'Activer la recherche par mots entiers (\\b…\\b) · Alt+W'}
                style={{
                  padding: '2px 8px', fontSize: 9,
                  fontFamily: 'var(--font-mono, monospace)',
                  background: wholeWord ? 'oklch(0.74 0.13 60 / 0.20)' : 'transparent',
                  color: wholeWord ? 'oklch(0.74 0.13 60)' : 'var(--fg-mute, #777)',
                  border: `1px ${wholeWord ? 'solid' : 'dashed'} ${wholeWord ? 'oklch(0.74 0.13 60 / 0.55)' : 'var(--line, rgba(255,255,255,0.18))'}`,
                  borderRadius: 4, cursor: 'pointer',
                  letterSpacing: '0.1em',
                  fontWeight: wholeWord ? 700 : 400,
                }}>
                W
              </button>
              {/* v82ez : toggle case-sensitive */}
              <button type="button"
                onClick={() => setCaseSensitive((v) => !v)}
                title={caseSensitive ? 'Recherche sensible à la casse · Alt+C pour passer en insensible' : 'Activer la sensibilité à la casse · Alt+C'}
                style={{
                  padding: '2px 8px', fontSize: 9,
                  fontFamily: 'var(--font-mono, monospace)',
                  background: caseSensitive ? 'oklch(0.74 0.13 60 / 0.20)' : 'transparent',
                  color: caseSensitive ? 'oklch(0.74 0.13 60)' : 'var(--fg-mute, #777)',
                  border: `1px ${caseSensitive ? 'solid' : 'dashed'} ${caseSensitive ? 'oklch(0.74 0.13 60 / 0.55)' : 'var(--line, rgba(255,255,255,0.18))'}`,
                  borderRadius: 4, cursor: 'pointer',
                  letterSpacing: '0.1em',
                  fontWeight: caseSensitive ? 700 : 400,
                }}>
                Aa
              </button>
              {query && (
                <span style={{
                  fontSize: 10, color: regexInvalid || matches.length === 0 ? 'oklch(0.55 0.18 25)' : 'var(--fg-mute, #777)',
                  fontFamily: 'var(--font-mono, monospace)',
                  fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap',
                }}>
                  {regexInvalid ? 'regex invalide' : matches.length === 0 ? '0 résultat' : `${currentMatch + 1} / ${matches.length}`}
                </span>
              )}
              {/* v82fc : toggle replace mode (visible seulement si onTextChange) */}
              {onTextChange && (
                <button type="button"
                  onClick={() => setReplaceMode((v) => !v)}
                  title={replaceMode ? 'Masquer le mode remplacer' : 'Afficher le mode remplacer'}
                  style={{
                    padding: '2px 8px', fontSize: 9,
                    fontFamily: 'var(--font-mono, monospace)',
                    background: replaceMode ? 'oklch(0.74 0.13 60 / 0.20)' : 'transparent',
                    color: replaceMode ? 'oklch(0.74 0.13 60)' : 'var(--fg-mute, #777)',
                    border: `1px ${replaceMode ? 'solid' : 'dashed'} ${replaceMode ? 'oklch(0.74 0.13 60 / 0.55)' : 'var(--line, rgba(255,255,255,0.18))'}`,
                    borderRadius: 4, cursor: 'pointer',
                    fontWeight: replaceMode ? 700 : 400,
                  }}>
                  ↻
                </button>
              )}
              {matches.length > 1 && (
                <>
                  <button type="button" onClick={goPrev} title="Précédent (Shift+Enter)"
                    style={{
                      padding: '2px 8px', fontSize: 11,
                      fontFamily: 'var(--font-mono, monospace)',
                      background: 'transparent', color: 'var(--fg, #f5f5f5)',
                      border: '1px solid var(--line, rgba(255,255,255,0.18))',
                      borderRadius: 4, cursor: 'pointer',
                    }}>↑</button>
                  <button type="button" onClick={goNext} title="Suivant (Enter)"
                    style={{
                      padding: '2px 8px', fontSize: 11,
                      fontFamily: 'var(--font-mono, monospace)',
                      background: 'transparent', color: 'var(--fg, #f5f5f5)',
                      border: '1px solid var(--line, rgba(255,255,255,0.18))',
                      borderRadius: 4, cursor: 'pointer',
                    }}>↓</button>
                </>
              )}
              {/* v82fi : revert vers originalText (visible seulement si
                  isEdited et onTextChange dispo). */}
              {onTextChange && isEdited && (
                <button type="button"
                  onClick={handleRevert}
                  title={`Annuler toutes les modifs et restaurer le contenu d'origine (${originalText?.length.toLocaleString('fr-FR')} car.). L'undo reste possible après.`}
                  style={{
                    padding: '4px 12px', fontSize: 11,
                    fontFamily: 'var(--font-mono, monospace)',
                    background: 'oklch(0.72 0.14 25 / 0.10)',
                    color: 'oklch(0.72 0.14 25)',
                    border: '1px solid oklch(0.72 0.14 25 / 0.45)',
                    borderRadius: 4, cursor: 'pointer',
                    fontWeight: 700,
                  }}>
                  ↺ revert
                </button>
              )}
              {/* v82ew : télécharger en .txt */}
              <button type="button"
                onClick={handleDownload}
                title={`Télécharger le contenu en ${name.replace(/\.[^.]+$/, '') || 'export'}.txt`}
                style={{
                  padding: '4px 12px', fontSize: 11,
                  fontFamily: 'var(--font-mono, monospace)',
                  background: 'transparent',
                  color: 'var(--fg, #f5f5f5)',
                  border: '1px solid var(--line, rgba(255,255,255,0.18))',
                  borderRadius: 4, cursor: 'pointer',
                }}>
                💾 .txt
              </button>
              {/* v82ev : copy-to-clipboard avec feedback temporaire */}
              <button type="button"
                onClick={handleCopy}
                title={copied ? 'Copié dans le presse-papiers' : 'Copier le texte intégral dans le presse-papiers'}
                style={{
                  padding: '4px 12px', fontSize: 11,
                  fontFamily: 'var(--font-mono, monospace)',
                  background: copied ? 'oklch(0.74 0.13 60 / 0.20)' : 'transparent',
                  color: copied ? 'oklch(0.74 0.13 60)' : 'var(--fg, #f5f5f5)',
                  border: `1px solid ${copied ? 'oklch(0.74 0.13 60 / 0.55)' : 'var(--line, rgba(255,255,255,0.18))'}`,
                  borderRadius: 4, cursor: 'pointer',
                  transition: 'all 0.18s',
                  fontWeight: copied ? 700 : 400,
                }}>
                {copied ? '✓ copié' : '📋 copier'}
              </button>
              <button type="button"
                onClick={() => setOpen(false)}
                title="Fermer (Esc)"
                style={{
                  padding: '4px 12px', fontSize: 11,
                  fontFamily: 'var(--font-mono, monospace)',
                  background: 'transparent', color: 'var(--fg, #f5f5f5)',
                  border: '1px solid var(--line, rgba(255,255,255,0.18))',
                  borderRadius: 4, cursor: 'pointer',
                }}>✕ fermer</button>
            </div>
            {/* v82fc : barre remplacer — rendue sous le header si
                onTextChange dispo et replaceMode activé. */}
            {/* v82fr : sections row — affiché si on détecte ≥ 2 sections
                concatenées (multi-files v82fk) et qu'on peut éditer. */}
            {onTextChange && sections.length >= 2 && (
              <div style={{
                padding: '8px 16px',
                borderBottom: '1px solid var(--line, rgba(255,255,255,0.10))',
                background: 'oklch(0.74 0.13 60 / 0.03)',
                display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap',
                fontFamily: 'var(--font-mono, monospace)', fontSize: 10,
              }}>
                <span style={{
                  color: 'oklch(0.74 0.13 60)',
                  letterSpacing: '0.14em', textTransform: 'uppercase',
                }}>
                  📑 {sections.length} sections
                </span>
                {sections.map((sec, i) => (
                  <span key={`${sec.name}-${i}`}
                    draggable
                    onDragStart={(e) => {
                      setDraggingSection(i)
                      e.dataTransfer.effectAllowed = 'move'
                      e.dataTransfer.setData('text/plain', String(i))
                    }}
                    onDragOver={(e) => {
                      if (draggingSection === null || draggingSection === i) return
                      e.preventDefault()
                      e.dataTransfer.dropEffect = 'move'
                    }}
                    onDrop={(e) => {
                      e.preventDefault()
                      e.stopPropagation()
                      const from = draggingSection
                      setDraggingSection(null)
                      if (from === null || from === i) return
                      handleReorderSection(from, i)
                    }}
                    onDragEnd={() => setDraggingSection(null)}
                    onDoubleClick={() => void handleCopySection(i)}
                    title={`${sec.name} · glisser pour réordonner · double-clic pour copier le contenu`}
                    style={{
                      display: 'inline-flex', alignItems: 'center', gap: 4,
                      padding: '2px 4px 2px 8px', borderRadius: 99,
                      background: copiedSectionIdx === i
                        ? 'oklch(0.74 0.13 60 / 0.30)'
                        : draggingSection === i
                          ? 'oklch(0.74 0.13 60 / 0.20)'
                          : 'oklch(0.74 0.13 60 / 0.08)',
                      border: `1px ${draggingSection === i ? 'dashed' : 'solid'} oklch(0.74 0.13 60 / ${copiedSectionIdx === i ? '0.65' : '0.45'})`,
                      color: copiedSectionIdx === i ? 'oklch(0.74 0.13 60)' : 'var(--fg, #f5f5f5)',
                      cursor: 'grab',
                      opacity: draggingSection !== null && draggingSection !== i ? 0.6 : 1,
                      fontWeight: copiedSectionIdx === i ? 700 : 400,
                      transition: 'background 120ms, opacity 120ms, color 120ms, border 120ms',
                    }}>
                    {/* drag handle visuel */}
                    <span style={{
                      color: 'var(--fg-mute, #777)', fontSize: 8,
                      letterSpacing: '-0.05em',
                    }}>⋮⋮</span>
                    <span style={{
                      maxWidth: 160, whiteSpace: 'nowrap', overflow: 'hidden',
                      textOverflow: 'ellipsis',
                    }}>{copiedSectionIdx === i
                      ? '✓ copié'
                      : (sec.name.length > 24 ? sec.name.slice(0, 22) + '…' : sec.name)
                    }</span>
                    {/* v82fu : rename section */}
                    <button type="button"
                      onClick={() => handleRenameSection(i)}
                      title={`Renommer la section "${sec.name}"`}
                      style={{
                        padding: '0 4px', fontSize: 9,
                        background: 'transparent', color: 'var(--fg-mute, #777)',
                        border: 'none', borderRadius: 99, cursor: 'pointer',
                        fontFamily: 'inherit',
                      }}>✎</button>
                    <button type="button"
                      onClick={() => handleDeleteSection(i)}
                      title={`Supprimer section "${sec.name}"`}
                      style={{
                        padding: '0 4px', fontSize: 10,
                        background: 'transparent', color: 'oklch(0.55 0.18 25)',
                        border: 'none', borderRadius: 99, cursor: 'pointer',
                        fontFamily: 'inherit',
                      }}>×</button>
                  </span>
                ))}
              </div>
            )}
            {onTextChange && replaceMode && (
              <div style={{
                padding: '8px 16px',
                borderBottom: '1px solid var(--line, rgba(255,255,255,0.10))',
                background: 'oklch(0.74 0.13 60 / 0.04)',
                display: 'flex', alignItems: 'center', gap: 8,
                fontFamily: 'var(--font-mono, monospace)', fontSize: 11,
              }}>
                <span style={{
                  color: 'oklch(0.74 0.13 60)',
                  letterSpacing: '0.14em', textTransform: 'uppercase',
                }}>
                  ↻ remplacer
                </span>
                <input
                  type="text"
                  value={replaceWith}
                  onChange={(e) => setReplaceWith(e.target.value)}
                  placeholder="par…"
                  style={{
                    padding: '4px 8px', fontSize: 11,
                    fontFamily: 'var(--font-mono, monospace)',
                    background: 'rgba(255,255,255,0.04)',
                    color: 'var(--fg, #f5f5f5)',
                    border: '1px solid var(--line, rgba(255,255,255,0.18))',
                    borderRadius: 4, minWidth: 160, outline: 'none',
                    flex: 1, maxWidth: 240,
                  }} />
                <button type="button"
                  onClick={handleReplaceCurrent}
                  disabled={matches.length === 0 || regexInvalid}
                  title="Remplacer la match courante"
                  style={{
                    padding: '4px 12px', fontSize: 11,
                    fontFamily: 'var(--font-mono, monospace)',
                    background: 'oklch(0.74 0.13 60 / 0.10)',
                    color: 'oklch(0.74 0.13 60)',
                    border: '1px solid oklch(0.74 0.13 60 / 0.40)',
                    borderRadius: 4, cursor: matches.length === 0 ? 'not-allowed' : 'pointer',
                    opacity: matches.length === 0 || regexInvalid ? 0.4 : 1,
                  }}>
                  remplacer
                </button>
                <button type="button"
                  onClick={handleReplaceAll}
                  disabled={matches.length === 0 || regexInvalid}
                  title={`Remplacer toutes les ${matches.length} occurrences`}
                  style={{
                    padding: '4px 12px', fontSize: 11,
                    fontFamily: 'var(--font-mono, monospace)',
                    background: 'oklch(0.74 0.13 60 / 0.20)',
                    color: 'oklch(0.74 0.13 60)',
                    border: '1px solid oklch(0.74 0.13 60 / 0.55)',
                    borderRadius: 4, cursor: matches.length === 0 ? 'not-allowed' : 'pointer',
                    opacity: matches.length === 0 || regexInvalid ? 0.4 : 1,
                    fontWeight: 700,
                  }}>
                  tout · {matches.length}
                </button>
                {/* v82fd : undo dernière replace (history stack cap 10) */}
                <button type="button"
                  onClick={handleUndo}
                  disabled={history.length === 0}
                  title={history.length === 0 ? 'Rien à annuler' : `Annuler dernière replace (${history.length} snapshot(s) en historique) · Ctrl+Z`}
                  style={{
                    padding: '4px 10px', fontSize: 11,
                    fontFamily: 'var(--font-mono, monospace)',
                    background: 'transparent',
                    color: history.length === 0 ? 'var(--fg-mute, #777)' : 'var(--fg, #f5f5f5)',
                    border: '1px solid var(--line, rgba(255,255,255,0.18))',
                    borderRadius: 4,
                    cursor: history.length === 0 ? 'not-allowed' : 'pointer',
                    opacity: history.length === 0 ? 0.4 : 1,
                  }}>
                  ↶ undo {history.length > 0 ? `(${history.length})` : ''}
                </button>
                {/* v82ff : redo (ré-applique un undo annulé) */}
                <button type="button"
                  onClick={handleRedo}
                  disabled={redoStack.length === 0}
                  title={redoStack.length === 0 ? 'Rien à refaire' : `Refaire (${redoStack.length} snapshot(s) en redo) · Ctrl+Shift+Z / Ctrl+Y`}
                  style={{
                    padding: '4px 10px', fontSize: 11,
                    fontFamily: 'var(--font-mono, monospace)',
                    background: 'transparent',
                    color: redoStack.length === 0 ? 'var(--fg-mute, #777)' : 'var(--fg, #f5f5f5)',
                    border: '1px solid var(--line, rgba(255,255,255,0.18))',
                    borderRadius: 4,
                    cursor: redoStack.length === 0 ? 'not-allowed' : 'pointer',
                    opacity: redoStack.length === 0 ? 0.4 : 1,
                  }}>
                  ↷ redo {redoStack.length > 0 ? `(${redoStack.length})` : ''}
                </button>
              </div>
            )}
            <pre style={{
              flex: 1, margin: 0, padding: '14px 18px',
              fontFamily: 'var(--font-mono, monospace)', fontSize: 12,
              lineHeight: 1.6, color: 'var(--fg, #f5f5f5)',
              whiteSpace: 'pre-wrap', wordBreak: 'break-word',
              overflowY: 'auto',
            }}>
              {/* v82ex/v82ey : split + wrap matches en <mark> avec
                  highlight spécial pour la match courante.
                  matches[].length variable en regex mode. */}
              {query && matches.length > 0 ? (() => {
                const out: ReactNode[] = []
                let cursor = 0
                matches.forEach(({ start, length }, idx) => {
                  if (start > cursor) out.push(<span key={`t${idx}`}>{text.slice(cursor, start)}</span>)
                  const isCurrent = idx === currentMatch
                  out.push(
                    <mark key={`m${idx}`}
                      ref={isCurrent ? (el) => el?.scrollIntoView({ block: 'center', behavior: 'smooth' }) : undefined}
                      style={{
                        background: isCurrent ? 'oklch(0.74 0.13 60 / 0.65)' : 'oklch(0.74 0.13 60 / 0.25)',
                        color: 'inherit',
                        padding: '0 2px', borderRadius: 2,
                        outline: isCurrent ? '1px solid oklch(0.74 0.13 60)' : 'none',
                      }}>
                      {text.slice(start, start + length)}
                    </mark>
                  )
                  cursor = start + length
                })
                if (cursor < text.length) out.push(<span key="tend">{text.slice(cursor)}</span>)
                return out
              })() : text}
            </pre>
          </div>
        </div>
      )}
    </>
  )
}
