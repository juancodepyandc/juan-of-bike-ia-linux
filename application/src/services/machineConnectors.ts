// machineConnectors.ts — typed wrapper around the bridge /api/connect/* endpoints.
//
// Both AuroraV*CodeView and AuroraV*CoworkView import this to:
//   - list / save / delete machine targets (SSH-reachable hosts)
//   - probe a target (auth check, OS, python/node versions)
//   - run a command, upload a file, generate a fresh ed25519 keypair
//   - probe a raw TCP port
//
// Credentials handling: the password can be sent per-request and never stored,
// OR persisted by setting save_password=true (stored in ~/.aurora_code_targets.json
// on the bridge host). Key-based auth is preferred — `keygen` returns a public
// key that the user pastes onto the target's ~/.ssh/authorized_keys.

const API = '/api/connect'

export type MachineTarget = {
  name: string
  host: string
  user: string
  port?: number
  deploy_path?: string
  key_path?: string
  platform?: 'raspberry_pi' | 'linux_x86' | 'linux_arm' | 'linux_wsl' | 'macos' | 'unknown'
  platform_hints?: string
  preview_url_base?: string
}

export type SshAuth = { password?: string; key_path?: string }

export type ProbeResult = {
  ok: boolean
  auth?: 'password' | 'key'
  out?: string
  err?: string
  rc?: number
  error?: string
}

export type RunResult = {
  ok: boolean
  rc?: number
  stdout?: string
  stderr?: string
  error?: string
}

export type UploadResult = { ok: boolean; bytes?: number; path?: string; error?: string }

export type KeygenResult = {
  ok: boolean
  private_key_path?: string
  public_key?: string
  instructions?: string
  error?: string
}

export type TcpProbeResult = { ok: boolean; rtt_ms: number; error?: string }

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(`${API}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  return r.json() as Promise<T>
}

export async function listTargets(): Promise<MachineTarget[]> {
  const r = await fetch(`${API}/targets/list`)
  const data = (await r.json()) as { ok: boolean; targets: MachineTarget[] }
  return data.ok ? data.targets : []
}

export async function saveTarget(target: MachineTarget & {
  save_password?: boolean
  password?: string
}): Promise<MachineTarget> {
  return postJson('/targets/save', target)
}

export async function deleteTarget(name: string): Promise<{ ok: boolean }> {
  return postJson('/targets/delete', { name })
}

export async function probe(
  refOrTarget: { target_name: string } | (Partial<MachineTarget> & { host: string; user: string }),
  auth: SshAuth = {},
): Promise<ProbeResult> {
  return postJson('/ssh/probe', { ...refOrTarget, ...auth })
}

export async function runCommand(
  refOrTarget: { target_name: string } | (Partial<MachineTarget> & { host: string; user: string }),
  command: string,
  opts: SshAuth & { timeout?: number } = {},
): Promise<RunResult> {
  return postJson('/ssh/run', { ...refOrTarget, command, ...opts })
}

export async function uploadFile(
  refOrTarget: { target_name: string } | (Partial<MachineTarget> & { host: string; user: string }),
  remotePath: string,
  contentBytes: Uint8Array | string,
  auth: SshAuth = {},
): Promise<UploadResult> {
  const bytes = typeof contentBytes === 'string'
    ? new TextEncoder().encode(contentBytes)
    : contentBytes
  let bin = ''
  for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i])
  const b64 = btoa(bin)
  return postJson('/ssh/upload', {
    ...refOrTarget,
    remote_path: remotePath,
    content_b64: b64,
    ...auth,
  })
}

export async function uploadProject(
  refOrTarget: { target_name: string } | (Partial<MachineTarget> & { host: string; user: string }),
  files: { path: string; content: string | Uint8Array }[],
  remoteBase: string,
  auth: SshAuth = {},
  onProgress?: (i: number, total: number, file: string) => void,
): Promise<{ ok: boolean; uploaded: number; total: number; errors: string[] }> {
  const errors: string[] = []
  let uploaded = 0
  for (let i = 0; i < files.length; i++) {
    const f = files[i]
    onProgress?.(i, files.length, f.path)
    const rp = `${remoteBase.replace(/\/$/, '')}/${f.path.replace(/^\//, '')}`
    const r = await uploadFile(refOrTarget, rp, f.content, auth)
    if (r.ok) uploaded++
    else errors.push(`${f.path}: ${r.error || 'unknown'}`)
  }
  return { ok: errors.length === 0, uploaded, total: files.length, errors }
}

export async function keygen(comment = 'aurora'): Promise<KeygenResult> {
  return postJson('/ssh/keygen', { comment })
}

export async function tcpProbe(host: string, port: number, timeout = 4): Promise<TcpProbeResult> {
  return postJson('/tcp/probe', { host, port, timeout })
}

// Convenience helpers used by code + cowork views ----------------------------

/** Map a target's `platform` field to a one-line hint the LLM uses when
 *  generating code that will run on this target. Mirrors what
 *  aurora_code_remote.enrich_for_target() does on the Python side.
 */
export function platformHintForLLM(target: MachineTarget): string {
  const p = target.platform || 'unknown'
  const hints = target.platform_hints || ''
  switch (p) {
    case 'raspberry_pi':
      return `Raspberry Pi (ARMv7/v8). ${hints || 'RPi.GPIO + picamera2 + lgpio available, Bookworm Python 3.11.'}`
    case 'linux_arm':
      return `Linux ARM. ${hints || 'standard Python/Node stack'}`
    case 'linux_x86':
      return `Linux x86_64. ${hints || 'standard Python/Node stack'}`
    case 'linux_wsl':
      return `WSL2 Ubuntu. ${hints || 'Python 3.12, Node 20, no hardware GPIO'}`
    case 'macos':
      return `macOS. ${hints || 'BSD userland, Homebrew available'}`
    default:
      return hints || 'unknown platform — keep code portable'
  }
}

/** Build a structured "remote context" block to append to the user's prompt
 *  before sending it to the code or cowork orchestrator. */
export function remoteContextBlock(target: MachineTarget | null): string {
  if (!target) return ''
  return [
    '',
    `## Remote target: ${target.name}`,
    `- host:        ${target.user}@${target.host}:${target.port ?? 22}`,
    `- deploy path: ${target.deploy_path ?? '/home/'+target.user+'/aurora_deploys'}`,
    `- platform:    ${platformHintForLLM(target)}`,
    target.preview_url_base ? `- preview at:  ${target.preview_url_base}` : '',
    'Code/output you generate will be uploaded and executed on this remote.',
    'Use only libraries available on the target platform.',
  ].filter(Boolean).join('\n')
}
