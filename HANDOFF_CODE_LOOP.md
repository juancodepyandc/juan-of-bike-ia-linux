# HANDOFF — Aurora code-generation autonomous loop

**Goal.** Drive AuroraIA-v2's existing `codeOrchestrator` from an autonomous loop that takes short or long user prompts, enriches them so a 5-word brief and a 500-word brief both produce expert-grade output, runs each prompt to a fidelityScore >= 90, validates the live preview via the cloudflared tunnel, and shows a real progress halo all the way through.

---

## 1. What already exists (do not rebuild)

| Layer | Where | What it does |
|---|---|---|
| Orchestrator | `application/src/services/codeOrchestrator.ts` | `orchestrateCodeGeneration({prompt, enrichedPrompt, …})` runs the full multi-pass pipeline with internal correction passes and emits phase / token / files / sandbox / score callbacks |
| Intent | `application/src/services/codeIntent.ts` | `classifyCodeIntent(enrichedPrompt)` -> `{projectType, complexity, language, …}` |
| Auto-correction | `application/src/services/codeAutoCorrection.ts` | re-runs failed builds, drives fidelity gate |
| Fidelity gate | `application/src/services/codeFidelityGate.ts` | scores 0..100 |
| Output elevate | `application/src/services/codeOutputElevate.ts` | post-generation polish |
| Design refs | `codeDesignDirectives.ts` + `codeDesignReference.ts` + `codeDesignResearch.ts` | injects design system context |
| Mission control | `codeMissionControl.ts` | high-level mission management |
| Sandbox | `codeSandbox*.ts` | runs the generated code, reports `sandboxPassed` |
| Save format | `application/saves/code/<ISO>-<slug>/` | `metadata.json` (module, prompt, fidelityScore, parameters, savedAt, savedPath) + `project/` (the generated files) |
| UI | `application/src/views/AuroraV1CodeView.tsx`, `AuroraV3CodeView.tsx` | the user-facing code module pages |
| Tunnel | `restart_tunnel.py` + `tunnel_url.txt` | cloudflared tunnel that exposes Vite (:1420) via bridge (:3001) on a `*.trycloudflare.com` URL |
| CDP test pattern | `cdp_tunnel_test_*.mjs` | headless Chrome over Chrome DevTools Protocol, navigate / evaluate / screenshot, used to gate other modules |
| Bridge | `application/bridge_server.py` line 1055-1103 has `/api/code/*` editor-side endpoints (install-model, detect-editor, open-folder) |

The orchestrator is a multi-pass system with built-in fidelity correction. Our loop must NOT duplicate that. It enriches the prompt, calls the orchestrator once per scene, polls the save folder + DOM for completion + fidelityScore, screenshots the live preview, and decides retry vs. next.

## 2. Loop architecture

```
queue.json
   |
   v
loop_iteration(prompt):
   1. enrich(prompt) -> enrichedPrompt        (concise expansion, 5x..15x, not 100x)
   2. drive UI via CDP:
        a. ensure tunnel URL is alive (restart_tunnel.py if stale)
        b. open <tunnel>/#code  (or whatever the in-app route is)
        c. paste enrichedPrompt into the prompt textarea
        d. click "Generate"
        e. observe progress (phase + token + score callbacks via window globals)
   3. poll application/saves/code/ for the new <ISO>-<slug> folder
   4. read metadata.json: fidelityScore + sandboxPassed
   5. screenshot the live preview (CDP) -> hero.png in the save folder
   6. score & flags:
        - fidelityScore >= 90 AND sandboxPassed -> success
        - else -> derive corrective hints from sandbox notes + screenshot diff,
                  refine prompt, retry up to N times
   7. git commit the save folder + screenshots on success
   8. emit progress event to the UI: {iter, total, phase, score, eta}
```

## 3. Prompt enrichment policy

Short prompt (5-50 chars) and long prompt (500+ chars) BOTH get the same scaffold:

- **Intent reaffirmation** — restate goal in one sentence
- **Stack hint** — html/css/js OR react+vite OR python cli OR node express, picked from `codeIntent.classifyCodeIntent`
- **Quality bar** — accessibility, responsive, no inline `<style>` clutter, semantic HTML, no placeholder lorem unless asked
- **Design system tone** — single-line, derived from `codeDesignDirectives`
- **Negative hints** — "no broken images, no fake links, no unfinished sections, no Bootstrap unless asked"

Enrichment factor cap: 12x the original character count. A 30-char prompt produces ~360 chars enriched; a 600-char prompt produces ~600 chars enriched (just normalized, not bloated).

The orchestrator already does its own internal enrichment, so our enrichment is a thin pre-filter that:
- removes typos / ambiguities
- adds stack/quality hints the user forgot to state
- never overrides explicit user choices

## 4. Live preview validation

After each generation:

1. Find `metadata.json.parameters.devCommand` (e.g. `npm run dev`) or fall back to `static_web` -> open `project/index.html` directly.
2. CDP open the URL.
3. `Page.captureScreenshot` -> `<save>/preview_hero.png`.
4. Run accessibility audit via `Audits.enable` + `Audits.getEncodedResponseBody` (Lighthouse if available, fail-soft if not).
5. Compute the same critic axes as the 3D loop (exposure, silhouette, etc., but on the screenshot) for a rough visual score.
6. Combine fidelityScore (model) + accessibility (Lighthouse) + visual (critic) -> total score in [0,1].

## 5. Progress display

Two surfaces:

- **Terminal**: a single-line ANSI progress bar (or 'halo' = pulsing dot when phase is indeterminate). Update every phase tick from `setPhase`.
- **In-app overlay**: emit `progress` events on the bridge so any open Aurora tab shows the loop's iteration & phase. The bridge already exposes `/api/*` POST endpoints; add `/api/code-loop/progress` (POST {iter, total, phase, score}).

## 6. File layout to add

```
application/python-services/aurora_code/
  README.md
  aurora_code_loop.py        # main orchestrator
  aurora_code_enrich.py      # prompt enricher (mirrors aurora_classify pattern)
  aurora_code_critic.py      # post-preview scoring
  cdp_drive.mjs              # CDP driver helper (Node, reused from cdp_tunnel_test_*)
  queue_pages.json           # initial queue: 1 short prompt + 1 long prompt per project_type
```

## 7. Initial test queue (one short + one long per project_type)

| project_type | short prompt (≤ 8 words) | long prompt (~80 words) |
|---|---|---|
| static_web | "landing page for a coffee shop" | full descriptive brief |
| react_vite | "todo list app with dark mode" | detailed UX brief |
| python_cli | "cli tool to rename files in bulk" | flags + spec |
| node_express | "rest api for a notes app" | endpoints + schema |
| markdown_blocks | "tutorial blocks: how http works" | section outline |

Loop runs both versions to verify enrichment works on tiny and verbose prompts alike.

## 8. Hard "do nots" (sanity from earlier sessions)

- Do not re-implement orchestration that codeOrchestrator already does (multi-pass, fidelity gate, sandbox).
- Do not pollute the project root (`AuroraIA-v2/`) with screenshots or logs. All loop artifacts go under `application/output/code-loop/` and `application/python-services/aurora_code/`.
- Do not over-enrich prompts beyond 12x ratio.
- Do not commit secrets (HF token, API keys) — the loop only reads env vars.
- Use `git add -f` for `application/output/code-loop/<run>/` since `application/output/` is gitignored at repo level.
- Run one heavy Python process at a time; kill orphans before relaunching (matches the user's standing rule for 3D loops).

## 9. Tunnel safety

Before each loop iteration:
1. `curl <tunnel_url>/api/health` -> if not 200, call `python restart_tunnel.py`, re-read `tunnel_url.txt`.
2. CDP-load the URL with a 10s timeout. If load fails, retry once. Then give up that iteration and mark it failed.

## 10. Success criterion

Loop's "all green" = for the 10-entry test queue, every iteration ends with `fidelityScore >= 90`, `sandboxPassed = true`, and preview Lighthouse accessibility score >= 90, within <= 3 correction attempts per scene.

---

**Suggested driver prompt for a fresh session that picks this up:**

```
Read HANDOFF_CODE_LOOP.md at the repo root. Build the aurora_code/ module per sections 6-7, drive it via the existing codeOrchestrator + cloudflared tunnel, run the 10-prompt test queue (5 short + 5 long, one pair per project_type), and report per-iteration {fidelityScore, sandbox, lighthouse, visual_score}. Use the same task-tracking discipline as the 3D loop (TaskCreate/Update per stage). Do not re-implement what codeOrchestrator already does. cwd = C:/Users/Juan/Desktop/ia/AuroraIA-v2/.
```
