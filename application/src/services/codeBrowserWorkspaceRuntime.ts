export type BrowserRuntimeFile = {
  name: string
  language?: string
  content: string
}

export type BrowserWorkspaceEntry = {
  path: string
  synthetic: boolean
  content?: string
  reason: 'main_entry' | 'app_component'
}

const ENTRY_CANDIDATES = [
  'src/main.tsx',
  'src/main.jsx',
  'src/main.ts',
  'src/main.js',
  'main.tsx',
  'main.jsx',
  'main.ts',
  'main.js',
]

const APP_FALLBACKS = [
  'src/App.tsx',
  'src/App.jsx',
  'src/App.ts',
  'src/App.js',
  'App.tsx',
  'App.jsx',
  'App.ts',
  'App.js',
]

const RUNTIME_EXTENSIONS = /\.(tsx|ts|jsx|js|mjs|css|json|svg)$/i
const HTML_EXTENSIONS = /\.(html|htm)$/i

export function normalizeRuntimePath(input: string): string {
  const normalized = input.replace(/\\/g, '/').replace(/^\.?\//, '')
  const parts: string[] = []
  for (const part of normalized.split('/')) {
    if (!part || part === '.') continue
    if (part === '..') {
      parts.pop()
      continue
    }
    parts.push(part)
  }
  return parts.join('/')
}

export function detectBrowserWorkspaceEntry(files: BrowserRuntimeFile[]): BrowserWorkspaceEntry | null {
  const byPath = buildRuntimeFileMap(files)

  for (const candidate of ENTRY_CANDIDATES) {
    if (byPath.has(candidate)) {
      return { path: candidate, synthetic: false, reason: 'main_entry' }
    }
  }

  for (const candidate of APP_FALLBACKS) {
    if (!byPath.has(candidate)) continue
    const importPath = candidate.startsWith('src/') ? `./${candidate.replace(/\.[^.]+$/, '')}` : `./${candidate.replace(/\.[^.]+$/, '')}`
    const content = [
      "import React from 'react'",
      "import { createRoot } from 'react-dom/client'",
      `import App from ${JSON.stringify(importPath)}`,
      '',
      "const rootEl = document.getElementById('root')",
      "if (!rootEl) throw new Error('Aurora runtime: #root introuvable')",
      'createRoot(rootEl).render(<App />)',
      '',
    ].join('\n')
    return {
      path: 'aurora-entry.tsx',
      synthetic: true,
      content,
      reason: 'app_component',
    }
  }

  return null
}

export function supportsBrowserWorkspaceRuntime(files: BrowserRuntimeFile[]): boolean {
  if (files.some((file) => HTML_EXTENSIONS.test(file.name))) return false
  const entry = detectBrowserWorkspaceEntry(files)
  if (!entry) return false

  const relevant = files
    .filter((file) => RUNTIME_EXTENSIONS.test(file.name))
    .map((file) => file.content)
    .join('\n')

  if (/\.(tsx|jsx)$/i.test(entry.path) || files.some((file) => /\.(tsx|jsx)$/i.test(file.name))) return true
  if (/\bfrom\s+['"](?:react|react-dom\/client|vue|svelte)/.test(relevant)) return true
  if (/\b(createRoot|ReactDOM\.render|createApp|new\s+Vue)\b/.test(relevant)) return true
  if (files.some((file) => /\bimport\s+.+\s+from\s+['"]\.{1,2}\//.test(file.content))) return true
  return false
}

export function buildBrowserWorkspacePreviewHtml(files: BrowserRuntimeFile[]): string | null {
  const entry = detectBrowserWorkspaceEntry(files)
  if (!entry || !supportsBrowserWorkspaceRuntime(files)) return null

  const runtimeFiles = buildRuntimeFileMap(files)
  if (entry.synthetic && entry.content) runtimeFiles.set(entry.path, entry.content)

  const payload = {
    files: Object.fromEntries(runtimeFiles.entries()),
    entryPath: `/${entry.path}`,
    entryReason: entry.reason,
  }

  const importMap = buildImportMap(files)
  const workerSource = buildWorkerSource()
  const payloadJson = safeJsonForInlineScript(payload)
  const importMapJson = safeJsonForInlineScript(importMap)
  const workerLiteral = safeJsString(workerSource)

  return `<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Aurora browser workspace</title>
  <script type="importmap">${importMapJson}</script>
  <style>
    html,body,#root{margin:0;min-height:100%;width:100%}
    body{font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#0d1117;color:#e6edf3}
    #root{min-height:100vh}
    #aurora-runtime-status{position:fixed;left:12px;bottom:12px;z-index:2147483647;max-width:min(420px,calc(100vw - 24px));border:1px solid rgba(148,163,184,.28);border-radius:10px;background:rgba(2,6,23,.86);color:#cbd5e1;padding:8px 10px;font:12px/1.45 ui-monospace,SFMono-Regular,Menlo,monospace;box-shadow:0 18px 48px rgba(0,0,0,.35);backdrop-filter:blur(12px)}
    #aurora-runtime-status[data-state="ready"]{opacity:.18}
    #aurora-runtime-status[data-state="error"]{border-color:rgba(248,113,113,.65);color:#fecaca;opacity:1}
  </style>
</head>
<body>
  <div id="root"></div>
  <div id="aurora-runtime-status" data-state="building">Compilation in-browser...</div>
  <script type="module">
    const auroraPayload = ${payloadJson};
    const auroraWorkerSource = ${workerLiteral};
    const statusEl = document.getElementById('aurora-runtime-status');
    const startedAt = performance.now();
    const send = (type, payload = {}) => {
      window.parent?.postMessage({ source: 'aurora-code-runtime', type, ...payload }, '*');
    };
    const setStatus = (state, text) => {
      if (!statusEl) return;
      statusEl.dataset.state = state;
      statusEl.textContent = text;
    };
    for (const level of ['log', 'info', 'warn', 'error']) {
      const original = console[level].bind(console);
      console[level] = (...args) => {
        send('console', { level, message: args.map(String).join(' ') });
        original(...args);
      };
    }
    window.addEventListener('error', (event) => {
      setStatus('error', event.message || 'Runtime error');
      send('error', { message: event.message, stack: event.error?.stack || null });
    });
    window.addEventListener('unhandledrejection', (event) => {
      const reason = event.reason instanceof Error ? event.reason : new Error(String(event.reason));
      setStatus('error', reason.message || 'Unhandled rejection');
      send('error', { message: reason.message, stack: reason.stack || null });
    });
    const workerUrl = URL.createObjectURL(new Blob([auroraWorkerSource], { type: 'text/javascript' }));
    const worker = new Worker(workerUrl, { type: 'module', name: 'aurora-code-esbuild' });
    worker.onmessage = async (event) => {
      const data = event.data || {};
      if (data.type === 'log') {
        setStatus('building', data.message || 'Compilation...');
        return;
      }
      if (data.type === 'error') {
        setStatus('error', data.message || 'Compilation failed');
        send('error', { message: data.message || 'Compilation failed', stack: data.stack || null });
        return;
      }
      if (data.type !== 'bundle') return;
      try {
        setStatus('building', 'Execution du bundle...');
        const moduleUrl = URL.createObjectURL(new Blob([data.code], { type: 'text/javascript' }));
        await import(moduleUrl);
        const durationMs = Math.round(performance.now() - startedAt);
        setStatus('ready', 'Bundle actif');
        send('perf', { metric: 'browser_workspace_ready_ms', value: durationMs, buildMs: data.durationMs, warnings: data.warnings || [] });
        setTimeout(() => URL.revokeObjectURL(moduleUrl), 1000);
      } catch (error) {
        setStatus('error', error?.message || String(error));
        send('error', { message: error?.message || String(error), stack: error?.stack || null });
      }
    };
    worker.onerror = (event) => {
      setStatus('error', event.message || 'Worker error');
      send('error', { message: event.message || 'Worker error' });
    };
    worker.postMessage({ type: 'build', ...auroraPayload });
  </script>
</body>
</html>`
}

function buildRuntimeFileMap(files: BrowserRuntimeFile[]): Map<string, string> {
  const out = new Map<string, string>()
  for (const file of files) {
    const path = normalizeRuntimePath(file.name)
    if (!path || !RUNTIME_EXTENSIONS.test(path)) continue
    out.set(path, file.content)
  }
  return out
}

function buildImportMap(files: BrowserRuntimeFile[]) {
  const source = files.map((file) => file.content).join('\n')
  const imports: Record<string, string> = {
    react: 'https://esm.sh/react@19.2.4',
    'react/jsx-runtime': 'https://esm.sh/react@19.2.4/jsx-runtime',
    'react-dom/client': 'https://esm.sh/react-dom@19.2.4/client',
  }
  const candidates: Record<string, string> = {
    'lucide-react': 'https://esm.sh/lucide-react@1.7.0?deps=react@19.2.4',
    'framer-motion': 'https://esm.sh/framer-motion@12.38.0?deps=react@19.2.4,react-dom@19.2.4',
    three: 'https://esm.sh/three@0.183.2',
    '@react-three/fiber': 'https://esm.sh/@react-three/fiber@9.5.0?deps=react@19.2.4,react-dom@19.2.4,three@0.183.2',
    '@react-three/drei': 'https://esm.sh/@react-three/drei@10.7.7?deps=react@19.2.4,react-dom@19.2.4,three@0.183.2',
    zustand: 'https://esm.sh/zustand@5.0.12?deps=react@19.2.4',
    vue: 'https://esm.sh/vue@3',
    svelte: 'https://esm.sh/svelte@5',
  }
  for (const [name, url] of Object.entries(candidates)) {
    if (new RegExp(`['"]${escapeRegex(name)}(?:/[^'"]*)?['"]`).test(source)) imports[name] = url
  }
  return { imports }
}

function buildWorkerSource(): string {
  return `
import * as esbuild from 'https://esm.sh/esbuild-wasm@0.28.1/esm/browser'

const CDN_WASM = 'https://cdn.jsdelivr.net/npm/esbuild-wasm@0.28.1/esbuild.wasm'
const EXTENSIONS = ['', '.tsx', '.ts', '.jsx', '.js', '.mjs', '.css', '.json', '.svg']
let initialized = null

function normalize(input) {
  const absolute = input.startsWith('/') ? input : '/' + input
  const parts = []
  for (const part of absolute.replace(/\\\\/g, '/').split('/')) {
    if (!part || part === '.') continue
    if (part === '..') parts.pop()
    else parts.push(part)
  }
  return '/' + parts.join('/')
}

function dirname(path) {
  const clean = normalize(path)
  const slash = clean.lastIndexOf('/')
  return slash <= 0 ? '/' : clean.slice(0, slash)
}

function isBareSpecifier(path) {
  return !path.startsWith('.') && !path.startsWith('/') && !path.startsWith('@/')
}

function loaderFor(path) {
  if (/\\.tsx$/i.test(path)) return 'tsx'
  if (/\\.ts$/i.test(path)) return 'ts'
  if (/\\.jsx$/i.test(path)) return 'jsx'
  if (/\\.m?js$/i.test(path)) return 'js'
  if (/\\.json$/i.test(path)) return 'json'
  if (/\\.svg$/i.test(path)) return 'js'
  return 'js'
}

function resolveLocal(specifier, resolveDir, files) {
  const base = specifier.startsWith('@/')
    ? '/src/' + specifier.slice(2)
    : specifier.startsWith('/')
      ? specifier
      : normalize((resolveDir || '/') + '/' + specifier)
  const clean = normalize(base)
  for (const ext of EXTENSIONS) {
    const candidate = normalize(clean + ext)
    if (files.has(candidate)) return candidate
  }
  for (const ext of EXTENSIONS.slice(1)) {
    const candidate = normalize(clean + '/index' + ext)
    if (files.has(candidate)) return candidate
  }
  throw new Error('Import local introuvable: ' + specifier + ' depuis ' + (resolveDir || '/'))
}

async function initEsbuild() {
  if (!initialized) initialized = esbuild.initialize({ wasmURL: CDN_WASM, worker: false })
  await initialized
}

self.onmessage = async (event) => {
  if (event.data?.type !== 'build') return
  const started = performance.now()
  const files = new Map(Object.entries(event.data.files || {}).map(([path, content]) => [normalize(path), String(content)]))
  const entryPath = normalize(event.data.entryPath || '')
  try {
    self.postMessage({ type: 'log', message: 'Chargement esbuild-wasm...' })
    await initEsbuild()
    self.postMessage({ type: 'log', message: 'Resolution des imports...' })
    const result = await esbuild.build({
      entryPoints: [entryPath],
      bundle: true,
      write: false,
      format: 'esm',
      platform: 'browser',
      target: ['es2022'],
      sourcemap: 'inline',
      jsx: 'automatic',
      jsxImportSource: 'react',
      logLevel: 'silent',
      define: { 'process.env.NODE_ENV': '"development"', global: 'globalThis' },
      plugins: [{
        name: 'aurora-vfs',
        setup(build) {
          build.onResolve({ filter: /.*/ }, (args) => {
            if (/^https?:\\/\\//i.test(args.path)) return { path: args.path, external: true }
            if (isBareSpecifier(args.path)) return { path: args.path, external: true }
            const resolved = resolveLocal(args.path, args.resolveDir, files)
            return { path: resolved, namespace: 'aurora-vfs' }
          })
          build.onLoad({ filter: /.*/, namespace: 'aurora-vfs' }, (args) => {
            const contents = files.get(normalize(args.path))
            if (contents == null) throw new Error('Fichier VFS introuvable: ' + args.path)
            if (/\\.css$/i.test(args.path)) {
              return {
                loader: 'js',
                resolveDir: dirname(args.path),
                contents: [
                  'const css = ' + JSON.stringify(contents) + ';',
                  'const style = document.createElement("style");',
                  'style.dataset.auroraRuntimeCss = ' + JSON.stringify(args.path) + ';',
                  'style.textContent = css;',
                  'document.head.appendChild(style);',
                  'export default css;',
                ].join('\\n'),
              }
            }
            if (/\\.svg$/i.test(args.path)) {
              const encoded = btoa(unescape(encodeURIComponent(contents)))
              return { loader: 'js', resolveDir: dirname(args.path), contents: 'export default "data:image/svg+xml;base64,' + encoded + '";' }
            }
            return { loader: loaderFor(args.path), resolveDir: dirname(args.path), contents }
          })
        },
      }],
    })
    const codeFile = result.outputFiles.find((file) => /\\.js(?:\\.map)?$/i.test(file.path)) || result.outputFiles[0]
    self.postMessage({
      type: 'bundle',
      code: codeFile?.text || '',
      durationMs: Math.round(performance.now() - started),
      warnings: result.warnings.map((warning) => warning.text),
    })
  } catch (error) {
    self.postMessage({ type: 'error', message: error?.message || String(error), stack: error?.stack || null })
  }
}
`
}

function safeJsonForInlineScript(value: unknown): string {
  return JSON.stringify(value)
    .replace(/</g, '\\u003c')
    .replace(/>/g, '\\u003e')
    .replace(/&/g, '\\u0026')
    .replace(/\u2028/g, '\\u2028')
    .replace(/\u2029/g, '\\u2029')
}

function safeJsString(value: string): string {
  return JSON.stringify(value)
    .replace(/<\/script/gi, '<\\/script')
    .replace(/\u2028/g, '\\u2028')
    .replace(/\u2029/g, '\\u2029')
}

function escapeRegex(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}
