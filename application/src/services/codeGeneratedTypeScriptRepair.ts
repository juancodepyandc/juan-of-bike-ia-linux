export function repairGeneratedTypeScriptContent(filename: string, content: string) {
  const normalized = filename.replace(/\\/g, '/').toLowerCase()
  if (!/\.[cm]?[jt]sx?$/.test(normalized)) return content

  let next = content

  // React 19 exposes a readonly ref overload when useRef<T>(null) is used with
  // non-nullable T. Generated R3F code frequently assigns to ref.current during
  // scene setup, so the ref must include null in its type parameter.
  next = next.replace(
    /\buseRef<((?:THREE\.)?(?:Mesh|Group|Object3D|InstancedMesh|PerspectiveCamera|OrthographicCamera|Camera|Scene|DirectionalLight|PointLight|SpotLight|AmbientLight|Line|Points|Sprite))>\(null\)/g,
    'useRef<$1 | null>(null)',
  )

  // Common Zustand shape emitted by local models: the store type only accepts a
  // concrete resources array, but components call setResources(prev => ...).
  next = next.replace(
    /setResources:\s*\(resources:\s*THREE\.Mesh\[\]\)\s*=>\s*void/g,
    'setResources: (resources: THREE.Mesh[] | ((prev: THREE.Mesh[]) => THREE.Mesh[])) => void',
  )
  next = next.replace(
    /setResources:\s*\(resources\)\s*=>\s*set\(\{\s*resources\s*\}\)/g,
    "setResources: (resources) => set((state) => ({ resources: typeof resources === 'function' ? resources(state.resources) : resources }))",
  )

  if (/\binterface\s+TableProps\s*<\s*TData\s*>/.test(next) || /\bconst\s+Table\s*=\s*<\s*TData\b/.test(next)) {
    next = next.replace(/\baccessorKey:\s*string\b/g, 'accessorKey?: keyof TData | string')
    next = next.replace(/key=\{column\.accessorKey\}/g, 'key={String(column.accessorKey || column.header)}')
    next = next.replace(
      /row\[column\.accessorKey\s+as\s+keyof\s+TData\]/g,
      '(column.accessorKey ? row[column.accessorKey as keyof TData] : undefined)',
    )
  }

  // Browser TS environments do not have NodeJS namespace for setInterval/setTimeout
  next = next.replace(/\bNodeJS\.(?:Timeout|Timer)\b/g, 'ReturnType<typeof setInterval>')

  // Clean unused date-fns imports when date-fns is not installed
  if (/import\s+\{[^}]*\}\s+from\s+['"]date-fns['"];?\s*\n?/.test(next) && !/\bformatDistance\b|\bparseISO\b|\bisAfter\b|\bisBefore\b/.test(next.replace(/import\s+\{[^}]*\}\s+from\s+['"]date-fns['"];?/, ''))) {
    next = next.replace(/import\s+\{[^}]*\}\s+from\s+['"]date-fns['"];?\s*\n?/, '')
  }

  // Permissive Date typing in serialized models (JSON ISO strings vs Date objects)
  next = next.replace(/\b(createdAt|updatedAt|dueDate)\s*:\s*Date\b/g, '$1: string | Date')
  next = next.replace(/\b(createdAt|updatedAt|dueDate)\s*\?\s*:\s*Date\b/g, '$1?: string | Date')

  // Task interface elasticity: local models often toggle between task.status and task.completed
  if (/\binterface\s+Task\b/.test(next)) {
    next = next.replace(/\binterface\s+Task\s*\{([\s\S]*?)\}/g, (m, body) => {
      let b = body
      if (!b.includes('completed')) b += '\n  completed?: boolean;'
      return `interface Task {${b}\n}`
    })
  }

  // Remove phantom mockData exports
  next = next.replace(/\bkanbanColumns:\s*typeof\s+mockKanbanColumns;?/g, 'kanbanColumns?: unknown[];')
  next = next.replace(/\bkanbanColumns:\s*mockKanbanColumns,?/g, 'kanbanColumns: [],')
  next = next.replace(/\bkanbanColumns:\s*}/g, 'kanbanColumns: []\n  }')
  next = next.replace(/,\s*mockKanbanColumns\b/g, '')
  next = next.replace(/\bmockKanbanColumns\s*,\s*/g, '')

  return next
}

