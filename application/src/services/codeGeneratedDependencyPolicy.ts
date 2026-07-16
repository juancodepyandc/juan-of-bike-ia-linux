// Compatibility majors for generated projects. The sandbox registry resolver
// selects the current published release inside these ranges at install time.
const GENERATED_NODE_SPECS: Readonly<Record<string, string>> = Object.freeze({
  '@monaco-editor/react': '^4',
  '@react-spring/three': '^9',
  '@react-three/drei': '^10',
  '@react-three/fiber': '^9',
  '@react-three/postprocessing': '^3',
  '@types/react': '^19',
  '@types/react-dom': '^19',
  '@vitejs/plugin-react': '^6',
  autoprefixer: '^10',
  'framer-motion': '^12',
  'lucide-react': '^1',
  'monaco-editor': 'latest',
  postcss: '^8',
  react: '^19',
  'react-dom': '^19',
  'react-icons': '^5',
  'react-router-dom': '^7',
  tailwindcss: '^3',
  three: 'latest',
  typescript: '^6',
  vite: '^8',
  zustand: '^5',
})

export function getGeneratedNodeDependencySpec(packageName: string): string {
  return GENERATED_NODE_SPECS[packageName] ?? 'latest'
}

export function getLegacyReactThreeDependencySpec(packageName: string): string {
  if (packageName === '@react-three/fiber') return '^8'
  if (packageName === '@react-three/drei') return '^9'
  if (packageName === '@react-three/postprocessing') return '^2'
  return getGeneratedNodeDependencySpec(packageName)
}
