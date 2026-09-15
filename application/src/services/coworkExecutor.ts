// ---------------------------------------------------------------------------
// coworkExecutor — runs validated CoworkActions and returns structured
// results. Each action kind has its own executor; the dispatcher in
// runAction() routes by kind.
//
// IMPORTANT: this module assumes the action has ALREADY passed
// coworkSafety.validateAction. It does NOT re-validate paths or commands —
// the orchestrator is responsible for calling validate first.
// ---------------------------------------------------------------------------

import {
  fsExists,
  fsReadText,
  fsWriteText,
  fsMkdir,
  runWorkspaceCommand,
  getWorkspacePath,
} from '../hooks/useTauri.ts'
import { isTauriRuntime, getBridgeUrl } from '../utils/runtime.ts'
import { MAIN_FALLBACK_MODEL } from '../config/models.ts'
import { searchWeb } from './auroraExtensionBridge.ts'
import { SAFETY_LIMITS } from './coworkSafety.ts'
import type { CoworkAction, CoworkActionResult, CoworkRuntime } from './coworkTypes.ts'

// ---------------------------------------------------------------------------
// Public dispatcher
// ---------------------------------------------------------------------------

export async function runAction(
  action: CoworkAction,
  runtime: CoworkRuntime,
  workspaceRoot: string,
  signal?: AbortSignal,
): Promise<CoworkActionResult> {
  const startedAt = performance.now()
  try {
    const result = await dispatch(action, runtime, workspaceRoot, signal)
    return { ...result, durationMs: Math.round(performance.now() - startedAt) }
  } catch (err) {
    return {
      ok: false,
      error: err instanceof Error ? err.message : String(err),
      durationMs: Math.round(performance.now() - startedAt),
    }
  }
}

async function dispatch(
  action: CoworkAction,
  runtime: CoworkRuntime,
  workspaceRoot: string,
  signal?: AbortSignal,
): Promise<Omit<CoworkActionResult, 'durationMs'>> {
  switch (action.kind) {
    case 'reply':
      return { ok: true, output: action.message }

    case 'finish':
      return { ok: true, output: action.summary }

    case 'read_file':
      return runReadFile(action.path, runtime)

    case 'list_dir':
      return runListDir(action.path, runtime, workspaceRoot, action.depth ?? 1)

    case 'write_file':
      return runWriteFile(action.path, action.content, runtime)

    case 'edit_file':
      return runEditFile(action.path, action.oldText, action.newText, runtime)

    case 'delete_file':
      return runDeleteFile(action.path, runtime)

    case 'shell':
      return runShell(action.command, action.args, action.cwd ?? workspaceRoot, action.timeoutMs)

    case 'web_search':
      return runWebSearch(action, signal)

    case 'fetch':
      return runFetch(action, signal)

    case 'open_url':
      return runOpenUrl(action.url, runtime)

    case 'clipboard_read':
      return runClipboardRead()

    case 'clipboard_write':
      return runClipboardWrite(action.text)

    case 'voice_speak':
      return runVoiceSpeak(action.text, runtime)

    case 'dom_query':
      return runDomQuery(action.selector, action.attribute)

    case 'ephemeral_tool': {
      const { runEphemeralToolSandbox } = await import('./ephemeralToolRunner')
      const res = await runEphemeralToolSandbox({
        name: action.toolName,
        packages: action.packages,
        scriptCode: action.scriptCode,
        autoCleanup: action.autoCleanup !== false,
        timeoutSeconds: action.timeoutSeconds,
      })
      return {
        ok: res.ok,
        output: res.ok
          ? `Outil éphémère exécuté avec succès (${res.elapsedSeconds}s, ${res.producedFiles.length} fichier(s) généré(s), nettoyage=${res.cleanedUp}).\nSortie :\n${res.stdout}`
          : `Erreur outil éphémère :\n${res.stderr || res.error}`,
        data: res,
      }
    }

    case 'file_bundle': {
      const { emitModuleFiles } = await import('./moduleFileExchange')
      const emitted = await emitModuleFiles(action.moduleTarget, action.files)
      return {
        ok: true,
        output: `${emitted.length} fichier(s) émis pour le module ${action.moduleTarget} :\n` +
          emitted.map((e) => `- ${e.filename} (${e.byteLength} o) -> ${e.targetPath}`).join('\n'),
        data: { emitted },
      }
    }

    case 'think':
      // Pure reasoning — surface the thought via output. Cheap & deterministic.
      return {
        ok: true,
        output: `Reflexion : ${action.topic}\n\n${action.thought}`,
        data: { topic: action.topic, thought: action.thought },
      }

    case 'think_long': {
      // Long-form reasoning : runs an Ollama mainModel chat with a clear
      // "think it through" instruction. The result feeds the next planner
      // iteration's history, letting Aurora chain a deep analysis with a
      // synthesis reply.
      try {
        const { ollamaChat } = await import('../hooks/useTauri')
        const { useAppStore } = await import('../stores/appStore')
        const state = useAppStore.getState() as { mainModel: string }
        const model = state.mainModel || MAIN_FALLBACK_MODEL
        const sys = 'Tu es un assistant analytique. Reflechis a fond a la question : structure, hypotheses, options envisagees, recommandation finale claire. Ecris en francais, organise en sections (## Contexte / ## Analyse / ## Recommandation).'
        const userMsg = `Sujet : ${action.topic}\n\n${action.prompt}`
        const ms = action.durationHintMs ?? 300_000
        const resp = await Promise.race([
          ollamaChat(model, [{ role: 'system', content: sys } as never, { role: 'user', content: userMsg } as never]),
          new Promise<never>((_, reject) => setTimeout(() => reject(new Error('think_long timeout')), ms)),
        ])
        let text = ''
        if (typeof resp === 'string') text = resp
        else if (resp && typeof resp === 'object') {
          const r = resp as { message?: { content?: string }; response?: string }
          text = r.message?.content ?? r.response ?? JSON.stringify(resp).slice(0, 2000)
        }
        return {
          ok: true,
          output: text || '(reflexion longue : reponse vide)',
          data: { topic: action.topic, reasoning: text, model },
        }
      } catch (err) {
        return { ok: false, error: err instanceof Error ? err.message : String(err) }
      }
    }

    case 'remember_fact': {
      try {
        const { loadSettings, saveSettings, rememberFact } = await import('./coworkSettings')
        const settings = loadSettings()
        const next = rememberFact(settings, action.fact, action.tags)
        saveSettings(next)
        const stored = next.userMemory.find((e) => e.fact.trim().toLowerCase() === action.fact.trim().toLowerCase())
        return {
          ok: true,
          output: `Aurora a memorise : "${action.fact.trim()}"${action.tags?.length ? ` (tags: ${action.tags.join(', ')})` : ''}.`,
          data: { id: stored?.id, fact: action.fact, tags: action.tags, totalMemory: next.userMemory.length },
        }
      } catch (err) {
        return { ok: false, error: err instanceof Error ? err.message : String(err) }
      }
    }

    case 'forget_fact': {
      try {
        const { loadSettings, saveSettings, forgetFact } = await import('./coworkSettings')
        const settings = loadSettings()
        const before = settings.userMemory.length
        const next = forgetFact(settings, { id: action.id, matching: action.matching })
        saveSettings(next)
        const removed = before - next.userMemory.length
        return {
          ok: true,
          output: removed > 0 ? `${removed} fait(s) oublie(s).` : 'Aucun fait correspondant.',
          data: { removed, totalMemory: next.userMemory.length },
        }
      } catch (err) {
        return { ok: false, error: err instanceof Error ? err.message : String(err) }
      }
    }

    case 'screenshot_desktop': {
      return runScreenshotDesktop(runtime, workspaceRoot, action.quality)
    }

    case 'vision_describe': {
      // Run a vision LLM on the image. Aurora uses qwen3-vl by default; the
      // result goes into the next planner iteration's history.
      try {
        const { ollamaChat } = await import('../hooks/useTauri')
        const { useAppStore } = await import('../stores/appStore')
        const state = useAppStore.getState() as { visionModel?: string; mainModel: string }
        const visionModel = state.visionModel || 'qwen3-vl:30b'
        const b64 = action.imageDataUrl.includes(',') ? action.imageDataUrl.split(',')[1] : action.imageDataUrl
        const question = action.question
          || 'Decris precisement cette image : layout, couleurs, sections, elements UI ou objets visibles, texte lisible, contexte general.'
        const resp = await ollamaChat(
          visionModel,
          [{ role: 'user', content: question, images: [b64] } as never],
        )
        let text = ''
        if (typeof resp === 'string') text = resp
        else if (resp && typeof resp === 'object') {
          const r = resp as { message?: { content?: string }; response?: string }
          text = r.message?.content ?? r.response ?? JSON.stringify(resp).slice(0, 1000)
        }
        return { ok: true, output: text, data: { description: text, model: visionModel } }
      } catch (err) {
        return { ok: false, error: err instanceof Error ? err.message : String(err) }
      }
    }

    case 'connector': {
      const { runConnectorAction } = await import('./coworkConnectors')
      const { loadSettings, saveSettings } = await import('./coworkSettings')
      const settings = loadSettings()
      const cfg = settings.connectors[action.connector as keyof typeof settings.connectors]
      if (!cfg || !cfg.enabled) {
        return { ok: false, error: `Connecteur "${action.connector}" non active. Active-le dans Settings -> Connecteurs.` }
      }
      const r = await runConnectorAction(action.connector as never, action.action, action.params ?? {}, {
        apiKey: cfg.apiKey,
        workspaceId: cfg.workspaceId,
        baseUrl: cfg.baseUrl,
      })
      // Track quota exhaustion : 402 (Payment Required), 429 (Too Many Requests),
      // or specific error keywords. The planner reads this on the next turn to
      // decide whether to fall back to the local equivalent.
      //
      // Symmetric : when a successful run lands and the connector was previously
      // marked quota_exhausted, CLEAR the flag — quota windows reset over time
      // and Aurora must re-trust connectors once they work again.
      if (!r.ok && r.error) {
        const msg = r.error.toLowerCase()
        const quotaSignals = ['429', '402', 'quota', 'limit exceeded', 'rate limit', 'insufficient_quota', 'billing', 'over the limit']
        if (quotaSignals.some((s) => msg.includes(s))) {
          const updated = { ...settings, connectors: { ...settings.connectors, [action.connector]: { ...cfg, lastCheck: { ok: false, at: Date.now(), message: `quota_exhausted: ${r.error.slice(0, 120)}` } } } }
          saveSettings(updated)
        }
      } else if (r.ok && cfg.lastCheck && /quota|exhausted|429|402|limit/i.test(cfg.lastCheck.message || '')) {
        const updated = { ...settings, connectors: { ...settings.connectors, [action.connector]: { ...cfg, lastCheck: { ok: true, at: Date.now(), message: 'quota cleared (run successful)' } } } }
        saveSettings(updated)
      }
      return r.ok
        ? { ok: true, output: r.output ?? JSON.stringify(r.data, null, 2).slice(0, 2000), data: r.data }
        : { ok: false, error: r.error || 'connector failed' }
    }

    case 'browser': {
      // Browser actions are forwarded to the Aurora-Connect extension via
      // the bridge. The bridge maintains a per-extension command queue +
      // result store. We pick the first active extension if none specified.
      try {
        const url = `${getBridgeUrl()}/api/cowork/extension/list`
        const listResp = await fetch(url, { signal: AbortSignal.timeout(5_000) })
        const listData = await listResp.json() as { ok: boolean; extensions?: Array<{ extId: string }> }
        const extId = action.extId || listData.extensions?.[0]?.extId
        if (!extId) {
          return { ok: false, error: 'Aucune extension Aurora-Connect detectee. Installe-la depuis Settings -> Aurora-Connect, puis recharge.' }
        }
        // Map Cowork operation -> extension command kind
        const dispatchResp = await fetch(`${getBridgeUrl()}/api/cowork/extension/dispatch`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ extId, kind: action.operation, payload: action.payload ?? {} }),
        })
        const dispatchData = await dispatchResp.json() as { ok: boolean; commandId?: string; error?: string }
        if (!dispatchData.ok || !dispatchData.commandId) {
          return { ok: false, error: dispatchData.error || 'dispatch failed' }
        }
        // Wait for the result (extension polls + executes)
        const awaitResp = await fetch(
          `${getBridgeUrl()}/api/cowork/extension/await-result?commandId=${dispatchData.commandId}&wait=25000`,
          { signal: AbortSignal.timeout(30_000) },
        )
        if (!awaitResp.ok) return { ok: false, error: `bridge ${awaitResp.status}` }
        const awaitData = await awaitResp.json() as { ok: boolean; result?: { ok: boolean; data?: unknown; error?: string } }
        if (!awaitData.ok || !awaitData.result) return { ok: false, error: 'extension n a pas repondu (timeout)' }
        return awaitData.result.ok
          ? { ok: true, output: typeof awaitData.result.data === 'string' ? awaitData.result.data : JSON.stringify(awaitData.result.data, null, 2).slice(0, 4000), data: awaitData.result.data }
          : { ok: false, error: awaitData.result.error || 'extension command failed' }
      } catch (err) {
        return { ok: false, error: err instanceof Error ? err.message : String(err) }
      }
    }

    default: {
      const _exhaustive: never = action
      return { ok: false, error: `Action kind non geree : ${JSON.stringify(_exhaustive)}` }
    }
  }
}

// ---------------------------------------------------------------------------
// Filesystem
// ---------------------------------------------------------------------------

async function runReadFile(
  path: string,
  runtime: CoworkRuntime,
): Promise<Omit<CoworkActionResult, 'durationMs'>> {
  if (runtime !== 'tauri-desktop') {
    // Web fallback via bridge — the bridge enforces its own workspace boundary.
    return readFileViaBridge(path)
  }
  const exists = await fsExists(path)
  if (!exists) return { ok: false, error: `Fichier introuvable : ${path}` }
  const content = await fsReadText(path)
  if (content.length > SAFETY_LIMITS.maxReadFileBytes) {
    return {
      ok: false,
      error: `Fichier trop volumineux (${content.length} > ${SAFETY_LIMITS.maxReadFileBytes} octets).`,
    }
  }
  return { ok: true, output: content, data: { path, bytes: content.length } }
}

async function readFileViaBridge(path: string): Promise<Omit<CoworkActionResult, 'durationMs'>> {
  try {
    const url = `${getBridgeUrl()}/api/cowork/read?path=${encodeURIComponent(path)}`
    const resp = await fetch(url, { signal: AbortSignal.timeout(SAFETY_LIMITS.defaultFetchTimeoutMs) })
    if (!resp.ok) return { ok: false, error: `Bridge ${resp.status} ${resp.statusText}` }
    const data = await resp.json() as { ok: boolean; content?: string; error?: string; bytes?: number }
    if (!data.ok) return { ok: false, error: data.error || 'Lecture refusee par le bridge.' }
    return { ok: true, output: data.content || '', data: { path, bytes: data.bytes ?? data.content?.length ?? 0 } }
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : String(err) }
  }
}

async function runWriteFile(
  path: string,
  content: string,
  runtime: CoworkRuntime,
): Promise<Omit<CoworkActionResult, 'durationMs'>> {
  if (runtime !== 'tauri-desktop') {
    return writeFileViaBridge(path, content)
  }
  await fsWriteText(path, content)
  return { ok: true, output: `Ecrit ${content.length} octets dans ${path}.`, data: { path, bytes: content.length } }
}

async function writeFileViaBridge(
  path: string,
  content: string,
): Promise<Omit<CoworkActionResult, 'durationMs'>> {
  try {
    const url = `${getBridgeUrl()}/api/cowork/write`
    const resp = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path, content }),
      signal: AbortSignal.timeout(SAFETY_LIMITS.defaultFetchTimeoutMs),
    })
    if (!resp.ok) return { ok: false, error: `Bridge ${resp.status} ${resp.statusText}` }
    const data = await resp.json() as { ok: boolean; error?: string; bytes?: number }
    if (!data.ok) return { ok: false, error: data.error || 'Ecriture refusee par le bridge.' }
    return { ok: true, output: `Ecrit ${data.bytes ?? content.length} octets via bridge.`, data: { path, bytes: data.bytes ?? content.length } }
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : String(err) }
  }
}

async function runEditFile(
  path: string,
  oldText: string,
  newText: string,
  runtime: CoworkRuntime,
): Promise<Omit<CoworkActionResult, 'durationMs'>> {
  const readResult = await runReadFile(path, runtime)
  if (!readResult.ok) return readResult
  const original = readResult.output ?? ''
  const occurrences = countOccurrences(original, oldText)
  if (occurrences === 0) {
    return { ok: false, error: `oldText introuvable dans ${path}.` }
  }
  if (occurrences > 1) {
    return {
      ok: false,
      error: `oldText apparait ${occurrences} fois dans ${path}. Aurora doit fournir un contexte plus large pour cibler un seul match.`,
    }
  }
  const updated = original.replace(oldText, newText)
  return runWriteFile(path, updated, runtime)
}

async function runDeleteFile(
  path: string,
  runtime: CoworkRuntime,
): Promise<Omit<CoworkActionResult, 'durationMs'>> {
  if (runtime !== 'tauri-desktop') {
    return deleteFileViaBridge(path)
  }
  // Use the existing fs_remove_dir_all command — it handles both files and dirs.
  const { invoke } = await import('@tauri-apps/api/core')
  await invoke('fs_remove_dir_all', { path })
  return { ok: true, output: `Supprime : ${path}.`, data: { path } }
}

async function deleteFileViaBridge(path: string): Promise<Omit<CoworkActionResult, 'durationMs'>> {
  try {
    const url = `${getBridgeUrl()}/api/cowork/delete`
    const resp = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path }),
      signal: AbortSignal.timeout(SAFETY_LIMITS.defaultFetchTimeoutMs),
    })
    if (!resp.ok) return { ok: false, error: `Bridge ${resp.status} ${resp.statusText}` }
    const data = await resp.json() as { ok: boolean; error?: string }
    if (!data.ok) return { ok: false, error: data.error || 'Suppression refusee par le bridge.' }
    return { ok: true, output: `Supprime via bridge : ${path}.`, data: { path } }
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : String(err) }
  }
}

async function runListDir(
  path: string,
  runtime: CoworkRuntime,
  workspaceRoot: string,
  depth: number,
): Promise<Omit<CoworkActionResult, 'durationMs'>> {
  if (runtime === 'web-mobile') {
    return { ok: false, error: 'list_dir indisponible sur web-mobile.' }
  }
  const scanDepth = Math.max(1, Math.min(8, Math.round(depth || 1)))
  const isWindows = (typeof navigator !== 'undefined' && /windows/i.test(navigator.userAgent))
  const target = path || workspaceRoot
  const exec = isWindows ? 'cmd' : 'find'
  const args = isWindows
    ? ['/c', 'dir', '/b', ...(scanDepth > 1 ? ['/s'] : [])]
    : [target, '-maxdepth', String(scanDepth), '-mindepth', '1', '-print']
  const cwd = isWindows ? target : (workspaceRoot || target)
  try {
    const result = await runWorkspaceCommand(exec, args, cwd, 30_000)
    if (!result.ok) return { ok: false, error: result.output || 'Echec list_dir.' }
    const lines = (result.output || '').split('\n').filter((l) => l.trim()).slice(0, SAFETY_LIMITS.maxListDirEntries)
    return {
      ok: true,
      output: lines.join('\n'),
      data: { path: target, entries: lines, count: lines.length, depth: scanDepth },
    }
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : String(err) }
  }
}

// ---------------------------------------------------------------------------
// Shell
// ---------------------------------------------------------------------------

async function runShell(
  command: string,
  args: string[],
  cwd: string,
  timeoutMs?: number,
): Promise<Omit<CoworkActionResult, 'durationMs'>> {
  const effectiveTimeout = Math.min(
    timeoutMs ?? SAFETY_LIMITS.defaultShellTimeoutMs,
    SAFETY_LIMITS.maxShellTimeoutMs,
  )
  // runWorkspaceCommand enforces the cwd existence; if the cwd does not
  // exist, fall back to the workspace root.
  let effectiveCwd = cwd
  try {
    if (!(await fsExists(cwd))) {
      effectiveCwd = await getWorkspacePath()
    }
  } catch { /* ignore — bridge mode may not support fsExists */ }
  const normalized = normalizePowerShellUtf8(command, args)
  try {
    const result = await runWorkspaceCommand(normalized.command, normalized.args, effectiveCwd, effectiveTimeout)
    return {
      ok: result.ok,
      output: result.output,
      data: { command: result.command, exitCode: result.exitCode, cwd: effectiveCwd },
      error: result.ok ? undefined : `Exit code ${result.exitCode}`,
    }
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err)
    if (/valid UTF-?8|utf-?8/i.test(message) && isPowerShellCommand(command)) {
      return {
        ok: false,
        error: `${message}. PowerShell a produit une sortie non UTF-8 ; relance avec encodage UTF-8 force ou une commande plus ciblee.`,
      }
    }
    return { ok: false, error: message }
  }
}

function isPowerShellCommand(command: string): boolean {
  const base = command.trim().split(/[\\/]/).pop()?.toLowerCase() || ''
  return base === 'powershell' || base === 'powershell.exe' || base === 'pwsh' || base === 'pwsh.exe'
}

function normalizePowerShellUtf8(command: string, args: string[]): { command: string; args: string[] } {
  if (!isPowerShellCommand(command)) return { command, args }
  const commandIndex = args.findIndex((arg) => /^-command$/i.test(arg))
  if (commandIndex < 0 || commandIndex >= args.length - 1) return { command, args }
  const script = args[commandIndex + 1] || ''
  if (/OutputEncoding|chcp\s+65001/i.test(script)) return { command, args }
  const prologue = [
    "try { [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false); $OutputEncoding = [Console]::OutputEncoding } catch {}",
    "$ProgressPreference='SilentlyContinue'",
  ].join('; ')
  const next = [...args]
  next[commandIndex + 1] = `${prologue}; ${script}`
  return { command, args: next }
}

// ---------------------------------------------------------------------------
// Screenshot Desktop — capture l ecran systeme complet (pas que le navigateur).
//
// Windows : PowerShell + System.Drawing (built-in, aucune install requise).
// Mac     : screencapture -x (built-in macOS).
// Linux   : essaie scrot puis gnome-screenshot puis import (ImageMagick).
//
// Le PNG est ecrit dans le workspace ($WORKSPACE/.cowork/screenshots/), puis
// lu en base64 et expose en dataUrl. Le bridge cowork retrouvera la dataUrl
// dans l historique pour la chaine vision_describe.
// ---------------------------------------------------------------------------

async function runScreenshotDesktop(
  runtime: CoworkRuntime,
  workspaceRoot: string,
  _quality?: 'fast' | 'hq',
): Promise<Omit<CoworkActionResult, 'durationMs'>> {
  if (runtime !== 'tauri-desktop') {
    return {
      ok: false,
      error: 'screenshot_desktop necessite le runtime tauri-desktop (acces direct au systeme). En web, utilise plutot { kind:"browser", operation:"screenshot" } pour capturer la page web active.',
    }
  }
  try {
    // 1. Determine output path under workspace
    const ts = Date.now()
    const outDir = `${workspaceRoot}/.cowork/screenshots`
    try { await fsMkdir(outDir) } catch { /* may already exist */ }
    const outPath = `${outDir}/desktop_${ts}.png`

    // 2. Detect OS via platform check (Tauri exposes navigator.platform)
    const platform = (typeof navigator !== 'undefined' ? navigator.platform : '').toLowerCase()
    const isWin = platform.includes('win')
    const isMac = platform.includes('mac')

    let captured = false
    let captureErr = ''

    if (isWin) {
      // PowerShell : capture ecran primaire via System.Drawing
      const psScript = [
        'Add-Type -AssemblyName System.Windows.Forms,System.Drawing;',
        '$s = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds;',
        '$bmp = New-Object System.Drawing.Bitmap $s.Width, $s.Height;',
        '$g = [System.Drawing.Graphics]::FromImage($bmp);',
        '$g.CopyFromScreen($s.Left, $s.Top, 0, 0, $bmp.Size);',
        `$bmp.Save('${outPath.replace(/\\/g, '\\\\').replace(/'/g, "''")}', [System.Drawing.Imaging.ImageFormat]::Png);`,
        '$bmp.Dispose(); $g.Dispose();',
      ].join(' ')
      const r = await runWorkspaceCommand('powershell', ['-NoProfile', '-NonInteractive', '-Command', psScript], workspaceRoot, 15_000)
      captured = r.ok
      captureErr = r.ok ? '' : r.output
    } else if (isMac) {
      const r = await runWorkspaceCommand('screencapture', ['-x', outPath], workspaceRoot, 15_000)
      captured = r.ok
      captureErr = r.ok ? '' : r.output
    } else {
      // Linux : try scrot, then gnome-screenshot, then import
      for (const [cmd, args] of [
        ['scrot', [outPath]] as const,
        ['gnome-screenshot', ['-f', outPath]] as const,
        ['import', ['-window', 'root', outPath]] as const,
      ]) {
        const r = await runWorkspaceCommand(cmd, args as unknown as string[], workspaceRoot, 15_000)
        if (r.ok) { captured = true; break }
        captureErr = r.output
      }
    }

    if (!captured) {
      return {
        ok: false,
        error: `screenshot_desktop a echoue : ${captureErr || 'commande indisponible'}. Verifie qu un outil de capture (PowerShell/screencapture/scrot/gnome-screenshot/import) est dispo.`,
      }
    }

    // 3. Read PNG bytes -> base64 -> dataUrl
    //    On lit via le bridge Tauri en binary (fsReadText decoderait en UTF-8 et casserait).
    const { invoke } = await import('@tauri-apps/api/core')
    const bytes = await invoke<number[]>('fs_read_binary', { path: outPath }).catch(() => null)
    if (!bytes || !Array.isArray(bytes)) {
      // Fallback : on a le path mais pas les bytes. Renvoie au moins le path
      // pour que vision_describe puisse essayer via path.
      return {
        ok: true,
        output: `Screenshot capture : ${outPath} (lecture base64 indisponible, vision_describe ne pourra pas analyser sans dataUrl).`,
        data: { path: outPath, sizeKB: 0 },
      }
    }
    // Convert byte array -> base64 (eviter btoa overflow sur grandes images)
    const buf = new Uint8Array(bytes)
    const sizeKB = Math.round(buf.byteLength / 1024)
    let binary = ''
    const CHUNK = 0x8000
    for (let i = 0; i < buf.length; i += CHUNK) {
      binary += String.fromCharCode.apply(null, Array.from(buf.subarray(i, i + CHUNK)))
    }
    const b64 = typeof btoa !== 'undefined'
      ? btoa(binary)
      : (globalThis as { Buffer?: { from(b: Uint8Array): { toString(enc: string): string } } }).Buffer?.from(buf).toString('base64') ?? ''
    const dataUrl = `data:image/png;base64,${b64}`

    return {
      ok: true,
      output: `Screenshot du bureau capture (${sizeKB} KB). dataUrl disponible — chaine maintenant vision_describe avec imageDataUrl=<la dataUrl ci-dessus> pour analyser le contenu.`,
      data: { path: outPath, sizeKB, dataUrl },
    }
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : String(err) }
  }
}

// ---------------------------------------------------------------------------
// Fetch
// ---------------------------------------------------------------------------

async function runWebSearch(
  action: Extract<CoworkAction, { kind: 'web_search' }>,
  signal?: AbortSignal,
): Promise<Omit<CoworkActionResult, 'durationMs'>> {
  const result = await searchWeb(action.query, { limit: action.limit ?? 5, signal })
  if (!result.ok) {
    return { ok: false, error: result.reason || 'Recherche web native echouee.' }
  }
  const hits = result.data ?? []
  const output = hits.length > 0
    ? hits.map((hit, index) => [
        `${index + 1}. ${hit.title || '(sans titre)'}`,
        hit.url ? `   ${hit.url}` : '',
        hit.snippet ? `   ${hit.snippet}` : '',
      ].filter(Boolean).join('\n')).join('\n\n')
    : 'Aucun resultat trouve.'
  return {
    ok: true,
    output,
    data: {
      query: action.query,
      hits,
      count: hits.length,
    },
  }
}

async function runFetch(
  action: Extract<CoworkAction, { kind: 'fetch' }>,
  signal?: AbortSignal,
): Promise<Omit<CoworkActionResult, 'durationMs'>> {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), SAFETY_LIMITS.defaultFetchTimeoutMs)
  const onAbort = () => controller.abort()
  signal?.addEventListener('abort', onAbort, { once: true })

  try {
    const resp = await fetch(action.url, {
      method: action.method ?? 'GET',
      headers: action.headers,
      body: action.body,
      signal: controller.signal,
    })
    const buf = await resp.arrayBuffer()
    if (buf.byteLength > SAFETY_LIMITS.maxFetchBytes) {
      return {
        ok: false,
        error: `Reponse trop grande (${buf.byteLength} > ${SAFETY_LIMITS.maxFetchBytes} octets).`,
      }
    }
    const ct = resp.headers.get('content-type') || ''
    let body: string
    if (/^(application\/json|text\/|application\/(xml|javascript|x-yaml))/i.test(ct)) {
      body = new TextDecoder().decode(buf)
    } else {
      body = `[binaire · ${buf.byteLength} octets · content-type ${ct}]`
    }
    return {
      ok: resp.ok,
      output: body,
      data: { status: resp.status, statusText: resp.statusText, contentType: ct, bytes: buf.byteLength },
      error: resp.ok ? undefined : `HTTP ${resp.status} ${resp.statusText}`,
    }
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : String(err) }
  } finally {
    clearTimeout(timeoutId)
    signal?.removeEventListener('abort', onAbort)
  }
}

// ---------------------------------------------------------------------------
// Browser helpers
// ---------------------------------------------------------------------------

async function runOpenUrl(
  url: string,
  _runtime: CoworkRuntime,
): Promise<Omit<CoworkActionResult, 'durationMs'>> {
  // Both Tauri (WebView2) and web runtimes support window.open. We prefer
  // it over the Tauri shell plugin because the plugin requires capability
  // declarations we cannot guarantee at build time, and window.open already
  // works correctly in both environments.
  if (typeof window !== 'undefined') {
    window.open(url, '_blank', 'noopener,noreferrer')
    return { ok: true, output: `Onglet ouvert : ${url}` }
  }
  return { ok: false, error: 'Pas d environnement window — open_url indisponible.' }
}

async function runClipboardRead(): Promise<Omit<CoworkActionResult, 'durationMs'>> {
  try {
    if (typeof navigator === 'undefined' || !navigator.clipboard) {
      return { ok: false, error: 'Clipboard API indisponible.' }
    }
    const text = await navigator.clipboard.readText()
    return { ok: true, output: text }
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : String(err) }
  }
}

async function runClipboardWrite(text: string): Promise<Omit<CoworkActionResult, 'durationMs'>> {
  try {
    if (typeof navigator === 'undefined' || !navigator.clipboard) {
      return { ok: false, error: 'Clipboard API indisponible.' }
    }
    await navigator.clipboard.writeText(text)
    return { ok: true, output: `Copie : ${text.slice(0, 80)}${text.length > 80 ? '…' : ''}` }
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : String(err) }
  }
}

// ---------------------------------------------------------------------------
// Voice (TTS) — uses Kokoro via voice_service.py (Tauri) or
// /api/voice/tts (bridge). Synthesises the text and plays it through an
// HTMLAudioElement so the user hears Aurora's reply without reopening the
// voice copilot module.
// ---------------------------------------------------------------------------

async function runVoiceSpeak(
  text: string,
  runtime: CoworkRuntime,
): Promise<Omit<CoworkActionResult, 'durationMs'>> {
  if (!text.trim()) return { ok: false, error: 'voice_speak.text vide' }
  try {
    const audioUrl = await synthesizeKokoroTts(text, runtime)
    if (!audioUrl) return { ok: false, error: 'Synthese TTS indisponible.' }
    if (typeof Audio === 'undefined') {
      return { ok: true, output: `TTS pret (${audioUrl}) — lecture impossible (pas de Audio API).` }
    }
    const audio = new Audio(audioUrl)
    audio.volume = 1.0
    await new Promise<void>((resolve, reject) => {
      audio.onended = () => resolve()
      audio.onerror = (e) => reject(new Error(`audio error: ${(e as Event).type}`))
      audio.play().catch(reject)
    })
    return { ok: true, output: `Lu a voix haute (${text.length} caracteres).` }
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : String(err) }
  }
}

async function synthesizeKokoroTts(text: string, runtime: CoworkRuntime): Promise<string | null> {
  if (runtime === 'tauri-desktop' && isTauriRuntime()) {
    // On Tauri call voice_service.py directly. The script writes a WAV
    // to the workspace output/ folder; read it back and convert to a
    // blob URL for playback.
    try {
      const { runPythonScript, getWorkspacePath, fsReadBinary } = await import('../hooks/useTauri')
      const wp = await getWorkspacePath()
      const tmpInput = `${wp}/output/voix/cowork_tts_${Date.now()}.txt`
      const tmpOutput = `${wp}/output/voix/cowork_tts_${Date.now()}.wav`
      const { fsWriteText } = await import('../hooks/useTauri')
      await fsWriteText(tmpInput, text)
      const out = await runPythonScript(
        `${wp}/python-services/voice_service.py`,
        ['--mode', 'tts', '--input', tmpInput, '--output', tmpOutput],
      )
      // Look for the JSON line {"ok": true, "wav": "<path>"} or just check the
      // expected output path.
      const last = out.split('\n').filter((l) => l.trim()).pop() || ''
      let wavPath = tmpOutput
      try {
        const json = JSON.parse(last) as { ok?: boolean; wav?: string }
        if (json.wav) wavPath = json.wav
      } catch { /* ignore */ }
      const bytes = await fsReadBinary(wavPath)
      const blob = new Blob([new Uint8Array(bytes)], { type: 'audio/wav' })
      return URL.createObjectURL(blob)
    } catch {
      return null
    }
  }
  // Web fallback: bridge synthesises the WAV and returns it.
  try {
    const resp = await fetch(`${getBridgeUrl()}/api/voice/tts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
      signal: AbortSignal.timeout(60_000),
    })
    if (!resp.ok) return null
    // The bridge may return JSON with a URL or a raw audio buffer.
    const ct = resp.headers.get('content-type') || ''
    if (/^audio\//.test(ct)) {
      const buf = await resp.arrayBuffer()
      return URL.createObjectURL(new Blob([buf], { type: ct }))
    }
    const data = await resp.json() as { ok?: boolean; url?: string; audio_url?: string }
    return data.url || data.audio_url || null
  } catch {
    return null
  }
}

// ---------------------------------------------------------------------------
// DOM query — web-only. Reads textContent (or the requested attribute) of
// matching elements. Capped at 50 elements / 5KB of returned text.
// ---------------------------------------------------------------------------

async function runDomQuery(
  selector: string,
  attribute?: string,
): Promise<Omit<CoworkActionResult, 'durationMs'>> {
  if (typeof document === 'undefined') {
    return { ok: false, error: 'document indisponible (Tauri shell ou SSR).' }
  }
  let nodes: Element[]
  try {
    nodes = Array.from(document.querySelectorAll(selector))
  } catch (err) {
    return { ok: false, error: `selecteur invalide: ${err instanceof Error ? err.message : String(err)}` }
  }
  const cappedNodes = nodes.slice(0, 50)
  const items = cappedNodes.map((el) => {
    if (attribute) {
      return el.getAttribute(attribute) ?? ''
    }
    return (el.textContent ?? '').trim()
  })
  let output = items.join('\n---\n')
  const maxBytes = 5000
  if (output.length > maxBytes) {
    output = output.slice(0, maxBytes) + `\n…[tronque · ${output.length - maxBytes} octets]`
  }
  return {
    ok: true,
    output,
    data: { selector, attribute, total: nodes.length, returned: cappedNodes.length },
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function countOccurrences(haystack: string, needle: string): number {
  if (!needle) return 0
  let count = 0
  let i = 0
  while ((i = haystack.indexOf(needle, i)) !== -1) {
    count += 1
    i += needle.length
  }
  return count
}

// Re-export so the orchestrator can ensure mkdir before write_file / large
// directory operations.
export { fsMkdir }

// ---------------------------------------------------------------------------
// v82m5 — Dual-signal escalation acceptance metric (network reporter)
//
// Closes the loop on whether the stronger `[HINT] DUAL_SIGNAL` nudge (emitted
// by `buildVisualRetryNudge` when both yield-ratio AND host_baseline_drift
// fired on the same extract entry) actually changes LLM behaviour.
//
// PURE detection lives in `coworkPlanParser.ts`
// (`detectDualSignalNudgeContext` + `detectDualSignalAcceptanceInPlan` +
// `pickHostFromHistoryForDualSignal`) so the orchestrator can call them
// without pulling browser/Tauri imports.
//
// THIS module owns only the network-reporter — it lives next to the
// executor because it depends on `getBridgeUrl()` which is a runtime concern
// (Tauri / cloudflare tunnel / localhost). The pipeline injects
// `reportDualSignalEvent` into the orchestrator as an optional dep so unit
// tests can stub it out without spinning up Flask.
//
// Bridge endpoints :
//   POST /api/cowork/dual-signal-event { kind, host }
//   GET  /api/cowork/dual-signal-stats → totals + per-host top5
// ---------------------------------------------------------------------------

/**
 * v82m5 — best-effort POST to the bridge's `/api/cowork/dual-signal-event`
 * endpoint. NEVER throws : on any network error / non-200 / runtime not
 * supporting fetch, the call silently no-ops. Pure observability — the
 * orchestrator's plan loop must not depend on this telemetry succeeding.
 *
 * The pipeline wraps this and injects it as `deps.reportDualSignal` so the
 * orchestrator stays decoupled from the network layer. URL is resolved via
 * `getBridgeUrl()` so the call works in Tauri / cloudflare tunnel /
 * localhost without env-var lookup.
 */
export async function reportDualSignalEvent(
  kind: 'emitted' | 'accepted',
  host: string,
): Promise<void> {
  try {
    if (kind !== 'emitted' && kind !== 'accepted') return
    const base = getBridgeUrl()
    const url = `${base.replace(/\/+$/, '')}/api/cowork/dual-signal-event`
    await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ kind, host: host || '' }),
    }).catch(() => {})
  } catch {
    // Pure observability — never propagate.
  }
}

/**
 * v82m7 — symmetric reporter for the tier-2 DUAL_SIGNAL_TREND nudge.
 * Same fire-and-forget contract as `reportDualSignalEvent` — never
 * throws, never blocks the plan loop. Posts to
 * `/api/cowork/trend-signal-event` so the bridge keeps tier-1 and
 * tier-2 metrics in separate ring buffers.
 */
export async function reportTrendSignalEvent(
  kind: 'emitted' | 'accepted',
  host: string,
): Promise<void> {
  try {
    if (kind !== 'emitted' && kind !== 'accepted') return
    const base = getBridgeUrl()
    const url = `${base.replace(/\/+$/, '')}/api/cowork/trend-signal-event`
    await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ kind, host: host || '' }),
    }).catch(() => {})
  } catch {
    // Pure observability — never propagate.
  }
}
