import { memo, useMemo } from 'react'
import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { InlineMath, BlockMath } from 'react-katex'
import 'katex/dist/katex.min.css'
import { MarkdownImage } from './chat/MediaEmbed.tsx'
import { domainOf, isRichMedia } from '../utils/mediaLinks.ts'

type Props = {
  content: string
  idPrefix?: string
  className?: string
}

function slugifyHeading(value: string): string {
  return value
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 60) || 'section'
}

function renderChildrenWithMath(node: unknown, keyPrefix: string): React.ReactNode {
  if (Array.isArray(node)) {
    return node.map((child, index) => renderChildrenWithMath(child, `${keyPrefix}-${index}`))
  }
  if (typeof node !== 'string') return node as React.ReactNode
  const raw = node as string

  const blockRegex = /\$\$([\s\S]+?)\$\$/g
  const blockParts = raw.split(blockRegex)
  if (blockParts.length > 1) {
    return blockParts.map((part, blockIndex) => {
      if (blockIndex % 2 === 1) {
        return <BlockMath key={`${keyPrefix}-block-${blockIndex}`}>{part.trim()}</BlockMath>
      }
      return renderInlineMath(part, `${keyPrefix}-inline-${blockIndex}`)
    })
  }
  return renderInlineMath(raw, keyPrefix)
}

function renderInlineMath(source: string, keyPrefix: string): React.ReactNode {
  const inlineRegex = /\$([^$\n]+?)\$/g
  const parts = source.split(inlineRegex)
  if (parts.length === 1) return source
  return parts.map((part, index) =>
    index % 2 === 1 ? <InlineMath key={`${keyPrefix}-m-${index}`}>{part}</InlineMath> : part,
  )
}

function extractHeadingText(children: React.ReactNode): string {
  if (typeof children === 'string') return children
  if (Array.isArray(children)) return children.map(extractHeadingText).join('')
  if (children && typeof children === 'object' && 'props' in (children as object)) {
    const element = children as { props?: { children?: React.ReactNode } }
    return extractHeadingText(element.props?.children)
  }
  return ''
}

function MarkdownProBase({ content, idPrefix = 'md', className }: Props) {
  const components = useMemo<Components>(() => {
    const headingId = new Map<string, number>()
    const buildId = (raw: string): string => {
      const base = slugifyHeading(raw)
      const count = headingId.get(base) ?? 0
      headingId.set(base, count + 1)
      return count === 0 ? base : `${base}-${count}`
    }

    return {
      h1: ({ children }) => {
        const id = buildId(extractHeadingText(children))
        return (
          <h1 id={id} className="mt-6 mb-3 text-2xl font-semibold gradient-text">
            {renderChildrenWithMath(children, `${idPrefix}-h1`)}
          </h1>
        )
      },
      h2: ({ children }) => {
        const id = buildId(extractHeadingText(children))
        return (
          <h2 id={id} className="mt-6 mb-2 text-lg font-semibold text-aurora-text">
            {renderChildrenWithMath(children, `${idPrefix}-h2`)}
          </h2>
        )
      },
      h3: ({ children }) => {
        const id = buildId(extractHeadingText(children))
        return (
          <h3 id={id} className="mt-4 mb-1.5 text-base font-medium text-aurora-accent">
            {renderChildrenWithMath(children, `${idPrefix}-h3`)}
          </h3>
        )
      },
      h4: ({ children }) => (
        <h4 className="mt-3 mb-1 text-sm font-medium text-aurora-text">{renderChildrenWithMath(children, `${idPrefix}-h4`)}</h4>
      ),
      p: ({ children }) => (
        <p className="my-3 text-sm leading-relaxed text-aurora-text">{renderChildrenWithMath(children, `${idPrefix}-p`)}</p>
      ),
      ul: ({ children }) => <ul className="my-3 list-disc space-y-1 pl-6 text-sm text-aurora-text">{children}</ul>,
      ol: ({ children }) => <ol className="my-3 list-decimal space-y-1 pl-6 text-sm text-aurora-text">{children}</ol>,
      li: ({ children }) => (
        <li className="leading-relaxed text-aurora-text">{renderChildrenWithMath(children, `${idPrefix}-li`)}</li>
      ),
      blockquote: ({ children }) => (
        <blockquote className="my-3 rounded-xl border-l-2 border-aurora-accent bg-aurora-accent/5 px-4 py-2 text-sm italic text-aurora-text-dim">
          {children}
        </blockquote>
      ),
      code: ({ className: codeClass, children }) => {
        const inline = !codeClass
        if (inline) {
          return (
            <code className="rounded bg-aurora-surface-2 px-1.5 py-0.5 text-[0.85em] text-aurora-accent">
              {children}
            </code>
          )
        }
        return (
          <code className={`${codeClass} block overflow-x-auto rounded-xl bg-aurora-surface p-3 text-[12px]`}>
            {children}
          </code>
        )
      },
      pre: ({ children }) => (
        <pre className="my-3 overflow-x-auto rounded-xl bg-aurora-surface/90 border border-aurora-border/40">
          {children}
        </pre>
      ),
      table: ({ children }) => (
        <div className="my-3 overflow-x-auto rounded-xl border border-aurora-border/40">
          <table className="w-full border-collapse text-[13px]">{children}</table>
        </div>
      ),
      thead: ({ children }) => <thead className="bg-aurora-surface-2/60">{children}</thead>,
      tbody: ({ children }) => <tbody>{children}</tbody>,
      tr: ({ children }) => <tr className="border-b border-aurora-border/30 last:border-0">{children}</tr>,
      th: ({ children }) => (
        <th className="px-3 py-2 text-left font-medium text-aurora-text">{renderChildrenWithMath(children, `${idPrefix}-th`)}</th>
      ),
      td: ({ children }) => (
        <td className="px-3 py-2 text-aurora-text-dim">{renderChildrenWithMath(children, `${idPrefix}-td`)}</td>
      ),
      // Une image du markdown se regarde : cliquer l'ouvre en plein écran.
      // Avant, elle sortait en <img> brut, sans taille ni bordure, et
      // débordait de la bulle.
      img: ({ src, alt }) => (
        <MarkdownImage src={typeof src === 'string' ? src : undefined} alt={alt} />
      ),
      a: ({ children, href }) => {
        const url = typeof href === 'string' ? href : ''
        // Un lien dont le texte EST l'URL et qui pointe vers un média est
        // remplacé par son domaine : la carte lisible correspondante est
        // rendue sous la bulle par MediaStrip. Afficher les deux ferait
        // doublon, n'afficher que l'URL nue ne dirait rien.
        const bare = typeof children === 'string' && children === url
        const label = bare && isRichMedia(url) ? (domainOf(url) || url) : children
        return (
          <a href={href} target="_blank" rel="noreferrer" className="text-aurora-accent hover:underline">
            {label}
          </a>
        )
      },
      hr: () => <hr className="my-4 border-t border-aurora-border/40" />,
      input: ({ checked, disabled }) => (
        <input type="checkbox" checked={Boolean(checked)} disabled={disabled} readOnly className="mr-2 align-middle accent-aurora-accent" />
      ),
    }
  }, [idPrefix])

  return (
    <div className={className}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {content}
      </ReactMarkdown>
    </div>
  )
}

export default memo(MarkdownProBase)
