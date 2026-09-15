import { memo, useCallback, useMemo, useState } from 'react'
import { ChevronDown, ChevronRight, File, FileCode2, Folder, FolderOpen } from 'lucide-react'
import {
  buildCodeFileTree,
  formatCodeFileSize,
  type CodeFileTreeNode,
} from '../services/codeFileTreeModel.ts'

type CodeFile = {
  name: string
  language: string
  content: string
}

// L'ARBRE est calcule par `services/codeFileTreeModel.ts` (pur, teste sur un
// vrai projet genere de 33 fichiers). Ce fichier ne fait que le peindre — il
// n'existe qu'UNE implementation d'arborescence dans le module.

const CODE_EXTENSIONS = new Set([
  'ts', 'tsx', 'js', 'jsx', 'mjs', 'cjs', 'py', 'rs', 'go', 'java',
  'c', 'cpp', 'cs', 'rb', 'php', 'swift', 'kt', 'vue', 'svelte', 'sh',
])

function getFileIcon(node: CodeFileTreeNode) {
  return CODE_EXTENSIONS.has(node.extension) ? FileCode2 : File
}

function TreeNodeRow({
  node,
  depth,
  activeFileIndex,
  collapsed,
  onToggle,
  onSelect,
  showSize,
}: {
  node: CodeFileTreeNode
  depth: number
  activeFileIndex: number
  collapsed: ReadonlySet<string>
  onToggle: (path: string) => void
  onSelect: (index: number) => void
  showSize: boolean
}) {
  const expanded = node.isDirectory && !collapsed.has(node.path)
  const isActive = node.fileIndex !== undefined && node.fileIndex === activeFileIndex
  const IconComponent = node.isDirectory
    ? (expanded ? FolderOpen : Folder)
    : getFileIcon(node)

  const handleClick = useCallback(() => {
    if (node.isDirectory) onToggle(node.path)
    else if (node.fileIndex !== undefined) onSelect(node.fileIndex)
  }, [node, onToggle, onSelect])

  return (
    <>
      <button
        onClick={handleClick}
        title={showSize ? `${node.path} — ${formatCodeFileSize(node.size)}` : node.path}
        className={`w-full flex items-center gap-1.5 px-2 py-1.5 text-left transition-colors rounded-lg text-[12px] ${
          isActive
            ? 'bg-aurora-accent/15 text-aurora-accent-light'
            : 'text-aurora-text-muted hover:bg-white/[0.04] hover:text-aurora-text'
        }`}
        style={{ paddingLeft: `${depth * 14 + 8}px` }}
      >
        {node.isDirectory ? (
          expanded
            ? <ChevronDown size={12} className="shrink-0 text-aurora-text-dim" />
            : <ChevronRight size={12} className="shrink-0 text-aurora-text-dim" />
        ) : (
          <span className="w-3 shrink-0" />
        )}
        <IconComponent
          size={14}
          className={`shrink-0 ${node.isDirectory ? 'text-aurora-yellow/70' : isActive ? 'text-aurora-accent-light' : 'text-aurora-text-dim'}`}
        />
        <span className="truncate">{node.name}</span>
        {showSize && (
          <span className="ml-auto shrink-0 pl-2 font-mono text-[9.5px] tabular-nums text-aurora-text-dim/80">
            {formatCodeFileSize(node.size)}
          </span>
        )}
      </button>
      {node.isDirectory && expanded && node.children.map((child) => (
        <TreeNodeRow
          key={child.path}
          node={child}
          depth={depth + 1}
          activeFileIndex={activeFileIndex}
          collapsed={collapsed}
          onToggle={onToggle}
          onSelect={onSelect}
          showSize={showSize}
        />
      ))}
    </>
  )
}

const CodeFileTree = memo(function CodeFileTree({
  files,
  activeFile,
  onSelectFile,
  showSize = false,
  collapsedPaths,
  onToggleDirectory,
}: {
  files: CodeFile[]
  activeFile: number
  onSelectFile: (index: number) => void
  /** Affiche la taille de chaque fichier/dossier a droite de la ligne. */
  showSize?: boolean
  /** Mode controle: dossiers replies pilotes par le parent (plein ecran). */
  collapsedPaths?: ReadonlySet<string>
  onToggleDirectory?: (path: string) => void
}) {
  const tree = useMemo(() => buildCodeFileTree(files), [files])
  const [ownCollapsed, setOwnCollapsed] = useState<ReadonlySet<string>>(() => new Set())

  const collapsed = collapsedPaths ?? ownCollapsed
  const handleToggle = useCallback((path: string) => {
    if (onToggleDirectory) {
      onToggleDirectory(path)
      return
    }
    setOwnCollapsed((previous) => {
      const next = new Set(previous)
      if (next.has(path)) next.delete(path)
      else next.add(path)
      return next
    })
  }, [onToggleDirectory])

  if (files.length === 0) {
    return (
      <div className="grid h-[14rem] place-items-center rounded-[1.4rem] border border-dashed border-aurora-border/40 bg-aurora-bg/35 text-center">
        <div>
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl border border-aurora-border/35 bg-aurora-surface-2">
            <Folder size={22} className="text-aurora-text-dim" />
          </div>
          <p className="mt-3 px-4 text-xs text-aurora-text-dim">
            Les fichiers livres apparaitront ici avec leur arborescence.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-0.5 overflow-y-auto max-h-full pr-1">
      {tree.map((node) => (
        <TreeNodeRow
          key={node.path}
          node={node}
          depth={0}
          activeFileIndex={activeFile}
          collapsed={collapsed}
          onToggle={handleToggle}
          onSelect={onSelectFile}
          showSize={showSize}
        />
      ))}
    </div>
  )
})

export default CodeFileTree
