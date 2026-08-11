// ---------------------------------------------------------------------------
// Modele d'arborescence projet — PUR (aucun React, aucun DOM, aucune I/O).
//
// Extrait de `components/CodeFileTree.tsx` ou il vivait en dur, pour que le
// panneau de livraison ET le viewer plein ecran partagent EXACTEMENT le meme
// calcul d'arbre. Une seule source de verite: pas de deuxieme systeme parallele.
//
// Note sur `size`: on mesure `content.length` (unites UTF-16), comme le fait
// deja `codeProjectTree.ts`. C'est une approximation d'octets, volontairement
// pas un TextEncoder (cout O(n) sur chaque fichier a chaque rendu).
// ---------------------------------------------------------------------------

export type CodeFileTreeInput = {
  name: string
  content: string
}

export type CodeFileTreeNode = {
  /** Dernier segment du chemin — ce qu'on affiche dans la ligne. */
  name: string
  /** Chemin normalise complet depuis la racine du projet. Cle React stable. */
  path: string
  isDirectory: boolean
  children: CodeFileTreeNode[]
  /** Index dans le tableau `files` d'origine. Absent pour un dossier. */
  fileIndex?: number
  /** Taille du fichier, ou somme des tailles descendantes pour un dossier. */
  size: number
  /** Extension en minuscules sans le point. '' pour un dossier ou `Dockerfile`. */
  extension: string
}

type DraftNode = {
  name: string
  path: string
  isDirectory: boolean
  order: DraftNode[]
  index: Map<string, DraftNode>
  fileIndex?: number
  size: number
}

/**
 * Decoupe un chemin de fichier en segments affichables.
 * - `\` de Windows ramenes sur `/`
 * - segments vides et `.` ignores (gere `a//b`, `./a`, `/a`, `a/`)
 * - `..` remonte reellement d'un cran (jamais de segment `..` affiche)
 * - un chemin qui ne produit aucun segment recoit un nom de repli: un fichier
 *   sans nom exploitable reste VISIBLE au lieu de disparaitre en silence.
 */
export function splitProjectPath(rawPath: string, fallbackIndex: number): string[] {
  const parts: string[] = []
  for (const segment of String(rawPath ?? '').replace(/\\/g, '/').split('/')) {
    const trimmed = segment.trim()
    if (!trimmed || trimmed === '.') continue
    if (trimmed === '..') {
      parts.pop()
      continue
    }
    parts.push(trimmed)
  }
  if (parts.length === 0) return [`fichier-${fallbackIndex + 1}`]
  return parts
}

/** Extension en minuscules sans le point. '' si absente ou si le nom commence par un point. */
export function fileExtensionOf(name: string): string {
  const dotIndex = name.lastIndexOf('.')
  if (dotIndex <= 0 || dotIndex === name.length - 1) return ''
  return name.slice(dotIndex + 1).toLowerCase()
}

function compareNodes(a: DraftNode, b: DraftNode): number {
  // Dossiers d'abord, puis ordre alphabetique numerique-aware (file2 < file10).
  if (a.isDirectory !== b.isDirectory) return a.isDirectory ? -1 : 1
  return a.name.localeCompare(b.name, 'en', { numeric: true })
}

function childKey(name: string, isDirectory: boolean): string {
  return `${isDirectory ? 'd' : 'f'}:${name}`
}

function attachChild(parent: DraftNode | null, roots: DraftNode[], rootIndex: Map<string, DraftNode>, node: DraftNode) {
  if (parent) {
    parent.order.push(node)
    parent.index.set(childKey(node.name, node.isDirectory), node)
    return
  }
  roots.push(node)
  rootIndex.set(childKey(node.name, node.isDirectory), node)
}

function finalize(drafts: DraftNode[]): CodeFileTreeNode[] {
  const sorted = [...drafts].sort(compareNodes)
  return sorted.map((draft) => {
    const children = draft.isDirectory ? finalize(draft.order) : []
    let size = draft.size
    for (const child of children) size += child.size
    return {
      name: draft.name,
      path: draft.path,
      isDirectory: draft.isDirectory,
      children,
      fileIndex: draft.fileIndex,
      size,
      extension: draft.isDirectory ? '' : fileExtensionOf(draft.name),
    }
  })
}

/**
 * Construit l'arbre affichable a partir d'une liste plate de fichiers.
 *
 * Garanties (couvertes par codeFileTreeModel.test.ts):
 *  - imbrication: `src/pages/HomePage.tsx` cree `src` > `pages` > `HomePage.tsx`
 *  - tri: dossiers avant fichiers, puis alphabetique numerique-aware
 *  - deduplication: un meme chemin livre deux fois ne produit qu'un noeud,
 *    pointant sur la PREMIERE occurrence, et n'est compte qu'une fois en taille
 *  - un fichier et un dossier homonymes cohabitent (`docs` + `docs/a.md`)
 *  - taille d'un dossier = somme de ses descendants
 */
export function buildCodeFileTree(files: readonly CodeFileTreeInput[]): CodeFileTreeNode[] {
  const roots: DraftNode[] = []
  const rootIndex = new Map<string, DraftNode>()

  for (let fileIndex = 0; fileIndex < files.length; fileIndex += 1) {
    const file = files[fileIndex]
    const parts = splitProjectPath(file?.name ?? '', fileIndex)
    let parent: DraftNode | null = null

    for (let depth = 0; depth < parts.length; depth += 1) {
      const name = parts[depth]
      const isDirectory = depth < parts.length - 1
      const path = parts.slice(0, depth + 1).join('/')
      const lookup: Map<string, DraftNode> = parent ? parent.index : rootIndex
      const existing: DraftNode | undefined = lookup.get(childKey(name, isDirectory))

      if (existing) {
        // Doublon exact: la premiere occurrence garde la main (index et taille).
        if (!isDirectory) break
        parent = existing
        continue
      }

      const node: DraftNode = {
        name,
        path,
        isDirectory,
        order: [],
        index: new Map(),
        fileIndex: isDirectory ? undefined : fileIndex,
        size: isDirectory ? 0 : (file?.content?.length ?? 0),
      }
      attachChild(parent, roots, rootIndex, node)
      if (!isDirectory) break
      parent = node
    }
  }

  return finalize(roots)
}

/** Tous les chemins de dossiers, en profondeur d'abord — pour un "tout replier". */
export function collectDirectoryPaths(nodes: readonly CodeFileTreeNode[]): string[] {
  const paths: string[] = []
  const walk = (list: readonly CodeFileTreeNode[]) => {
    for (const node of list) {
      if (!node.isDirectory) continue
      paths.push(node.path)
      walk(node.children)
    }
  }
  walk(nodes)
  return paths
}

/** Nombre de fichiers reellement presents dans l'arbre (doublons deja fusionnes). */
export function countTreeFiles(nodes: readonly CodeFileTreeNode[]): number {
  let total = 0
  for (const node of nodes) {
    if (node.isDirectory) total += countTreeFiles(node.children)
    else total += 1
  }
  return total
}

/** Taille lisible, en francais: 512 o / 4,6 Ko / 1,2 Mo. */
export function formatCodeFileSize(size: number): string {
  if (!Number.isFinite(size) || size < 0) return '0 o'
  if (size < 1024) return `${Math.round(size)} o`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1).replace('.', ',')} Ko`
  return `${(size / (1024 * 1024)).toFixed(1).replace('.', ',')} Mo`
}
