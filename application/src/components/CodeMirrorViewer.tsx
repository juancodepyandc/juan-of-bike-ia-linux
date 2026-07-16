import { memo, useEffect, useMemo, useRef, type CSSProperties } from 'react'
import { EditorState, type Extension } from '@codemirror/state'
import { EditorView, lineNumbers } from '@codemirror/view'
import { javascript } from '@codemirror/lang-javascript'
import { html } from '@codemirror/lang-html'
import { css } from '@codemirror/lang-css'
import { List } from 'react-window'

type Props = {
  code: string
  language?: string
  showLineNumbers?: boolean
  search?: string
}

const VIRTUALIZED_LINE_LIMIT = 12_000
const VIRTUALIZED_CHAR_LIMIT = 700_000

function detectLanguageExtension(language?: string): Extension[] {
  const lower = (language || '').toLowerCase()
  if (/\.(tsx|jsx)$/.test(lower) || lower === 'tsx' || lower === 'jsx') {
    return [javascript({ typescript: lower.includes('tsx'), jsx: true })]
  }
  if (/\.(ts)$/.test(lower) || lower === 'ts' || lower === 'typescript') {
    return [javascript({ typescript: true })]
  }
  if (/\.(mjs|cjs|js)$/.test(lower) || lower === 'js' || lower === 'javascript') {
    return [javascript({ jsx: true })]
  }
  if (/\.(html|htm|vue|svelte)$/.test(lower) || lower === 'html' || lower === 'markup') return [html()]
  if (/\.(css|scss|sass|less)$/.test(lower) || lower === 'css') return [css()]
  if (/\.(json)$/.test(lower) || lower === 'json') return [javascript()]
  return []
}

const auroraTheme = EditorView.theme({
  '&': {
    minHeight: '28rem',
    background: '#091116',
    color: '#e2e8f0',
    fontSize: '13px',
  },
  '.cm-scroller': {
    fontFamily: 'ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace',
    lineHeight: '1.55',
  },
  '.cm-content': {
    padding: '1.25rem 0',
    caretColor: '#fbbf24',
  },
  '.cm-line': {
    padding: '0 1.25rem',
  },
  '.cm-gutters': {
    background: '#091116',
    borderRight: '1px solid rgba(148,163,184,.16)',
    color: 'rgba(148,163,184,.72)',
  },
  '.cm-activeLineGutter': {
    background: 'rgba(251,191,36,.08)',
  },
  '&.cm-focused': {
    outline: 'none',
  },
})

function CodeMirrorViewerBase({ code, language, showLineNumbers = true, search }: Props) {
  const lines = useMemo(() => code.split('\n'), [code])
  const useVirtualized = code.length > VIRTUALIZED_CHAR_LIMIT || lines.length > VIRTUALIZED_LINE_LIMIT

  if (useVirtualized) {
    return (
      <VirtualizedCodeViewer
        lines={lines}
        showLineNumbers={showLineNumbers}
        search={search}
      />
    )
  }

  return (
    <CodeMirrorReadOnly
      code={code}
      language={language}
      showLineNumbers={showLineNumbers}
    />
  )
}

function CodeMirrorReadOnly({
  code,
  language,
  showLineNumbers,
}: {
  code: string
  language?: string
  showLineNumbers: boolean
}) {
  const hostRef = useRef<HTMLDivElement>(null)
  const extensions = useMemo<Extension[]>(() => {
    const base: Extension[] = [
      auroraTheme,
      EditorView.lineWrapping,
      EditorView.editable.of(false),
      EditorState.readOnly.of(true),
    ]
    if (showLineNumbers) base.push(lineNumbers())
    base.push(...detectLanguageExtension(language))
    return base
  }, [language, showLineNumbers])

  useEffect(() => {
    const host = hostRef.current
    if (!host) return
    host.innerHTML = ''
    const view = new EditorView({
      parent: host,
      state: EditorState.create({ doc: code, extensions }),
    })
    return () => view.destroy()
  }, [code, extensions])

  return <div ref={hostRef} className="min-h-[28rem] bg-[#091116]" />
}

function VirtualizedCodeViewer({
  lines,
  showLineNumbers,
  search,
}: {
  lines: string[]
  showLineNumbers: boolean
  search?: string
}) {
  const searchNeedle = search && search.trim().length >= 2 ? search.trim().toLowerCase() : ''
  const rowProps = useMemo(
    () => ({ lines, showLineNumbers, searchNeedle }),
    [lines, showLineNumbers, searchNeedle],
  )
  const sizeKb = Math.round(lines.join('\n').length / 1024)

  return (
    <div className="bg-[#091116] text-[#e2e8f0]">
      <div className="sticky top-0 z-10 flex items-center justify-between gap-3 border-b border-aurora-border/25 bg-[#101820] px-4 py-2 text-[11px] text-aurora-yellow">
        <span>Fichier volumineux ({sizeKb} KB) - rendu virtualise</span>
        <span>{lines.length.toLocaleString('fr-FR')} lignes</span>
      </div>
      <List
        rowComponent={VirtualizedLine}
        rowCount={Math.max(1, lines.length)}
        rowHeight={22}
        rowProps={rowProps}
        overscanCount={24}
        defaultHeight={620}
        style={{ height: 'min(68vh, 760px)', minHeight: '28rem', width: '100%' }}
      />
    </div>
  )
}

function VirtualizedLine({
  index,
  style,
  lines,
  showLineNumbers,
  searchNeedle,
  ariaAttributes,
}: {
  index: number
  style: CSSProperties
  lines: string[]
  showLineNumbers: boolean
  searchNeedle: string
  ariaAttributes: { 'aria-posinset': number; 'aria-setsize': number; role: 'listitem' }
}) {
  const text = lines[index] ?? ''
  const match = searchNeedle && text.toLowerCase().includes(searchNeedle)
  return (
    <div
      {...ariaAttributes}
      style={{
        ...style,
        display: 'grid',
        gridTemplateColumns: showLineNumbers ? '4.5rem minmax(0, 1fr)' : 'minmax(0, 1fr)',
        gap: '0.75rem',
        padding: '0 1.25rem',
        fontFamily: 'ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace',
        fontSize: '13px',
        lineHeight: '22px',
        whiteSpace: 'pre',
        background: match ? 'rgba(250,189,64,.14)' : 'transparent',
      }}
    >
      {showLineNumbers && (
        <span style={{ color: 'rgba(148,163,184,.72)', textAlign: 'right', userSelect: 'none' }}>
          {index + 1}
        </span>
      )}
      <span style={{ overflow: 'visible' }}>{text || ' '}</span>
    </div>
  )
}

export default memo(CodeMirrorViewerBase)
