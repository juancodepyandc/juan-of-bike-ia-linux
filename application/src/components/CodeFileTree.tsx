import { memo, useCallback, useMemo, useState } from 'react'
import { ChevronDown, ChevronRight, File, FileCode2, Folder, FolderOpen } from 'lucide-react'

type CodeFile = {
  name: string
  language: string
  content: string
}

interface TreeNode {
  name: string
  path: string
  isDirectory: boolean
  children: TreeNode[]
  fileIndex?: number
}

function buildTree(files: CodeFile[]): TreeNode[] {
  const root: TreeNode[] = []

  for (let index = 0; index < files.length; index += 1) {
    const file = files[index]
    const parts = file.name.replace(/\\/g, '/').split('/')
    let currentLevel = root

    for (let depth = 0; depth < parts.length; depth += 1) {
      const part = parts[depth]
      const isFile = depth === parts.length - 1
      const path = parts.slice(0, depth + 1).join('/')

      let existing = currentLevel.find((node) => node.name === part && node.isDirectory === !isFile)
      if (!existing) {
        existing = {
          name: part,
          path,
          isDirectory: !isFile,
          children: [],
          fileIndex: isFile ? index : undefined,
        }
        currentLevel.push(existing)
      }

      if (!isFile) {
        currentLevel = existing.children
      }
    }
  }

  return sortTree(root)
}

function sortTree(nodes: TreeNode[]): TreeNode[] {
  return nodes
    .map((node) => ({
      ...node,
      children: node.isDirectory ? sortTree(node.children) : node.children,
    }))
    .sort((a, b) => {
      if (a.isDirectory && !b.isDirectory) return -1
      if (!a.isDirectory && b.isDirectory) return 1
      return a.name.localeCompare(b.name)
    })
}

function getFileIcon(name: string) {
  const ext = name.split('.').pop()?.toLowerCase()
  const codeExts = new Set(['ts', 'tsx', 'js', 'jsx', 'py', 'rs', 'go', 'java', 'c', 'cpp', 'cs', 'rb', 'php', 'swift', 'kt'])
  if (ext && codeExts.has(ext)) return FileCode2
  return File
}

function TreeNodeRow({
  node,
  depth,
  activeFileIndex,
  onSelect,
}: {
  node: TreeNode
  depth: number
  activeFileIndex: number
  onSelect: (index: number) => void
}) {
  const [expanded, setExpanded] = useState(true)
  const isActive = node.fileIndex === activeFileIndex
  const IconComponent = node.isDirectory
    ? (expanded ? FolderOpen : Folder)
    : getFileIcon(node.name)

  const handleClick = useCallback(() => {
    if (node.isDirectory) {
      setExpanded((prev) => !prev)
    } else if (node.fileIndex !== undefined) {
      onSelect(node.fileIndex)
    }
  }, [node, onSelect])

  return (
    <>
      <button
        onClick={handleClick}
        className={`w-full flex items-center gap-1.5 px-2 py-1.5 text-left transition-colors rounded-lg text-[12px] ${
          isActive
            ? 'bg-aurora-accent/15 text-aurora-accent-light'
            : 'text-aurora-text-muted hover:bg-white/[0.04] hover:text-aurora-text'
        }`}
        style={{ paddingLeft: `${depth * 14 + 8}px` }}
      >
        {node.isDirectory ? (
          expanded ? <ChevronDown size={12} className="shrink-0 text-aurora-text-dim" /> : <ChevronRight size={12} className="shrink-0 text-aurora-text-dim" />
        ) : (
          <span className="w-3 shrink-0" />
        )}
        <IconComponent size={14} className={`shrink-0 ${node.isDirectory ? 'text-aurora-yellow/70' : isActive ? 'text-aurora-accent-light' : 'text-aurora-text-dim'}`} />
        <span className="truncate">{node.name}</span>
      </button>
      {node.isDirectory && expanded && node.children.map((child) => (
        <TreeNodeRow
          key={child.path}
          node={child}
          depth={depth + 1}
          activeFileIndex={activeFileIndex}
          onSelect={onSelect}
        />
      ))}
    </>
  )
}

const CodeFileTree = memo(function CodeFileTree({
  files,
  activeFile,
  onSelectFile,
}: {
  files: CodeFile[]
  activeFile: number
  onSelectFile: (index: number) => void
}) {
  const tree = useMemo(() => buildTree(files), [files])

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
          onSelect={onSelectFile}
        />
      ))}
    </div>
  )
})

export default CodeFileTree
