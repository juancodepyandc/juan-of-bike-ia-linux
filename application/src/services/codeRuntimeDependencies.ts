// Deterministic pins for the in-browser viewer only. Generated projects use
// the live registry resolver instead of copying this compatibility catalog.
export const CODE_THREE_CDN_VERSION = '0.183.2'
export const CODE_THREE_CDN_BASE = `https://cdn.jsdelivr.net/npm/three@${CODE_THREE_CDN_VERSION}`
export const CODE_THREE_ADDONS_BASE = `${CODE_THREE_CDN_BASE}/examples/jsm`

export const CODE_REACT_THREE_COMPATIBILITY = [
  '`three@^0.183.2`',
  '`@react-three/fiber@^9.5.0`',
  '`@react-three/drei@^10.7.7`',
  '`@react-three/postprocessing@^3.0.4`',
].join(', ')

export const CODE_BROWSER_RUNTIME_IMPORTS: Record<string, string> = {
  react: 'https://esm.sh/react@19.2.4',
  'react/jsx-runtime': 'https://esm.sh/react@19.2.4/jsx-runtime',
  'react-dom/client': 'https://esm.sh/react-dom@19.2.4/client',
}

export const CODE_BROWSER_RUNTIME_CANDIDATES: Record<string, string> = {
  'lucide-react': 'https://esm.sh/lucide-react@1.7.0?deps=react@19.2.4',
  'framer-motion': 'https://esm.sh/framer-motion@12.38.0?deps=react@19.2.4,react-dom@19.2.4',
  three: 'https://esm.sh/three@0.183.2',
  '@react-three/fiber': 'https://esm.sh/@react-three/fiber@9.5.0?deps=react@19.2.4,react-dom@19.2.4,three@0.183.2',
  '@react-three/drei': 'https://esm.sh/@react-three/drei@10.7.7?deps=react@19.2.4,react-dom@19.2.4,three@0.183.2',
  zustand: 'https://esm.sh/zustand@5.0.12?deps=react@19.2.4',
  vue: 'https://esm.sh/vue@3',
  svelte: 'https://esm.sh/svelte@5',
}
