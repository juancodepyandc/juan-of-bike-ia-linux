import { memo, useState } from 'react'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism'

type Props = {
  code: string
  language?: string
  showLineNumbers?: boolean
  search?: string
}

// Beyond this size, react-syntax-highlighter becomes a UI-freeze hazard
// (thousands of <span> per line × Prism tokenizer × re-render cost). We
// fall back to a plain <pre> and let the user opt in to full highlighting.
const SYNTAX_HIGHLIGHT_LIMIT = 50_000

function detectLanguageFromName(name: string): string {
  const lower = name.toLowerCase()
  if (lower.endsWith('.ts') || lower.endsWith('.tsx')) return 'typescript'
  if (lower.endsWith('.js') || lower.endsWith('.jsx') || lower.endsWith('.mjs') || lower.endsWith('.cjs')) return 'javascript'
  if (lower.endsWith('.py')) return 'python'
  if (lower.endsWith('.rs')) return 'rust'
  if (lower.endsWith('.go')) return 'go'
  if (lower.endsWith('.java')) return 'java'
  if (lower.endsWith('.kt') || lower.endsWith('.kts')) return 'kotlin'
  if (lower.endsWith('.rb')) return 'ruby'
  if (lower.endsWith('.php')) return 'php'
  if (lower.endsWith('.cs')) return 'csharp'
  if (lower.endsWith('.cpp') || lower.endsWith('.cc') || lower.endsWith('.cxx') || lower.endsWith('.hpp') || lower.endsWith('.h')) return 'cpp'
  if (lower.endsWith('.c')) return 'c'
  if (lower.endsWith('.swift')) return 'swift'
  if (lower.endsWith('.sh') || lower.endsWith('.bash') || lower.endsWith('.zsh')) return 'bash'
  if (lower.endsWith('.ps1')) return 'powershell'
  if (lower.endsWith('.sql')) return 'sql'
  if (lower.endsWith('.json')) return 'json'
  if (lower.endsWith('.yaml') || lower.endsWith('.yml')) return 'yaml'
  if (lower.endsWith('.toml')) return 'toml'
  if (lower.endsWith('.xml')) return 'xml'
  if (lower.endsWith('.html') || lower.endsWith('.htm')) return 'markup'
  if (lower.endsWith('.css') || lower.endsWith('.scss') || lower.endsWith('.sass') || lower.endsWith('.less')) return 'css'
  if (lower.endsWith('.md') || lower.endsWith('.markdown')) return 'markdown'
  if (lower.endsWith('.dockerfile') || lower === 'dockerfile' || lower.endsWith('/dockerfile')) return 'docker'
  if (lower.endsWith('.vue')) return 'markup'
  if (lower.endsWith('.svelte')) return 'markup'
  return 'text'
}

function CodeBlockBase({ code, language, showLineNumbers = true, search }: Props) {
  const detectedLanguage = language && language !== 'unknown' && language !== 'text'
    ? language
    : detectLanguageFromName(language ?? '')
  const searchNeedle = search && search.trim().length >= 2 ? search.trim().toLowerCase() : null
  const [forceHighlight, setForceHighlight] = useState(false)
  const isTooLarge = code.length > SYNTAX_HIGHLIGHT_LIMIT

  // Fallback for very large files: plain <pre> keeps the page responsive.
  // Highlighting 100K+ chars with Prism + rendering thousands of spans is
  // the #1 cause of "page crash vers la fin" on heavy projects.
  if (isTooLarge && !forceHighlight) {
    const sizeKb = Math.round(code.length / 1024)
    return (
      <div className="relative" style={{ fontSize: '13px', lineHeight: '1.55' }}>
        <div
          className="sticky top-0 z-10 flex items-center justify-between gap-3 px-4 py-2 text-[11px]"
          style={{
            background: 'rgba(250,189,64,0.12)',
            borderBottom: '1px solid rgba(250,189,64,0.35)',
            color: '#facc15',
          }}
        >
          <span>
            Fichier volumineux ({sizeKb} KB) — affichage brut pour éviter le gel de la page.
          </span>
          <button
            type="button"
            onClick={() => setForceHighlight(true)}
            className="rounded-md px-2 py-1 text-[10px] font-semibold"
            style={{
              background: 'rgba(250,189,64,0.22)',
              border: '1px solid rgba(250,189,64,0.5)',
              color: '#fde68a',
            }}
          >
            Forcer la coloration
          </button>
        </div>
        <pre
          style={{
            margin: 0,
            padding: '1.25rem',
            background: 'transparent',
            whiteSpace: 'pre',
            overflowX: 'auto',
            fontFamily: 'inherit',
            fontSize: '13px',
            lineHeight: '1.55',
            color: '#e2e8f0',
          }}
        >
          {code}
        </pre>
      </div>
    )
  }

  return (
    <SyntaxHighlighter
      language={detectedLanguage || 'text'}
      style={vscDarkPlus}
      showLineNumbers={showLineNumbers}
      wrapLines={Boolean(searchNeedle)}
      lineProps={(lineNumber: number) => {
        if (!searchNeedle) return { style: {} }
        const lines = code.split('\n')
        const current = lines[lineNumber - 1] ?? ''
        if (current.toLowerCase().includes(searchNeedle)) {
          return { style: { backgroundColor: 'rgba(250,189,64,0.14)' } }
        }
        return { style: {} }
      }}
      customStyle={{
        margin: 0,
        padding: '1.25rem',
        background: 'transparent',
        fontSize: '13px',
        lineHeight: '1.55',
      }}
      codeTagProps={{
        style: { fontFamily: 'inherit', fontSize: '13px' },
      }}
    >
      {code}
    </SyntaxHighlighter>
  )
}

export default memo(CodeBlockBase)
