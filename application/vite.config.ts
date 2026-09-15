import { defineConfig, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { readFileSync, readdirSync, rmSync, statSync } from 'node:fs'
import { resolve } from 'node:path'
import { execSync } from 'node:child_process'

function readGitInfo(): { commit: string; branch: string; ts: string } {
  try {
    const commit = execSync('git rev-parse --short HEAD', { stdio: 'pipe' }).toString().trim()
    const branch = execSync('git rev-parse --abbrev-ref HEAD', { stdio: 'pipe' }).toString().trim()
    const ts = new Date().toISOString()
    return { commit, branch, ts }
  } catch {
    return { commit: 'unknown', branch: 'unknown', ts: new Date().toISOString() }
  }
}

function readTunnelHost(): string | null {
  try {
    // tunnel.txt is versioned and written by the Linux launcher. Keep the
    // old local-only filename as a migration fallback for existing installs.
    for (const filename of ['tunnel.txt', 'tunnel_url.txt']) {
      const p = resolve(__dirname, '..', filename)
      try {
        statSync(p)
        const raw = readFileSync(p, 'utf8').trim()
        if (!raw) continue
        const m = raw.match(/^https?:\/\/([^/\s]+)/i)
        if (m) return m[1]
      } catch {
        // Try the legacy filename before considering the tunnel unavailable.
      }
    }
    return null
  } catch {
    return null
  }
}

function pruneBundledPublicAssets(): Plugin {
  const keptAvatars = new Set(['aurora-default.vrm', 'natsu-dragneel.glb'])

  return {
    name: 'aurora-prune-bundled-public-assets',
    apply: 'build',
    closeBundle() {
      const distRoot = resolve(__dirname, 'dist')
      // `public/_pbr_test` n'existe plus : les 110 scripts proceduraux qui y
      // deposaient leur GLB ecrivent desormais sous
      // `application/output/3d/<projet>/`, comme l'exige aurora_output_paths.
      // Ce nettoyage devenait un no-op sur un dossier absent.

      const avatarsDir = resolve(distRoot, 'avatars')
      try {
        for (const entry of readdirSync(avatarsDir, { withFileTypes: true })) {
          if (!keptAvatars.has(entry.name)) {
            rmSync(resolve(avatarsDir, entry.name), { recursive: true, force: true })
          }
        }
      } catch {
        return
      }
    },
  }
}

function ensureFreshReactOptimizeDeps() {
  const viteDepsDir = resolve(__dirname, 'node_modules', '.vite', 'deps')
  const reactDomClientCache = resolve(viteDepsDir, 'react-dom_client.js')

  try {
    const reactPkg = JSON.parse(readFileSync(resolve(__dirname, 'node_modules', 'react', 'package.json'), 'utf8')) as { version?: string }
    const reactDomPkg = JSON.parse(readFileSync(resolve(__dirname, 'node_modules', 'react-dom', 'package.json'), 'utf8')) as { version?: string }
    const cachedClient = readFileSync(reactDomClientCache, 'utf8')
    const reactMajor = Number(String(reactPkg.version || '').split('.')[0])
    const reactDomMajor = Number(String(reactDomPkg.version || '').split('.')[0])
    const expectsReact19Elements = reactMajor >= 19 || reactDomMajor >= 19
    const cacheIsLegacyReactDom =
      cachedClient.includes('Symbol.for("react.element")') &&
      !cachedClient.includes('react.transitional.element')

    if (expectsReact19Elements && cacheIsLegacyReactDom) {
      console.warn('[aurora] cache Vite ReactDOM obsolete detecte, regeneration de node_modules/.vite/deps')
      rmSync(viteDepsDir, { recursive: true, force: true })
    }
  } catch {
    // No cache yet, or node_modules is being installed. Vite will rebuild normally.
  }
}

const GIT_INFO = readGitInfo()
const host = process.env.TAURI_DEV_HOST
const TUNNEL_HOST = process.env.AURORA_HMR_TUNNEL === 'true' ? readTunnelHost() : null

ensureFreshReactOptimizeDeps()

export default defineConfig(async () => ({
  plugins: [react(), tailwindcss(), pruneBundledPublicAssets()],
  clearScreen: false,
  resolve: {
    dedupe: ['react', 'react-dom'],
    alias: {
      react: resolve(__dirname, 'node_modules', 'react'),
      'react-dom': resolve(__dirname, 'node_modules', 'react-dom'),
    },
  },
  define: {
    __AURORA_COMMIT__: JSON.stringify(GIT_INFO.commit),
    __AURORA_BRANCH__: JSON.stringify(GIT_INFO.branch),
    __AURORA_BUILD_TS__: JSON.stringify(GIT_INFO.ts),
  },
  optimizeDeps: {
    entries: ['index.html'],
    include: [
      'three',
      '@react-three/fiber',
      '@react-three/drei',
      'three/examples/jsm/controls/OrbitControls.js',
      'three/examples/jsm/math/MeshSurfaceSampler.js',
      'three/examples/jsm/loaders/GLTFLoader.js',
      'three/examples/jsm/loaders/OBJLoader.js',
    ],
  },
  build: {
    chunkSizeWarningLimit: 900,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined
          if (id.includes('@react-three/fiber')) return 'r3f'
          if (id.includes('@react-three/drei')) return 'r3drei'
          if (id.includes('three/examples')) return 'three-extras'
          if (id.includes('\\three\\') || id.includes('/three/')) return 'three-core'
          if (id.includes('framer-motion')) return 'motion'
          if (id.includes('react-router') || id.includes('\\react\\') || id.includes('/react/')) return 'react'
          if (id.includes('zustand')) return 'state'
          if (id.includes('lucide-react')) return 'icons'
          return undefined
        },
      },
    },
  },
  server: {
    port: 1420,
    strictPort: true,
    allowedHosts: true,
    host: host || '0.0.0.0',
    hmr: host
      ? { protocol: 'ws', host, port: 1421, overlay: false }
      : TUNNEL_HOST
        ? { protocol: 'wss', host: TUNNEL_HOST, clientPort: 443, overlay: false }
        : { overlay: false },
    watch: {
      ignored: [
        '**/src-tauri/**',
        '**/node_modules/**',
        '**/.venv/**',
        '**/__pycache__/**',
        '**/logs/**',
        '**/.git/**',
        '**/.claude/**',
        '**/output/**',
        '**/cache/**',
        '**/public/generated/**',
        '**/*.glb',
        '**/*.obj',
        '**/*.fbx',
        '**/*.png',
        '**/*.jpg',
        '**/*.jpeg',
        '**/*.webp',
        '**/*.mp4',
        '**/*.webm',
        '**/*.wav',
        '**/*.safetensors',
      ],
    },
    warmup: {
      clientFiles: [
        './src/main.tsx',
        './src/App.tsx',
        './src/components/AuroraV1AppShell.tsx',
        './src/components/AuroraSphereV1.tsx',
        './src/components/AuroraAmbientField.tsx',
        './src/components/AuroraCommandPalette.tsx',
        './src/views/AuroraV1ChatView.tsx',
        './src/views/CodeView.tsx',
        './src/views/ModelView.tsx',
        './src/views/MangaVideoView.tsx',
        './src/views/MangaAcademyView.tsx',
        './src/views/VoiceCopilotView.tsx',
      ],
    },
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:3001',
        changeOrigin: true,
      },
      '/proxy': {
        target: 'http://127.0.0.1:3001',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://127.0.0.1:3001',
        ws: true,
        changeOrigin: true,
      },
    },
  },
  preview: {
    port: 1420,
    strictPort: true,
    host: '0.0.0.0',
    allowedHosts: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:3001',
        changeOrigin: true,
      },
      '/proxy': {
        target: 'http://127.0.0.1:3001',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://127.0.0.1:3001',
        ws: true,
        changeOrigin: true,
      },
    },
  },
}))
