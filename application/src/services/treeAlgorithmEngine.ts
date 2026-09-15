// ---------------------------------------------------------------------------
// Tree Algorithm Engine — Self-Balancing Binary Search Tree Invariants
// ---------------------------------------------------------------------------

export type NodeColor = 'RED' | 'BLACK'

export interface RedBlackNode<T> {
  value: T
  color: NodeColor
  left: RedBlackNode<T> | null
  right: RedBlackNode<T> | null
  parent: RedBlackNode<T> | null
}

export class RedBlackTree<T> {
  root: RedBlackNode<T> | null = null
  private compare: (a: T, b: T) => number

  constructor(compareFn?: (a: T, b: T) => number) {
    this.compare = compareFn || ((a: any, b: any) => (a < b ? -1 : a > b ? 1 : 0))
  }

  insert(value: T): void {
    const newNode: RedBlackNode<T> = {
      value,
      color: 'RED',
      left: null,
      right: null,
      parent: null,
    }

    if (!this.root) {
      newNode.color = 'BLACK'
      this.root = newNode
      return
    }

    let current: RedBlackNode<T> | null = this.root
    let parent: RedBlackNode<T> | null = null

    while (current !== null) {
      parent = current
      const cmp = this.compare(value, current.value)
      if (cmp < 0) {
        current = current.left
      } else if (cmp > 0) {
        current = current.right
      } else {
        return // Duplicates ignored
      }
    }

    newNode.parent = parent
    if (this.compare(value, parent!.value) < 0) {
      parent!.left = newNode
    } else {
      parent!.right = newNode
    }

    this.fixInsert(newNode)
  }

  private rotateLeft(node: RedBlackNode<T>): void {
    const rightChild = node.right!
    node.right = rightChild.left
    if (rightChild.left) {
      rightChild.left.parent = node
    }
    rightChild.parent = node.parent
    if (!node.parent) {
      this.root = rightChild
    } else if (node === node.parent.left) {
      node.parent.left = rightChild
    } else {
      node.parent.right = rightChild
    }
    rightChild.left = node
    node.parent = rightChild
  }

  private rotateRight(node: RedBlackNode<T>): void {
    const leftChild = node.left!
    node.left = leftChild.right
    if (leftChild.right) {
      leftChild.right.parent = node
    }
    leftChild.parent = node.parent
    if (!node.parent) {
      this.root = leftChild
    } else if (node === node.parent.right) {
      node.parent.right = leftChild
    } else {
      node.parent.left = leftChild
    }
    leftChild.right = node
    node.parent = leftChild
  }

  private fixInsert(node: RedBlackNode<T>): void {
    let current = node
    while (current.parent && current.parent.color === 'RED') {
      const grandParent = current.parent.parent!
      if (current.parent === grandParent.left) {
        const uncle = grandParent.right
        if (uncle && uncle.color === 'RED') {
          current.parent.color = 'BLACK'
          uncle.color = 'BLACK'
          grandParent.color = 'RED'
          current = grandParent
        } else {
          if (current === current.parent.right) {
            current = current.parent
            this.rotateLeft(current)
          }
          current.parent!.color = 'BLACK'
          grandParent.color = 'RED'
          this.rotateRight(grandParent)
        }
      } else {
        const uncle = grandParent.left
        if (uncle && uncle.color === 'RED') {
          current.parent.color = 'BLACK'
          uncle.color = 'BLACK'
          grandParent.color = 'RED'
          current = grandParent
        } else {
          if (current === current.parent.left) {
            current = current.parent
            this.rotateRight(current)
          }
          current.parent!.color = 'BLACK'
          grandParent.color = 'RED'
          this.rotateLeft(grandParent)
        }
      }
    }
    this.root!.color = 'BLACK'
  }

  verifyRedBlackInvariants(): { valid: boolean; errors: string[] } {
    const errors: string[] = []
    if (!this.root) {
      return { valid: true, errors }
    }

    if (this.root.color !== 'BLACK') {
      errors.push('La racine doit etre NOIRE.')
    }

    // Invariant: pas de deux rouges consecutifs
    const checkRedChildren = (node: RedBlackNode<T> | null) => {
      if (!node) return
      if (node.color === 'RED') {
        if (node.left && node.left.color === 'RED') {
          errors.push(`Violation: noeud ROUGE ${node.value} a un enfant gauche ROUGE ${node.left.value}.`)
        }
        if (node.right && node.right.color === 'RED') {
          errors.push(`Violation: noeud ROUGE ${node.value} a un enfant droit ROUGE ${node.right.value}.`)
        }
      }
      checkRedChildren(node.left)
      checkRedChildren(node.right)
    }
    checkRedChildren(this.root)

    // Invariant: hauteur noire constante sur toutes les branches
    const computeBlackHeight = (node: RedBlackNode<T> | null): number => {
      if (!node) return 1
      const leftH = computeBlackHeight(node.left)
      const rightH = computeBlackHeight(node.right)
      if (leftH !== rightH) {
        errors.push(`Desequilibre hauteur noire au noeud ${node.value}: gauche=${leftH}, droite=${rightH}.`)
      }
      return (node.color === 'BLACK' ? 1 : 0) + Math.max(leftH, rightH)
    }
    computeBlackHeight(this.root)

    return {
      valid: errors.length === 0,
      errors,
    }
  }
}
