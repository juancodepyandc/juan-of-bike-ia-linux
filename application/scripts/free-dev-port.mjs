import { execSync } from 'node:child_process'

const port = Number.parseInt(process.env.AURORA_DEV_PORT ?? '1420', 10)
const tauriExeName = process.env.AURORA_TAURI_EXE_NAME ?? 'juan-of-bike-ia'

function getPidsOnWindows(targetPort) {
  const output = execSync(
    `powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort ${targetPort} -State Listen | Select-Object -ExpandProperty OwningProcess -Unique"`,
    {
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'ignore'],
    },
  )

  return [...new Set(
    output
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean)
      .filter((pid) => /^\d+$/.test(pid))
  )]
}

function getPidsOnUnix(targetPort) {
  const output = execSync(`lsof -ti tcp:${targetPort}`, {
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'ignore'],
  })

  return [...new Set(
    output
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter((pid) => /^\d+$/.test(pid))
  )]
}

function getPortPids(targetPort) {
  try {
    return process.platform === 'win32'
      ? getPidsOnWindows(targetPort)
      : getPidsOnUnix(targetPort)
  } catch {
    return []
  }
}

function getTauriDevPids() {
  try {
    if (process.platform === 'win32') {
      const output = execSync(
        `powershell -NoProfile -Command "Get-Process -Name '${tauriExeName}' -ErrorAction SilentlyContinue | Where-Object { $_.Path -like '*src-tauri*target*debug*${tauriExeName}.exe' } | Select-Object -ExpandProperty Id"`,
        {
          encoding: 'utf8',
          stdio: ['ignore', 'pipe', 'ignore'],
        },
      )

      return [...new Set(
        output
          .split(/\r?\n/)
          .map((line) => line.trim())
          .filter((pid) => /^\d+$/.test(pid))
      )]
    }

    const output = execSync(`pgrep -f "src-tauri/.*/${tauriExeName}"`, {
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'ignore'],
    })

    return [...new Set(
      output
        .split(/\r?\n/)
        .map((line) => line.trim())
        .filter((pid) => /^\d+$/.test(pid))
    )]
  } catch {
    return []
  }
}

function killPid(pid) {
  if (process.platform === 'win32') {
    execSync(`taskkill /PID ${pid} /F`, {
      stdio: ['ignore', 'ignore', 'ignore'],
    })
    return
  }

  process.kill(Number(pid), 'SIGKILL')
}

const pids = getPortPids(port).filter((pid) => Number(pid) !== process.pid)
const tauriPids = getTauriDevPids().filter((pid) => Number(pid) !== process.pid)

if (pids.length === 0) {
  console.log(`[aurora] port ${port} libre`)
}

for (const pid of pids) {
  try {
    killPid(pid)
    console.log(`[aurora] process ${pid} arrete sur le port ${port}`)
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    console.warn(`[aurora] impossible d'arreter ${pid} sur ${port}: ${message}`)
  }
}

if (tauriPids.length === 0) {
  console.log(`[aurora] aucun ancien processus ${tauriExeName} a fermer`)
}

for (const pid of tauriPids) {
  try {
    killPid(pid)
    console.log(`[aurora] processus Tauri ${pid} arrete`)
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    console.warn(`[aurora] impossible d'arreter le processus Tauri ${pid}: ${message}`)
  }
}
