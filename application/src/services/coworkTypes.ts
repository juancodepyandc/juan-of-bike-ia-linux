// ---------------------------------------------------------------------------
// coworkTypes — shared types for the Cowork action pipeline (v2).
//
// Kept in a separate file to avoid circular imports between safety, planner,
// executor, audit, and the orchestrator.
// ---------------------------------------------------------------------------

export type CoworkRuntime = 'tauri-desktop' | 'web-desktop' | 'web-mobile'

// ---------------------------------------------------------------------------
// Action catalog — every operation Aurora can request goes through one of
// these strongly-typed kinds. The planner LLM is constrained to emit JSON
// matching this shape (see coworkPlanner.ts).
// ---------------------------------------------------------------------------

export type CoworkAction =
  | { kind: 'reply'; message: string }
  | { kind: 'read_file'; path: string }
  | { kind: 'list_dir'; path: string; depth?: number }
  | { kind: 'write_file'; path: string; content: string }
  | { kind: 'edit_file'; path: string; oldText: string; newText: string }
  | { kind: 'delete_file'; path: string }
  | { kind: 'shell'; command: string; args: string[]; cwd?: string; timeoutMs?: number }
  | { kind: 'web_search'; query: string; limit?: number }
  | {
      kind: 'fetch'
      url: string
      method?: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH'
      headers?: Record<string, string>
      body?: string
    }
  | { kind: 'open_url'; url: string }
  | { kind: 'clipboard_read' }
  | { kind: 'clipboard_write'; text: string }
  | { kind: 'voice_speak'; text: string }
  | { kind: 'dom_query'; selector: string; attribute?: string }

  // Reasoning trace — Aurora "thinks out loud" for the user. The orchestrator
  // emits the message as a streaming event but doesn't forward to the LLM
  // history (since the planner already saw the same context).
  | { kind: 'think'; topic: string; thought: string }
  // Long-running reasoning : when a question is complex enough to benefit from
  // a dedicated mini-LLM call (think-it-through pass). The executor runs an
  // Ollama chat with mainModel + the topic+prompt and returns the resulting
  // reasoning in the result, which the next planner iteration sees in history.
  // Use durationHintMs to set the abort timeout (default 5min).
  | { kind: 'think_long'; topic: string; prompt: string; durationHintMs?: number }
  // v16 — User memory : remember/forget facts that survive across sessions.
  // remember_fact persists into settings.userMemory (LRU capped at 50).
  // The planner re-injects all current facts into every system prompt so
  // Aurora makes contextually-aware decisions.
  | { kind: 'remember_fact'; fact: string; tags?: string[] }
  | { kind: 'forget_fact'; id?: string; matching?: string }
  // Vision analysis — runs qwen3-vl on a base64 data URL (typically a
  // screenshot from browser.screenshot) and returns a textual description.
  // The result lands in the next planner iteration's history, ready to feed
  // a synthesis reply.
  | { kind: 'vision_describe'; imageDataUrl: string; question?: string }
  // v115 — capture l ecran systeme (bureau complet, pas que le navigateur).
  // Sur Windows utilise PowerShell + System.Drawing ; sur Mac screencapture ;
  // sur Linux gnome-screenshot/scrot/import. Retourne dataUrl + path local
  // pour que la prochaine iteration chaine vision_describe et obtienne une
  // analyse riche du bureau. Action systeme : marche uniquement en runtime
  // tauri-desktop (en web, fallback explicite vers browser.screenshot).
  | { kind: 'screenshot_desktop'; display?: 'primary' | 'all'; quality?: 'fast' | 'hq' }
  // External connector action — id picks a registered connector (github,
  // vercel, canva, ...), action picks an operation it exposes, params are
  // forwarded as-is to the connector runner.
  | { kind: 'connector'; connector: string; action: string; params?: Record<string, unknown> }
  // Browser tab control via Aurora-Connect extension. Operations are all
  // those the extension exposes: list_tabs / get_active_tab / read_dom /
  // read_html / click / fill / eval / screenshot / navigate / analyze_page /
  // extract_structured (v82l6 — comprehension-based extraction via Ollama).
  | {
      kind: 'browser'
      operation: 'list_tabs' | 'get_active_tab' | 'read_dom' | 'read_html'
        | 'click' | 'fill' | 'eval' | 'screenshot' | 'navigate' | 'analyze_page'
        | 'extract_structured'
      payload?: Record<string, unknown>
      extId?: string
    }
  | { kind: 'finish'; summary: string }

export type CoworkActionKind = CoworkAction['kind']

// ---------------------------------------------------------------------------
// Plan — what the LLM proposes after seeing the user prompt + state.
// ---------------------------------------------------------------------------

export type CoworkPlan = {
  reasoning: string
  actions: CoworkAction[]
  expectedOutcome: string
}

// ---------------------------------------------------------------------------
// Execution result + event stream
// ---------------------------------------------------------------------------

export type CoworkActionResult = {
  ok: boolean
  output?: string         // truncated string preview
  data?: unknown          // structured data when relevant (e.g. directory listing)
  error?: string
  durationMs: number
}

export type CoworkActionEvent = {
  kind: 'info' | 'success' | 'warn' | 'error'
  message: string
  detail?: string
  at: number
  // When the event corresponds to an action, link to it for UI grouping.
  actionId?: string
  actionKind?: CoworkActionKind
}

// ---------------------------------------------------------------------------
// Capability listing — surfaced to the UI, used by the planner system prompt.
// ---------------------------------------------------------------------------

export type CoworkCapabilityId =
  | 'filesystem'
  | 'shell'
  | 'fetch'
  | 'clipboard'
  | 'voice'
  | 'dom'
  | 'mobile-bridge'

export type CoworkCapability = {
  id: CoworkCapabilityId
  label: string
  description: string
  enabled: boolean
  destructive: boolean
}

// ---------------------------------------------------------------------------
// Confirmation request — emitted when an action requires user approval.
// ---------------------------------------------------------------------------

export type CoworkConfirmation = {
  id: string
  action: CoworkAction
  reason: string
  destructive: boolean
  // Resolver wired up by the orchestrator; UI calls one of these.
  approve: () => void
  skip: () => void
  abort: () => void
  // Optional: remember approval for the rest of the session for "outside
  // workspace" path scope.
  rememberPath?: string
}
