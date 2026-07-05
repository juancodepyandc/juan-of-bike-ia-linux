import { runPythonScript } from '../../hooks/useTauri'

function scriptPath(name: string) {
  return `python-services/cyber/${name}`
}

function parseJsonLastLine(output: string): unknown {
  const lines = output.split('\n').map((l) => l.trim()).filter(Boolean)
  for (let i = lines.length - 1; i >= 0; i--) {
    try { return JSON.parse(lines[i]) } catch { /* keep searching */ }
  }
  return null
}

async function run<T>(script: string, args: string[]): Promise<T> {
  const out = await runPythonScript(scriptPath(script), args)
  const parsed = parseJsonLastLine(out) as T | null
  if (!parsed) throw new Error(`Sortie Python non-parseable: ${out.slice(-300)}`)
  return parsed
}

// === network ===
export interface DnsResult { [key: string]: string[] | string | number | null }
export function cyberDnsLookup(domain: string) {
  return run<DnsResult>('network_ops.py', ['dns', domain])
}

export interface TlsCertResult {
  subject?: string | Record<string, string>; issuer?: string | Record<string, string>;
  not_before?: string; not_after?: string; notBefore?: string; notAfter?: string;
  serial?: string; serialNumber?: string;
  sans?: string[]; subjectAlternativeName?: string[]; version?: string | number; error?: string;
}
export function cyberTlsCert(host: string, port = 443) {
  return run<TlsCertResult>('network_ops.py', ['tls', host, '--port', String(port)])
}

export function cyberWhois(domain: string) {
  return run<Record<string, unknown>>('network_ops.py', ['whois', domain])
}

export interface HttpHeadersResult {
  status?: number; url?: string; headers?: Record<string, string>;
  securityScore?: number; missing?: string[]; present?: string[];
  missing_security_headers?: string[]; error?: string;
}
export function cyberHttpHeaders(url: string) {
  return run<HttpHeadersResult>('network_ops.py', ['http', url])
}

export interface PortScanResult {
  target: string; ip?: string;
  open?: Array<{ port: number; service?: string; banner?: string }>;
  openPorts?: Array<{ port: number; service?: string; banner?: string }>;
  closed?: number[]; totalScanned?: number; durationMs?: number; error?: string; blocked?: boolean;
}
export function cyberPortScan(target: string, ports: number[] = []) {
  const args = ['scan', target]
  if (ports.length) args.push('--ports', ports.join(','))
  return run<PortScanResult>('network_ops.py', args)
}

export function cyberTraceroute(target: string) {
  return run<{ hops: Array<{ hop: number; ip?: string; rttMs?: number }>; error?: string }>(
    'network_ops.py', ['traceroute', target],
  )
}

export function cyberPcapDemo() {
  return run<{ packets: Array<Record<string, unknown>> }>('network_ops.py', ['pcap-demo'])
}

// === forensics ===
export interface MagicResult { type?: string; extension?: string; mime?: string; detail?: string; matches?: string[]; error?: string }
export function cyberMagic(path: string) { return run<MagicResult>('forensics_ops.py', ['magic', path]) }

export interface FileHashesResult { md5?: string; sha1?: string; sha256?: string; size?: number; error?: string }
export function cyberFileHashes(path: string) { return run<FileHashesResult>('forensics_ops.py', ['hash', path]) }

export interface StringsResult {
  strings?: Array<{ offset: number; value: string; encoding: string }>;
  ascii_count?: number; utf16_count?: number; total_count?: number; error?: string;
}
export function cyberStrings(path: string) { return run<StringsResult>('forensics_ops.py', ['strings', path]) }

export interface ExifResult { tags?: Record<string, unknown>; error?: string }
export function cyberExif(path: string) { return run<ExifResult>('forensics_ops.py', ['exif', path]) }

export interface EntropyResult { blocks?: Array<{ offset: number; entropy: number; size?: number }>; global?: number; error?: string }
export function cyberEntropy(path: string) { return run<EntropyResult>('forensics_ops.py', ['entropy', path]) }

export interface MemScanResult {
  matches?: Array<{ offset: number; pattern: string; value: string }>;
  urls?: string[]; ips?: string[]; emails?: string[]; credential_hints?: string[]; error?: string;
}
export function cyberMemScan(path: string) { return run<MemScanResult>('forensics_ops.py', ['memscan', path]) }

// === stego ===
export function cyberImgEncode(cover: string, secret: string, out: string) {
  return run<{ out?: string; capacity?: number; error?: string }>(
    'stego_ops.py', ['img-enc', '--cover', cover, '--secret', secret, '--out', out],
  )
}
export function cyberImgDecode(stego: string) {
  return run<{ secret?: string; bytes?: number; error?: string }>('stego_ops.py', ['img-dec', '--stego', stego])
}
export function cyberImgDiff(cover: string, stego: string, out: string) {
  return run<{ out?: string; changedPixels?: number; error?: string }>(
    'stego_ops.py', ['img-diff', '--cover', cover, '--stego', stego, '--out', out],
  )
}
export function cyberAudEncode(cover: string, secret: string, out: string) {
  return run<{ out?: string; capacity?: number; error?: string }>(
    'stego_ops.py', ['aud-enc', '--cover', cover, '--secret', secret, '--out', out],
  )
}
export function cyberAudDecode(stego: string) {
  return run<{ secret?: string; error?: string }>('stego_ops.py', ['aud-dec', '--stego', stego])
}
export function cyberLsbStats(path: string) {
  return run<{ lsbHistogram?: Record<string, number>; chiSquare?: number; suspicionScore?: number; error?: string }>(
    'stego_ops.py', ['lsb-stats', '--stego', path],
  )
}

// === password KDF ===
export interface KdfResult { hash: string; durationMs: number; algo: string; params: Record<string, number>; error?: string }
export function cyberArgon2(pw: string, time = 3, mem = 65536, par = 4) {
  return run<KdfResult>('password_ops.py', ['argon2', pw, '--time', String(time), '--mem', String(mem), '--par', String(par)])
}
export function cyberBcrypt(pw: string, rounds = 12) {
  return run<KdfResult>('password_ops.py', ['bcrypt', pw, '--rounds', String(rounds)])
}
export function cyberScrypt(pw: string, n = 1 << 15) {
  return run<KdfResult>('password_ops.py', ['scrypt', pw, '--n', String(n)])
}
