import { spawn } from 'node:child_process'

const viteArgs = ['vite', '--host', '0.0.0.0', '--port', '1420']
const command = process.platform === 'win32' ? 'npx.cmd' : 'npx'
const child = spawn(command, ['--no-install', ...viteArgs], {
  stdio: 'inherit',
  env: {
    ...process.env,
    VITE_CLOUD_MODE: 'true',
    VITE_BRIDGE_URL: process.env.VITE_BRIDGE_URL || 'http://127.0.0.1:3001',
  },
})

child.on('exit', (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal)
    return
  }

  process.exit(code ?? 0)
})
